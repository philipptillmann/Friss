import hashlib
import hmac
import json
import math
import os
import sqlite3
import unicodedata
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Literal
from uuid import UUID, uuid4

import httpx
from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from . import authentication as login_auth
import time
import secrets
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, model_validator

DATA = Path(os.getenv('FRISS_DATA_DIR', 'data'))
KEY = os.getenv('FRISS_API_KEY', '')

def db():
    c = sqlite3.connect(DATA / 'friss.sqlite3', timeout=30)
    c.row_factory = sqlite3.Row
    return c

def normalize(s):
    s = s.casefold().replace('ä', 'a').replace('ö', 'o').replace('ü', 'u')
    return ''.join(c for c in unicodedata.normalize('NFKD', s) if not unicodedata.combining(c))

@asynccontextmanager
async def lifespan(app):
    if len(KEY) < 32 and not login_auth.PASSWORD_HASH:
        raise RuntimeError('FRISS_API_KEY must contain at least 32 characters')
    DATA.mkdir(parents=True, exist_ok=True)
    (DATA / 'originals').mkdir(exist_ok=True)
    with db() as c:
        c.executescript('''
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY, expires REAL NOT NULL, password_version TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS login_attempts(client TEXT PRIMARY KEY, failures INTEGER NOT NULL, window REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS foods(code TEXT PRIMARY KEY, payload TEXT NOT NULL, search TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS recipes(id TEXT PRIMARY KEY, payload TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS entries(id TEXT PRIMARY KEY, fingerprint TEXT NOT NULL, payload TEXT NOT NULL);
        ''')
        for path in sorted((DATA / 'bls').glob('*.json')):
            for food in json.loads(path.read_text()).values():
                c.execute('INSERT OR IGNORE INTO foods VALUES(?,?,?)', (food['bls_code'], json.dumps(food), normalize(food['name_de']+' '+food['name_en'])))
    yield

bearer = HTTPBearer(auto_error=False)

async def auth(request: Request, credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
    if KEY and credentials and hmac.compare_digest(credentials.credentials, KEY):
        return
    if login_auth.session_valid(request, db):
        if request.method not in ['GET', 'HEAD', 'OPTIONS']:
            login_auth.same_origin(request)
        return
    raise HTTPException(401, 'Login required')

app = FastAPI(title='Friss', version='1.3.0', lifespan=lifespan)

# Only unambiguous legacy macronutrient units. Micronutrients await source-unit confirmation.
BLS_UNITS = {k:'g' for k in ['dietaryCarbohydrates','dietaryFiber','dietarySugar','dietaryFatTotal','dietaryFatMonounsaturated','dietaryFatPolyunsaturated','dietaryFatSaturated','dietaryProtein']}
BLS_UNITS['dietaryEnergyConsumed'] = 'kcal'
OFF_MAP = {'energy-kcal':('dietaryEnergyConsumed','kcal'), 'carbohydrates':('dietaryCarbohydrates','g'), 'fiber':('dietaryFiber','g'), 'sugars':('dietarySugar','g'), 'fat':('dietaryFatTotal','g'), 'saturated-fat':('dietaryFatSaturated','g'), 'proteins':('dietaryProtein','g'), 'sodium':('dietarySodium','g'), 'caffeine':('dietaryCaffeine','g')}

class Quantity(BaseModel):
    value: float = Field(gt=0, allow_inf_nan=False)
    unit: Literal['g','ml']

class Entry(BaseModel):
    id: UUID
    type: Literal['text','barcode','picture','item','drink']
    timestamp: datetime
    quantity: Quantity | None = None
    description: str | None = Field(default=None, max_length=10000)
    barcode: str | None = Field(default=None, pattern=r'^\d{8,14}$')
    bls_code: str | None = None
    filename: str | None = None
    recipe_id: UUID | None = None
    drink: Literal['water','coffee','alcohol'] | None = None
    caffeine_mg: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    alcohol_abv: float | None = Field(default=None, ge=0, le=100, allow_inf_nan=False)

    @model_validator(mode='after')
    def validate_entry(self):
        if self.timestamp.utcoffset() is None:
            raise ValueError('timestamp requires timezone')
        if self.type == 'barcode' and not self.barcode:
            raise ValueError('barcode required')
        if self.type == 'drink' and not self.drink:
            raise ValueError('drink required')
        return self

def load_entry(id):
    with db() as c:
        row = c.execute('SELECT payload FROM entries WHERE id=?', (str(id),)).fetchone()
    if not row:
        raise HTTPException(404, 'Entry not found')
    return json.loads(row['payload'])

def save_entry(e):
    with db() as c:
        c.execute('UPDATE entries SET payload=? WHERE id=?', (json.dumps(e), e['id']))

async def process(e):
    e.update(status='needs_review', reason='Food or quantity unresolved', nutrients={}, warnings=[])
    q = e.get('quantity')
    food = None
    if e['type'] == 'drink':
        if not q or q['unit'] != 'ml':
            e['reason'] = 'Drink volume in ml required'
            return
        if e['drink'] == 'water':
            e['nutrients']['dietaryWater'] = {'value':q['value'], 'unit':'ml'}
        if e.get('caffeine_mg') is not None:
            e['nutrients']['dietaryCaffeine'] = {'value':e['caffeine_mg'], 'unit':'mg'}
        if e['drink'] == 'alcohol':
            if e.get('alcohol_abv') is None:
                e['reason'] = 'Alcohol ABV required'
                return
            e['ethanol_g'] = q['value'] * e['alcohol_abv'] / 100 * 0.789
            e['warnings'].append('Ethanol recorded internally; drink calories need product data')
        if not e['nutrients'] and 'ethanol_g' not in e:
            e['reason'] = 'Caffeine amount or product data required'
            return
        e.update(status='processed', reason=None)
        return
    if e.get('bls_code') or e['type'] == 'text':
        with db() as c:
            if e.get('bls_code'):
                row = c.execute('SELECT payload FROM foods WHERE code=?',(e['bls_code'],)).fetchone()
            else:
                rows = c.execute('SELECT payload FROM foods WHERE search LIKE ? LIMIT 2',('%'+normalize(e.get('description') or '')+'%',)).fetchall()
                row = rows[0] if len(rows)==1 else None
            if row:
                food = json.loads(row['payload'])
        if food:
            e['source'] = {'provider':'BLS', 'code':food['bls_code']}
            e['food'] = food
            e['warnings'].append('Legacy BLS basis assumed per 100 g; confirm source units before Health export')
            raw = {k: {'value':v,'unit':BLS_UNITS.get(k)} for k,v in food['nutrients'].items()}
            basis = 'g'
    elif e['type'] == 'barcode':
        try:
            async with httpx.AsyncClient(timeout=12, headers={'User-Agent':'Friss/0.1 (self-hosted nutrition tracker)'}) as client:
                response = await client.get('https://world.openfoodfacts.org/api/v2/product/'+e['barcode']+'.json', params={'fields':'product_name,nutriments'})
                response.raise_for_status()
                product = response.json()
            if product.get('status') != 1:
                e['reason']='Barcode not found'
                return
            food = product['product']
            e['food'] = food
            e['source'] = {'provider':'Open Food Facts','code':e['barcode']}
            raw = {target:{'value':food.get('nutriments',{}).get(key+'_100g'), 'unit':unit} for key,(target,unit) in OFF_MAP.items()}
            basis = 'g'
        except (httpx.HTTPError, ValueError, KeyError):
            e.update(status='failed', reason='Open Food Facts unavailable or invalid response')
            return
    if not food:
        return
    if not q or q['unit'] != basis:
        e['reason'] = 'Quantity in grams required; ml needs density conversion'
        return
    for key, item in raw.items():
        value = item['value']
        if isinstance(value,(float,int)) and not isinstance(value,bool) and math.isfinite(value) and value>=0 and item['unit']:
            e['nutrients'][key]={'value':value*q['value']/100, 'unit':item['unit']}
        elif value is not None:
            e['warnings'].append(key+': source value or unit unresolved')
    if e['nutrients']:
        e.update(status='processed', reason=None)

@app.get('/health', dependencies=[Depends(auth)])
async def health():
    return {'status':'ok'}

@app.get('/foods', dependencies=[Depends(auth)])
async def foods(q: str = Query(min_length=1,max_length=200), lang: Literal['de','en']='de', limit:int=Query(default=20,ge=1,le=100)):
    query = normalize(q).replace('\\','\\\\').replace('%','\\%').replace('_','\\_')
    with db() as c:
        rows=c.execute("SELECT payload FROM foods WHERE search LIKE ? ESCAPE '\\' ORDER BY code LIMIT ?", ('%'+query+'%',limit)).fetchall()
    return [{'display_name':f['name_'+lang], **f} for f in [json.loads(r['payload']) for r in rows]]

@app.post('/entries', status_code=201, dependencies=[Depends(auth)])
async def create(entry: Entry):
    if entry.recipe_id:
        load_recipe(entry.recipe_id)
    payload=entry.model_dump(mode='json')
    fingerprint=hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest()
    e={**payload,'status':'unprocessed','health_status':'pending','revision':1}
    with db() as c:
        existing=c.execute('SELECT fingerprint,payload FROM entries WHERE id=?',(e['id'],)).fetchone()
        if existing:
            if existing['fingerprint'] != fingerprint:
                raise HTTPException(409,'ID already used with different content')
            return json.loads(existing['payload'])
        # Preserve validated original before processing; transaction commits before network lookup.
        (DATA/'originals'/f"{e['id']}.json").write_text(json.dumps(payload,ensure_ascii=False))
        c.execute('INSERT INTO entries VALUES(?,?,?)',(e['id'],fingerprint,json.dumps(e)))
    await process(e)
    save_entry(e)
    return e

@app.get('/entries', dependencies=[Depends(auth)])
async def entries(status: str | None=None, limit:int=Query(default=100,ge=1,le=1000), start:datetime | None=None, end:datetime | None=None):
    with db() as c:
        rows=c.execute('SELECT payload FROM entries ORDER BY rowid DESC').fetchall()
    result=[json.loads(r['payload']) for r in rows]
    if any(t is not None and t.utcoffset() is None for t in (start,end)):
        raise HTTPException(422, 'Date filters require timezone')
    return [e for e in result if not e.get('recipe_id') and (status is None or e['status']==status) and (start is None or datetime.fromisoformat(e['timestamp'])>=start) and (end is None or datetime.fromisoformat(e['timestamp'])<end)][:limit]

@app.get('/entries/{id}', dependencies=[Depends(auth)])
async def get_entry(id: UUID):
    return load_entry(id)

class Resolution(BaseModel):
    bls_code: str
    quantity: Quantity

@app.post('/entries/{id}/resolve', dependencies=[Depends(auth)])
async def resolve(id:UUID, resolution:Resolution):
    e=load_entry(id)
    if e['health_status'] != 'pending':
        raise HTTPException(409,'Export already reserved or acknowledged; Health correction required')
    e.update(bls_code=resolution.bls_code, quantity=resolution.quantity.model_dump(), revision=e['revision']+1)
    await process(e)
    save_entry(e)
    return e

@app.put('/entries/{id}/photo', dependencies=[Depends(auth)])
async def photo(id: UUID, request:Request):
    e=load_entry(id)
    if e['type'] != 'picture':
        raise HTTPException(422,'Picture entry required')
    content=bytearray()
    async for chunk in request.stream():
        content.extend(chunk)
        if len(content)>15*1024*1024:
            raise HTTPException(413,'Photo exceeds 15 MiB')
    if not content.startswith(b'\xff\xd8\xff'):
        raise HTTPException(422,'JPEG required')
    path=DATA/'originals'/f'{id}.jpeg'
    try:
        with path.open('xb') as f:
            f.write(content)
    except FileExistsError:
        if path.read_bytes()!=content:
            raise HTTPException(409,'Original photo cannot be overwritten')
    e['photo_received']=True
    save_entry(e)
    return e

@app.get('/health-export/pending', dependencies=[Depends(auth)])
async def pending():
    return [e for e in await entries(limit=1000) if not e.get('recipe_id') and e['status']=='processed' and e['health_status']=='pending' and e.get('source',{}).get('provider')!='BLS' and e['nutrients']]

@app.post('/health-export/{id}/claim', dependencies=[Depends(auth)])
async def claim(id:UUID):
    # Atomic reservation: never automatically retry a possibly partially written Health batch.
    with db() as c:
        c.execute('BEGIN IMMEDIATE')
        row=c.execute('SELECT payload FROM entries WHERE id=?',(str(id),)).fetchone()
        if not row:
            raise HTTPException(404,'Entry not found')
        e=json.loads(row['payload'])
        if e.get('recipe_id') or e['status']!='processed' or e['health_status']!='pending' or e.get('source',{}).get('provider')=='BLS' or not e['nutrients']:
            raise HTTPException(409,'Entry not exportable')
        e.update(health_status='claimed', export_token=str(uuid4()))
        c.execute('UPDATE entries SET payload=? WHERE id=?',(json.dumps(e),str(id)))
    return e

class Ack(BaseModel):
    export_token: str
    success: bool

@app.post('/health-export/{id}/ack', dependencies=[Depends(auth)])
async def ack(id:UUID, body:Ack):
    e=load_entry(id)
    if e.get('export_token')!=body.export_token:
        raise HTTPException(409,'Invalid export token')
    if e['health_status'] in ['synced','needs_review']:
        return e
    e['health_status']='synced' if body.success else 'needs_review'
    save_entry(e)
    return e


@app.get("/", include_in_schema=False)
async def dashboard():
    return HTMLResponse((Path(__file__).parent / "static" / "index.html").read_text())

app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")


class Login(BaseModel):
    password: str = Field(min_length=1, max_length=1024)

@app.post('/auth/login')
async def password_login(body: Login, request: Request, response: Response):
    login_auth.same_origin(request)
    if not login_auth.PASSWORD_HASH:
        raise HTTPException(503, 'Set a password on the server first')
    client = request.client.host if request.client else 'unknown'
    now = time.time()
    with db() as c:
        c.execute('BEGIN IMMEDIATE')
        row = c.execute('SELECT * FROM login_attempts WHERE client=?', (client,)).fetchone()
        failures = row['failures'] if row and row['window'] > now - 900 else 0
        window = row['window'] if failures else now
        if failures >= 10:
            raise HTTPException(429, 'Too many attempts; wait 15 minutes')
        c.execute('INSERT OR REPLACE INTO login_attempts VALUES(?,?,?)', (client, failures+1, window))
    if not login_auth.verify_password(body.password):
        raise HTTPException(401, 'Incorrect password')
    token = secrets.token_urlsafe(32)
    with db() as c:
        c.execute('DELETE FROM login_attempts WHERE client=?', (client,))
        c.execute('DELETE FROM sessions WHERE expires<?', (now,))
        c.execute('INSERT INTO sessions VALUES(?,?,?)', (login_auth.token_hash(token), now+login_auth.LIFETIME, hashlib.sha256(login_auth.PASSWORD_HASH.encode()).hexdigest()))
    response.set_cookie(login_auth.COOKIE, token, max_age=login_auth.LIFETIME, httponly=True, secure=login_auth.SECURE, samesite='strict', path='/')
    response.headers['Cache-Control'] = 'no-store'
    return {'authenticated': True}

@app.post('/auth/logout')
async def password_logout(request: Request, response: Response):
    login_auth.same_origin(request)
    token = request.cookies.get(login_auth.COOKIE, '')
    with db() as c:
        c.execute('DELETE FROM sessions WHERE token=?', (login_auth.token_hash(token),))
    response.delete_cookie(login_auth.COOKIE, path='/', secure=login_auth.SECURE, httponly=True, samesite='strict')
    return {'authenticated': False}


@app.middleware("http")
async def prevent_stale_dashboard(request: Request, call_next):
    response = await call_next(request)
    response.headers['Cache-Control'] = 'no-store'
    return response


class Recipe(BaseModel):
    id: UUID
    name: str = Field(min_length=1, max_length=200)
    servings: float = Field(gt=0, allow_inf_nan=False)
    finished_weight_g: float | None = Field(default=None, gt=0, allow_inf_nan=False)
    notes: str = Field(default='', max_length=10000)

class RecipeEdit(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    servings: float = Field(gt=0, allow_inf_nan=False)
    finished_weight_g: float | None = Field(default=None, gt=0, allow_inf_nan=False)
    notes: str = Field(default='', max_length=10000)

def load_recipe(id):
    with db() as c:
        row=c.execute('SELECT payload FROM recipes WHERE id=?',(str(id),)).fetchone()
    if not row: raise HTTPException(404, 'Recipe not found')
    return json.loads(row['payload'])

def recipe_details(recipe):
    with db() as c:
        ingredients=[json.loads(r['payload']) for r in c.execute('SELECT payload FROM entries')]
    ingredients=[e for e in ingredients if e.get('recipe_id')==recipe['id']]
    ready=bool(ingredients) and all(e['status']=='processed' for e in ingredients)
    totals={}
    # A nutrient absent from any ingredient is unknown for the entire recipe.
    keys=set.intersection(*(set(e.get('nutrients',{})) for e in ingredients)) if ingredients else set()
    mass={'g':1,'mg':.001,'mcg':.000001}
    for key in keys:
        values=[e['nutrients'][key] for e in ingredients]
        unit=values[0]['unit']
        if all(v['unit']==unit for v in values):
            value=sum(v['value'] for v in values)
        elif unit in mass and all(v['unit'] in mass for v in values):
            value=sum(v['value']*mass[v['unit']]/mass[unit] for v in values)
        else: continue
        totals[key]={'value':value,'unit':unit}
    blocked=any(e.get('source',{}).get('provider')=='BLS' for e in ingredients)
    return {**recipe,'ingredients':ingredients,'status':'ready' if ready else 'needs_review','nutrients':totals if ready else {},'health_blocked':blocked,'warnings':list(dict.fromkeys(w for e in ingredients for w in e.get('warnings',[])))}

@app.post('/recipes', status_code=201, dependencies=[Depends(auth)])
async def create_recipe(body: Recipe):
    r=body.model_dump(mode='json')
    with db() as c:
        old=c.execute('SELECT payload FROM recipes WHERE id=?',(r['id'],)).fetchone()
        if old:
            if json.loads(old['payload'])!=r: raise HTTPException(409,'Recipe ID already used')
        else: c.execute('INSERT INTO recipes VALUES(?,?)',(r['id'],json.dumps(r)))
    return recipe_details(r)

@app.get('/recipes', dependencies=[Depends(auth)])
async def recipes():
    with db() as c: rows=c.execute('SELECT payload FROM recipes ORDER BY rowid DESC').fetchall()
    return [recipe_details(json.loads(r['payload'])) for r in rows]

@app.get('/recipes/{id}', dependencies=[Depends(auth)])
async def get_recipe(id: UUID):
    return recipe_details(load_recipe(id))

@app.put('/recipes/{id}', dependencies=[Depends(auth)])
async def edit_recipe(id: UUID, body: RecipeEdit):
    load_recipe(id)
    r={'id':str(id),**body.model_dump(mode='json')}
    with db() as c: c.execute('UPDATE recipes SET payload=? WHERE id=?',(json.dumps(r),str(id)))
    return recipe_details(r)

class RecipeIntake(BaseModel):
    id: UUID
    timestamp: datetime
    unit: Literal['portion','fraction','g']
    amount: float = Field(gt=0, allow_inf_nan=False)

    @model_validator(mode='after')
    def timezone_required(self):
        if self.timestamp.utcoffset() is None: raise ValueError('timestamp requires timezone')
        if self.unit=='fraction' and self.amount>1: raise ValueError('Fraction must be at most 1')
        return self

@app.post('/recipes/{id}/intake', status_code=201, dependencies=[Depends(auth)])
async def recipe_intake(id:UUID, body:RecipeIntake):
    original={'recipe':str(id),**body.model_dump(mode='json')}
    fingerprint=hashlib.sha256(json.dumps(original,sort_keys=True).encode()).hexdigest()
    with db() as c:
        old=c.execute('SELECT fingerprint,payload FROM entries WHERE id=?',(str(body.id),)).fetchone()
    if old:
        if old['fingerprint']!=fingerprint: raise HTTPException(409,'ID already used')
        return json.loads(old['payload'])
    r=recipe_details(load_recipe(id))
    if r['status']!='ready': raise HTTPException(409,'Resolve all ingredients and quantities first')
    if body.unit=='g' and not r['finished_weight_g']:
        raise HTTPException(422,'Set finished recipe weight before logging grams')
    factor=body.amount / r['servings'] if body.unit=='portion' else body.amount / r['finished_weight_g'] if body.unit=='g' else body.amount
    e={'id':str(body.id),'type':'recipe','timestamp':body.timestamp.isoformat(),'status':'processed','health_status':'pending','revision':1,'description':r['name'],'quantity':{'value':body.amount,'unit':body.unit},'source':{'provider':'BLS' if r['health_blocked'] else 'Recipe','recipe_id':r['id']},'recipe_snapshot':r,'nutrients':{k:{'value':v['value']*factor,'unit':v['unit']} for k,v in r['nutrients'].items()},'warnings':r['warnings']+['Nutrients missing in any ingredient remain unknown; cooking losses are not modelled'],'reason':None}
    ethanol=sum(i.get('ethanol_g',0) for i in r['ingredients'])
    if ethanol: e['ethanol_g']=ethanol*factor
    with db() as c:
        c.execute('BEGIN IMMEDIATE')
        old=c.execute('SELECT fingerprint,payload FROM entries WHERE id=?',(e['id'],)).fetchone()
        if old:
            if old['fingerprint']!=fingerprint: raise HTTPException(409,'ID already used')
            return json.loads(old['payload'])
        (DATA/'originals'/f"{e['id']}.json").write_text(json.dumps(original))
        c.execute('INSERT INTO entries VALUES(?,?,?)',(e['id'],fingerprint,json.dumps(e)))
    return e
