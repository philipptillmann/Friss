import json
import unittest
from uuid import uuid4
import test_api as support
from app import main

class AmountDefaultsTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp=support.ApiTests.asyncSetUp
    asyncTearDown=support.ApiTests.asyncTearDown
    payload=support.ApiTests.payload

    async def test_search_and_direct_defaults_preserve_favorites(self):
        food={'bls_code':'BAR','name_de':'Schokoriegel','name_en':'Chocolate bar','nutrients':{'dietaryEnergyConsumed':500}}
        with main.db() as c:c.execute('INSERT INTO foods VALUES(?,?,?)',('BAR',json.dumps(food),'schokoriegel chocolate bar'))
        for amount in [20,35,None]:
            await self.client.post('/entries',json=self.payload(type='item',drink=None,bls_code='BAR',quantity={'value':amount,'unit':'g'} if amount else None))
        search=(await self.client.get('/search',params={'q':'Schoko','remote':'false'})).json()
        self.assertEqual(search['results'][0]['default_quantity'],{'value':35,'unit':'g'})
        self.assertEqual((await self.client.get('/food-amounts',params={'source':'bls','id':'BAR'})).json()['quantity']['value'],35)
        await self.client.post('/favorites',json={'id':str(uuid4()),'label':'Schokoriegel','entry':{'type':'item','bls_code':'BAR','quantity':{'value':15,'unit':'g'}},'version':0})
        search=(await self.client.get('/search',params={'q':'Schoko','remote':'false'})).json()
        self.assertEqual(search['results'][0]['default_quantity']['value'],15)
        self.assertEqual((await self.client.get('/food-amounts',params={'source':'bls','id':'missing'})).json(),{'quantity':None})
        self.assertEqual((await self.client.get('/food-amounts',params={'source':'bls','id':'BAR'},headers={'Authorization':'bad'})).status_code,401)

    async def test_manual_and_barcode_identity_and_recipe_ingredients(self):
        # Stored entries avoid any external product requests in this test.
        for spec in [{'type':'manual','manual_id':'own'},{'type':'barcode','barcode':'4001234567890'},{'type':'picture','bls_code':'BLS'}]:
            entry={**spec,'id':str(uuid4()),'quantity':{'value':42,'unit':'g'},'recipe_id':'recipe','timestamp':'2026-01-01T00:00:00Z'}
            with main.db() as c:c.execute('INSERT INTO entries VALUES(?,?,?)',(entry['id'],'test',json.dumps(entry)))
        for source,id in [('manual','own'),('off','4001234567890'),('bls','BLS')]:
            r=await self.client.get('/food-amounts',params={'source':source,'id':id});self.assertEqual(r.json()['quantity']['value'],42)
