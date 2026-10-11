import json
import unittest
from uuid import uuid4
import test_api as support
from app import main

class FavoriteTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp=support.ApiTests.asyncSetUp
    asyncTearDown=support.ApiTests.asyncTearDown
    payload=support.ApiTests.payload

    def food(self):
        food={'bls_code':'FAV','name_de':'Milch','name_en':'Milk','nutrients':{'dietaryEnergyConsumed':60,'dietaryProtein':3}}
        with main.db() as c:
            c.execute('INSERT OR IGNORE INTO foods VALUES(?,?,?)',('FAV',json.dumps(food),'milch milk'))

    async def test_recent_recipe_and_daily_dedup_order(self):
        self.food()
        recipe={'id':str(uuid4()),'name':'Milk recipe','servings':1}
        await self.client.post('/recipes',json=recipe)
        first=self.payload(type='item',drink=None,bls_code='FAV',quantity={'value':100,'unit':'g'})
        await self.client.post('/entries',json=first)
        second=self.payload(type='item',drink=None,bls_code='FAV',quantity={'value':90,'unit':'g'},recipe_id=recipe['id'])
        await self.client.post('/entries',json=second)
        photo=self.payload(type='picture',drink=None,quantity=None)
        await self.client.post('/entries',json=photo)
        await self.client.post('/entries',json=self.payload(drink='coffee',caffeine_mg=80))
        recent=(await self.client.get('/recent-ingredients')).json()
        self.assertEqual(len(recent),2)
        self.assertEqual(recent[0]['entry']['drink'],'coffee')
        milk=recent[1]
        self.assertEqual(milk['last_location'],'recipe')
        self.assertEqual(milk['entry']['quantity'],{'value':90,'unit':'g'})
        self.assertEqual(milk['name_en'],'Milk')
        self.assertNotIn('health_status',milk['entry'])
        self.assertNotIn('recipe_id',milk['entry'])
        self.assertEqual(len((await self.client.get('/recent-ingredients',params={'limit':1})).json()),1)
        # Resolved photos become reusable foods, not a photo-upload requirement.
        await self.client.post('/entries/'+photo['id']+'/resolve',json={'bls_code':'FAV','quantity':{'value':120,'unit':'g'}})
        recent=(await self.client.get('/recent-ingredients')).json()
        self.assertEqual(recent[1]['entry']['type'],'item')
        self.assertEqual(recent[1]['entry']['quantity']['value'],120)

    async def test_favorite_crud_reuse_and_existing_entry_preserved(self):
        self.food()
        body={'id':str(uuid4()),'label':'My milk','version':0,'entry':{'type':'item','bls_code':'FAV','quantity':{'value':150,'unit':'g'}}}
        favorite=(await self.client.post('/favorites',json=body)).json()
        self.assertEqual(favorite['label'],'My milk')
        self.assertEqual((await self.client.post('/favorites',json=body)).json(),favorite)
        self.assertEqual((await self.client.get('/entries')).json(),[])
        consume=self.payload(**favorite['entry'],capture_method='favorite')
        logged=(await self.client.post('/entries',json=consume)).json()
        self.assertEqual(logged['nutrients']['dietaryEnergyConsumed']['value'],90)
        self.assertEqual(logged['health_status'],'pending')
        self.assertEqual((await self.client.get('/entries/'+consume['id']+'/details')).json()['capture_method'],'favorite')
        edit={**favorite,'label':'Milk revised','entry':{**favorite['entry'],'quantity':{'value':200,'unit':'g'}}}
        updated=(await self.client.put('/favorites/'+favorite['id'],json=edit)).json()
        self.assertEqual(updated['version'],1)
        self.assertEqual((await self.client.put('/favorites/'+favorite['id'],json=edit)).status_code,409)
        self.assertEqual((await self.client.delete('/favorites/'+favorite['id'],params={'version':0})).status_code,409)
        self.assertEqual((await self.client.get('/entries/'+consume['id'])).json(),logged)
        self.assertEqual((await self.client.delete('/favorites/'+favorite['id'],params={'version':1})).status_code,200)
        self.assertEqual((await self.client.get('/favorites')).json(),[])
        self.assertEqual((await self.client.get('/entries/'+consume['id'])).json(),logged)

    async def test_validation_auth_and_persistence(self):
        for path in ['/favorites','/recent-ingredients']:
            self.assertEqual((await self.client.get(path,headers={'Authorization':'bad'})).status_code,401)
        template={'id':str(uuid4()),'label':'Water','version':0,'entry':{'type':'drink','drink':'water','quantity':{'value':250,'unit':'ml'}}}
        self.assertEqual((await self.client.post('/favorites',json=template,headers={'Authorization':'bad'})).status_code,401)
        self.assertEqual((await self.client.post('/favorites',json={**template,'entry':{'type':'item','bls_code':'missing'}})).status_code,422)
        self.assertEqual((await self.client.post('/favorites',json={**template,'entry':{'type':'drink','drink':'coffee','quantity':{'value':200,'unit':'ml'}}})).status_code,422)
        self.assertEqual((await self.client.post('/favorites',json={**template,'label':'   '})).status_code,422)
        self.assertEqual((await self.client.post('/favorites',json=template)).status_code,201)
        await self.life.__aexit__(None,None,None)
        self.life=main.lifespan(main.app)
        await self.life.__aenter__()
        self.assertEqual((await self.client.get('/favorites')).json()[0]['label'],'Water')
