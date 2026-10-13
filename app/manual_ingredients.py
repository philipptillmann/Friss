"""User-entered food definitions with explicit per-100-g nutrient units."""
import json
from datetime import datetime,timezone
from typing import Literal
from uuid import UUID
from fastapi import Depends,HTTPException
from pydantic import BaseModel,Field,model_validator
from . import fooddata_import,fddb_import
from .home import ALL_NUTRIENTS

NUTRIENTS={'dietary'+n for n in ALL_NUTRIENTS}|{'dietaryCaffeine'}
class Nutrient(BaseModel):
    value:float=Field(ge=0,allow_inf_nan=False)
    unit:Literal['kcal','g','mg','mcg','ml']

class SourceValue(BaseModel):
    name:str=Field(max_length=250)
    value:float|str|None
    unit:str=Field(max_length=32)

class CarbohydrateConversion(BaseModel):
    method:Literal['us_total_minus_fibre']
    status:Literal['converted','missing_fibre','invalid_fibre']
    total_g:float=Field(ge=0,allow_inf_nan=False)
    fibre_g:float|None=Field(default=None,ge=0,allow_inf_nan=False)
    result_g:float|None=Field(default=None,ge=0,allow_inf_nan=False)

class ImportSource(BaseModel):
    provider:Literal['FoodData Explorer','FDDB']
    url:str=Field(max_length=2000)
    imported_at:datetime
    basis_g:Literal[100]
    values:list[SourceValue]=Field(max_length=1000)
    carbohydrate_conversion:CarbohydrateConversion|None=None
    @model_validator(mode='after')
    def valid(self):
        self.url=(fddb_import if self.provider=='FDDB' else fooddata_import).canonical_url(self.url)
        if self.imported_at.utcoffset() is None:raise ValueError('Import timestamp requires timezone')
        return self

class ManualEdit(BaseModel):
    name_de:str=Field(min_length=1,max_length=200)
    name_en:str=Field(default='',max_length=200)
    notes:str=Field(default='',max_length=10000)
    nutrients:dict[str,Nutrient]
    source:ImportSource|None=None
    ethanol_g_per100:float|None=Field(default=None,ge=0,le=100,allow_inf_nan=False)
    version:int=Field(ge=0)
    @model_validator(mode='after')
    def valid(self):
        self.name_de=self.name_de.strip();self.name_en=self.name_en.strip() or self.name_de
        if not self.name_de:raise ValueError('Name required')
        if not self.nutrients and self.ethanol_g_per100 is None:raise ValueError('Enter at least one nutrient')
        for key,n in self.nutrients.items():
            if key not in NUTRIENTS:raise ValueError('Unknown nutrition identifier')
            allowed={'kcal'} if key=='dietaryEnergyConsumed' else {'g','ml'} if key=='dietaryWater' else {'g','mg','mcg'}
            if n.unit not in allowed:raise ValueError('Invalid nutrient unit')
        return self

class Manual(ManualEdit):
    id:UUID

def load(db,id):
    with db() as c:row=c.execute('SELECT payload FROM manual_ingredients WHERE id=?',(str(id),)).fetchone()
    if not row:raise HTTPException(404,'Manual ingredient not found')
    return json.loads(row['payload'])

def install(app,db,auth):
    @app.get('/manual-ingredients/schema',dependencies=[Depends(auth)])
    async def schema():
        macros={'dietaryProtein','dietaryCarbohydrates','dietaryFiber','dietarySugar','dietaryFatTotal','dietaryFatSaturated','dietaryFatMonounsaturated','dietaryFatPolyunsaturated'}
        micro={'dietaryVitaminA','dietaryVitaminD','dietaryVitaminK','dietaryVitaminB12','dietaryFolate','dietaryBiotin','dietaryChromium','dietaryIodine','dietaryMolybdenum','dietarySelenium'}
        return [{'key':key,'unit':'kcal' if key=='dietaryEnergyConsumed' else 'ml' if key=='dietaryWater' else 'g' if key in macros else 'mcg' if key in micro else 'mg','units':['kcal'] if key=='dietaryEnergyConsumed' else ['ml','g'] if key=='dietaryWater' else ['g','mg','mcg']} for key in sorted(NUTRIENTS)]
    @app.get('/manual-ingredients',dependencies=[Depends(auth)])
    async def listing():
        with db() as c:return [json.loads(r['payload']) for r in c.execute('SELECT payload FROM manual_ingredients ORDER BY rowid DESC')]
    @app.post('/manual-ingredients',status_code=201,dependencies=[Depends(auth)])
    async def add(body:Manual):
        value=body.model_dump(mode='json')
        if value['version']!=0:raise HTTPException(422,'New ingredient requires version 0')
        with db() as c:
            c.execute('BEGIN IMMEDIATE')
            row=c.execute('SELECT payload FROM manual_ingredients WHERE id=?',(str(body.id),)).fetchone()
            if row:
                old=json.loads(row['payload'])
                if any(old.get(k)!=v for k,v in value.items()):raise HTTPException(409,'ID already used')
                return old
            value['updated_at']=datetime.now(timezone.utc).isoformat()
            c.execute('INSERT INTO manual_ingredients VALUES(?,?)',(value['id'],json.dumps(value)))
        return value
    @app.put('/manual-ingredients/{id}',dependencies=[Depends(auth)])
    async def edit(id:UUID,body:ManualEdit):
        value=body.model_dump(mode='json')
        with db() as c:
            c.execute('BEGIN IMMEDIATE')
            row=c.execute('SELECT payload FROM manual_ingredients WHERE id=?',(str(id),)).fetchone()
            if not row:raise HTTPException(404,'Manual ingredient not found')
            if json.loads(row['payload'])['version']!=body.version:raise HTTPException(409,'Ingredient changed; reload first')
            value.update(id=str(id),version=body.version+1,updated_at=datetime.now(timezone.utc).isoformat())
            c.execute('UPDATE manual_ingredients SET payload=? WHERE id=?',(json.dumps(value),str(id)))
        return value
    @app.delete('/manual-ingredients/{id}',dependencies=[Depends(auth)])
    async def remove(id:UUID,version:int):
        with db() as c:
            c.execute('BEGIN IMMEDIATE')
            row=c.execute('SELECT payload FROM manual_ingredients WHERE id=?',(str(id),)).fetchone()
            if not row:raise HTTPException(404,'Manual ingredient not found')
            if json.loads(row['payload'])['version']!=version:raise HTTPException(409,'Ingredient changed; reload first')
            c.execute('DELETE FROM manual_ingredients WHERE id=?',(str(id),))
        return {'deleted':True}
