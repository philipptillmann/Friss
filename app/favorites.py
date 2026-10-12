"""Reusable ingredient templates, independent of consumption and Health state."""
import json
from datetime import datetime, timezone
from typing import Literal
from uuid import UUID, uuid4
from fastapi import Depends, HTTPException, Query
from pydantic import BaseModel, Field, model_validator

class Ingredient(BaseModel):
    type: Literal['item','barcode','text','drink','manual']
    quantity: dict | None = None
    manual_id: UUID | None = None
    bls_code: str | None = None
    barcode: str | None = None
    description: str | None = None
    drink: Literal['water','coffee','alcohol'] | None = None
    caffeine_mg: float | None = None
    alcohol_abv: float | None = None

class FavoriteEdit(BaseModel):
    label: str = Field(min_length=1,max_length=200)
    entry: Ingredient
    version: int = Field(ge=0)

    @model_validator(mode='after')
    def nonblank(self):
        self.label=self.label.strip()
        if not self.label: raise ValueError('Label required')
        return self

class Favorite(FavoriteEdit):
    id: UUID

def reusable(e):
    if e['type']=='recipe': return None
    code=e.get('bls_code') or (e.get('food') or {}).get('bls_code')
    if e['type']=='manual':spec={'type':'manual','manual_id':e['manual_id']}
    elif code: spec={'type':'item','bls_code':code}
    elif e.get('barcode'): spec={'type':'barcode','barcode':e['barcode']}
    elif e['type']=='drink':
        spec={k:e.get(k) for k in ['type','drink','caffeine_mg','alcohol_abv','description']}
    elif e['type']=='text' and e.get('description'): spec={'type':'text','description':e['description']}
    else: return None
    spec['quantity']=e.get('quantity')
    food=e.get('food') or {}
    label_de=food.get('name_de') or food.get('product_name') or e.get('description') or e.get('barcode') or e.get('drink')
    label_en=food.get('name_en') or food.get('product_name') or e.get('description') or e.get('barcode') or e.get('drink')
    return {'entry':spec,'name_de':label_de,'name_en':label_en,'last_entry_id':e['id'],'last_timestamp':e['timestamp'],'last_location':'recipe' if e.get('recipe_id') else 'daily'}

def identity(spec):
    if spec['type']=='manual':return ('manual',spec['manual_id'])
    if spec['type']=='item': return ('item',spec['bls_code'])
    if spec['type']=='barcode': return ('barcode',spec['barcode'])
    if spec['type']=='text': return ('text',spec['description'].strip().casefold())
    return ('drink',spec.get('drink'),spec.get('caffeine_mg'),spec.get('alcohol_abv'),spec.get('description'))

def install(app,db,auth,Entry):
    def validate(body):
        if body.entry.type!='item' and body.entry.bls_code:
            raise HTTPException(422,'BLS code requires item type')
        if body.entry.type!='barcode' and body.entry.barcode:
            raise HTTPException(422,'Barcode requires barcode type')
        try:
            e=Entry(id=uuid4(),timestamp=datetime.now(timezone.utc),**body.entry.model_dump())
        except ValueError: raise HTTPException(422,'Invalid ingredient fields or quantity')
        if e.type=='manual':
            from .manual_ingredients import load
            load(db,e.manual_id)
        if e.type=='item':
            with db() as c: row=c.execute('SELECT code FROM foods WHERE code=?',(e.bls_code,)).fetchone()
            if not row: raise HTTPException(422,'Select an existing BLS food')
        if e.type=='text' and not (e.description or '').strip(): raise HTTPException(422,'Description required')
        if e.type=='drink':
            if not e.quantity or e.quantity.unit!='ml' and not (e.drink=='alcohol' and e.quantity.unit=='g'): raise HTTPException(422,'Drink amount in ml required')
            if e.drink=='coffee' and e.caffeine_mg is None: raise HTTPException(422,'Caffeine amount required')
            if e.drink=='alcohol' and e.quantity.unit=='ml' and e.alcohol_abv is None: raise HTTPException(422,'Alcohol content required')
        elif e.quantity and e.quantity.unit!='g': raise HTTPException(422,'Food amount must use grams')
        return body.model_dump(mode='json')

    @app.get('/recent-ingredients',dependencies=[Depends(auth)])
    async def recent(limit:int=Query(default=100,ge=1,le=200)):
        with db() as c: rows=c.execute('SELECT payload FROM entries ORDER BY rowid DESC').fetchall()
        result=[];seen=set()
        for row in rows:
            candidate=reusable(json.loads(row['payload']))
            if not candidate: continue
            key=identity(candidate['entry'])
            if key in seen: continue
            seen.add(key);result.append(candidate)
            if len(result)==limit: break
        return result

    @app.get('/favorites',dependencies=[Depends(auth)])
    async def favorites():
        with db() as c: return [json.loads(r['payload']) for r in c.execute('SELECT payload FROM favorites ORDER BY rowid DESC')]

    @app.post('/favorites',status_code=201,dependencies=[Depends(auth)])
    async def add(body:Favorite):
        value=validate(body)
        if value['version']!=0: raise HTTPException(422,'New favorite requires version 0')
        with db() as c:
            c.execute('BEGIN IMMEDIATE')
            row=c.execute('SELECT payload FROM favorites WHERE id=?',(str(body.id),)).fetchone()
            if row:
                old=json.loads(row['payload'])
                if any(old[k]!=value[k] for k in ['id','label','entry','version']): raise HTTPException(409,'Favorite ID already used')
                return old
            value['updated_at']=datetime.now(timezone.utc).isoformat()
            c.execute('INSERT INTO favorites VALUES(?,?)',(value['id'],json.dumps(value)))
        return value

    @app.put('/favorites/{id}',dependencies=[Depends(auth)])
    async def edit(id:UUID,body:FavoriteEdit):
        value=validate(body)
        with db() as c:
            c.execute('BEGIN IMMEDIATE')
            row=c.execute('SELECT payload FROM favorites WHERE id=?',(str(id),)).fetchone()
            if not row: raise HTTPException(404,'Favorite not found')
            old=json.loads(row['payload'])
            if old['version']!=value['version']: raise HTTPException(409,'Favorite changed; reload before saving')
            value.update(id=str(id),version=value['version']+1,updated_at=datetime.now(timezone.utc).isoformat())
            c.execute('UPDATE favorites SET payload=? WHERE id=?',(json.dumps(value),str(id)))
        return value

    @app.delete('/favorites/{id}',dependencies=[Depends(auth)])
    async def delete(id:UUID,version:int=Query(ge=0)):
        with db() as c:
            c.execute('BEGIN IMMEDIATE')
            row=c.execute('SELECT payload FROM favorites WHERE id=?',(str(id),)).fetchone()
            if not row: raise HTTPException(404,'Favorite not found')
            if json.loads(row['payload'])['version']!=version: raise HTTPException(409,'Favorite changed; reload before deleting')
            c.execute('DELETE FROM favorites WHERE id=?',(str(id),))
        return {'deleted':True}
