import json
import unittest
from unittest.mock import patch
from uuid import uuid4
import httpx
import test_api as support
from app import main

class ResumeTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp=support.ApiTests.asyncSetUp
    asyncTearDown=support.ApiTests.asyncTearDown
    payload=support.ApiTests.payload

    async def test_known_bls_quantity_only_preserves_recipe_and_original(self):
        food={'bls_code':'RESUME','name_de':'Milch','name_en':'Milk','nutrients':{'dietaryEnergyConsumed':60,'dietaryProtein':3}}
        with main.db() as c:c.execute('INSERT INTO foods VALUES(?,?,?)',('RESUME',json.dumps(food),'milch milk'))
        recipe={'id':str(uuid4()),'name':'Cappuccino','servings':1}
        await self.client.post('/recipes',json=recipe)
        p=self.payload(type='item',drink=None,bls_code='RESUME',quantity=None,recipe_id=recipe['id'])
        entry=(await self.client.post('/entries',json=p)).json()
        self.assertEqual(entry['status'],'needs_review')
        raw=(main.DATA/'originals'/f"{p['id']}.json").read_text()
        updated=(await self.client.post('/entries/'+p['id']+'/resolve',json={'quantity':{'value':90,'unit':'g'}})).json()
        self.assertEqual(updated['status'],'processed')
        self.assertEqual(updated['bls_code'],'RESUME')
        self.assertEqual(updated['recipe_id'],recipe['id'])
        self.assertEqual(updated['timestamp'],entry['timestamp'])
        self.assertEqual(updated['nutrients']['dietaryEnergyConsumed']['value'],54)
        self.assertEqual((main.DATA/'originals'/f"{p['id']}.json").read_text(),raw)

    async def test_barcode_missing_quantity_uses_saved_product(self):
        code='4006381333931'
        upstream=httpx.AsyncClient(transport=httpx.MockTransport(lambda r:httpx.Response(200,json={'status':1,'product':{'product_name':'Known product','nutriments':{'energy-kcal_100g':200}}})))
        p=self.payload(type='barcode',drink=None,barcode=code,quantity=None)
        with patch('app.main.httpx.AsyncClient',return_value=upstream):
            entry=(await self.client.post('/entries',json=p)).json()
        self.assertEqual(entry['food']['product_name'],'Known product')
        with patch('app.main.httpx.AsyncClient',side_effect=AssertionError('Must reuse stored product')):
            result=await self.client.post('/entries/'+p['id']+'/resolve',json={'quantity':{'value':150,'unit':'g'},'barcode':code,'timestamp':entry['timestamp']})
        self.assertEqual(result.status_code,200)
        self.assertEqual(result.json()['nutrients']['dietaryEnergyConsumed']['value'],300)
        self.assertEqual(result.json()['type'],'barcode')

    async def test_drink_metadata_and_timestamp_validation(self):
        p=self.payload(drink='coffee',caffeine_mg=None)
        entry=(await self.client.post('/entries',json=p)).json()
        url='/entries/'+p['id']+'/resolve'
        self.assertEqual((await self.client.post(url,json={'quantity':{'value':200,'unit':'ml'},'timestamp':'2026-10-04T15:31:00'})).status_code,422)
        result=await self.client.post(url,json={'quantity':{'value':200,'unit':'ml'},'caffeine_mg':80,'timestamp':entry['timestamp']})
        self.assertEqual(result.json()['nutrients']['dietaryCaffeine']['value'],80)
        self.assertEqual(result.json()['timestamp'],entry['timestamp'])
        self.assertEqual((await self.client.get('/')).status_code,200)
        self.assertNotIn("Menge (g, optional)",(await self.client.get('/')).text)
