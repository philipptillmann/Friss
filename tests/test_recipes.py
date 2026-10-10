import json
from uuid import uuid4
import unittest
import test_api as support

class RecipeTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = support.ApiTests.asyncSetUp
    asyncTearDown = support.ApiTests.asyncTearDown
    payload = support.ApiTests.payload
    async def setup_recipe(self,weight=600):
        food={'bls_code':'RECIPE_TEST','name_de':'Zutat','name_en':'Ingredient','nutrients':{'dietaryEnergyConsumed':200,'dietaryProtein':10}}
        with __import__('app.main',fromlist=['db']).db() as c:
            c.execute('INSERT OR IGNORE INTO foods VALUES(?,?,?)',('RECIPE_TEST',json.dumps(food),'zutat ingredient'))
        recipe={'id':str(uuid4()),'name':'Test meal','servings':4,'finished_weight_g':weight}
        response=await self.client.post('/recipes',json=recipe)
        self.assertEqual(response.status_code,201)
        ingredient={'id':str(uuid4()),'type':'item','bls_code':'RECIPE_TEST','recipe_id':recipe['id'],'quantity':{'value':300,'unit':'g'},'timestamp':'2026-10-10T12:00:00+02:00'}
        self.assertEqual((await self.client.post('/entries',json=ingredient)).status_code,201)
        return recipe,ingredient

    async def test_recipe_portions_grams_snapshot_and_idempotency(self):
        r,i=await self.setup_recipe()
        self.assertEqual((await self.client.get('/entries')).json(),[])
        self.assertEqual((await self.client.get('/health-export/pending')).json(),[])
        self.assertEqual((await self.client.post('/health-export/'+i['id']+'/claim')).status_code,409)
        body={'id':str(uuid4()),'timestamp':'2026-10-10T12:00:00+02:00','unit':'portion','amount':1}
        url='/recipes/'+r['id']+'/intake'
        e=(await self.client.post(url,json=body)).json()
        self.assertEqual(e['nutrients']['dietaryEnergyConsumed']['value'],150)
        self.assertEqual((await self.client.post(url,json=body)).json(),e)
        body['amount']=2
        self.assertEqual((await self.client.post(url,json=body)).status_code,409)
        for unit,amount in [('g',150),('fraction',.25)]:
            body.update(id=str(uuid4()),unit=unit,amount=amount)
            result=(await self.client.post(url,json=body)).json()
            self.assertEqual(result['nutrients']['dietaryEnergyConsumed']['value'],150)
        await self.client.put('/recipes/'+r['id'],json={'name':'Changed','servings':2,'finished_weight_g':400})
        old=(await self.client.get('/entries/'+e['id'])).json()
        self.assertEqual(old['recipe_snapshot']['name'],'Test meal')
        self.assertEqual(old['nutrients']['dietaryEnergyConsumed']['value'],150)
        self.assertEqual((await self.client.post('/health-export/'+e['id']+'/claim')).status_code,409)

    async def test_unresolved_and_finished_weight_required(self):
        r,i=await self.setup_recipe(weight=None)
        body={'id':str(uuid4()),'timestamp':'2026-10-10T12:00:00+02:00','unit':'g','amount':100}
        url='/recipes/'+r['id']+'/intake'
        self.assertEqual((await self.client.post(url,json=body)).status_code,422)
        unresolved={'id':str(uuid4()),'type':'picture','timestamp':body['timestamp'],'recipe_id':r['id']}
        self.assertEqual((await self.client.post('/entries',json=unresolved)).status_code,201)
        body['unit']='portion'
        self.assertEqual((await self.client.post(url,json=body)).status_code,409)
        await self.client.post('/entries/'+unresolved['id']+'/resolve',json={'bls_code':'RECIPE_TEST','quantity':{'value':50,'unit':'g'}})
        body['amount']=1
        self.assertEqual((await self.client.post(url,json=body)).status_code,201)

    async def test_recipe_auth_and_validation(self):
        self.assertEqual((await self.client.get('/recipes',headers={'Authorization':'bad'})).status_code,401)
        self.assertEqual((await self.client.post('/recipes',json={'id':str(uuid4()),'name':'X','servings':0})).status_code,422)
        p=self.payload(recipe_id=str(uuid4()))
        self.assertEqual((await self.client.post('/entries',json=p)).status_code,404)
