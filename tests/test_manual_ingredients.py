import json
import unittest
from uuid import uuid4
import test_api as support
from app import main

class ManualTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp=support.ApiTests.asyncSetUp
    asyncTearDown=support.ApiTests.asyncTearDown
    payload=support.ApiTests.payload

    def ingredient(self):
        return {'id':str(uuid4()),'name_de':'Meine Milch','name_en':'My milk','notes':'Label values','version':0,'nutrients':{'dietaryEnergyConsumed':{'value':60,'unit':'kcal'},'dietaryProtein':{'value':3,'unit':'g'},'dietaryFatTotal':{'value':0,'unit':'g'},'dietaryCaffeine':{'value':10,'unit':'mg'}},'ethanol_g_per100':2}

    async def test_meal_recipe_scaling_and_immutable_logged_values(self):
        ingredient=self.ingredient()
        self.assertEqual((await self.client.post('/manual-ingredients',json=ingredient)).status_code,201)
        p=self.payload(type='manual',drink=None,manual_id=ingredient['id'],quantity={'value':150,'unit':'g'})
        meal=(await self.client.post('/entries',json=p)).json()
        self.assertEqual(meal['status'],'processed')
        self.assertEqual(meal['nutrients']['dietaryEnergyConsumed']['value'],90)
        self.assertEqual(meal['nutrients']['dietaryFatTotal']['value'],0)
        self.assertNotIn('dietaryCarbohydrates',meal['nutrients'])
        self.assertEqual(meal['ethanol_g'],3)
        recipe={'id':str(uuid4()),'name':'Milk recipe','servings':2,'finished_weight_g':200}
        await self.client.post('/recipes',json=recipe)
        component=self.payload(type='manual',drink=None,manual_id=ingredient['id'],recipe_id=recipe['id'],quantity={'value':200,'unit':'g'})
        await self.client.post('/entries',json=component)
        intake={'id':str(uuid4()),'timestamp':p['timestamp'],'unit':'portion','amount':1}
        logged=(await self.client.post('/recipes/'+recipe['id']+'/intake',json=intake)).json()
        self.assertEqual(logged['nutrients']['dietaryEnergyConsumed']['value'],60)
        self.assertEqual(logged['ethanol_g'],2)
        changed={**ingredient,'nutrients':{**ingredient['nutrients'],'dietaryEnergyConsumed':{'value':100,'unit':'kcal'}}}
        self.assertEqual((await self.client.put('/manual-ingredients/'+ingredient['id'],json=changed)).status_code,200)
        self.assertEqual((await self.client.get('/entries/'+p['id'])).json(),meal)
        self.assertEqual((await self.client.get('/recipes/'+recipe['id'])).json()['nutrients']['dietaryEnergyConsumed']['value'],120)
        future=self.payload(type='manual',drink=None,manual_id=ingredient['id'],quantity={'value':100,'unit':'g'})
        self.assertEqual((await self.client.post('/entries',json=future)).json()['nutrients']['dietaryEnergyConsumed']['value'],100)

    async def test_resume_snapshot_after_edit_delete_and_reuse(self):
        ingredient=self.ingredient()
        await self.client.post('/manual-ingredients',json=ingredient)
        p=self.payload(type='manual',drink=None,manual_id=ingredient['id'],quantity=None)
        entry=(await self.client.post('/entries',json=p)).json()
        self.assertEqual(entry['status'],'needs_review')
        recent=(await self.client.get('/recent-ingredients')).json()[0]
        self.assertEqual(recent['entry']['manual_id'],ingredient['id'])
        favorite={'id':str(uuid4()),'label':'My milk','version':0,'entry':recent['entry']}
        self.assertEqual((await self.client.post('/favorites',json=favorite)).status_code,201)
        self.assertEqual((await self.client.delete('/manual-ingredients/'+ingredient['id'],params={'version':0})).status_code,200)
        resolved=(await self.client.post('/entries/'+p['id']+'/resolve',json={'quantity':{'value':100,'unit':'g'}})).json()
        self.assertEqual(resolved['nutrients']['dietaryEnergyConsumed']['value'],60)
        self.assertEqual((await self.client.post('/entries',json=self.payload(type='manual',drink=None,manual_id=ingredient['id']))).status_code,404)

    async def test_validation_health_auth_and_persistence(self):
        ingredient=self.ingredient()
        self.assertEqual((await self.client.get('/manual-ingredients',headers={'Authorization':'bad'})).status_code,401)
        for nutrients in [{},{'dietaryProtein':{'value':3,'unit':'kcal'}},{'unsupported':{'value':1,'unit':'g'}},{'dietaryProtein':{'value':-1,'unit':'g'}}]:
            invalid={**ingredient,'nutrients':nutrients,'ethanol_g_per100':None}
            self.assertEqual((await self.client.post('/manual-ingredients',json=invalid)).status_code,422)
        await self.client.post('/manual-ingredients',json=ingredient)
        self.assertEqual((await self.client.post('/manual-ingredients',json=ingredient)).status_code,201)
        p=self.payload(type='manual',drink=None,manual_id=ingredient['id'],quantity={'value':100,'unit':'g'})
        await self.client.post('/entries',json=p)
        prepared=await self.client.post('/health-days/prepare',json={'day':'2026-10-04','timezone':'Europe/Berlin'})
        self.assertEqual(prepared.status_code,200)
        self.assertTrue(any(s['identifier']=='dietaryEnergyConsumed' for s in prepared.json()['samples']))
        await self.life.__aexit__(None,None,None)
        self.life=main.lifespan(main.app);await self.life.__aenter__()
        self.assertEqual((await self.client.get('/manual-ingredients')).json()[0]['id'],ingredient['id'])
