"""Immutable daily export batches; Health writes happen on the iPhone."""
from . import bls_units, nutrient_policy
from . import home
import hashlib
import json
from datetime import date, datetime, time, timedelta
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from fastapi import Depends, HTTPException
from pydantic import BaseModel

class DayRequest(BaseModel):
    day: date
    timezone: str

class Confirmation(BaseModel):
    export_token: str
    success: bool

def zone_for(name):
    try: return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError): raise HTTPException(422, 'Unknown timezone')

def daily(records, day, zone):
    return sorted([e for e in records if not e.get('recipe_id') and datetime.fromisoformat(e['timestamp']).astimezone(zone).date()==day], key=lambda e:e['id'])

def fingerprint(entries):
    data=[{k:v for k,v in e.items() if k not in ('health_status','export_token')} for e in entries]
    return hashlib.sha256(json.dumps(data,sort_keys=True).encode()).hexdigest()

def blocked(entries):
    if not entries: return 'empty'
    if any(e['status']!='processed' for e in entries): return 'unresolved'
    if any(bls_units.blocked(e) for e in entries): return 'bls_units'
    if any(e['health_status']!='pending' for e in entries): return 'previous_export'
    if not any(bls_units.exportable(e) for e in entries): return 'no_nutrients'
    return None

def install(app, db, auth):
    @app.get('/health-days', dependencies=[Depends(auth)])
    async def days(tz: str='UTC'):
        zone=zone_for(tz)
        with db() as c:
            missing_as_zero=nutrient_policy.enabled(connection=c)
            records=[json.loads(r['payload']) for r in c.execute('SELECT payload FROM entries')]
            batches=[json.loads(r['payload']) for r in c.execute('SELECT payload FROM health_days')]
        known={datetime.fromisoformat(e['timestamp']).astimezone(zone).date() for e in records if not e.get('recipe_id')}
        known.update(date.fromisoformat(b['day']) for b in batches if b['timezone']==tz)
        result=[]
        for day in sorted(known,reverse=True):
            entries=daily(records,day,zone)
            batch=next((b for b in batches if b['day']==day.isoformat() and b['timezone']==tz),None)
            reason=blocked([home.interpreted_entry(e,missing_as_zero) for e in entries])
            result.append({'missing_nutrients_as_zero':missing_as_zero,'day':day.isoformat(),'entries':len(entries),'status':batch['status'] if batch else 'not_exported','changed':bool(batch and (batch['fingerprint']!=fingerprint(entries) or batch.get('missing_nutrients_as_zero',False)!=missing_as_zero)), 'blocked':None if batch else reason,'batch_id':batch['id'] if batch else None})
        return result

    @app.post('/health-days/prepare', dependencies=[Depends(auth)])
    async def prepare(body: DayRequest):
        zone=zone_for(body.timezone)
        with db() as c:
            c.execute('BEGIN IMMEDIATE')
            old=c.execute('SELECT payload FROM health_days WHERE day=? AND timezone=?',(body.day.isoformat(),body.timezone)).fetchone()
            if old: raise HTTPException(409, 'Day already reserved or exported; review Apple Health before corrections')
            missing_as_zero=nutrient_policy.enabled(connection=c)
            records=[json.loads(r['payload']) for r in c.execute('SELECT payload FROM entries')]
            entries=daily(records,body.day,zone)
            reason=blocked([home.interpreted_entry(e,missing_as_zero) for e in entries])
            reserved={eid for r in c.execute('SELECT payload FROM health_days') for eid in json.loads(r['payload'])['entry_ids']}
            if any(e['id'] in reserved for e in entries): reason='previous_export'
            if reason: raise HTTPException(409, reason)
            totals={}
            for e in entries:
                for key,n in home.interpreted_entry(e,missing_as_zero)['nutrients'].items():
                    unit=n['unit'];value=n['value']
                    # BLS food water is a mass, not a logged drink volume.
                    # Keep it visible in Friss; export only explicit water volumes.
                    if key=='dietaryWater' and unit!='ml': continue
                    if unit in ('g','mg','mcg'):
                        value*=dict(g=1,mg=.001,mcg=.000001)[unit];unit='g'
                    if key in totals and totals[key]['unit']!=unit: raise HTTPException(409,'Incompatible nutrient units')
                    totals.setdefault(key,{'value':0,'unit':unit})['value']+=value
                    if n.get('assumed'):totals[key]['assumed']=True
            # Samples are day totals, represented at local noon, never a predicted BAC.
            timestamp=datetime.combine(body.day,time(12),zone).isoformat()
            batch={'missing_nutrients_as_zero':missing_as_zero,'id':str(uuid4()),'day':body.day.isoformat(),'timezone':body.timezone,'status':'prepared','fingerprint':fingerprint(entries),'export_token':str(uuid4()),'samples':[{'identifier':k,'value':v['value'],'unit':v['unit'],'timestamp':timestamp,**({'assumed':True} if v.get('assumed') else {})} for k,v in sorted(totals.items())],'entry_ids':[e['id'] for e in entries],'confirmation_source':None}
            c.execute('INSERT INTO health_days VALUES(?,?,?,?)',(batch['id'],batch['day'],batch['timezone'],json.dumps(batch)))
            for e in entries:
                e.update(health_status='claimed',export_token=batch['export_token'])
                c.execute('UPDATE entries SET payload=? WHERE id=?',(json.dumps(e),e['id']))
        return batch

    @app.get('/health-days/{id}',dependencies=[Depends(auth)])
    async def batch(id:UUID):
        with db() as c: row=c.execute('SELECT payload FROM health_days WHERE id=?',(str(id),)).fetchone()
        if not row: raise HTTPException(404,'Export not found')
        return json.loads(row['payload'])

    @app.post('/health-days/{id}/ack',dependencies=[Depends(auth)])
    async def acknowledge(id:UUID,body:Confirmation):
        with db() as c:
            c.execute('BEGIN IMMEDIATE')
            row=c.execute('SELECT payload FROM health_days WHERE id=?',(str(id),)).fetchone()
            if not row: raise HTTPException(404,'Export not found')
            b=json.loads(row['payload'])
            if body.export_token!=b['export_token']: raise HTTPException(409,'Invalid export token')
            desired='confirmed' if body.success else 'needs_review'
            if b['status']!='prepared':
                if b['status']!=desired: raise HTTPException(409,'Export already acknowledged')
                return b
            b.update(status=desired,confirmation_source='iphone_or_user',confirmed_at=datetime.now().astimezone().isoformat())
            c.execute('UPDATE health_days SET payload=? WHERE id=?',(json.dumps(b),str(id)))
            for eid in b['entry_ids']:
                row=c.execute('SELECT payload FROM entries WHERE id=?',(eid,)).fetchone()
                if not row: continue
                e=json.loads(row['payload'])
                e['health_status']='synced' if body.success else 'needs_review'
                c.execute('UPDATE entries SET payload=? WHERE id=?',(json.dumps(e),eid))
        return b
