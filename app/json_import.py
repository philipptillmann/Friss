"""Offline JSON handoff from ChatGPT or any other external text/image tool.

Only food identities / quantities are accepted, not invented nutrient totals.
Preview never books entries. Commit writes all entries atomically; a fixed batch
UUID makes retries safe. Original pasted/uploaded text is retained unchanged.
"""
import hashlib
import json
import re
import time
from datetime import datetime
from typing import Literal
from uuid import UUID,uuid4,uuid5,NAMESPACE_URL

from fastapi import Depends,HTTPException
from pydantic import BaseModel,ConfigDict,Field,ValidationError,model_validator
from . import food_search,nutrient_policy

MAX_BYTES=256*1024
class Quantity(BaseModel):
    model_config=ConfigDict(extra='forbid')
    value:float=Field(gt=0,allow_inf_nan=False)
    unit:Literal['g','ml']

class Item(BaseModel):
    model_config=ConfigDict(extra='forbid')
    name:str=Field(min_length=1,max_length=200)
    quantity:Quantity|None=None
    notes:str=Field(default='',max_length=2000)
    bls_code:str|None=Field(default=None,min_length=1,max_length=100)
    manual_id:UUID|None=None
    barcode:str|None=Field(default=None,pattern=r'^\d{8,14}$')
    @model_validator(mode='after')
    def valid(self):
        self.name=self.name.strip()
        if not self.name:raise ValueError('Food name required')
        for text in [self.name,self.notes,self.bls_code or '']:text.encode('utf-8')
        if sum(v is not None for v in [self.bls_code,self.manual_id,self.barcode])>1:raise ValueError('Choose one food reference')
        return self

class Meal(BaseModel):
    model_config=ConfigDict(extra='forbid')
    format:Literal['friss-meal-v1']=Field(alias='schema')
    title:str=Field(default='',max_length=300)
    timestamp:datetime|None=None
    items:list[Item]=Field(min_length=1,max_length=100)
    @model_validator(mode='after')
    def aware(self):
        self.title.encode('utf-8')
        if self.timestamp is not None and self.timestamp.utcoffset() is None:raise ValueError('Timestamp needs timezone offset')
        return self

class Preview(BaseModel):
    raw:str=Field(min_length=1,max_length=MAX_BYTES)
    lang:Literal['de','en']='de'

class Commit(Preview):
    id:UUID
    timestamp:datetime
    recipe_id:UUID|None=None
    items:list[Item]=Field(min_length=1,max_length=100)
    @model_validator(mode='after')
    def aware(self):
        if self.timestamp.utcoffset() is None:raise ValueError('Timestamp needs timezone offset')
        return self


def parse(raw):
    try:size=len(raw.encode('utf-8'))
    except UnicodeError:raise HTTPException(422,'Invalid Unicode in JSON import')
    if size>MAX_BYTES:raise HTTPException(413,'JSON import exceeds 256 KiB')
    text=raw.strip()
    fenced=re.fullmatch(r'```(?:json)?\s*([\s\S]*?)\s*```',text,re.I)
    if fenced:text=fenced.group(1)
    def pairs(items):
        result={}
        for key,value in items:
            if key in result:raise ValueError('Duplicate JSON key: '+key)
            result[key]=value
        return result
    def invalid(value):raise ValueError('Invalid number: '+value)
    try:return Meal.model_validate(json.loads(text,object_pairs_hook=pairs,parse_constant=invalid))
    except (ValueError,RecursionError) as exc:
        if isinstance(exc,ValidationError):
            errors=[{'field':'.'.join(str(x) for x in e['loc']),'message':e['msg']} for e in exc.errors()[:10]]
            raise HTTPException(422,{'message':'Use the friss-meal-v1 format','errors':errors})
        raise HTTPException(422,'Invalid JSON: '+str(exc)[:250])


def matches(db,normalize,item,lang):
    found=[]
    with db() as c:
        if item.bls_code:
            row=c.execute('SELECT payload FROM foods WHERE code=?',(item.bls_code,)).fetchone()
            if not row:raise HTTPException(422,'Unknown BLS code: '+item.bls_code)
            food=json.loads(row['payload']);found.append({'kind':'bls','id':item.bls_code,'label':food['name_'+lang]})
        if item.manual_id:
            row=c.execute('SELECT payload FROM manual_ingredients WHERE id=?',(str(item.manual_id),)).fetchone()
            if not row:raise HTTPException(422,'Own ingredient not found')
            food=json.loads(row['payload']);found.append({'kind':'manual','id':str(item.manual_id),'label':food['name_'+lang]})
        manual=[json.loads(r['payload']) for r in c.execute('SELECT payload FROM manual_ingredients')]
    if item.barcode:found.append({'kind':'barcode','id':item.barcode,'label':item.barcode})
    query=food_search.term(item.name,normalize)
    own=[m for m in manual if query in food_search.term(m['name_de']+' '+m['name_en'],normalize)]
    own.sort(key=lambda m:(food_search.term(m['name_'+lang],normalize)!=query,len(m['name_'+lang])))
    found.extend({'kind':'manual','id':m['id'],'label':m['name_'+lang]} for m in own[:6])
    foods=food_search.search(db,normalize,item.name,lang,6)
    found.extend({'kind':'bls','id':f['bls_code'],'label':f['display_name'],'query':item.name} for f in foods)
    unique=[];seen=set()
    for f in found:
        key=(f['kind'],f['id'])
        if key not in seen:unique.append(f);seen.add(key)
    return unique


def immutable(path,text):
    try:
        with path.open('x',encoding='utf-8') as f:f.write(text)
    except FileExistsError:
        if path.read_text()!=text:raise HTTPException(409,'Import original already exists with different content')


def install(app,db,auth,Entry,process,data_dir,normalize):
    @app.post('/json-import/preview',dependencies=[Depends(auth)])
    async def preview(body:Preview):
        meal=parse(body.raw)
        return {**meal.model_dump(mode='json',by_alias=True),'items':[{**i.model_dump(mode='json'),'matches':matches(db,normalize,i,body.lang)} for i in meal.items]}

    @app.post('/json-import/commit',status_code=201,dependencies=[Depends(auth)])
    async def commit(body:Commit):
        meal=parse(body.raw)
        if len(body.items)!=len(meal.items):raise HTTPException(422,'Preview item count changed; preview the edited JSON again')
        payload=body.model_dump(mode='json')
        fingerprint=hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest()
        # Fast completed retry: does not depend on foods/recipes still existing.
        with db() as c:
            old=c.execute('SELECT fingerprint,payload,lease FROM json_import_batches WHERE id=?',(str(body.id),)).fetchone()
        if old:
            if old['fingerprint']!=fingerprint:raise HTTPException(409,'Import ID already used with different content')
            saved=json.loads(old['payload'])
            if saved['status']=='completed':return saved
            if old['lease']>time.time():raise HTTPException(409,'Import is already being processed; retry shortly')
        prepared=[]
        for index,item in enumerate(body.items):
            if item.bls_code:
                with db() as c:
                    if not c.execute('SELECT code FROM foods WHERE code=?',(item.bls_code,)).fetchone():raise HTTPException(422,'Unknown BLS code: '+item.bls_code)
            kind='manual' if item.manual_id else 'item' if item.bls_code else 'barcode' if item.barcode else 'text'
            native=Entry(id=uuid5(NAMESPACE_URL,'friss-json-import:'+str(body.id)+':'+str(index)),type=kind,
                         timestamp=body.timestamp,quantity=item.quantity.model_dump() if item.quantity else None,
                         description=item.name,bls_code=item.bls_code,manual_id=item.manual_id,barcode=item.barcode,
                         recipe_id=body.recipe_id,capture_method='json_import').model_dump(mode='json')
            entry={**native,'status':'unprocessed','health_status':'pending','revision':1,
                   'import_context':{'batch_id':str(body.id),'index':index,'title':meal.title,'original_name':meal.items[index].name,'notes':item.notes}}
            if item.manual_id:
                with db() as c:
                    row=c.execute('SELECT payload FROM manual_ingredients WHERE id=?',(str(item.manual_id),)).fetchone()
                if not row:raise HTTPException(422,'Own ingredient was removed')
                entry['manual_snapshot']=json.loads(row['payload'])
            prepared.append((native,entry))
        token=str(uuid4())
        with db() as c:
            c.execute('BEGIN IMMEDIATE')
            if body.recipe_id and not c.execute('SELECT id FROM recipes WHERE id=?',(str(body.recipe_id),)).fetchone():raise HTTPException(404,'Recipe not found')
            old=c.execute('SELECT fingerprint,payload,lease FROM json_import_batches WHERE id=?',(str(body.id),)).fetchone()
            if old:
                if old['fingerprint']!=fingerprint:raise HTTPException(409,'Import ID already used with different content')
                saved=json.loads(old['payload'])
                if saved['status']=='completed':return saved
                if old['lease']>time.time():raise HTTPException(409,'Import is already being processed; retry shortly')
            c.execute('INSERT OR REPLACE INTO json_import_batches VALUES(?,?,?,?,?)',(str(body.id),fingerprint,json.dumps({'id':str(body.id),'status':'processing'}),token,time.time()+120))
        try:
            originals=data_dir()/'originals'
            immutable(originals/f'import-{body.id}.txt',body.raw)
            immutable(originals/f'import-{body.id}.json',json.dumps(meal.model_dump(mode='json',by_alias=True),ensure_ascii=False,indent=2))
            for native,entry in prepared:
                immutable(originals/f"{entry['id']}.json",json.dumps({**native,'import_context':entry['import_context']},ensure_ascii=False))
                if entry['type']=='text':entry.update(status='needs_review',reason='Assign the imported food to a database entry',nutrients={},warnings=[])
                else:await process(entry)
                with db() as c:
                    updated=c.execute('UPDATE json_import_batches SET lease=? WHERE id=? AND token=?',(time.time()+120,str(body.id),token))
                    if updated.rowcount!=1:raise HTTPException(409,'Import lease changed; retry the same import')
            missing_as_zero=nutrient_policy.enabled(db)
            result={'id':str(body.id),'status':'completed','count':len(prepared),'entry_ids':[e['id'] for _,e in prepared],
                    'needs_review':sum(not nutrient_policy.ready(e) if missing_as_zero else e['status']!='processed' for _,e in prepared)}
            with db() as c:
                c.execute('BEGIN IMMEDIATE')
                current=c.execute('SELECT token FROM json_import_batches WHERE id=?',(str(body.id),)).fetchone()
                if not current or current['token']!=token:raise HTTPException(409,'Import lease changed; retry the same import')
                for native,entry in prepared:
                    ef=hashlib.sha256(json.dumps(native,sort_keys=True).encode()).hexdigest()
                    existing=c.execute('SELECT fingerprint FROM entries WHERE id=?',(entry['id'],)).fetchone()
                    if existing:
                        if existing['fingerprint']!=ef:raise HTTPException(409,'Entry ID conflicts with existing entry')
                    else:c.execute('INSERT INTO entries VALUES(?,?,?)',(entry['id'],ef,json.dumps(entry)))
                c.execute('UPDATE json_import_batches SET payload=?,lease=0 WHERE id=? AND token=?',(json.dumps(result),str(body.id),token))
            return result
        except BaseException:
            with db() as c:c.execute('UPDATE json_import_batches SET lease=0 WHERE id=? AND token=?',(str(body.id),token))
            raise
