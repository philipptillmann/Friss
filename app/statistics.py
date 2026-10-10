"""Daily statistics with local-calendar boundaries and explicit missing days."""
import json
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from fastapi import Depends, HTTPException, Query
from .home import summarize

METRICS={'energy_kcal':('dietaryEnergyConsumed','kcal'),'protein_g':('dietaryProtein','g'),'carbohydrates_g':('dietaryCarbohydrates','g'),'fat_g':('dietaryFatTotal','g')}

def build_statistics(records,start,end,zone):
    groups={}
    day=start
    while day<=end:
        groups[day.isoformat()]=[]
        day+=timedelta(days=1)
    for e in records:
        if e.get('recipe_id'): continue
        day=datetime.fromisoformat(e['timestamp']).astimezone(zone).date().isoformat()
        if day in groups: groups[day].append(e)
    daily=[]
    for day,entries in groups.items():
        summary=summarize(entries)
        known={r['key']:r for r in summary['nutrients']}
        values={};partial={}
        for metric,(key,unit) in METRICS.items():
            r=known.get(key,{})
            matches=[v['value'] for v in r.get('values',[]) if v['unit']==unit]
            values[metric]=sum(matches) if matches else None
            partial[metric]=bool(r.get('partial') or (entries and summary['unresolved']))
        any_processed=any(e['status']=='processed' for e in entries)
        for metric,field in [('water_ml','drinking_water_ml'),('caffeine_mg','caffeine_mg'),('alcohol_g','ethanol_g')]:
            values[metric]=summary[field] if any_processed else None
            partial[metric]=bool(summary['unresolved'])
        daily.append({'date':day,'entries':len(entries),'unresolved':summary['unresolved'],'values':values,'partial':partial})
    aggregates={}
    for metric in [*METRICS,'water_ml','caffeine_mg','alcohol_g']:
        observed=[d['values'][metric] for d in daily if d['values'][metric] is not None]
        aggregates[metric]={'total':sum(observed) if observed else None,'average':sum(observed)/len(observed) if observed else None,'days':len(observed),'partial_days':sum(d['partial'][metric] for d in daily if d['values'][metric] is not None)}
    return {'start':start.isoformat(),'end':end.isoformat(),'timezone':str(zone),'days':daily,'metrics':aggregates,'logged_days':sum(bool(d['entries']) for d in daily),'unresolved':sum(d['unresolved'] for d in daily)}

def install(app,db,auth):
    @app.get('/statistics',dependencies=[Depends(auth)])
    async def statistics(start:date,end:date,tz:str=Query(default='UTC',max_length=100)):
        if end<start or (end-start).days>=366: raise HTTPException(422,'Select between 1 and 366 days')
        try: zone=ZoneInfo(tz)
        except (ZoneInfoNotFoundError,ValueError): raise HTTPException(422,'Unknown timezone')
        with db() as c: records=[json.loads(r['payload']) for r in c.execute('SELECT payload FROM entries')]
        return build_statistics(records,start,end,zone)
