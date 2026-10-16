"""BAC estimates from actual journal entries and the saved body profile.

Uniform drinking between start and finish (or instantaneous intake if omitted).
Exponential absorption with a shared rate; elimination stops at zero. Between intake-rate changes, absorption is integrated analytically, including
reflection at zero when absorption initially falls below elimination. No elimination debt is carried across sober gaps.
"""
import json
import math
from datetime import datetime, timedelta, timezone
from fastapi import Depends, HTTPException


def alcohol_entries(records):
    return sorted([e for e in records if not e.get('recipe_id') and
                   (e.get('drink')=='alcohol' or e.get('ethanol_g',0)>0)],
                  key=lambda e:(datetime.fromisoformat(e['timestamp']),e.get('id','')))


def estimate(records, profile, moments):
    if not profile:return [None for _ in moments]
    events=[]
    for e in alcohol_entries(records):
        if e['status']!='processed' or e.get('ethanol_g',0)<=0:continue
        start=datetime.fromisoformat(e['timestamp'])
        finish=datetime.fromisoformat(e['finished_at']) if e.get('finished_at') else start
        if finish>start:
            rate=e['ethanol_g']/((finish-start).total_seconds()/3600)
            events.extend([(start,0,rate),(finish,0,-rate)])
        else:events.append((start,e['ethanol_g'],0))
    events.sort(key=lambda event:event[0])
    result=[];index=0;gut=0;bac=0;previous=None;input_rate=0
    scale=.1/(profile['mass_kg']*profile['distribution'])
    absorption=profile['absorption_per_hour'];elimination=profile['elimination_percent_per_hour']
    def advance(to):
        nonlocal previous,gut,bac
        if previous is not None:
            hours=(to-previous).total_seconds()/3600
            decay=-math.expm1(-absorption*hours)
            absorbed=gut*decay+input_rate*(hours-decay/absorption)
            # With continuous drinking absorption can rise through elimination.
            # Reflect at zero at the interior minimum, rather than accumulating
            # a negative alcohol balance before absorption overtakes elimination.
            initial=scale*absorption*gut-elimination
            final=scale*(input_rate+(absorption*gut-input_rate)*math.exp(-absorption*hours))-elimination
            if initial<0<final:
                crossing=-math.log((input_rate-elimination/scale)/(input_rate-absorption*gut))/absorption
                first_decay=-math.expm1(-absorption*crossing)
                first_absorbed=gut*first_decay+input_rate*(crossing-first_decay/absorption)
                bac=max(0,bac+scale*first_absorbed-elimination*crossing)
                bac=max(0,bac+scale*(absorbed-first_absorbed)-elimination*(hours-crossing))
            else:bac=max(0,bac+scale*absorbed-elimination*hours)
            gut=max(0,gut+input_rate*hours-absorbed)
        previous=to
    for moment in moments:
        while index<len(events) and events[index][0]<=moment:
            at,grams,rate_change=events[index];advance(at);gut+=grams;input_rate=max(0,input_rate+rate_change);index+=1
        advance(moment);result.append(bac)
    return result


def current(records,profile,now):
    if not profile:return {'percent':None,'reason':'profile_required'}
    logged=[e for e in alcohol_entries(records) if datetime.fromisoformat(e['timestamp'])<=now]
    if any(e['status']!='processed' for e in logged):return {'percent':None,'reason':'unresolved_alcohol'}
    value=estimate(logged,profile,[now])[0]
    return {'percent':value,'reason':'model_estimate' if logged else 'no_logged_drinks','as_of':now.isoformat()}


def install(app,db,auth):
    @app.get('/alcohol-summary',dependencies=[Depends(auth)])
    async def summary(start:datetime,end:datetime):
        if start.utcoffset() is None or end.utcoffset() is None or not 0<(end-start).total_seconds()<=72*3600:
            raise HTTPException(422,'Provide a timezone-aware range of at most 72 hours')
        with db() as c:
            records=[json.loads(r['payload']) for r in c.execute('SELECT payload FROM entries')]
            row=c.execute('SELECT payload FROM preferences WHERE id=1').fetchone()
            profile=json.loads(row['payload']).get('bac') if row else None
        logged=alcohol_entries(records)
        selected=[e for e in logged if start<=datetime.fromisoformat(e['timestamp'])<end]
        count=math.ceil((end-start).total_seconds()/60)
        moments=[start+(end-start)*i/count for i in range(count+1)]
        # Sample every minute; events are integrated at their exact timestamps.
        values=estimate(logged,profile,moments)
        unresolved=any(e['status']!='processed' and datetime.fromisoformat(e['timestamp'])<end for e in logged)
        return {'start':start.isoformat(),'end':end.isoformat(),'entries':selected,
                'ethanol_g':sum(e.get('ethanol_g',0) for e in selected if e['status']=='processed'),
                'current_bac':current(records,profile,datetime.now(timezone.utc)),
                'profile':profile,'unresolved':unresolved,
                'points':[{'timestamp':t.isoformat(),'bac_percent':v} for t,v in zip(moments,values)] if profile and not unresolved else []}
