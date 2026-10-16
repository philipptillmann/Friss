"""Local nutrition-label OCR. Suggestions only; saving remains explicit."""
import io
import math
import re
import subprocess
import warnings
from fastapi import Depends,HTTPException,Request
from PIL import Image,ImageOps,UnidentifiedImageError
from starlette.concurrency import run_in_threadpool

MAX_BYTES=10*1024*1024
# Match longer names first; do not confuse total fat with saturated fat.
LABELS=[
 (r'(?:davon\s+)?gesättigte\s+fettsäuren|saturated\s+(?:fat|fatty acids)','dietaryFatSaturated','g'),
 (r'einfach\s+ungesättigte\s+fettsäuren|monounsaturated\s+fat','dietaryFatMonounsaturated','g'),
 (r'mehrfach\s+ungesättigte\s+fettsäuren|polyunsaturated\s+fat','dietaryFatPolyunsaturated','g'),
 (r'kohlenhydrate|carbohydrates?','dietaryCarbohydrates','g'),
 (r'(?:davon\s+)?zucker|(?:total\s+)?sugars?','dietarySugar','g'),
 (r'ballaststoffe|(?:dietary\s+)?fib(?:re|er)','dietaryFiber','g'),
 (r'eiweiß|eiweiss|protein','dietaryProtein','g'),
 (r'(?:gesamt)?fett|(?:total\s+)?fat','dietaryFatTotal','g'),
 (r'natrium|sodium','dietarySodium','mg'),
 (r'cholesterin|cholesterol','dietaryCholesterol','mg'),
 (r'koffein|caffeine','dietaryCaffeine','mg'),
 (r'kalzium|calcium','dietaryCalcium','mg'),
 (r'magnesium','dietaryMagnesium','mg'),
 (r'eisen|iron','dietaryIron','mg'),
 (r'zink|zinc','dietaryZinc','mg'),
 (r'kalium|potassium','dietaryPotassium','mg'),
 (r'vitamin\s+b12','dietaryVitaminB12','mcg'),
 (r'vitamin\s+b6','dietaryVitaminB6','mg'),
 (r'vitamin\s+c','dietaryVitaminC','mg'),
 (r'vitamin\s+d','dietaryVitaminD','mcg'),
 (r'vitamin\s+e','dietaryVitaminE','mg'),
 (r'vitamin\s+k','dietaryVitaminK','mcg'),
]
MASS={'g':1,'mg':.001,'mcg':.000001,'µg':.000001,'μg':.000001,'ug':.000001}
VALUE=r'(?<![\d.,])([0-9]+(?:[.,][0-9]+)?)\s*(kcal|kj|mcg|mg|µg|μg|ug|g)\b'

def parse(text):
    text=text[:30000]
    normalized=text.casefold().replace('\u00a0',' ')
    # A fixed, readable 100g column is required. Never mistake portion or US
    # daily-value columns for the per-100g basis.
    basis=bool(re.search(r'\b100\s*g\b',normalized))
    unsafe=bool(re.search(r'\b100\s*ml\b|nutrition\s+facts|total\s+carbohydrate|(?:per|pro|je)\s+(?:portion|serving)',normalized))
    if not basis or unsafe:
        return {'text':text,'nutrients':{},'basis':'unconfirmed','warnings':['Use a label with a clearly readable per-100-g column. Per-serving, US Nutrition Facts and per-100-ml labels need manual conversion.']}
    nutrients={};problems=[];salt=None
    def add(key,value,unit):
        if not math.isfinite(value) or value<0:return
        if key in nutrients and nutrients[key]!={'value':value,'unit':unit}:
            nutrients.pop(key);problems.append(key)
        elif key not in problems:nutrients[key]={'value':value,'unit':unit}
    lines=[s.strip() for s in normalized.splitlines() if s.strip()]
    for index,line in enumerate(lines):
        # Explicit tables with multiple quantity columns are ambiguous after OCR.
        # Do not choose a column based on visual position lost in plain text.
        found=list(re.finditer(VALUE,line))
        if not found and index+1<len(lines) and not re.search(r'[<>≤≥]',line):
            found=list(re.finditer(VALUE,lines[index+1])) if re.match(r'^\d',lines[index+1]) else []
        if re.search(r'[<>≤≥]',line):continue
        if re.search(r'\b(?:energie|energy|brennwert|kalorien|calories)\b',line):
            kcal=[m for m in found if m[2]=='kcal'];kj=[m for m in found if m[2]=='kj']
            if len(kcal)==1:add('dietaryEnergyConsumed',float(kcal[0][1].replace(',','.')),'kcal')
            elif not kcal and len(kj)==1:add('dietaryEnergyConsumed',float(kj[0][1].replace(',','.'))/4.184,'kcal')
            continue
        if len(found)!=1:continue
        m=found[0];value=float(m[1].replace(',','.'));unit=m[2]
        if unit not in MASS:continue
        if re.search(r'\b(?:salz|salt)\b',line):
            salt=value*MASS[unit];continue
        for pattern,key,target in LABELS:
            if re.search(r'\b(?:'+pattern+r')\b',line):
                amount=value*MASS[unit]/MASS[target]
                # A macronutrient cannot exceed the entire 100g sample.
                if target=='g' and amount>100:break
                add(key,amount,target);break
    if salt is not None and 'dietarySodium' not in nutrients:
        add('dietarySodium',salt/2.5*1000,'mg')
    return {'text':text,'basis':'100g','nutrients':nutrients,'warnings':['OCR suggestions must be checked against the package. Missing, ambiguous columns and less-than values are left blank. Salt is converted to sodium using salt / 2.5.']}

def scan(data):
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error',Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as source:
                if source.format not in ('JPEG','PNG','WEBP'):raise HTTPException(422,'Use JPEG, PNG or WebP')
                if source.width*source.height>16000000:raise HTTPException(422,'Image exceeds 16 megapixels')
                image=ImageOps.autocontrast(ImageOps.exif_transpose(source).convert('L'))
                scale=min(2,2400/max(image.size))
                image=image.resize((max(1,int(image.width*scale)),max(1,int(image.height*scale))))
                out=io.BytesIO();image.save(out,format='PNG')
    except (UnidentifiedImageError,OSError,ValueError,Image.DecompressionBombError,Image.DecompressionBombWarning):raise HTTPException(422,'Invalid image')
    try:
        result=subprocess.run(['tesseract','stdin','stdout','-l','deu+eng','--psm','6'],input=out.getvalue(),capture_output=True,timeout=25,check=False)
    except FileNotFoundError:raise HTTPException(503,'OCR is not installed. Rebuild the Docker image with update.sh.')
    except subprocess.TimeoutExpired:raise HTTPException(422,'OCR timed out. Try a closer crop of the nutrition label.')
    if result.returncode:raise HTTPException(422,'OCR could not read this image')
    text=result.stdout.decode('utf-8',errors='replace').strip()
    if not text:raise HTTPException(422,'No label text recognized. Try a sharper photo.')
    return parse(text)

def install(app,auth):
    @app.post('/manual-ingredients/scan-label',dependencies=[Depends(auth)])
    async def preview(request:Request):
        data=bytearray()
        async for chunk in request.stream():
            data.extend(chunk)
            if len(data)>MAX_BYTES:raise HTTPException(413,'Image exceeds 10 MiB')
        return await run_in_threadpool(scan,bytes(data))
