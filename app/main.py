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
from fastapi import Depends, FastAPI, HTTPException, Query, Request
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
    if len(KEY) < 32:
        raise RuntimeError('FRISS_API_KEY must contain at least 32 characters')
    DATA.mkdir(parents=True, exist_ok=True)
    (DATA / 'originals').mkdir(exist_ok=True)
    with db() as c:
        c.executescript('''
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS foods(code TEXT PRIMARY KEY, payload TEXT NOT NULL, search TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS entries(id TEXT PRIMARY KEY, fingerprint TEXT NOT NULL, payload TEXT NOT NULL);
        ''')
        for path in sorted((DATA / 'bls').glob('*.json')):
            for food in json.loads(path.read_text()).values():
                c.execute('INSERT OR IGNORE INTO foods VALUES(?,?,?)', (food['bls_code'], json.dumps(food), normalize(food['name_de']+' '+food['name_en'])))
    yield

bearer = HTTPBearer(auto_error=False)

async def auth(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
    if not KEY or credentials is None or not hmac.compare_digest(credentials.credentials, KEY):
        raise HTTPException(401, 'Invalid API key')

app = FastAPI(title='Friss', version='1.1.0', lifespan=lifespan)

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
    return [e for e in result if (status is None or e['status']==status) and (start is None or datetime.fromisoformat(e['timestamp'])>=start) and (end is None or datetime.fromisoformat(e['timestamp'])<end)][:limit]

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
    return [e for e in await entries(limit=1000) if e['status']=='processed' and e['health_status']=='pending' and e.get('source',{}).get('provider')!='BLS' and e['nutrients']]

@app.post('/health-export/{id}/claim', dependencies=[Depends(auth)])
async def claim(id:UUID):
    # Atomic reservation: never automatically retry a possibly partially written Health batch.
    with db() as c:
        c.execute('BEGIN IMMEDIATE')
        row=c.execute('SELECT payload FROM entries WHERE id=?',(str(id),)).fetchone()
        if not row:
            raise HTTPException(404,'Entry not found')
        e=json.loads(row['payload'])
        if e['status']!='processed' or e['health_status']!='pending' or e.get('source',{}).get('provider')=='BLS' or not e['nutrients']:
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
