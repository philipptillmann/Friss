import unittest
from datetime import datetime,timedelta,timezone
from uuid import uuid4
import test_api as support
from app import alcohol

PROFILE={'mass_kg':80,'distribution':.68,'elimination_percent_per_hour':.015,'absorption_per_hour':3}

class AlcoholTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp=support.ApiTests.asyncSetUp
    asyncTearDown=support.ApiTests.asyncTearDown
    payload=support.ApiTests.payload

    async def profile(self):
        prefs=(await self.client.get('/settings')).json();prefs['bac']=PROFILE
        return (await self.client.put('/settings',json=prefs)).json()

    async def summary(self,**params):
        return await self.client.get('/alcohol-summary',params={'start':'2026-10-04T00:00:00+02:00','end':'2026-10-05T00:00:00+02:00',**params})

    async def test_journal_direct_grams_volume_idempotency_and_curve(self):
        await self.profile()
        direct=self.payload(drink='alcohol',description='Whisky',quantity={'value':20,'unit':'g'},timestamp='2026-10-04T18:00:00+02:00')
        first=(await self.client.post('/entries',json=direct)).json()
        self.assertEqual(first['ethanol_g'],20);self.assertEqual(first['status'],'processed')
        self.assertEqual((await self.client.post('/entries',json=direct)).json(),first)
        volume=self.payload(drink='alcohol',quantity={'value':500,'unit':'ml'},alcohol_abv=5,timestamp='2026-10-04T19:00:00+02:00')
        second=(await self.client.post('/entries',json=volume)).json();self.assertAlmostEqual(second['ethanol_g'],19.725)
        result=(await self.summary()).json();self.assertEqual(len(result['entries']),2)
        self.assertAlmostEqual(result['ethanol_g'],39.725);self.assertEqual(len(result['points']),1441)
        self.assertEqual(result['points'][18*60]['bac_percent'],0)
        self.assertGreater(result['points'][19*60]['bac_percent'],0)
        self.assertEqual(len((await self.client.get('/entries')).json()),2)
        self.assertEqual((await self.client.post('/entries',json={**direct,'id':str(uuid4()),'alcohol_abv':40})).status_code,422)
        await self.client.patch('/entries/'+first['id']+'/time',json={'timestamp':'2026-10-04T20:00:00+02:00'})
        changed=(await self.summary()).json();self.assertEqual(changed['points'][19*60]['bac_percent'],0)
        await self.client.delete('/entries/'+second['id']);self.assertEqual(len((await self.summary()).json()['entries']),1)
        await self.client.delete('/entries/'+first['id']);self.assertEqual((await self.summary()).json()['ethanol_g'],0)

    async def test_prior_day_carry_profile_missing_validation_and_recipe_exclusion(self):
        direct=self.payload(drink='alcohol',quantity={'value':30,'unit':'g'},timestamp='2026-10-03T23:30:00+02:00')
        await self.client.post('/entries',json=direct)
        missing=(await self.summary()).json();self.assertIsNone(missing['profile']);self.assertEqual(missing['points'],[])
        await self.profile();result=(await self.summary()).json()
        self.assertEqual(result['entries'],[]);self.assertEqual(result['ethanol_g'],0)
        self.assertGreater(result['points'][0]['bac_percent'],0)
        recipe={'id':str(uuid4()),'name':'Test recipe','servings':1}
        await self.client.post('/recipes',json=recipe)
        await self.client.post('/entries',json=self.payload(drink='alcohol',quantity={'value':100,'unit':'g'},recipe_id=recipe['id']))
        self.assertEqual((await self.summary()).json()['ethanol_g'],0)
        self.assertEqual((await self.summary(start='2026-10-04T00:00:00')).status_code,422)
        self.assertEqual((await self.summary(end='2026-10-10T00:00:00+02:00')).status_code,422)
        self.assertEqual((await self.client.get('/alcohol-summary',params={'start':direct['timestamp'],'end':'2026-10-05T00:00:00+02:00'},headers={'Authorization':'bad'})).status_code,401)

    async def test_gram_quick_button_and_favorite(self):
        prefs=await self.profile();button={'id':str(uuid4()),'label':'20 g Alkohol','entry':{'type':'drink','drink':'alcohol','quantity':{'value':20,'unit':'g'}}}
        prefs['buttons'].append(button)
        self.assertEqual((await self.client.put('/settings',json=prefs)).status_code,200)
        body={'id':str(uuid4()),'timestamp':'2026-10-04T20:00:00+02:00'}
        logged=(await self.client.post('/quick-buttons/'+button['id']+'/intake',json=body)).json()
        self.assertEqual(logged['ethanol_g'],20);self.assertEqual(logged['timestamp'],body['timestamp'])
        favorite={'id':str(uuid4()),'label':'20 g','entry':button['entry'],'version':0}
        self.assertEqual((await self.client.post('/favorites',json=favorite)).status_code,201)
        resolved=(await self.client.post('/entries/'+logged['id']+'/resolve',json={'quantity':{'value':15,'unit':'g'}})).json()
        self.assertEqual(resolved['ethanol_g'],15)

class AlcoholCalculationTests(unittest.TestCase):
    def test_sober_gap_and_current_curve_agree(self):
        start=datetime(2026,10,4,18,tzinfo=timezone.utc)
        def drink(hours):return {'id':str(hours),'type':'drink','drink':'alcohol','status':'processed','timestamp':(start+timedelta(hours=hours)).isoformat(),'ethanol_g':14}
        moments=[start+timedelta(hours=h) for h in [0,1,10,11]]
        values=alcohol.estimate([drink(0),drink(10)],PROFILE,moments)
        self.assertEqual(values[0],0);self.assertEqual(values[2],0)
        self.assertAlmostEqual(values[1],values[3],places=10)
        self.assertAlmostEqual(alcohol.current([drink(0),drink(10)],PROFILE,moments[-1])['percent'],values[-1])
        # Sampling resolution must not change the solution.
        fine=[start+timedelta(minutes=m) for m in range(661)]
        self.assertAlmostEqual(alcohol.estimate([drink(0),drink(10)],PROFILE,fine)[-1],values[-1])
