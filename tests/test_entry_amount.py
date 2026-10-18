import json
import unittest
from uuid import uuid4
import test_api as support
import test_recipes as recipes_support
from app import main

class EntryAmountTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp=support.ApiTests.asyncSetUp
    asyncTearDown=support.ApiTests.asyncTearDown
    payload=support.ApiTests.payload
    setup_recipe=recipes_support.RecipeTests.setup_recipe

    async def change(self,id,value,unit,revision=1):
        return await self.client.patch('/entries/'+id+'/amount',json={'quantity':{'value':value,'unit':unit},'revision':revision})

    async def test_diary_and_ingredient_same_editor_frozen_snapshot(self):
        recipe,ingredient=await self.setup_recipe()
        intake=(await self.client.post('/recipes/'+recipe['id']+'/intake',json={'id':str(uuid4()),'timestamp':ingredient['timestamp'],'unit':'portion','amount':1})).json()
        original=(main.DATA/'originals'/(ingredient['id']+'.json')).read_text()
        # Updating the live database must not change nutrients of an existing food.
        with main.db() as c:
            row=json.loads(c.execute('SELECT payload FROM foods WHERE code=?',('RECIPE_TEST',)).fetchone()[0]);row['nutrients']['dietaryEnergyConsumed']=900
            c.execute('UPDATE foods SET payload=? WHERE code=?',(json.dumps(row),'RECIPE_TEST'))
        r=await self.change(ingredient['id'],150,'g');self.assertEqual(r.status_code,200,r.text)
        self.assertEqual(r.json()['nutrients']['dietaryEnergyConsumed']['value'],300)
        self.assertEqual((main.DATA/'originals'/(ingredient['id']+'.json')).read_text(),original)
        details=(await self.client.get('/recipes')).json()[0]
        self.assertEqual(details['nutrients']['dietaryEnergyConsumed']['value'],300)
        unchanged=main.load_entry(intake['id']);self.assertEqual(unchanged['nutrients']['dietaryEnergyConsumed']['value'],150)
        r=await self.change(intake['id'],2,'portion');self.assertEqual(r.status_code,200,r.text)
        self.assertEqual(r.json()['nutrients']['dietaryEnergyConsumed']['value'],300)
        self.assertEqual(r.json()['recipe_snapshot'],unchanged['recipe_snapshot'])
        self.assertEqual((await self.change(intake['id'],150,'g',2)).status_code,422)
        self.assertEqual((await self.change(intake['id'],3,'portion',1)).status_code,409)

    async def test_drink_amounts_and_export_changes(self):
        p=self.payload();e=(await self.client.post('/entries',json=p)).json()
        batch=(await self.client.post('/health-days/prepare',json={'day':'2026-10-04','timezone':'Europe/Berlin'})).json()
        await self.client.post('/health-days/'+batch['id']+'/ack',json={'export_token':batch['export_token'],'success':True})
        r=await self.change(e['id'],500,'ml');self.assertEqual(r.status_code,200,r.text)
        self.assertEqual(r.json()['nutrients']['dietaryWater']['value'],500)
        self.assertEqual(r.json()['health_status'],'synced')
        days=(await self.client.get('/health-days',params={'tz':'Europe/Berlin'})).json();self.assertTrue(days[0]['changed'])
        self.assertEqual((await self.client.get('/health-days/'+batch['id'])).json()['samples'],batch['samples'])
        self.assertEqual((await self.change(e['id'],500,'ml',2)).json()['revision'],2)
        e=main.load_entry(e['id']);e['health_status']='claimed';main.save_entry(e)
        self.assertEqual((await self.change(e['id'],750,'ml',2)).status_code,409)

    async def test_unknown_quantity_validation_and_auth(self):
        recipe,ingredient=await self.setup_recipe()
        p=self.payload(type='item',drink=None,bls_code='RECIPE_TEST',quantity=None)
        await self.client.post('/entries',json=p)
        r=await self.change(p['id'],50,'g');self.assertEqual(r.status_code,200,r.text)
        self.assertEqual(r.json()['nutrients']['dietaryEnergyConsumed']['value'],100)
        for value in [0,-1]:self.assertEqual((await self.change(p['id'],value,'g',2)).status_code,422)
        self.assertEqual((await self.client.patch('/entries/'+p['id']+'/amount',json={'quantity':{'value':10,'unit':'g'},'revision':2},headers={'Authorization':'bad'})).status_code,401)
        missing=self.payload(type='text',drink=None,description='Unresolved',quantity=None)
        await self.client.post('/entries',json=missing)
        self.assertEqual((await self.change(missing['id'],50,'g')).status_code,422)
        self.assertIsNone(main.load_entry(missing['id'])['quantity'])
