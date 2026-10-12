import copy
import json
import unittest
from uuid import uuid4
import test_api as support
from app import main,home,nutrient_policy

class MissingNutrientTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp=support.ApiTests.asyncSetUp
    asyncTearDown=support.ApiTests.asyncTearDown
    payload=support.ApiTests.payload

    async def setting(self,value):
        prefs=(await self.client.get('/settings')).json();prefs['missing_nutrients_as_zero']=value
        response=await self.client.put('/settings',json=prefs)
        self.assertEqual(response.status_code,200);return response.json()

    async def food(self,nutrients):
        ingredient={'id':str(uuid4()),'version':0,'name_de':'Test','name_en':'Test','nutrients':nutrients}
        self.assertEqual((await self.client.post('/manual-ingredients',json=ingredient)).status_code,201)
        return ingredient

    async def summary(self):
        data=(await self.client.get('/home-summary',params={'start':'2026-10-04T00:00:00+02:00','end':'2026-10-05T00:00:00+02:00'})).json()
        return {n['key']:n for n in data['nutrients']},data

    async def test_toggle_reversible_existing_entries_statistics_and_restart(self):
        self.assertFalse((await self.client.get('/settings')).json()['missing_nutrients_as_zero'])
        food=await self.food({'dietaryEnergyConsumed':{'value':100,'unit':'kcal'}})
        entry=self.payload(type='manual',drink=None,manual_id=food['id'],quantity={'value':100,'unit':'g'})
        await self.client.post('/entries',json=entry)
        with main.db() as c:before=c.execute('SELECT payload FROM entries WHERE id=?',(entry['id'],)).fetchone()['payload']
        original=(main.DATA/'originals'/f"{entry['id']}.json").read_bytes()
        rows,_=await self.summary();self.assertTrue(rows['dietaryProtein']['partial'])
        await self.setting(True)
        rows,_=await self.summary();self.assertEqual(rows['dietaryProtein']['values'],[{'value':0,'unit':'g'}]);self.assertFalse(rows['dietaryProtein']['partial'])
        displayed=(await self.client.get('/entries')).json()[0]
        self.assertTrue(displayed['nutrients']['dietaryProtein']['assumed'])
        details=(await self.client.get('/entries/'+entry['id']+'/details')).json()
        self.assertEqual(details['contributions']['dietaryProtein']['value'],0)
        stats=(await self.client.get('/statistics',params={'start':'2026-10-04','end':'2026-10-05','tz':'Europe/Berlin'})).json()
        self.assertEqual(stats['days'][0]['values']['protein_g'],0);self.assertFalse(stats['days'][0]['partial']['protein_g'])
        self.assertIsNone(stats['days'][1]['values']['protein_g']) # No entries remains a gap.
        await self.life.__aexit__(None,None,None);self.life=main.lifespan(main.app);await self.life.__aenter__()
        self.assertTrue((await self.client.get('/settings')).json()['missing_nutrients_as_zero'])
        await self.setting(False)
        rows,_=await self.summary();self.assertTrue(rows['dietaryProtein']['partial'])
        with main.db() as c:after=c.execute('SELECT payload FROM entries WHERE id=?',(entry['id'],)).fetchone()['payload']
        self.assertEqual(after,before);self.assertEqual((main.DATA/'originals'/f"{entry['id']}.json").read_bytes(),original)
        self.assertNotIn('dietaryProtein',(await self.client.get('/manual-ingredients')).json()[0]['nutrients'])

    async def test_recipe_mixed_coverage_uses_known_terms_and_raw_snapshot(self):
        a=await self.food({'dietaryEnergyConsumed':{'value':100,'unit':'kcal'},'dietaryProtein':{'value':10,'unit':'g'},'dietaryVitaminC':{'value':5,'unit':'mg'}})
        b=await self.food({'dietaryEnergyConsumed':{'value':200,'unit':'kcal'}})
        recipe={'id':str(uuid4()),'name':'Mixed','servings':2}
        await self.client.post('/recipes',json=recipe)
        for ingredient in [a,b]:await self.client.post('/entries',json=self.payload(type='manual',drink=None,manual_id=ingredient['id'],quantity={'value':100,'unit':'g'},recipe_id=recipe['id']))
        await self.setting(True)
        r=(await self.client.get('/recipes/'+recipe['id'])).json()
        self.assertEqual(r['nutrients']['dietaryProtein']['value'],10)
        self.assertNotIn('dietaryProtein',r['raw_nutrients'])
        intake={'id':str(uuid4()),'timestamp':'2026-10-04T18:00:00+02:00','amount':1,'unit':'portion'}
        await self.client.post('/recipes/'+recipe['id']+'/intake',json=intake)
        rows,_=await self.summary();self.assertEqual(rows['dietaryProtein']['values'][0]['value'],5);self.assertFalse(rows['dietaryProtein']['partial'])
        details=(await self.client.get('/entries/'+intake['id']+'/details')).json()
        self.assertEqual(details['contributions']['dietaryVitaminC']['value'],2.5)
        await self.setting(False)
        rows,_=await self.summary();self.assertTrue(rows['dietaryProtein']['partial'])

    async def test_individual_health_claim_freezes_assumptions_and_blank_recipe_ready(self):
        food=await self.food({'dietaryEnergyConsumed':{'value':100,'unit':'kcal'}})
        p=self.payload(type='manual',drink=None,manual_id=food['id'],quantity={'value':100,'unit':'g'})
        await self.client.post('/entries',json=p)
        await self.setting(True)
        claim=(await self.client.post('/health-export/'+p['id']+'/claim')).json()
        self.assertEqual(claim['nutrients']['dietaryProtein']['value'],0)
        await self.setting(False)
        frozen=(await self.client.get('/entries/'+p['id'])).json()
        self.assertEqual(frozen['health_export_nutrients']['dietaryProtein']['value'],0)
        self.assertNotIn('dietaryProtein',frozen['nutrients'])
        self.assertTrue(frozen['health_export_missing_as_zero'])

    async def test_health_batches_capture_policy_without_overwriting_prior_exports(self):
        food=await self.food({'dietaryEnergyConsumed':{'value':100,'unit':'kcal'}})
        await self.client.post('/entries',json=self.payload(type='manual',drink=None,manual_id=food['id'],quantity={'value':100,'unit':'g'}))
        await self.setting(True)
        batch=(await self.client.post('/health-days/prepare',json={'day':'2026-10-04','timezone':'Europe/Berlin'})).json()
        samples={n['identifier']:n for n in batch['samples']}
        self.assertTrue(samples['dietaryProtein']['assumed']);self.assertEqual(samples['dietaryProtein']['value'],0);self.assertTrue(batch['missing_nutrients_as_zero'])
        frozen=copy.deepcopy(batch)
        await self.setting(False)
        stored=(await self.client.get('/health-days/'+batch['id'])).json();self.assertEqual(stored,frozen)
        days=(await self.client.get('/health-days',params={'tz':'Europe/Berlin'})).json();self.assertTrue(days[0]['changed'])
        self.assertEqual((await self.client.post('/health-days/prepare',json={'day':'2026-10-04','timezone':'Europe/Berlin'})).status_code,409)

    async def test_resolved_bls_with_blank_nutrients_and_unknown_quantity(self):
        food={'bls_code':'EMPTY','name_de':'Empty','name_en':'Empty','nutrients':{'dietaryProtein':None}}
        with main.db() as c:c.execute('INSERT INTO foods VALUES(?,?,?)',('EMPTY',json.dumps(food),'empty'))
        await self.client.post('/entries',json=self.payload(type='item',drink=None,bls_code='EMPTY',quantity={'value':100,'unit':'g'}))
        await self.client.post('/entries',json=self.payload(type='item',drink=None,bls_code='EMPTY',quantity=None))
        await self.setting(True)
        entries=(await self.client.get('/entries')).json()
        known=next(e for e in entries if e['quantity']);unknown=next(e for e in entries if not e['quantity'])
        self.assertEqual(known['status'],'processed');self.assertEqual(known['nutrients']['dietaryProtein']['value'],0)
        self.assertEqual(unknown['status'],'needs_review');self.assertEqual(unknown['nutrients'],{})

class MissingPolicyUnitTests(unittest.TestCase):
    def test_trace_becomes_assumed_zero_but_unverified_numeric_values_remain_visible(self):
        e={'type':'item','status':'processed','quantity':{'value':100,'unit':'g'},'source':{'provider':'BLS'},'food':{'bls_code':'X','nutrients':{'dietaryVitaminC':'TR','dietarySelenium':3,'dietaryProtein':None}},'nutrients':{}}
        values=home.nutrient_values(e,True)
        self.assertEqual(values['dietaryVitaminC']['value'],0);self.assertTrue(values['dietaryVitaminC']['assumed'])
        self.assertEqual(home.nutrient_values(e,False)['dietaryVitaminC']['qualifier'],'TR')
        self.assertEqual(values['dietarySelenium']['value'],3);self.assertIsNone(values['dietarySelenium']['unit'])
        self.assertEqual(values['dietaryProtein']['value'],0)
        off={**e,'source':{'provider':'Open Food Facts'},'food':{'nutriments':{'fiber_100g':'TR','proteins_100g':''}}}
        values=home.nutrient_values(off,True)
        self.assertEqual(values['dietaryFiber']['value'],0);self.assertTrue(values['dietaryFiber']['assumed']);self.assertEqual(values['dietaryProtein']['value'],0)

    def test_detection_limits_and_recipe_sums_are_complete_only_when_enabled(self):
        for marker in ['<LOD','<LOQ','<LOD or <LOQ','<LOD / <LOQ',' TR ','≤ LOQ','<LOD oder <LOQ']:
            empty={'type':'item','status':'processed','quantity':{'value':100,'unit':'g'},'source':{'provider':'BLS'},'food':{'bls_code':'X','nutrients':{'dietaryCalcium':marker}},'nutrients':{}}
            known={'type':'manual','status':'processed','quantity':{'value':100,'unit':'g'},'nutrients':{'dietaryCalcium':{'value':100,'unit':'mg'}}}
            before={n['key']:n for n in home.summarize([known,empty],False)['nutrients']}
            after={n['key']:n for n in home.summarize([known,empty],True)['nutrients']}
            self.assertTrue(before['dietaryCalcium']['partial']);self.assertEqual(before['dietaryCalcium']['qualifiers'],[marker])
            self.assertFalse(after['dietaryCalcium']['partial']);self.assertEqual(after['dietaryCalcium']['qualifiers'],[])
            self.assertAlmostEqual(after['dietaryCalcium']['values'][0]['value'],.1)
            recipe={'type':'recipe','status':'processed','quantity':{'value':.5,'unit':'fraction'},'nutrients':{},'recipe_snapshot':{'ingredients':[known,empty]}}
            value=home.nutrient_values(recipe,True)['dietaryCalcium']
            self.assertEqual(value['value'],50);self.assertTrue(value['assumed'])
        for bad in ['Incompatible nutrient units','UNKNOWN','source value or unit unresolved',3]:self.assertFalse(nutrient_policy.assumable_qualifier(bad))
