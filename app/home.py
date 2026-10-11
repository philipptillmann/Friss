"""Persisted Home preferences, button images, and daily nutrient summaries."""
import io
import json
import math
import warnings
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import Depends, HTTPException, Query, Request, Response
from PIL import Image, ImageOps, UnidentifiedImageError
from pydantic import BaseModel, Field, model_validator, ValidationError
from typing import Literal

class Preset(BaseModel):
    type: Literal['drink','item','text','barcode','recipe']
    quantity: dict
    recipe_id: UUID | None = None
    drink: Literal['water','coffee','alcohol'] | None = None
    bls_code: str | None = None
    description: str | None = Field(default=None, max_length=10000)
    barcode: str | None = None
    caffeine_mg: float | None = None
    alcohol_abv: float | None = None

class QuickButton(BaseModel):
    id: UUID
    label: str = Field(min_length=1, max_length=100)
    entry: Preset

class BACProfile(BaseModel):
    mass_kg: float = Field(ge=1, le=500, allow_inf_nan=False)
    distribution: float = Field(ge=.01, le=2, allow_inf_nan=False)
    elimination_percent_per_hour: float = Field(ge=0, le=1, allow_inf_nan=False)
    absorption_per_hour: float = Field(ge=.001, le=100, allow_inf_nan=False)

class Goals(BaseModel):
    energy_kcal: float | None = Field(default=None, gt=0, le=50000, allow_inf_nan=False)
    protein_g: float | None = Field(default=None, gt=0, le=5000, allow_inf_nan=False)
    carbohydrates_g: float | None = Field(default=None, gt=0, le=5000, allow_inf_nan=False)
    fat_g: float | None = Field(default=None, gt=0, le=5000, allow_inf_nan=False)

class Preferences(BaseModel):
    version: int = Field(ge=0)
    buttons: list[QuickButton]
    bac: BACProfile | None = None
    goals: Goals | None = None

    @model_validator(mode='after')
    def unique_ids(self):
        if len({b.id for b in self.buttons})!=len(self.buttons): raise ValueError('Button IDs must be unique')
        return self

class QuickIntake(BaseModel):
    id: UUID
    timestamp: datetime

    @model_validator(mode='after')
    def aware(self):
        if self.timestamp.utcoffset() is None: raise ValueError('Timezone required')
        return self

DEFAULT = {'version':0,'bac':None,'buttons':[
    {'id':'99a66c6b-a706-4493-bde2-77bc35555e01','label':'Wasser / Water','entry':{'type':'drink','drink':'water','quantity':{'value':250,'unit':'ml'}}},
    {'id':'99a66c6b-a706-4493-bde2-77bc35555e02','label':'Kaffee / Coffee','entry':{'type':'drink','drink':'coffee','quantity':{'value':200,'unit':'ml'},'caffeine_mg':80}}
]}
# For nutrients without confirmed legacy units, show source-unit quantities separately.
ALL_NUTRIENTS = ('EnergyConsumed Carbohydrates Fiber Sugar FatTotal FatMonounsaturated FatPolyunsaturated FatSaturated Cholesterol Protein VitaminA Thiamin Riboflavin Niacin PantothenicAcid VitaminB6 Biotin VitaminB12 VitaminC VitaminD VitaminE VitaminK Folate Calcium Chloride Iron Magnesium Phosphorus Potassium Sodium Zinc Chromium Copper Iodine Manganese Molybdenum Selenium Water').split()
MASS = {'g':1,'mg':.001,'mcg':.000001}

def nutrient_values(e):
    values={k:dict(v) for k,v in e.get('nutrients',{}).items()}
    if e.get('source',{}).get('provider')=='BLS' and e.get('food',{}).get('bls_code') and (e.get('quantity') or {}).get('unit')=='g':
        for key,raw in e['food'].get('nutrients',{}).items():
            if key not in values:
                if isinstance(raw,(int,float)) and not isinstance(raw,bool) and math.isfinite(raw) and raw>=0:
                    values[key]={'value':raw*e['quantity']['value']/100,'unit':None}
                else: values[key]={'value':None,'unit':None,'qualifier':raw}
    if e.get('recipe_snapshot'):
        r=e['recipe_snapshot'];q=e['quantity'];factor=q['value']/r['servings'] if q['unit']=='portion' else q['value']/r['finished_weight_g'] if q['unit']=='g' else q['value']
        ingredients=[nutrient_values(i) for i in r['ingredients']]
        common=set.intersection(*(set(v) for v in ingredients)) if ingredients else set()
        for key in common-set(values):
            terms=[v[key] for v in ingredients]
            if all(v.get('value') is not None and v.get('unit')==terms[0].get('unit') for v in terms):
                values[key]={'value':sum(v['value'] for v in terms)*factor,'unit':terms[0].get('unit')}
    return values

def summarize(day_entries):
    foods=[e for e in day_entries if e['type']!='drink']
    calculated=[e for e in foods if e['status']=='processed']
    source=[nutrient_values(e) for e in calculated]
    keys={'dietary'+n for n in ALL_NUTRIENTS}|set().union(*(set(v) for v in source))
    result=[]
    for key in sorted(keys):
        parts=[v[key] for v in source if key in v and v[key].get('value') is not None]
        qualifiers=list(dict.fromkeys(str(v[key].get('qualifier')) for v in source if key in v and v[key].get('qualifier') is not None))
        # Keep confirmed values and legacy source values separate; never combine their units.
        groups={}
        for part in parts:
            unit=part.get('unit');group='g' if unit in MASS else unit
            groups[group]=groups.get(group,0)+part['value']*(MASS[unit] if unit in MASS else 1)
        result.append({'key':key,'values':[{'value':v,'unit':u} for u,v in groups.items()], 'covered':len(parts),'total':len(foods),'partial':len(parts)<len(foods),'qualifiers':qualifiers})
    caffeine=0;water=0
    for e in day_entries:
        if e['status']!='processed': continue
        n=e.get('nutrients',{}).get('dietaryCaffeine')
        if n and n['unit'] in MASS: caffeine+=n['value']*MASS[n['unit']]*1000
        water+=e.get('drinking_water_ml',0)
        if e.get('drink')=='water': water+=e.get('nutrients',{}).get('dietaryWater',{}).get('value',0)
    return {'nutrients':result,'caffeine_mg':caffeine,'ethanol_g':sum(e.get('ethanol_g',0) for e in day_entries if e['status']=='processed'),'drinking_water_ml':water,'unresolved':sum(e['status']!='processed' for e in day_entries)}

def current_bac(entries,profile,now):
    if not profile: return {'percent':None,'reason':'profile_required'}
    # Use the entire retained history up to now, rather than reset elimination at midnight.
    drinks=[];unresolved=False
    for e in entries:
        timestamp=datetime.fromisoformat(e['timestamp'])
        if timestamp>now or e.get('recipe_id'): continue
        if e.get('drink')=='alcohol' and e['status']!='processed': unresolved=True
        if e.get('ethanol_g',0)>0 and e['status']=='processed': drinks.append((timestamp,e['ethanol_g']))
    if unresolved: return {'percent':None,'reason':'unresolved_alcohol'}
    if not drinks: return {'percent':0,'reason':'no_logged_drinks'}
    origin=min(t for t,_ in drinks)
    elapsed=(now-origin).total_seconds()/3600
    absorbed=sum(.1*g/(profile['mass_kg']*profile['distribution'])*(-math.expm1(-profile['absorption_per_hour']*(now-t).total_seconds()/3600)) for t,g in drinks)
    return {'percent':max(0,absorbed-profile['elimination_percent_per_hour']*elapsed),'reason':'model_estimate','origin':origin.isoformat(),'as_of':now.isoformat()}

def install(app, db, auth, Entry, create, load_recipe, RecipeIntake, recipe_intake):
    def settings():
        with db() as c:
            row=c.execute('SELECT payload FROM preferences WHERE id=1').fetchone()
            value=json.loads(row['payload']) if row else json.loads(json.dumps(DEFAULT))
            images={r['id'] for r in c.execute('SELECT id FROM button_images')}
        return {'goals':None,**value,'buttons':[{**b,'has_image':b['id'] in images} for b in value['buttons']]}

    @app.get('/settings',dependencies=[Depends(auth)])
    async def get_settings(): return settings()

    @app.put('/settings',dependencies=[Depends(auth)])
    async def put_settings(body: Preferences):
        for b in body.buttons:
            if b.entry.type=='recipe':
                if not b.entry.recipe_id: raise HTTPException(422,'Recipe required')
                recipe=load_recipe(b.entry.recipe_id)
                q=b.entry.quantity
                try:
                    RecipeIntake(id=b.id,timestamp=datetime.now(timezone.utc),amount=q.get('value'),unit=q.get('unit'))
                except ValidationError: raise HTTPException(422,'Invalid recipe serving')
                if q.get('unit')=='g' and not recipe.get('finished_weight_g'): raise HTTPException(422,'Recipe finished weight required for grams')
                continue
            if b.entry.recipe_id is not None: raise HTTPException(422,'Use recipe type to link a recipe')
            try:
                validated=Entry(id=b.id,timestamp=datetime.now(timezone.utc),**b.entry.model_dump())
            except ValidationError:
                raise HTTPException(422,'Invalid preset fields or quantity')
            if validated.type=='item' and not validated.bls_code: raise HTTPException(422,'BLS code required')
            if validated.type=='text' and not validated.description: raise HTTPException(422,'Text required')
            if validated.quantity is None: raise HTTPException(422,'Preset amount required')
            if validated.type=='drink' and validated.quantity.unit!='ml': raise HTTPException(422,'Drink volume must use ml')
            if validated.drink=='coffee' and validated.caffeine_mg is None: raise HTTPException(422,'Caffeine amount required')
            if validated.drink=='alcohol' and validated.alcohol_abv is None: raise HTTPException(422,'ABV required')
        value=body.model_dump(mode='json')
        with db() as c:
            c.execute('BEGIN IMMEDIATE')
            row=c.execute('SELECT payload FROM preferences WHERE id=1').fetchone()
            current=json.loads(row['payload'])['version'] if row else 0
            if current!=value['version']: raise HTTPException(409,'Settings changed; reload before saving')
            value['version']+=1
            c.execute('INSERT OR REPLACE INTO preferences VALUES(1,?)',(json.dumps(value),))
            keep={b['id'] for b in value['buttons']}
            for image in c.execute('SELECT id FROM button_images').fetchall():
                if image['id'] not in keep: c.execute('DELETE FROM button_images WHERE id=?',(image['id'],))
        return settings()

    def find_button(id):
        b=next((b for b in settings()['buttons'] if b['id']==str(id)),None)
        if not b: raise HTTPException(404,'Button not found')
        return b

    @app.post('/quick-buttons/{id}/intake',dependencies=[Depends(auth)])
    async def quick_intake(id:UUID,body:QuickIntake):
        b=find_button(id)
        if b['entry']['type']=='recipe':
            q=b['entry']['quantity']
            return await recipe_intake(UUID(b['entry']['recipe_id']),RecipeIntake(id=body.id,timestamp=body.timestamp,unit=q['unit'],amount=q['value']))
        return await create(Entry(id=body.id,timestamp=body.timestamp,**{**b['entry'],'description':b['entry'].get('description') or b['label']}))

    @app.put('/quick-buttons/{id}/image',dependencies=[Depends(auth)])
    async def upload_image(id:UUID,request:Request):
        find_button(id);data=bytearray()
        async for chunk in request.stream():
            data.extend(chunk)
            if len(data)>5*1024*1024: raise HTTPException(413,'Image exceeds 5 MiB')
        try:
            with warnings.catch_warnings():
                warnings.simplefilter('error',Image.DecompressionBombWarning)
                with Image.open(io.BytesIO(data)) as im:
                    if im.format not in ['JPEG','PNG','WEBP']: raise ValueError('Use JPEG, PNG or WebP')
                    if im.width*im.height>16000000: raise ValueError('Image exceeds 16 megapixels')
                    im=ImageOps.exif_transpose(im);im.thumbnail((512,512));out=io.BytesIO();im.convert('RGBA').save(out,format='PNG')
        except (UnidentifiedImageError,OSError,ValueError,Image.DecompressionBombWarning,Image.DecompressionBombError):
            raise HTTPException(422,'Invalid image; use JPEG, PNG or WebP under 16 megapixels')
        with db() as c: c.execute('INSERT OR REPLACE INTO button_images VALUES(?,?)',(str(id),out.getvalue()))
        return {'saved':True}

    @app.get('/quick-buttons/{id}/image',dependencies=[Depends(auth)])
    async def image(id:UUID):
        find_button(id)
        with db() as c: row=c.execute('SELECT content FROM button_images WHERE id=?',(str(id),)).fetchone()
        if not row: raise HTTPException(404,'No image')
        return Response(bytes(row['content']),media_type='image/png')

    @app.delete('/quick-buttons/{id}/image',dependencies=[Depends(auth)])
    async def delete_image(id:UUID):
        find_button(id)
        with db() as c: c.execute('DELETE FROM button_images WHERE id=?',(str(id),))
        return {'deleted':True}

    @app.get('/home-summary',dependencies=[Depends(auth)])
    async def summary(start:datetime,end:datetime):
        if start.utcoffset() is None or end.utcoffset() is None or end<=start or end-start>timedelta(days=2): raise HTTPException(422,'Provide a timezone-aware day range')
        with db() as c: records=[json.loads(r['payload']) for r in c.execute('SELECT payload FROM entries')]
        records=[e for e in records if not e.get('recipe_id')]
        daily=[e for e in records if start<=datetime.fromisoformat(e['timestamp'])<end]
        return {**summarize(daily),'current_bac':current_bac(records,settings()['bac'],datetime.now(timezone.utc))}
