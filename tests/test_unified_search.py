import json
import unittest
from uuid import uuid4
from unittest.mock import AsyncMock,patch
import test_api as support
from app import main,off_search

class UnifiedSearchTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp=support.ApiTests.asyncSetUp
    asyncTearDown=support.ApiTests.asyncTearDown
    payload=support.ApiTests.payload

    async def setup_foods(self):
        f={'bls_code':'SUGAR','name_de':'Haushaltszucker raffiniert','name_en':'Refined sugar','nutrients':{'dietaryEnergyConsumed':400}}
        with main.db() as c:c.execute('INSERT INTO foods VALUES(?,?,?)',(f['bls_code'],json.dumps(f),'haushaltszucker raffiniert refined sugar'))
        own={'id':str(uuid4()),'name_de':'Zucker selbst','name_en':'Own sugar','version':0,'nutrients':{'dietaryEnergyConsumed':{'value':390,'unit':'kcal'}}}
        await self.client.post('/manual-ingredients',json=own)
        r={'id':str(uuid4()),'name':'Zucker Mischung','servings':2}
        await self.client.post('/recipes',json=r)
        fav={'id':str(uuid4()),'label':'Mein Zucker','entry':{'type':'item','bls_code':'SUGAR','quantity':{'value':10,'unit':'g'}},'version':0}
        self.assertEqual((await self.client.post('/favorites',json=fav)).status_code,201)
        return own,r

    async def test_sources_favorite_learning_and_query_binding(self):
        own,r=await self.setup_foods()
        with patch.object(off_search,'search',AsyncMock(return_value=[{'barcode':'4001234567890','display_name':'Zucker Produkt','brand':'Marke','package_quantity':'1 kg'}])):
            response=await self.client.get('/search',params={'q':'Zucker'})
        self.assertEqual(response.status_code,200);results=response.json()['results']
        self.assertEqual({r['source'] for r in results},{'bls','manual','recipe','off'})
        bls=next(x for x in results if x['source']=='bls');self.assertTrue(bls['favorite'])
        self.assertEqual(bls['default_quantity'],{'value':10,'unit':'g'})
        chosen=next(x for x in results if x['source']=='manual')
        body={'id':str(uuid4()),'query':'Zucker','lang':'de','token':chosen['selection_token']}
        self.assertEqual((await self.client.post('/search/selections',json=body)).status_code,200)
        self.assertEqual((await self.client.post('/search/selections',json=body)).status_code,200)
        again=(await self.client.get('/search',params={'q':'Zucker','remote':'false'})).json()['results']
        self.assertEqual(again[0]['source'],'manual')
        self.assertEqual((await self.client.post('/search/selections',json={**body,'id':str(uuid4()),'query':'Milk'})).status_code,422)
        self.assertEqual((await self.client.post('/search/selections',json={**body,'id':str(uuid4()),'token':'forged'})).status_code,422)
        no_recipes=(await self.client.get('/search',params={'q':'Zucker','remote':'false','include_recipes':'false'})).json()['results']
        self.assertNotIn('recipe',{x['source'] for x in no_recipes})
        self.assertEqual((await self.client.get('/search',params={'q':'Zucker'},headers={'Authorization':'bad'})).status_code,401)

    async def test_off_choices_stay_available_and_remote_failure_keeps_local_results(self):
        await self.setup_foods()
        with patch.object(off_search,'search',AsyncMock(return_value=[{'barcode':'4001234567890','display_name':'Zucker Produkt','brand':'Marke','package_quantity':'1 kg'}])):
            result=(await self.client.get('/search',params={'q':'Zucker'})).json()
        product=next(x for x in result['results'] if x['source']=='off')
        await self.client.post('/search/selections',json={'id':str(uuid4()),'query':'Zucker','token':product['selection_token']})
        local=(await self.client.get('/search',params={'q':'Zucker','remote':'false'})).json()
        self.assertEqual(local['results'][0]['id'],product['id'])
        from fastapi import HTTPException
        with patch.object(off_search,'search',AsyncMock(side_effect=HTTPException(502,'Offline'))):
            offline=(await self.client.get('/search',params={'q':'Zucker'})).json()
        self.assertTrue(offline['warnings']);self.assertGreater(len(offline['results']),1)

    async def test_old_bls_preferences_and_favorite_alias(self):
        await self.setup_foods()
        body={'id':str(uuid4()),'query':'Zucker','lang':'de','bls_code':'SUGAR'}
        await self.client.post('/food-search/selections',json=body)
        results=(await self.client.get('/search',params={'q':'Zucker','remote':'false'})).json()['results']
        self.assertEqual(results[0]['id'],'SUGAR')
        alias=(await self.client.get('/search',params={'q':'Mein Zucker','remote':'false'})).json()['results']
        self.assertEqual(alias[0]['id'],'SUGAR');self.assertTrue(alias[0]['favorite'])
