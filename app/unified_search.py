"""Shared local/remote food search with query-bound learned selections."""
import base64
import hashlib
import hmac
import json
import secrets
import time
from uuid import UUID
from typing import Literal
from fastapi import Depends,HTTPException,Query
from pydantic import BaseModel,Field
from . import food_search,off_search

SIGNING_KEY=secrets.token_bytes(32)

def identity(entry):
    if entry.get('bls_code') or (entry.get('food') or {}).get('bls_code'):return 'bls',entry.get('bls_code') or entry['food']['bls_code']
    if entry.get('type')=='manual':return 'manual',entry.get('manual_id')
    if entry.get('type')=='barcode':return 'off',entry.get('barcode')
    return None

def last_quantities(db):
    # Insertion order is when the user last used a product, not its meal date.
    with db() as c:rows=c.execute('SELECT payload FROM entries ORDER BY rowid DESC').fetchall()
    result={}
    for row in rows:
        e=json.loads(row['payload']);key=identity(e);q=e.get('quantity')
        if key and key[1] and key not in result and q and q.get('unit')=='g' and isinstance(q.get('value'),(int,float)) and q['value']>0:
            result[key]=q
    return result

def sign(query,lang,item):
    payload={'query':query,'lang':lang,'expires':int(time.time())+3600,'item':item}
    raw=base64.urlsafe_b64encode(json.dumps(payload,separators=(',',':')).encode()).decode()
    return raw+'.'+hmac.new(SIGNING_KEY,raw.encode(),hashlib.sha256).hexdigest()

def verify(token):
    try:
        raw,signature=token.rsplit('.',1)
        if not hmac.compare_digest(signature,hmac.new(SIGNING_KEY,raw.encode(),hashlib.sha256).hexdigest()):raise ValueError()
        value=json.loads(base64.urlsafe_b64decode(raw))
        if value['expires']<time.time():raise ValueError()
        return value
    except (ValueError,KeyError,TypeError):raise HTTPException(422,'Search selection expired or invalid. Search again.')

class Selection(BaseModel):
    id: UUID
    query: str=Field(min_length=1,max_length=80)
    lang: Literal['de','en']='de'
    token: str=Field(min_length=1,max_length=20000)

def install(app,db,auth,normalize):
    @app.get('/food-amounts',dependencies=[Depends(auth)])
    async def amount(source:Literal['bls','off','manual'],id:str=Query(min_length=1,max_length=100)):
        return {'quantity':last_quantities(db).get((source,id))}

    @app.get('/search',dependencies=[Depends(auth)])
    async def search(q:str=Query(min_length=1,max_length=80),lang:Literal['de','en']='de',remote:bool=True,include_recipes:bool=True):
        query=food_search.term(q,normalize)
        if not query:raise HTTPException(422,'Enter a search term')
        with db() as c:
            own=[json.loads(r['payload']) for r in c.execute('SELECT payload FROM manual_ingredients')]
            recipes=[json.loads(r['payload']) for r in c.execute('SELECT payload FROM recipes')] if include_recipes else []
            favorites=[json.loads(r['payload']) for r in c.execute('SELECT payload FROM favorites')]
            old_bls=c.execute('SELECT code,COUNT(*) AS hits,MAX(rowid) AS recent FROM food_search_selections WHERE query=? AND lang=? GROUP BY code',(query,lang)).fetchall()
            learned=c.execute('SELECT source,target,payload,COUNT(*) AS hits,MAX(rowid) AS recent FROM search_selections WHERE query=? AND lang=? GROUP BY source,target',(query,lang)).fetchall()
        candidates={};warnings=[]
        def add(item):
            key=(item['source'],item['id'])
            if key not in candidates:candidates[key]=item
        for f in food_search.search(db,normalize,q,lang,15):add({'source':'bls','id':f['bls_code'],'label':f['display_name']})
        for f in own:
            if query in food_search.term(f['name_de']+' '+f.get('name_en',''),normalize):add({'source':'manual','id':f['id'],'label':f.get('name_'+lang) or f['name_de']})
        for r in recipes:
            if query in food_search.term(r['name'],normalize):add({'source':'recipe','id':r['id'],'label':r['name'],'category':r.get('category','food')})
        # Keep previously chosen OFF products available immediately / offline.
        for row in learned:
            if row['source']=='off':
                item=json.loads(row['payload']);item.pop('favorite',None);item.pop('default_quantity',None);add(item)
        if remote and len(query)>=2:
            try:
                for product in await off_search.search(q.strip(),lang,10):
                    add({'source':'off','id':product['barcode'],'label':product['display_name'],'brand':product['brand'],'package_quantity':product['package_quantity']})
            except HTTPException as exc:warnings.append(str(exc.detail))
        for f in favorites:
            key=identity(f['entry'])
            if key in candidates:
                candidates[key]['favorite']=True
                candidates[key]['default_quantity']=f['entry'].get('quantity')
            elif query in food_search.term(f['label'],normalize):
                if key:
                    add({'source':key[0],'id':key[1],'label':f['label'],'favorite':True,'default_quantity':f['entry'].get('quantity')})
                else:add({'source':'favorite','id':f['id'],'label':f['label'],'favorite':True,'entry':f['entry']})
        preferences={('bls',row['code']):(row['hits'],row['recent']) for row in old_bls}
        preferences.update({(row['source'],row['target']):(row['hits'],row['recent']) for row in learned if row['source']!='bls' or ('bls',row['target']) not in preferences})
        def rank(item):
            hits,recent=preferences.get((item['source'],item['id']),(0,0));name=food_search.term(item['label'],normalize)
            return (-hits,-recent,name!=query,not name.startswith(query),not item.get('favorite',False),len(name),item['label'],item['source'])
        amounts=last_quantities(db)
        for key,item in candidates.items():
            if not item.get('default_quantity') and key in amounts:item['default_quantity']=amounts[key]
        results=sorted(candidates.values(),key=rank)[:60]
        return {'results':[{**item,'favorite':bool(item.get('favorite')),'selection_token':sign(query,lang,item)} for item in results],'warnings':warnings}

    @app.post('/search/selections',dependencies=[Depends(auth)])
    async def selected(body:Selection):
        query=food_search.term(body.query,normalize);proof=verify(body.token)
        if proof['query']!=query or proof['lang']!=body.lang:raise HTTPException(422,'Selection does not belong to this search')
        item=proof['item'];source=item['source'];target=item['id']
        with db() as c:
            c.execute('BEGIN IMMEDIATE')
            previous=c.execute('SELECT query,lang,source,target FROM search_selections WHERE id=?',(str(body.id),)).fetchone()
            if previous:
                if tuple(previous)!=(query,body.lang,source,target):raise HTTPException(409,'Selection ID already used')
                return {'learned':True}
            table,column={'bls':('foods','code'),'manual':('manual_ingredients','id'),'recipe':('recipes','id'),'favorite':('favorites','id')}.get(source,(None,None))
            if table and not c.execute(f'SELECT 1 FROM {table} WHERE {column}=?',(target,)).fetchone():raise HTTPException(422,'Selected item was removed')
            c.execute('INSERT INTO search_selections VALUES(?,?,?,?,?,?)',(str(body.id),query,body.lang,source,target,json.dumps(item)))
            if source=='bls':c.execute('INSERT INTO food_search_selections VALUES(?,?,?,?)',(str(body.id),query,body.lang,target))
        return {'learned':True}
