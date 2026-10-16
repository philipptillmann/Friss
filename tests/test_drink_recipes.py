import json
import unittest
from uuid import uuid4
import test_api as support
from app import main,home

class DrinkRecipeTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp=support.ApiTests.asyncSetUp
    asyncTearDown=support.ApiTests.asyncTearDown
    payload=support.ApiTests.payload

    async def make(self):
        r={'id':str(uuid4()),'name':'Spritz','category':'drink','servings':2,'finished_volume_ml':400,'finished_weight_g':450,'alcohol_abv':10,'notes':'Instructions'}
        self.assertEqual((await self.client.post('/recipes',json=r)).status_code,201)
        ingredient=self.payload(type='drink',drink='water',recipe_id=r['id'],quantity={'value':200,'unit':'ml'})
        await self.client.post('/entries',json=ingredient)
        return r,ingredient

    async def intake(self,r,amount=1,unit='portion'):
        body={'id':str(uuid4()),'timestamp':'2026-10-16T18:00:00+02:00','amount':amount,'unit':unit}
        response=await self.client.post('/recipes/'+r['id']+'/intake',json=body)
        self.assertEqual(response.status_code,201)
        return response.json()

    async def test_drink_volume_abv_quick_button_and_migration_keep_identity(self):
        r,i=await self.make()
        entry=await self.intake(r,100,'ml')
        self.assertAlmostEqual(entry['ethanol_g'],7.89)
        self.assertEqual(entry['drinking_water_ml'],50)
        self.assertAlmostEqual(home.nutrient_values(entry)['dietaryWater']['value'],50)
        settings=(await self.client.get('/settings')).json()
        settings['buttons']=[{'id':str(uuid4()),'label':'Spritz','entry':{'type':'recipe','recipe_id':r['id'],'quantity':{'value':100,'unit':'ml'}}}]
        self.assertEqual((await self.client.put('/settings',json=settings)).status_code,200)
        button=settings['buttons'][0]
        logged=await self.client.post('/quick-buttons/'+button['id']+'/intake',json={'id':str(uuid4()),'timestamp':'2026-10-16T18:00:00+02:00'})
        self.assertEqual(logged.status_code,200);self.assertAlmostEqual(logged.json()['ethanol_g'],7.89)
        food={'id':str(uuid4()),'name':'Cappuccino','servings':1}
        await self.client.post('/recipes',json=food)
        ingredient=self.payload(recipe_id=food['id']);await self.client.post('/entries',json=ingredient)
        moved=await self.client.patch('/recipes/'+food['id']+'/category',json={'category':'drink'})
        self.assertEqual(moved.status_code,200)
        self.assertEqual(moved.json()['id'],food['id']);self.assertEqual(moved.json()['category'],'drink')
        self.assertEqual(moved.json()['ingredients'][0]['id'],ingredient['id'])
        self.assertEqual((await self.client.get('/entries/'+entry['id'])).json()['recipe_snapshot']['alcohol_abv'],10)

    async def test_future_only_and_amendment_preserve_amount_time_health_and_audit(self):
        r,i=await self.make()
        portion=await self.intake(r)
        volume=await self.intake(r,100,'ml')
        volume.update(health_status='synced',export_token='retained');main.save_entry(volume)
        original=(main.DATA/'originals'/f"{portion['id']}.json").read_text()
        edit={k:v for k,v in r.items() if k!='id'};edit['alcohol_abv']=20
        future=await self.client.put('/recipes/'+r['id'],json=edit)
        self.assertEqual(future.json()['amended_entries'],0)
        self.assertAlmostEqual(main.load_entry(portion['id'])['ethanol_g'],15.78)
        amended=await self.client.put('/recipes/'+r['id'],json={**edit,'amend_existing':True})
        self.assertEqual(amended.status_code,200);self.assertEqual(amended.json()['amended_entries'],2)
        for old,factor in [(portion,.5),(volume,.25)]:
            e=main.load_entry(old['id'])
            self.assertEqual(e['quantity'],old['quantity']);self.assertEqual(e['timestamp'],old['timestamp'])
            self.assertAlmostEqual(e['ethanol_g'],400*.2*.789*factor)
            self.assertEqual(e['health_status'],old['health_status'])
            self.assertTrue((main.DATA/'originals'/f"{old['id']}-revision-1.json").exists())
        self.assertEqual(main.load_entry(volume['id'])['export_token'],'retained')
        self.assertEqual((main.DATA/'originals'/f"{portion['id']}.json").read_text(),original)
        self.assertEqual((await self.client.put('/recipes/'+r['id'],json={**edit,'amend_existing':True})).json()['amended_entries'],0)

    async def test_amendment_failure_rolls_back_recipe_and_all_entries(self):
        r,i=await self.make()
        portion=await self.intake(r);weight=await self.intake(r,100,'g')
        edit={k:v for k,v in r.items() if k!='id'};edit.update(alcohol_abv=30,finished_weight_g=None,amend_existing=True)
        response=await self.client.put('/recipes/'+r['id'],json=edit)
        self.assertEqual(response.status_code,422)
        self.assertEqual(main.load_recipe(r['id'])['alcohol_abv'],10)
        self.assertEqual(main.load_entry(portion['id'])['ethanol_g'],portion['ethanol_g'])
        self.assertEqual(main.load_entry(weight['id'])['ethanol_g'],weight['ethanol_g'])

    async def test_food_recipe_correction_and_invalid_drink_parameters(self):
        r={'id':str(uuid4()),'name':'Milk','servings':1}
        await self.client.post('/recipes',json=r)
        ingredient=self.payload(type='drink',drink='water',recipe_id=r['id'],quantity={'value':100,'unit':'ml'})
        await self.client.post('/entries',json=ingredient)
        e=await self.intake(r)
        await self.client.post('/entries/'+ingredient['id']+'/resolve',json={'quantity':{'value':200,'unit':'ml'}})
        result=await self.client.put('/recipes/'+r['id'],json={'name':'Milk corrected','servings':1,'amend_existing':True})
        self.assertEqual(result.json()['amended_entries'],1)
        self.assertEqual(main.load_entry(e['id'])['drinking_water_ml'],200)
        for bad in [{'category':'drink','alcohol_abv':5},{'category':'food','finished_volume_ml':500,'alcohol_abv':5},{'category':'drink','finished_volume_ml':500,'alcohol_abv':5,'added_ethanol_g':10}]:
            body={'id':str(uuid4()),'name':'Invalid','servings':1,**bad}
            self.assertEqual((await self.client.post('/recipes',json=body)).status_code,422)

    async def test_health_batch_is_marked_changed_and_removed_alcohol_cleared(self):
        r,i=await self.make();entry=await self.intake(r)
        batch=await self.client.post('/health-days/prepare',json={'day':'2026-10-16','timezone':'Europe/Berlin'})
        self.assertEqual(batch.status_code,200)
        edit={k:v for k,v in r.items() if k!='id'};edit.update(alcohol_abv=0,amend_existing=True)
        result=await self.client.put('/recipes/'+r['id'],json=edit)
        self.assertEqual(result.status_code,200)
        self.assertNotIn('ethanol_g',main.load_entry(entry['id']))
        self.assertEqual(main.load_entry(entry['id'])['health_status'],'claimed')
        days=(await self.client.get('/health-days',params={'tz':'Europe/Berlin'})).json()
        self.assertTrue(days[0]['changed'])
        original=(await self.client.get('/health-days/'+batch.json()['id'])).json()
        self.assertEqual(original['samples'],batch.json()['samples'])
