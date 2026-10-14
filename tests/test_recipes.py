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
        self.assertEqual((await self.client.post('/health-export/'+e['id']+'/claim')).status_code,200)

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

    async def test_additional_amounts_recipe_button_scaling_and_snapshot(self):
        r,i=await self.setup_recipe()
        edit={'name':'Cappuccino batch','servings':4,'finished_weight_g':600,'added_water_ml':200,'added_caffeine_mg':160,'added_ethanol_g':20}
        response=await self.client.put('/recipes/'+r['id'],json=edit)
        self.assertEqual(response.status_code,200)
        settings=(await self.client.get('/settings')).json()
        button={'id':str(uuid4()),'label':'Cappuccino','entry':{'type':'recipe','recipe_id':r['id'],'quantity':{'value':1,'unit':'portion'}}}
        settings['buttons']=[button]
        self.assertEqual((await self.client.put('/settings',json=settings)).status_code,200)
        intake={'id':str(uuid4()),'timestamp':'2026-10-10T12:00:00+02:00'}
        url='/quick-buttons/'+button['id']+'/intake'
        e=(await self.client.post(url,json=intake)).json()
        self.assertEqual(e['type'],'recipe')
        self.assertEqual(e['nutrients']['dietaryEnergyConsumed']['value'],150)
        self.assertEqual(e['nutrients']['dietaryCaffeine'],{'value':40,'unit':'mg'})
        self.assertEqual(e['nutrients']['dietaryWater'],{'value':50,'unit':'ml'})
        self.assertEqual(e['ethanol_g'],5)
        self.assertEqual(e['drinking_water_ml'],50)
        for unit,amount in [('g',150),('fraction',.25)]:
            body={'id':str(uuid4()),'timestamp':intake['timestamp'],'unit':unit,'amount':amount}
            scaled=(await self.client.post('/recipes/'+r['id']+'/intake',json=body)).json()
            self.assertEqual(scaled['nutrients']['dietaryCaffeine']['value'],40)
            self.assertEqual(scaled['ethanol_g'],5)
        await self.client.put('/recipes/'+r['id'],json={**edit,'added_caffeine_mg':320})
        self.assertEqual((await self.client.post(url,json=intake)).json(),e)
        self.assertEqual(e['recipe_snapshot']['added_caffeine_mg'],160)
        from app.home import summarize
        totals=summarize([e])
        self.assertEqual(totals['caffeine_mg'],40)
        self.assertEqual(totals['drinking_water_ml'],50)
        self.assertEqual(totals['ethanol_g'],5)
        settings=(await self.client.get('/settings')).json()
        settings['buttons'][0]['entry']['quantity']={'value':.25,'unit':'fraction'}
        self.assertEqual((await self.client.put('/settings',json=settings)).status_code,200)

    async def test_recipe_button_validation_and_addition_only_recipe(self):
        r={'id':str(uuid4()),'name':'Water and caffeine','servings':2,'added_water_ml':500,'added_caffeine_mg':100}
        self.assertEqual((await self.client.post('/recipes',json=r)).json()['status'],'ready')
        settings=(await self.client.get('/settings')).json()
        button={'id':str(uuid4()),'label':'Recipe','entry':{'type':'recipe','recipe_id':r['id'],'quantity':{'value':100,'unit':'g'}}}
        settings['buttons']=[button]
        self.assertEqual((await self.client.put('/settings',json=settings)).status_code,422)
        button['entry']['quantity']={'value':2,'unit':'fraction'}
        self.assertEqual((await self.client.put('/settings',json=settings)).status_code,422)
        button['entry']['quantity']={'value':1,'unit':'portion'}
        self.assertEqual((await self.client.put('/settings',json=settings)).status_code,200)
        response=await self.client.post('/quick-buttons/'+button['id']+'/intake',json={'id':str(uuid4()),'timestamp':'2026-10-10T12:00:00+02:00'})
        self.assertEqual(response.json()['nutrients']['dietaryWater']['value'],250)
        self.assertEqual(response.json()['nutrients']['dietaryCaffeine']['value'],50)
        self.assertEqual((await self.client.post('/recipes',json={**r,'id':str(uuid4()),'added_ethanol_g':-1})).status_code,422)

    async def test_duplicate_recipe_independent_ingredients_and_retry(self):
        from app import main
        r,i=await self.setup_recipe()
        edit={k:r[k] for k in ('name','servings','finished_weight_g')}
        edit.update(notes='Original notes',added_water_ml=100,added_caffeine_mg=50,added_ethanol_g=5)
        await self.client.put('/recipes/'+r['id'],json=edit)
        body={'id':str(uuid4()),'name':'New variation'}
        path='/recipes/'+r['id']+'/duplicate'
        response=await self.client.post(path,json=body);self.assertEqual(response.status_code,201)
        copy=response.json();ingredient=copy['ingredients'][0]
        self.assertEqual(copy['notes'],'Original notes');self.assertEqual(copy['added_water_ml'],100)
        self.assertEqual(copy['added_caffeine_mg'],50);self.assertEqual(copy['added_ethanol_g'],5)
        self.assertEqual(copy['finished_weight_g'],600);self.assertEqual(copy['servings'],4)
        self.assertNotEqual(ingredient['id'],i['id']);self.assertEqual(ingredient['recipe_id'],copy['id'])
        self.assertEqual(ingredient['nutrients'],main.load_entry(i['id'])['nutrients'])
        self.assertEqual((await self.client.get('/entries')).json(),[])
        self.assertTrue((main.DATA/'originals'/f"{ingredient['id']}.json").exists())
        await self.client.put('/recipes/'+copy['id'],json={**edit,'name':'Renamed copy'})
        await self.client.delete('/entries/'+ingredient['id'])
        retried=await self.client.post(path,json=body)
        self.assertEqual(retried.status_code,201);self.assertEqual(retried.json()['ingredients'],[])
        self.assertEqual(retried.json()['name'],'Renamed copy')
        original=(await self.client.get('/recipes/'+r['id'])).json()
        self.assertEqual(len(original['ingredients']),1);self.assertEqual(original['name'],r['name'])
        self.assertEqual((await self.client.post(path,json={**body,'name':'Other'})).status_code,409)

    async def test_duplicate_recipe_auth_and_unknown_source(self):
        path='/recipes/'+str(uuid4())+'/duplicate'
        body={'id':str(uuid4()),'name':'Copy'}
        self.assertEqual((await self.client.post(path,json=body,headers={'Authorization':'bad'})).status_code,401)
        self.assertEqual((await self.client.post(path,json=body)).status_code,404)
        self.assertEqual((await self.client.post(path,json={**body,'name':''})).status_code,422)
