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
from uuid import UUID, uuid4, uuid5

import httpx
from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from . import authentication as login_auth
from . import bls_units, nutrient_policy
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
        CREATE TABLE IF NOT EXISTS food_search_selections(id TEXT PRIMARY KEY, query TEXT NOT NULL, lang TEXT NOT NULL, code TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS food_search_query ON food_search_selections(query,lang,code);
        CREATE TABLE IF NOT EXISTS preferences(id INTEGER PRIMARY KEY, payload TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS button_images(id TEXT PRIMARY KEY, content BLOB NOT NULL);
        CREATE TABLE IF NOT EXISTS manual_ingredients(id TEXT PRIMARY KEY, payload TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS favorites(id TEXT PRIMARY KEY, payload TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS recipes(id TEXT PRIMARY KEY, payload TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS health_days(id TEXT PRIMARY KEY, day TEXT NOT NULL, timezone TEXT NOT NULL, payload TEXT NOT NULL, UNIQUE(day,timezone));
        CREATE TABLE IF NOT EXISTS entries(id TEXT PRIMARY KEY, fingerprint TEXT NOT NULL, payload TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS json_import_batches(id TEXT PRIMARY KEY, fingerprint TEXT NOT NULL, payload TEXT NOT NULL, token TEXT NOT NULL, lease REAL NOT NULL);
        ''')
        for path in sorted((DATA / 'bls').glob('*.json')):
            for food in json.loads(path.read_text()).values():
                c.execute('INSERT OR IGNORE INTO foods VALUES(?,?,?)', (food['bls_code'], json.dumps(food), normalize(food['name_de']+' '+food['name_en'])))
        bls_units.migrate(c)
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

app = FastAPI(title='Friss', version='1.25.0', lifespan=lifespan)

BLS_UNITS = bls_units.UNITS
OFF_MAP = nutrient_policy.OFF_MAP

class Quantity(BaseModel):
    value: float = Field(gt=0, allow_inf_nan=False)
    unit: Literal['g','ml']

class Entry(BaseModel):
    id: UUID
    type: Literal['text','barcode','picture','item','drink','manual']
    timestamp: datetime
    quantity: Quantity | None = None
    description: str | None = Field(default=None, max_length=10000)
    barcode: str | None = Field(default=None, pattern=r'^\d{8,14}$')
    manual_id: UUID | None = None
    bls_code: str | None = None
    filename: str | None = None
    capture_method: Literal['recent','favorite','json_import'] | None = None
    recipe_id: UUID | None = None
    drink: Literal['water','coffee','alcohol'] | None = None
    caffeine_mg: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    alcohol_abv: float | None = Field(default=None, ge=0, le=100, allow_inf_nan=False)

    @model_validator(mode='after')
    def validate_entry(self):
        if self.timestamp.utcoffset() is None:
            raise ValueError('timestamp requires timezone')
        if self.type=='manual' and (not self.manual_id or self.bls_code):
            raise ValueError('Manual ingredient required; do not combine with BLS')
        if self.type == 'barcode' and not self.barcode:
            raise ValueError('barcode required')
        if self.type=='drink' and self.drink=='alcohol' and self.quantity and self.quantity.unit=='g' and self.alcohol_abv is not None:
            raise ValueError('Use grams of pure alcohol OR drink volume and ABV')
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

async def process(e, reuse_off=False):
    e.update(status='needs_review', reason='Food or quantity unresolved', nutrients={}, warnings=[])
    e.pop('ethanol_g',None)
    q = e.get('quantity')
    food = None
    if e.get('imported_nutrition') and not any(e.get(k) for k in ('bls_code','manual_id','barcode')):
        snapshot=e['imported_nutrition']
        e['food']={'name_de':snapshot['name'],'name_en':snapshot['name']}
        e['source']={'provider':'ChatGPT import','basis':snapshot['basis'],'estimated':snapshot['estimated']}
        if snapshot['estimated']:e['warnings'].append('Nutrient values estimated by external AI; review before export')
        unit='g' if snapshot['basis']=='100g' else 'ml'
        if not q or q['unit']!=unit:
            e['reason']='Quantity in '+unit+' required for imported nutrition'
            return
        e['nutrients']={key:{'value':n['value']*q['value']/100,'unit':n['unit']} for key,n in snapshot['nutrients'].items() if n is not None}
        e.update(status='processed',reason=None)
        return
    if e['type'] == 'drink':
        if e['drink']=='alcohol' and q and q['unit']=='g':
            e['ethanol_g']=q['value']
            e.update(status='processed',reason=None)
            e['warnings'].append('Pure ethanol recorded; total drink calories need product data')
            return
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
    if e['type']=='manual':
        snapshot=e.get('manual_snapshot') or manual_ingredients.load(db,e['manual_id'])
        e['manual_snapshot']=snapshot
        food={'name_de':snapshot['name_de'],'name_en':snapshot['name_en'],'manual_id':snapshot['id']}
        e['food']=food;e['source']={'provider':'Manual','id':snapshot['id'],'version':snapshot['version']}
        raw=snapshot['nutrients'];basis='g'
        if q and q['unit']=='g' and snapshot.get('ethanol_g_per100') is not None:
            e['ethanol_g']=snapshot['ethanol_g_per100']*q['value']/100
    elif e.get('bls_code') or e['type'] == 'text':
        with db() as c:
            if e.get('bls_code'):
                row = c.execute('SELECT payload FROM foods WHERE code=?',(e['bls_code'],)).fetchone()
            else:
                rows = c.execute('SELECT payload FROM foods WHERE search LIKE ? LIMIT 2',('%'+normalize(e.get('description') or '')+'%',)).fetchall()
                row = rows[0] if len(rows)==1 else None
            if row:
                food = json.loads(row['payload'])
        if food:
            e['source'] = {'provider':'BLS', 'code':food['bls_code'], 'units_version':bls_units.VERSION}
            e['food'] = food
            raw = {k: {'value':v,'unit':BLS_UNITS.get(k)} for k,v in food['nutrients'].items()}
            basis = 'g'
    elif e['type'] == 'barcode':
        try:
            if reuse_off and e.get('source',{}).get('provider')=='Open Food Facts' and e.get('food'):
                food=e['food']
            else:
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
    if e['nutrients'] or 'ethanol_g' in e:
        e.update(status='processed', reason=None)

@app.get('/health', dependencies=[Depends(auth)])
async def health():
    return {'status':'ok'}

@app.get('/foods', dependencies=[Depends(auth)])
async def foods(q: str = Query(min_length=1,max_length=200), lang: Literal['de','en']='de', limit:int=Query(default=20,ge=1,le=100)):
    return food_search.search(db, normalize, q, lang, limit)

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
        if entry.type=='manual':
            e['manual_snapshot']=manual_ingredients.load(db,entry.manual_id)
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
    missing_as_zero=nutrient_policy.enabled(db)
    result=[json.loads(r['payload']) for r in rows]
    if any(t is not None and t.utcoffset() is None for t in (start,end)):
        raise HTTPException(422, 'Date filters require timezone')
    selected=[e for e in result if not e.get('recipe_id') and (status is None or ('processed' if missing_as_zero and nutrient_policy.ready(e) else e['status'])==status) and (start is None or datetime.fromisoformat(e['timestamp'])>=start) and (end is None or datetime.fromisoformat(e['timestamp'])<end)][:limit]
    return [home.interpreted_entry(e,missing_as_zero) for e in selected]

@app.delete('/entries', dependencies=[Depends(auth)])
async def reset_day(start: datetime, end: datetime):
    if start.utcoffset() is None or end.utcoffset() is None or not 0 < (end-start).total_seconds() <= 90000:
        raise HTTPException(422, 'Specify a timezone-aware day interval of at most 25 hours')
    with db() as c:
        c.execute('BEGIN IMMEDIATE')
        selected=[json.loads(r['payload']) for r in c.execute('SELECT payload FROM entries')]
        selected=[e for e in selected if not e.get('recipe_id') and start <= datetime.fromisoformat(e['timestamp']) < end]
        c.executemany('DELETE FROM entries WHERE id=?', [(e['id'],) for e in selected])
    return {'deleted':len(selected), 'health_correction_required':any(e['health_status'] != 'pending' for e in selected)}

@app.delete('/entries/{id}', dependencies=[Depends(auth)])
async def delete_entry(id: UUID):
    with db() as c:
        c.execute('BEGIN IMMEDIATE')
        row=c.execute('SELECT payload FROM entries WHERE id=?', (str(id),)).fetchone()
        if not row:
            raise HTTPException(404, 'Entry not found')
        e=json.loads(row['payload'])
        c.execute('DELETE FROM entries WHERE id=?', (str(id),))
    return {'deleted':1, 'health_correction_required':e['health_status'] != 'pending'}

@app.get('/entries/{id}', dependencies=[Depends(auth)])
async def get_entry(id: UUID):
    return home.interpreted_entry(load_entry(id),nutrient_policy.enabled(db))

@app.get('/entries/{id}/details', dependencies=[Depends(auth)])
async def entry_details(id: UUID):
    e=load_entry(id)
    return {**home.interpreted_entry(e,nutrient_policy.enabled(db)),'contributions':home.nutrient_values(e,nutrient_policy.enabled(db))}

class EntryTime(BaseModel):
    timestamp: datetime
    @model_validator(mode='after')
    def aware(self):
        if self.timestamp.utcoffset() is None:
            raise ValueError('Timezone required')
        return self

class EntryCopy(EntryTime):
    id: UUID

@app.post('/entries/{id}/copy',status_code=201,dependencies=[Depends(auth)])
async def copy_entry(id: UUID,body: EntryCopy):
    request={'source_id':str(id),**body.model_dump(mode='json')}
    fingerprint=hashlib.sha256(json.dumps(request,sort_keys=True).encode()).hexdigest()
    with db() as c:
        c.execute('BEGIN IMMEDIATE')
        existing=c.execute('SELECT fingerprint,payload FROM entries WHERE id=?',(str(body.id),)).fetchone()
        if existing:
            if existing['fingerprint']!=fingerprint:raise HTTPException(409,'Copy ID already used with different content')
            return json.loads(existing['payload'])
        row=c.execute('SELECT payload FROM entries WHERE id=?',(str(id),)).fetchone()
        if not row:raise HTTPException(404,'Entry not found')
        original=json.loads(row['payload'])
        if original.get('recipe_id'):raise HTTPException(422,'Copy a diary entry, not a recipe ingredient')
        e={k:v for k,v in original.items() if k not in ('export_token','original_timestamp','health_status','revision','id','timestamp','copied_from')}
        e.update(id=str(body.id),timestamp=body.timestamp.isoformat(),health_status='pending',revision=1,
                 copied_from={'id':str(id),'timestamp':original['timestamp']})
        # Freeze actual data, not the optional zero-value interpretation. No lookup
        # or recipe recalculation: changes to food sources cannot alter a copy.
        path=DATA/'originals'/f"{body.id}.json"
        text=json.dumps(e,ensure_ascii=False)
        if path.exists() and path.read_text()!=text:raise HTTPException(409,'Copy original already exists with different content')
        if not path.exists():path.write_text(text)
        photo=DATA/'originals'/f'{id}.jpeg'
        if photo.exists():
            target=DATA/'originals'/f'{body.id}.jpeg'
            data=photo.read_bytes()
            if target.exists() and target.read_bytes()!=data:raise HTTPException(409,'Copy photo already exists with different content')
            if not target.exists():target.write_bytes(data)
        c.execute('INSERT INTO entries VALUES(?,?,?)',(e['id'],fingerprint,json.dumps(e)))
    return e

@app.patch('/entries/{id}/time', dependencies=[Depends(auth)])
async def edit_entry_time(id: UUID, body: EntryTime):
    with db() as c:
        c.execute('BEGIN IMMEDIATE')
        row=c.execute('SELECT payload FROM entries WHERE id=?',(str(id),)).fetchone()
        if not row: raise HTTPException(404,'Entry not found')
        e=json.loads(row['payload'])
        if e['timestamp']!=body.timestamp.isoformat():
            e.setdefault('original_timestamp',e['timestamp'])
            e.update(timestamp=body.timestamp.isoformat(),revision=e.get('revision',1)+1)
            c.execute('UPDATE entries SET payload=? WHERE id=?',(json.dumps(e),str(id)))
    return e

class Resolution(BaseModel):
    bls_code: str | None = None
    quantity: Quantity
    timestamp: datetime | None = None
    barcode: str | None = Field(default=None,pattern=r'^\d{8,14}$')
    description: str | None = Field(default=None,max_length=10000)
    caffeine_mg: float | None = Field(default=None,ge=0,allow_inf_nan=False)
    alcohol_abv: float | None = Field(default=None,ge=0,le=100,allow_inf_nan=False)

    @model_validator(mode='after')
    def aware(self):
        if self.timestamp is not None and self.timestamp.utcoffset() is None:
            raise ValueError('Timezone required')
        return self

@app.post('/entries/{id}/resolve', dependencies=[Depends(auth)])
async def resolve(id:UUID, resolution:Resolution):
    e=load_entry(id)
    if e['health_status'] != 'pending':
        raise HTTPException(409,'Export already reserved or acknowledged; Health correction required')
    if e['type']=='recipe': raise HTTPException(422,'Recipe servings cannot be resolved as ingredients')
    barcode_changed=resolution.barcode is not None and resolution.barcode!=e.get('barcode')
    if barcode_changed:
        e.pop('food',None);e.pop('source',None);e['bls_code']=None
    if resolution.bls_code is not None:
        e['bls_code']=resolution.bls_code
    elif not barcode_changed and (e.get('food') or {}).get('bls_code'):
        e['bls_code']=e['food']['bls_code']
    for field in ['barcode','description','caffeine_mg','alcohol_abv']:
        value=getattr(resolution,field)
        if value is not None: e[field]=value
    if resolution.timestamp is not None:
        if datetime.fromisoformat(e['timestamp'])!=resolution.timestamp:
            e.setdefault('original_timestamp',e['timestamp'])
            e['timestamp']=resolution.timestamp.isoformat()
    if e.get('drink')=='alcohol' and resolution.quantity.unit=='g': e['alcohol_abv']=None
    e.update(quantity=resolution.quantity.model_dump(), revision=e['revision']+1)
    await process(e,reuse_off=True)
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
    return [{**e,'nutrients':bls_units.exportable(e)} for e in await entries(limit=1000) if not e.get('recipe_id') and e['status']=='processed' and e['health_status']=='pending' and not bls_units.blocked(e) and bls_units.exportable(e)]

@app.post('/health-export/{id}/claim', dependencies=[Depends(auth)])
async def claim(id:UUID):
    # Atomic reservation: never automatically retry a possibly partially written Health batch.
    with db() as c:
        c.execute('BEGIN IMMEDIATE')
        row=c.execute('SELECT payload FROM entries WHERE id=?',(str(id),)).fetchone()
        if not row:
            raise HTTPException(404,'Entry not found')
        e=json.loads(row['payload'])
        effective=home.interpreted_entry(e,nutrient_policy.enabled(connection=c))
        if e.get('recipe_id') or day_export_reserved(e['id']) or effective['status']!='processed' or e['health_status']!='pending' or bls_units.blocked(e) or not bls_units.exportable(effective):
            raise HTTPException(409,'Entry not exportable')
        e.update(health_status='claimed', export_token=str(uuid4()),health_export_nutrients=bls_units.exportable(effective),health_export_missing_as_zero=nutrient_policy.enabled(connection=c))
        c.execute('UPDATE entries SET payload=? WHERE id=?',(json.dumps(e),str(id)))
    return {**e,'nutrients':e['health_export_nutrients']}

def day_export_reserved(id):
    with db() as c:
        return any(id in json.loads(r['payload'])['entry_ids'] for r in c.execute('SELECT payload FROM health_days'))

class Ack(BaseModel):
    export_token: str
    success: bool

@app.post('/health-export/{id}/ack', dependencies=[Depends(auth)])
async def ack(id:UUID, body:Ack):
    e=load_entry(id)
    if day_export_reserved(str(id)):
        raise HTTPException(409,'Acknowledge the entire day export instead')
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


class RecipeFields(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    category: Literal['food','drink'] = 'food'
    servings: float = Field(gt=0, allow_inf_nan=False)
    finished_weight_g: float | None = Field(default=None,gt=0,allow_inf_nan=False)
    finished_volume_ml: float | None = Field(default=None,gt=0,allow_inf_nan=False)
    alcohol_abv: float | None = Field(default=None,ge=0,le=100,allow_inf_nan=False)
    notes: str = Field(default='',max_length=10000)
    added_water_ml: float = Field(default=0,ge=0,allow_inf_nan=False)
    added_caffeine_mg: float = Field(default=0,ge=0,allow_inf_nan=False)
    added_ethanol_g: float = Field(default=0,ge=0,allow_inf_nan=False)
    @model_validator(mode='after')
    def alcohol_basis(self):
        if self.alcohol_abv is not None:
            if self.category!='drink' or not self.finished_volume_ml:raise ValueError('ABV needs a drink and its total volume in ml')
            if self.added_ethanol_g:raise ValueError('Use total ABV OR additional ethanol, not both')
        return self

class Recipe(RecipeFields):
    id: UUID

class RecipeEdit(RecipeFields):
    amend_existing: bool = False


def load_recipe(id):
    with db() as c:
        row=c.execute('SELECT payload FROM recipes WHERE id=?',(str(id),)).fetchone()
    if not row: raise HTTPException(404, 'Recipe not found')
    return json.loads(row['payload'])

def recipe_details(recipe):
    with db() as c:
        ingredients=[json.loads(r['payload']) for r in c.execute('SELECT payload FROM entries')]
    ingredients=[e for e in ingredients if e.get('recipe_id')==recipe['id']]
    additions=recipe.get('alcohol_abv') is not None or any(recipe.get(k,0)>0 for k in ['added_water_ml','added_caffeine_mg','added_ethanol_g'])
    missing_as_zero=nutrient_policy.enabled(db)
    ready=(bool(ingredients) or additions) and all(nutrient_policy.ready(e) if missing_as_zero else e['status']=='processed' for e in ingredients)
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
    caffeine=recipe.get('added_caffeine_mg',0)
    water=recipe.get('added_water_ml',0)
    ethanol=recipe.get('added_ethanol_g',0)+sum(i.get('ethanol_g',0) for i in ingredients)
    for ingredient in ingredients:
        n=ingredient.get('nutrients',{}).get('dietaryCaffeine')
        if n and n['unit'] in mass: caffeine+=n['value']*mass[n['unit']]*1000
        if ingredient.get('drink')=='water': water+=ingredient.get('nutrients',{}).get('dietaryWater',{}).get('value',0)
    if recipe.get('alcohol_abv') is not None:ethanol=recipe['finished_volume_ml']*recipe['alcohol_abv']/100*.789
    if caffeine: totals['dietaryCaffeine']={'value':caffeine,'unit':'mg'}
    if water: totals['dietaryWater']={'value':water,'unit':'ml'}
    blocked=any(bls_units.blocked(e) for e in ingredients)
    raw_totals=totals
    if ready and missing_as_zero:
        pseudo={'type':'recipe','status':'processed','quantity':{'value':1,'unit':'fraction'},'nutrients':totals,'recipe_snapshot':{**recipe,'ingredients':ingredients}}
        totals={k:v for k,v in home.nutrient_values(pseudo,True).items() if v.get('value') is not None and v.get('unit')}
    return {**recipe,'raw_nutrients':raw_totals,'raw_ingredients':ingredients,'ethanol_g':ethanol,'drinking_water_ml':water,'ingredients':[home.interpreted_entry(e,missing_as_zero) for e in ingredients],'status':'ready' if ready else 'needs_review','nutrients':totals if ready else {},'health_blocked':blocked,'warnings':list(dict.fromkeys(w for e in ingredients for w in e.get('warnings',[])))}

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

class RecipeDuplicate(BaseModel):
    id: UUID
    name: str = Field(min_length=1,max_length=200)

@app.post('/recipes/{id}/duplicate',status_code=201,dependencies=[Depends(auth)])
async def duplicate_recipe(id: UUID,body: RecipeDuplicate):
    request={'source_id':str(id),**body.model_dump(mode='json')}
    with db() as c:
        c.execute('BEGIN IMMEDIATE')
        old=c.execute('SELECT payload FROM recipes WHERE id=?',(str(body.id),)).fetchone()
        if old:
            r=json.loads(old['payload'])
            if r.get('duplicate_request')!=request:raise HTTPException(409,'Recipe ID already used')
        else:
            source=c.execute('SELECT payload FROM recipes WHERE id=?',(str(id),)).fetchone()
            if not source:raise HTTPException(404,'Recipe not found')
            r={**json.loads(source['payload']),'id':str(body.id),'name':body.name,'copied_from':str(id),'duplicate_request':request}
            ingredients=[json.loads(row['payload']) for row in c.execute('SELECT payload FROM entries')]
            ingredients=[e for e in ingredients if e.get('recipe_id')==str(id)]
            for ingredient in ingredients:
                eid=str(uuid5(body.id,ingredient['id']))
                e={k:v for k,v in ingredient.items() if k not in ('export_token','original_timestamp','copied_from')}
                e.update(id=eid,recipe_id=r['id'],health_status='pending',revision=1,copied_from={'id':ingredient['id'],'timestamp':ingredient['timestamp']})
                text=json.dumps(e,ensure_ascii=False);path=DATA/'originals'/f'{eid}.json'
                if path.exists() and path.read_text()!=text:raise HTTPException(409,'Ingredient original already exists with different content')
                if not path.exists():path.write_text(text)
                photo=DATA/'originals'/f"{ingredient['id']}.jpeg"
                if photo.exists():
                    target=DATA/'originals'/f'{eid}.jpeg';data=photo.read_bytes()
                    if target.exists() and target.read_bytes()!=data:raise HTTPException(409,'Ingredient photo already exists with different content')
                    if not target.exists():target.write_bytes(data)
                fingerprint=hashlib.sha256(text.encode()).hexdigest()
                c.execute('INSERT INTO entries VALUES(?,?,?)',(eid,fingerprint,json.dumps(e)))
            c.execute('INSERT INTO recipes VALUES(?,?)',(r['id'],json.dumps(r)))
    return recipe_details(r)

@app.get('/recipes/{id}', dependencies=[Depends(auth)])
async def get_recipe(id: UUID):
    return recipe_details(load_recipe(id))

class RecipeCategory(BaseModel):
    category: Literal['food','drink']

@app.patch('/recipes/{id}/category',dependencies=[Depends(auth)])
async def migrate_recipe(id: UUID,body: RecipeCategory):
    with db() as c:
        c.execute('BEGIN IMMEDIATE')
        row=c.execute('SELECT payload FROM recipes WHERE id=?',(str(id),)).fetchone()
        if not row:raise HTTPException(404,'Recipe not found')
        r=json.loads(row['payload'])
        if body.category=='food' and r.get('alcohol_abv') is not None:raise HTTPException(422,'Remove ABV before moving a drink to food recipes')
        r['category']=body.category
        c.execute('UPDATE recipes SET payload=? WHERE id=?',(json.dumps(r),str(id)))
    return recipe_details(r)

@app.put('/recipes/{id}', dependencies=[Depends(auth)])
async def edit_recipe(id: UUID, body: RecipeEdit):
    with db() as c:
        c.execute('BEGIN IMMEDIATE')
        row=c.execute('SELECT payload FROM recipes WHERE id=?',(str(id),)).fetchone()
        if not row:raise HTTPException(404,'Recipe not found')
        previous=json.loads(row['payload'])
        r={**{k:previous[k] for k in ('copied_from','duplicate_request') if k in previous},'id':str(id),**body.model_dump(mode='json',exclude={'amend_existing'})}
        updated=[]
        if body.amend_existing:
            details=recipe_details(r)
            if details['status']!='ready':raise HTTPException(409,'Resolve ingredients before amending logged entries')
            entries=[json.loads(row['payload']) for row in c.execute('SELECT payload FROM entries')]
            for old in entries:
                if old.get('recipe_id') or old.get('type')!='recipe' or old.get('source',{}).get('recipe_id')!=str(id):continue
                q=old['quantity']
                replacement=recipe_entry(details,RecipeIntake(id=old['id'],timestamp=old['timestamp'],amount=q['value'],unit=q['unit']))
                changes={k:replacement.get(k) for k in ('description','source','recipe_snapshot','nutrients','warnings','reason','status','drinking_water_ml','ethanol_g')}
                if all(old.get(k)==v for k,v in changes.items()):continue
                audit=DATA/'originals'/f"{old['id']}-revision-{old.get('revision',1)}.json"
                text=json.dumps(old,ensure_ascii=False)
                if audit.exists() and audit.read_text()!=text:raise HTTPException(409,'Existing revision archive differs')
                if not audit.exists():audit.write_text(text)
                entry={**old,**{k:v for k,v in changes.items() if v is not None},'revision':old.get('revision',1)+1}
                for key in ('drinking_water_ml','ethanol_g'):
                    if changes[key] is None:entry.pop(key,None)
                c.execute('UPDATE entries SET payload=? WHERE id=?',(json.dumps(entry),entry['id']))
                updated.append(entry['id'])
        c.execute('UPDATE recipes SET payload=? WHERE id=?',(json.dumps(r),str(id)))
    return {**recipe_details(r),'amended_entries':len(updated)}

class RecipeIntake(BaseModel):
    id: UUID
    timestamp: datetime
    unit: Literal['portion','fraction','g','ml']
    amount: float = Field(gt=0, allow_inf_nan=False)

    @model_validator(mode='after')
    def timezone_required(self):
        if self.timestamp.utcoffset() is None: raise ValueError('timestamp requires timezone')
        if self.unit=='fraction' and self.amount>1: raise ValueError('Fraction must be at most 1')
        return self


def recipe_entry(r,body):
    if r['status']!='ready': raise HTTPException(409,'Resolve all ingredients and quantities first')
    if body.unit=='g' and not r['finished_weight_g']:
        raise HTTPException(422,'Set finished recipe weight before logging grams')
    if body.unit=='ml' and not r.get('finished_volume_ml'):raise HTTPException(422,'Set total drink volume before logging ml')
    factor=body.amount / r['servings'] if body.unit=='portion' else body.amount / r['finished_weight_g'] if body.unit=='g' else body.amount/r['finished_volume_ml'] if body.unit=='ml' else body.amount
    e={'id':str(body.id),'type':'recipe','timestamp':body.timestamp.isoformat(),'status':'processed','health_status':'pending','revision':1,'description':r['name'],'quantity':{'value':body.amount,'unit':body.unit},'source':{'provider':'BLS' if r['health_blocked'] else 'Recipe','recipe_id':r['id']},'recipe_snapshot':{**{k:v for k,v in r.items() if k not in ('raw_nutrients','raw_ingredients')},'nutrients':r['raw_nutrients'],'ingredients':r['raw_ingredients']},'nutrients':{k:{'value':v['value']*factor,'unit':v['unit']} for k,v in r['raw_nutrients'].items()},'warnings':r['warnings']+['Nutrients missing in any ingredient remain unknown; cooking losses are not modelled'],'reason':None}
    ethanol=r['ethanol_g']
    if r['drinking_water_ml']: e['drinking_water_ml']=r['drinking_water_ml']*factor
    if ethanol: e['ethanol_g']=ethanol*factor
    return e

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
    e=recipe_entry(r,body)
    with db() as c:
        c.execute('BEGIN IMMEDIATE')
        old=c.execute('SELECT fingerprint,payload FROM entries WHERE id=?',(e['id'],)).fetchone()
        if old:
            if old['fingerprint']!=fingerprint: raise HTTPException(409,'ID already used')
            return json.loads(old['payload'])
        (DATA/'originals'/f"{e['id']}.json").write_text(json.dumps(original))
        c.execute('INSERT INTO entries VALUES(?,?,?)',(e['id'],fingerprint,json.dumps(e)))
    return e


from . import home
home.install(app, db, auth, Entry, create, load_recipe, RecipeIntake, recipe_intake)

from . import statistics
statistics.install(app, db, auth)

from . import health_days
health_days.install(app, db, auth)

from . import barcode_scan
barcode_scan.install(app, auth)

from . import favorites
favorites.install(app, db, auth, Entry)

from . import food_search
food_search.install(app, db, auth, normalize)

from . import manual_ingredients
manual_ingredients.install(app,db,auth)

from . import alcohol
alcohol.install(app,db,auth)

from . import fooddata_import
fooddata_import.install(app,auth)

from . import json_import
json_import.install(app,db,auth,Entry,process,lambda:DATA,normalize)

from . import label_ocr
label_ocr.install(app,auth)
