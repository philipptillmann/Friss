import unittest
from datetime import date
from zoneinfo import ZoneInfo
from app.statistics import build_statistics
import test_api as support

class StatisticsTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp=support.ApiTests.asyncSetUp
    asyncTearDown=support.ApiTests.asyncTearDown
    payload=support.ApiTests.payload

    async def test_statistics_range_auth_and_unlogged_days(self):
        await self.client.post('/entries',json=self.payload())
        query={'start':'2026-10-04','end':'2026-10-06','tz':'Europe/Berlin'}
        response=await self.client.get('/statistics',params=query)
        self.assertEqual(response.status_code,200)
        result=response.json();self.assertEqual(len(result['days']),3)
        self.assertEqual(result['days'][0]['values']['water_ml'],250)
        self.assertIsNone(result['days'][1]['values']['water_ml'])
        self.assertEqual(result['metrics']['water_ml']['average'],250)
        self.assertEqual(result['metrics']['water_ml']['days'],1)
        self.assertEqual(result['logged_days'],1)
        self.assertEqual((await self.client.get('/statistics',params=query,headers={'Authorization':'bad'})).status_code,401)
        for invalid in [{**query,'tz':'not/a/zone'},{**query,'end':'2026-10-01'},{**query,'end':'2028-01-01'}]:
            self.assertEqual((await self.client.get('/statistics',params=invalid)).status_code,422)

    async def test_local_midnight_dst_and_recipe_ingredients(self):
        entries=[{'type':'drink','drink':'water','status':'processed','timestamp':stamp,'nutrients':{'dietaryWater':{'value':100,'unit':'ml'}}} for stamp in ['2026-10-24T22:30:00+00:00','2026-10-25T22:30:00+00:00','2026-10-25T23:30:00+00:00']]
        entries.append({**entries[0],'recipe_id':'ingredient'})
        result=build_statistics(entries,date(2026,10,25),date(2026,10,26),ZoneInfo('Europe/Berlin'))
        self.assertEqual([d['entries'] for d in result['days']],[2,1])
        self.assertEqual(result['metrics']['water_ml']['total'],300)
        self.assertEqual(result['metrics']['water_ml']['average'],150)

    async def test_missing_nutrients_partial_days_and_no_duplicate_recipe(self):
        food={'type':'recipe','timestamp':'2026-10-04T12:00:00+02:00','status':'processed','nutrients':{'dietaryEnergyConsumed':{'value':300,'unit':'kcal'},'dietaryProtein':{'value':20,'unit':'g'}}}
        unresolved={'type':'text','status':'needs_review','timestamp':food['timestamp'],'nutrients':{}}
        result=build_statistics([food,unresolved,{**food,'recipe_id':'ingredient'}],date(2026,10,4),date(2026,10,5),ZoneInfo('Europe/Berlin'))
        self.assertEqual(result['metrics']['energy_kcal']['total'],300)
        self.assertEqual(result['metrics']['energy_kcal']['average'],300)
        self.assertEqual(result['metrics']['energy_kcal']['partial_days'],1)
        self.assertIsNone(result['days'][0]['values']['fat_g'])
        self.assertEqual(result['unresolved'],1)
