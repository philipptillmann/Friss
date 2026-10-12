"""Import per-100-g nutrients from the linked FoodData Explorer ingredient pages.

Only the explicitly supported public host/path is fetched, without redirects.
Structured data and nutrient table cells are parsed as data; scripts are never
executed. Unsupported components / units remain unknown, not zero.
"""
import json
import math
import re
from datetime import datetime, timezone
from html.parser import HTMLParser
from urllib.parse import urlsplit

import httpx
from fastapi import Depends, HTTPException
from pydantic import BaseModel, Field

HOST='fooddata.the50.store'
MAX_BYTES=2*1024*1024
MASS={'g':1,'mg':.001,'mcg':.000001}
# Preferred total forms only. Do not add subcomponents to a total or conflate IU
# vitamin A with RAE, or food / DFE folate with total folate.
NAMES={
 'energy':('EnergyConsumed','kcal'),
 'protein':('Protein','g'),
 'total lipid (fat)':('FatTotal','g'),
 'carbohydrate, by difference':('Carbohydrates','g'),
 'fiber, total dietary':('Fiber','g'),
 'sugars, total':('Sugar','g'),
 'sugars, total including nlea':('Sugar','g'),
 'fatty acids, total saturated':('FatSaturated','g'),
 'fatty acids, total monounsaturated':('FatMonounsaturated','g'),
 'fatty acids, total polyunsaturated':('FatPolyunsaturated','g'),
 'cholesterol':('Cholesterol','mg'),
 'vitamin a, rae':('VitaminA','mcg'),
 'thiamin':('Thiamin','mg'),
 'riboflavin':('Riboflavin','mg'),
 'niacin':('Niacin','mg'),
 'pantothenic acid':('PantothenicAcid','mg'),
 'vitamin b-6':('VitaminB6','mg'),
 'biotin':('Biotin','mcg'),
 'vitamin b-12':('VitaminB12','mcg'),
 'vitamin c, total ascorbic acid':('VitaminC','mg'),
 'vitamin d (d2 + d3)':('VitaminD','mcg'),
 'vitamin d (d2 + d3), international units':('VitaminD','mcg'),
 'vitamin e (alpha-tocopherol)':('VitaminE','mg'),
 'vitamin k (phylloquinone)':('VitaminK','mcg'),
 'folate, total':('Folate','mcg'),
 'calcium, ca':('Calcium','mg'),
 'chloride, cl':('Chloride','mg'),
 'iron, fe':('Iron','mg'),
 'magnesium, mg':('Magnesium','mg'),
 'phosphorus, p':('Phosphorus','mg'),
 'potassium, k':('Potassium','mg'),
 'sodium, na':('Sodium','mg'),
 'zinc, zn':('Zinc','mg'),
 'chromium, cr':('Chromium','mcg'),
 'copper, cu':('Copper','mg'),
 'iodine, i':('Iodine','mcg'),
 'manganese, mn':('Manganese','mg'),
 'molybdenum, mo':('Molybdenum','mcg'),
 'selenium, se':('Selenium','mcg'),
 'water':('Water','g'),
 'caffeine':('Caffeine','mg'),
 'alcohol, ethyl':('ethanol','g'),
}

class ImportRequest(BaseModel):
    url:str=Field(min_length=1,max_length=2000)


def canonical_url(value):
    try:
        u=urlsplit(value.strip())
        if u.scheme!='https' or u.hostname!=HOST or u.username or u.password or u.port not in (None,443):raise ValueError()
        path=u.path.rstrip('/')
        if not re.fullmatch(r'/ingredients/[0-9]+-[a-z0-9-]{1,250}',path):raise ValueError()
    except ValueError:raise HTTPException(422,'Use a FoodData Explorer ingredient link: https://fooddata.the50.store/ingredients/…')
    return 'https://'+HOST+path


class Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.datasets=[];self.script=None;self.title='';self.in_h1=False
        self.tables=[];self.table=None;self.row=None;self.cell=None
    def handle_starttag(self,tag,attrs):
        if tag=='script' and dict(attrs).get('type')=='application/ld+json':self.script=''
        if tag=='h1':self.in_h1=True
        if tag=='table':self.table=[]
        if self.table is not None:
            if tag=='tr':self.row=[]
            if tag in ('td','th'):self.cell=''
    def handle_data(self,text):
        if self.script is not None:self.script+=text
        if self.in_h1:self.title+=text
        if self.cell is not None:self.cell+=text
    def handle_endtag(self,tag):
        if tag=='script' and self.script is not None:
            try:self.datasets.append(json.loads(self.script))
            except (ValueError,RecursionError):pass
            self.script=None
        if tag=='h1':self.in_h1=False
        if tag in ('td','th') and self.cell is not None:
            if self.row is not None:self.row.append(self.cell.strip())
            self.cell=None
        if tag=='tr' and self.row is not None:
            if self.table is not None:self.table.append(self.row)
            self.row=None
        if tag=='table' and self.table is not None:self.tables.append(self.table);self.table=None


def normalized(text):return ' '.join(str(text).strip().casefold().split())


def unit_name(text):
    u=normalized(text).replace('µ','u').replace('μ','u')
    return {'ug':'mcg','microgram':'mcg','mcg':'mcg','kcal':'kcal','kj':'kJ','g':'g','mg':'mg','iu':'IU','ml':'ml'}.get(u)


def number(value):
    if isinstance(value,bool):raise ValueError()
    if isinstance(value,str):
        # The supported English site uses comma thousands and a dot decimal.
        value=value.strip()
        if not re.fullmatch(r'(?:\d+(?:\.\d+)?|\d{1,3}(?:,\d{3})+(?:\.\d+)?)',value):raise ValueError()
        value=value.replace(',','')
    n=float(value)
    if not math.isfinite(n) or n<0:raise ValueError()
    return n


def convert(value,unit,target,key):
    if unit==target:return value
    if unit in MASS and target in MASS:return value*MASS[unit]/MASS[target]
    if key=='EnergyConsumed' and unit=='kJ':return value/4.184
    if key=='VitaminD' and unit=='IU':return value*.025
    raise ValueError()


def parse(html,url):
    page=Page();page.feed(html)
    candidates=[]
    def collect(value):
        if isinstance(value,list):
            for item in value:collect(item)
        elif isinstance(value,dict):
            if value.get('@type')=='Dataset' and isinstance(value.get('variableMeasured'),list):candidates.append(value)
            if '@graph' in value:collect(value['@graph'])
    for dataset in page.datasets:collect(dataset)
    rows=[];basis=False
    for dataset in candidates:
        if re.search(r'\bper\s+100\s*g\b',str(dataset.get('description','')),re.I):
            basis=True
            rows.extend({'name':v.get('name'),'value':v.get('value'),'unit':v.get('unitText')} for v in dataset['variableMeasured'] if isinstance(v,dict))
    structured={(normalized(r['name']),unit_name(r['unit'])) for r in rows}
    for table in page.tables:
        if table and len(table[0])>=3 and normalized(table[0][0])=='nutrient' and re.search(r'100\s*g',table[0][1],re.I):
            basis=True
            # Structured values retain precision; the visible table may be rounded.
            rows.extend({'name':r[0],'value':r[1],'unit':r[2]} for r in table[1:] if len(r)>=3 and (normalized(r[0]),unit_name(r[2])) not in structured)
    name=' '.join(page.title.split()).strip()
    if not name and candidates:name=re.sub(r'\s*[—–-]\s*nutrient profile\s*$','',str(candidates[0].get('name',''))).strip()
    if not basis or not name or len(name)>200 or not rows or len(rows)>1000:
        raise HTTPException(422,'No supported per-100-g nutrient data found on this ingredient page')
    nutrients={};ethanol=None;original=[];skipped=[];warnings=[];seen=set()
    # Prefer explicit nutrient forms / kcal / mass over alternate energy or IU.
    rows.sort(key=lambda r:unit_name(r.get('unit')) in ('kJ','IU'))
    for row in rows:
        identity=(str(row['name']),str(row['value']),str(row['unit']))
        if identity in seen:continue
        seen.add(identity)
        raw_value=row['value']
        if not isinstance(raw_value,(str,int,float,type(None))) or isinstance(raw_value,bool) or isinstance(raw_value,(int,float)) and not math.isfinite(raw_value): raw_value=str(raw_value)
        if isinstance(raw_value,str):raw_value=raw_value[:500]
        original.append({'name':str(row['name'] or '')[:250],'value':raw_value,'unit':str(row['unit'] or '')[:32]})
        mapping=NAMES.get(normalized(row['name']))
        if not mapping:
            skipped.append({'name':row['name'],'reason':'unsupported_nutrient'});continue
        key,target=mapping
        try:
            value=convert(number(row['value']),unit_name(row['unit']),target,key)
            if not math.isfinite(value) or key=='ethanol' and value>100:raise ValueError()
        except (TypeError,ValueError,OverflowError):
            skipped.append({'name':row['name'],'reason':'unknown_value_or_unit'});continue
        if key=='ethanol':
            if ethanol is not None and not math.isclose(ethanol,value,rel_tol=1e-6,abs_tol=1e-8):raise HTTPException(422,'Conflicting ethanol values on source page')
            ethanol=value;continue
        identifier='dietary'+key
        if identifier in nutrients:
            if unit_name(row['unit']) in ('kJ','IU'):
                continue
            previous=nutrients[identifier]['value']
            if not math.isclose(previous,value,rel_tol=1e-6,abs_tol=1e-8):
                # Alternative forms can have different estimates; retain first,
                # but disagreement in same source name must not silently pass.
                existing=next((r for r in original[:-1] if normalized(r['name'])==normalized(row['name'])),None)
                if existing:raise HTTPException(422,'Conflicting nutrient values on source page: '+str(row['name']))
                warnings.append('Alternate value not combined: '+str(row['name']))
            continue
        nutrients[identifier]={'value':value,'unit':target}
    if not nutrients and ethanol is None:raise HTTPException(422,'No supported nutrients with known units found')
    if 'dietaryWater' in nutrients:warnings.append('Food water is imported as grams, not as a drinking-water volume.')
    if any(normalized(r['name'])=='carbohydrate, by difference' for r in rows):warnings.append('USDA carbohydrates by difference include fibre; BLS available carbohydrates use a different definition.')
    warnings.append('Only published, supported values are imported. Missing nutrients are not inferred as zero.')
    notes='Imported from FoodData Explorer / USDA\nSource: '+url+'\nBasis: per 100 g\n'+'\n'.join(warnings)
    return {'name_de':name,'name_en':name,'notes':notes,'nutrients':nutrients,'ethanol_g_per100':ethanol,
            'source':{'provider':'FoodData Explorer','url':url,'imported_at':datetime.now(timezone.utc).isoformat(),'basis_g':100,'values':original},
            'warnings':warnings,'skipped':skipped}


async def fetch(url):
    try:
        async with httpx.AsyncClient(timeout=15,follow_redirects=False,headers={'User-Agent':'Friss/1.15 (self-hosted nutrition importer)','Accept':'text/html'}) as client:
            async with client.stream('GET',url) as response:
                if response.status_code==404:raise HTTPException(404,'Ingredient page not found')
                if response.status_code!=200:raise HTTPException(502,'FoodData Explorer is unavailable or returned a redirect')
                if 'text/html' not in response.headers.get('content-type','').lower():raise HTTPException(422,'Expected an ingredient HTML page')
                content=bytearray()
                async for chunk in response.aiter_bytes():
                    content.extend(chunk)
                    if len(content)>MAX_BYTES:raise HTTPException(422,'Source page is too large')
                return bytes(content).decode('utf-8',errors='replace')
    except httpx.HTTPError:raise HTTPException(502,'FoodData Explorer could not be reached; try again later')


def install(app,auth):
    @app.post('/manual-ingredients/import',dependencies=[Depends(auth)])
    async def preview(body:ImportRequest):
        url=canonical_url(body.url)
        return parse(await fetch(url),url)
