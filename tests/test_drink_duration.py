import unittest
from datetime import datetime,timedelta,timezone
from uuid import uuid4
import test_api as support
from app import alcohol,main
PROFILE={'mass_kg':80,'distribution':.68,'elimination_percent_per_hour':.015,'absorption_per_hour':3}

class DurationModelTests(unittest.TestCase):
    def drink(self,hours=2):
        start=datetime(2026,10,16,23,tzinfo=timezone.utc)
        return {'id':'drink','type':'drink','drink':'alcohol','status':'processed','timestamp':start.isoformat(),'finished_at':(start+timedelta(hours=hours)).isoformat(),'ethanol_g':40}

    def test_spread_intake_lower_initial_bac_and_sampling_invariance(self):
        e=self.drink();start=datetime.fromisoformat(e['timestamp']);moments=[start+timedelta(minutes=m) for m in range(361)]
        spread=alcohol.estimate([e],PROFILE,moments)
        instant=alcohol.estimate([{**e,'finished_at':None}],PROFILE,moments)
        self.assertEqual(spread[0],0);self.assertLess(spread[30],instant[30]);self.assertLess(max(spread),max(instant))
        sparse=alcohol.estimate([e],PROFILE,[moments[60],moments[180],moments[-1]])
        for actual,expected in zip(sparse,[spread[60],spread[180],spread[-1]]):self.assertAlmostEqual(actual,expected,places=11)
        self.assertGreater(spread[90],0) # Consumption continues past midnight.

    def test_overlapping_drinks_equal_combined_rate_and_sober_gaps(self):
        e=self.drink();start=datetime.fromisoformat(e['timestamp']);moments=[start+timedelta(hours=h) for h in [0,1,2,5,24,25,26]]
        split=alcohol.estimate([{**e,'ethanol_g':20},{**e,'id':'second','ethanol_g':20}],PROFILE,moments)
        combined=alcohol.estimate([e],PROFILE,moments)
        for a,b in zip(split,combined):self.assertAlmostEqual(a,b,places=11)
        later={**e,'timestamp':(start+timedelta(hours=24)).isoformat(),'finished_at':(start+timedelta(hours=26)).isoformat()}
        repeated=alcohol.estimate([e,later],PROFILE,moments)
        self.assertAlmostEqual(repeated[1],repeated[-2],places=8)
        self.assertEqual(alcohol.estimate([self.drink(0)],PROFILE,moments),alcohol.estimate([{**e,'finished_at':None}],PROFILE,moments))

class DurationApiTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp=support.ApiTests.asyncSetUp
    asyncTearDown=support.ApiTests.asyncTearDown
    payload=support.ApiTests.payload
    async def test_create_edit_clear_copy_and_validation(self):
        body=self.payload(drink='alcohol',quantity={'value':40,'unit':'g'},timestamp='2026-10-16T23:00:00+02:00',finished_at='2026-10-17T01:00:00+02:00')
        response=await self.client.post('/entries',json=body);self.assertEqual(response.status_code,201)
        self.assertEqual(response.json()['finished_at'],body['finished_at'])
        for finish in ['2026-10-16T22:00:00+02:00','2026-10-17T01:00:00']:
            self.assertEqual((await self.client.post('/entries',json={**body,'id':str(uuid4()),'finished_at':finish})).status_code,422)
        copied=await self.client.post('/entries/'+body['id']+'/copy',json={'id':str(uuid4()),'timestamp':'2026-10-18T23:00:00+02:00'})
        self.assertEqual(copied.json()['finished_at'],'2026-10-19T01:00:00+02:00')
        edited=await self.client.patch('/entries/'+body['id']+'/time',json={'timestamp':'2026-10-16T23:00:00+02:00','finished_at':'2026-10-17T02:00:00+02:00'})
        self.assertEqual(edited.json()['finished_at'],'2026-10-17T02:00:00+02:00')
        cleared=await self.client.patch('/entries/'+body['id']+'/time',json={'timestamp':body['timestamp'],'finished_at':None})
        self.assertIsNone(cleared.json()['finished_at'])

    async def test_drink_recipe_duration_survives_amendment(self):
        r={'id':str(uuid4()),'name':'Beer','category':'drink','servings':1,'finished_volume_ml':500,'alcohol_abv':5}
        await self.client.post('/recipes',json=r)
        intake={'id':str(uuid4()),'timestamp':'2026-10-16T23:00:00Z','finished_at':'2026-10-17T01:00:00Z','unit':'portion','amount':1}
        e=await self.client.post('/recipes/'+r['id']+'/intake',json=intake);self.assertEqual(e.status_code,201)
        edit={k:v for k,v in r.items() if k!='id'};edit.update(alcohol_abv=6,amend_existing=True)
        self.assertEqual((await self.client.put('/recipes/'+r['id'],json=edit)).status_code,200)
        self.assertEqual(main.load_entry(intake['id'])['finished_at'],'2026-10-17T01:00:00+00:00')
