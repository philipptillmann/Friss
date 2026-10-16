"""Daily statistics with local-calendar boundaries and explicit missing days."""
import json
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from fastapi import Depends, HTTPException, Query
from .home import summarize,ALL_NUTRIENTS,MASS
from . import nutrient_policy

METRICS={'energy_kcal':('dietaryEnergyConsumed','kcal'),'protein_g':('dietaryProtein','g'),'carbohydrates_g':('dietaryCarbohydrates','g'),'fat_g':('dietaryFatTotal','g')}

MICRO={'VitaminA','VitaminD','VitaminK','VitaminB12','Folate','Biotin','Chromium','Iodine','Molybdenum','Selenium'}
GRAMS={'Carbohydrates','Fiber','Sugar','FatTotal','FatMonounsaturated','FatPolyunsaturated','FatSaturated','Protein','Water'}
for nutrient in ALL_NUTRIENTS:
    key='dietary'+nutrient
    if key not in {k for k,u in METRICS.values()}:
        METRICS[key]=(key,'g' if nutrient in GRAMS else 'mcg' if nutrient in MICRO else 'mg')


def build_statistics(records,start,end,zone,missing_as_zero=False,goals=None):
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
        summary=summarize(entries,missing_as_zero)
        known={r['key']:r for r in summary['nutrients']}
        values={};partial={}
        for metric,(key,unit) in METRICS.items():
            r=known.get(key,{})
            matches=[v['value'] if v['unit']==unit else v['value']*MASS[v['unit']]/MASS[unit] for v in r.get('values',[]) if v['unit']==unit or v['unit'] in MASS and unit in MASS]
            incompatible=any(v['unit']!=unit and not (v['unit'] in MASS and unit in MASS) for v in r.get('values',[]))
            values[metric]=sum(matches) if matches else None
            partial[metric]=bool(r.get('partial') or incompatible or (entries and summary['unresolved']))
        any_processed=any(e['status']=='processed' for e in entries)
        for metric,field in [('water_ml','drinking_water_ml'),('caffeine_mg','caffeine_mg'),('alcohol_g','ethanol_g')]:
            values[metric]=summary[field] if any_processed else None
            partial[metric]=bool(summary['unresolved'])
        daily.append({'date':day,'entries':len(entries),'unresolved':summary['unresolved'],'values':values,'partial':partial})
    aggregates={}
    for metric in [*METRICS,'water_ml','caffeine_mg','alcohol_g']:
        observed=[d['values'][metric] for d in daily if d['values'][metric] is not None]
        aggregates[metric]={'total':sum(observed) if observed else None,'average':sum(observed)/len(observed) if observed else None,'days':len(observed),'partial_days':sum(d['partial'][metric] for d in daily if d['values'][metric] is not None)}
    return {'goals':goals or {},'metric_definitions':{**{metric:{'key':key,'unit':unit} for metric,(key,unit) in METRICS.items()},'water_ml':{'key':None,'unit':'ml'},'caffeine_mg':{'key':'dietaryCaffeine','unit':'mg'},'alcohol_g':{'key':None,'unit':'g'}},'start':start.isoformat(),'end':end.isoformat(),'timezone':str(zone),'days':daily,'metrics':aggregates,'logged_days':sum(bool(d['entries']) for d in daily),'unresolved':sum(d['unresolved'] for d in daily)}

def install(app,db,auth):
    @app.get('/statistics',dependencies=[Depends(auth)])
    async def statistics(start:date,end:date,tz:str=Query(default='UTC',max_length=100)):
        if end<start or (end-start).days>=366: raise HTTPException(422,'Select between 1 and 366 days')
        try: zone=ZoneInfo(tz)
        except (ZoneInfoNotFoundError,ValueError): raise HTTPException(422,'Unknown timezone')
        with db() as c:
            records=[json.loads(r['payload']) for r in c.execute('SELECT payload FROM entries')]
            row=c.execute('SELECT payload FROM preferences WHERE id=1').fetchone()
            goals=json.loads(row['payload']).get('goals') if row else None
        return build_statistics(records,start,end,zone,nutrient_policy.enabled(db),goals)
