import io
import unittest
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from PIL import Image
import test_api as support
from app import home

class HomeTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp=support.ApiTests.asyncSetUp
    asyncTearDown=support.ApiTests.asyncTearDown
    payload=support.ApiTests.payload

    async def test_settings_validation_revision_and_quick_intake(self):
        settings=(await self.client.get('/settings')).json()
        self.assertEqual(settings['version'],0)
        button=settings['buttons'][0]
        saved=await self.client.put('/settings',json=settings)
        self.assertEqual(saved.status_code,200)
        self.assertEqual((await self.client.put('/settings',json=settings)).status_code,409)
        intake={'id':str(uuid4()),'timestamp':'2026-10-10T12:00:00+02:00'}
        result=await self.client.post('/quick-buttons/'+button['id']+'/intake',json=intake)
        self.assertEqual(result.status_code,200)
        self.assertEqual(result.json()['nutrients']['dietaryWater']['value'],250)
        self.assertEqual((await self.client.post('/quick-buttons/'+button['id']+'/intake',json=intake)).json(),result.json())
        invalid=saved.json();invalid['buttons'][0]['entry']['quantity']['value']=-1
        self.assertEqual((await self.client.put('/settings',json=invalid)).status_code,422)
        self.assertEqual((await self.client.get('/settings',headers={'Authorization':'bad'})).status_code,401)

    async def test_goals_persist_across_other_settings_and_restart(self):
        prefs=(await self.client.get('/settings')).json()
        prefs['goals']={'energy_kcal':2000,'protein_g':120,'carbohydrates_g':None,'fat_g':65}
        saved=(await self.client.put('/settings',json=prefs)).json()
        self.assertEqual(saved['goals'],prefs['goals'])
        saved['buttons'][0]['label']='Glass of water'
        updated=(await self.client.put('/settings',json=saved)).json()
        self.assertEqual(updated['goals'],prefs['goals'])
        await self.life.__aexit__(None,None,None)
        self.life=support.main.lifespan(support.main.app)
        await self.life.__aenter__()
        self.assertEqual((await self.client.get('/settings')).json()['goals'],prefs['goals'])

    async def test_image_upload_auth_and_delete(self):
        s=(await self.client.get('/settings')).json();id=s['buttons'][0]['id'];url='/quick-buttons/'+id+'/image'
        self.assertEqual((await self.client.put(url,content=b'invalid')).status_code,422)
        buf=io.BytesIO();Image.new('RGB',(40,40),'green').save(buf,'JPEG')
        self.assertEqual((await self.client.put(url,content=buf.getvalue())).status_code,200)
        response=await self.client.get(url)
        self.assertEqual(response.headers['content-type'],'image/png')
        self.assertTrue(response.content.startswith(b'\x89PNG'))
        self.assertEqual((await self.client.get(url,headers={'Authorization':'bad'})).status_code,401)
        self.assertTrue((await self.client.get('/settings')).json()['buttons'][0]['has_image'])
        await self.client.delete(url)
        self.assertEqual((await self.client.get(url)).status_code,404)

    async def test_summary_provisional_units_and_unknowns(self):
        e={'type':'item','status':'processed','source':{'provider':'BLS'},'quantity':{'value':200,'unit':'g'},'food':{'bls_code':'X','nutrients':{'dietaryVitaminB6':50,'dietaryVitaminC':'TR','dietarySelenium':None}},'nutrients':{'dietaryEnergyConsumed':{'value':100,'unit':'kcal'}}}
        s=home.summarize([e]);n={v['key']:v for v in s['nutrients']}
        self.assertAlmostEqual(n['dietaryVitaminB6']['values'][0]['value'],.0001)
        self.assertEqual(n['dietaryVitaminB6']['values'][0]['unit'],'g')
        self.assertEqual(n['dietaryVitaminC']['qualifiers'],['TR'])
        self.assertEqual(n['dietarySelenium']['values'],[])
        self.assertEqual(n['dietaryEnergyConsumed']['values'][0]['value'],100)
        missing={**e,'status':'needs_review'};n={v['key']:v for v in home.summarize([e,missing])['nutrients']}
        self.assertTrue(n['dietaryEnergyConsumed']['partial'])
        self.assertEqual(home.summarize([{'type':'drink','drink':'coffee','status':'processed','nutrients':{'dietaryCaffeine':{'value':.08,'unit':'g'}}}])['caffeine_mg'],80)

    async def test_contributor_amounts_match_totals_and_recipe_exclusion(self):
        entries=[
            {'id':'a','type':'manual','status':'processed','timestamp':'2026-10-12T08:00:00Z','quantity':{'value':100,'unit':'g'},'description':'Breakfast','nutrients':{'dietaryProtein':{'value':10,'unit':'g'},'dietaryCaffeine':{'value':.08,'unit':'g'}}},
            {'id':'b','type':'manual','status':'processed','timestamp':'2026-10-12T09:00:00Z','quantity':{'value':100,'unit':'g'},'description':'Snack','nutrients':{'dietaryProtein':{'value':500,'unit':'mg'}}},
            {'id':'water','type':'drink','drink':'water','status':'processed','timestamp':'2026-10-12T10:00:00Z','nutrients':{'dietaryWater':{'value':250,'unit':'ml'}}},
            {'id':'recipe','type':'recipe','status':'processed','timestamp':'2026-10-12T11:00:00Z','description':'Recipe meal','quantity':{'value':1,'unit':'portion'},'nutrients':{'dietaryProtein':{'value':3,'unit':'g'}},'drinking_water_ml':50,'ethanol_g':5},
            {'id':'pending','type':'item','status':'needs_review','timestamp':'2026-10-12T12:00:00Z','quantity':None,'nutrients':{}}]
        summary=home.summarize(entries)
        protein=next(r for r in summary['nutrients'] if r['key']=='dietaryProtein')
        self.assertEqual({r['id'] for r in protein['contributors']},{'a','b','recipe','pending'})
        actual=sum(v['value']*home.MASS[v['unit']] for r in protein['contributors'] for v in r['values'])
        self.assertEqual(actual,protein['values'][0]['value']);self.assertEqual(actual,13.5)
        self.assertEqual(next(r for r in protein['contributors'] if r['id']=='pending')['values'],[])
        self.assertEqual(sum(r['values'][0]['value'] for r in summary['contributors']['caffeine_mg']),summary['caffeine_mg'])
        self.assertEqual(sum(r['values'][0]['value'] for r in summary['contributors']['drinking_water_ml']),300)
        self.assertEqual(summary['contributors']['ethanol_g'][0]['id'],'recipe')
        await self.client.post('/entries',json=self.payload())
        recipe={'id':str(uuid4()),'name':'Recipe','servings':1}
        await self.client.post('/recipes',json=recipe)
        ingredient=self.payload(recipe_id=recipe['id']);await self.client.post('/entries',json=ingredient)
        result=(await self.client.get('/home-summary',params={'start':'2026-10-04T00:00:00+02:00','end':'2026-10-05T00:00:00+02:00'})).json()
        ids={r['id'] for r in result['contributors']['drinking_water_ml']}
        self.assertNotIn(ingredient['id'],ids);self.assertEqual(len(ids),1)

    async def test_bac_profile_and_midnight_history(self):
        now=datetime(2026,10,10,0,30,tzinfo=timezone.utc)
        profile={'mass_kg':80,'distribution':.68,'elimination_percent_per_hour':.015,'absorption_per_hour':3}
        e={'type':'drink','drink':'alcohol','status':'processed','timestamp':(now-timedelta(hours=1)).isoformat(),'ethanol_g':40}
        self.assertIsNone(home.current_bac([e],None,now)['percent'])
        result=home.current_bac([e],profile,now)
        import math
        self.assertAlmostEqual(result['percent'],.1*40/(80*.68)*(1-math.exp(-3))-.015)
        self.assertIsNone(home.current_bac([{**e,'status':'needs_review'}],profile,now)['percent'])
        self.assertEqual(home.current_bac([{**e,'timestamp':(now+timedelta(hours=1)).isoformat()}],profile,now)['percent'],0)

    async def test_summary_day_range_excludes_ingredients(self):
        await self.client.post('/entries',json=self.payload())
        result=await self.client.get('/home-summary',params={'start':'2026-10-04T00:00:00+02:00','end':'2026-10-05T00:00:00+02:00'})
        self.assertEqual(result.status_code,200)
        self.assertEqual(result.json()['drinking_water_ml'],250)
        self.assertEqual((await self.client.get('/home-summary',params={'start':'2026-10-04T00:00:00','end':'2026-10-05T00:00:00'})).status_code,422)
