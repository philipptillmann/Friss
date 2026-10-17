import unittest
from unittest.mock import patch
import httpx
import test_api as support
from app import main,off_search

class OFFSearchTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp=support.ApiTests.asyncSetUp
    asyncTearDown=support.ApiTests.asyncTearDown
    payload=support.ApiTests.payload

    async def test_search_cache_auth_and_selected_product_intake(self):
        off_search.cache.clear();off_search.requests.clear();calls=[]
        def handle(request):
            calls.append(request)
            if request.url.path=='/cgi/search.pl':
                self.assertEqual(request.url.params['search_terms'],'Hafermilch')
                return httpx.Response(200,json={'products':[{'code':'4001234567890','product_name':'Oat milk','product_name_de':'Hafermilch','brands':'Test brand','quantity':'1 L'}, {'code':'invalid','product_name':'Ignored'}]})
            self.assertIn('/api/v2/product/4001234567890.json',request.url.path)
            return httpx.Response(200,json={'status':1,'product':{'product_name':'Hafermilch','nutriments':{'energy-kcal_100g':40,'proteins_100g':1}}})
        original=httpx.AsyncClient
        with patch.object(httpx,'AsyncClient',lambda **kw:original(transport=httpx.MockTransport(handle),**kw)):
            self.assertEqual((await self.client.get('/products/search',params={'q':'Hafermilch'},headers={'Authorization':'bad'})).status_code,401)
            self.assertEqual(calls,[])
            result=await self.client.get('/products/search',params={'q':'Hafermilch'})
            self.assertEqual(result.status_code,200)
            self.assertEqual(result.json(),[{'barcode':'4001234567890','display_name':'Hafermilch','brand':'Test brand','package_quantity':'1 L'}])
            again=await self.client.get('/products/search',params={'q':'Hafermilch'})
            self.assertEqual(again.json(),result.json());self.assertEqual(len(calls),1)
            entry=await self.client.post('/entries',json=self.payload(type='barcode',drink=None,barcode=result.json()[0]['barcode'],quantity={'value':150,'unit':'g'}))
            self.assertEqual(entry.status_code,201);self.assertEqual(entry.json()['status'],'processed')
            self.assertEqual(entry.json()['nutrients']['dietaryEnergyConsumed']['value'],60)
            self.assertEqual(entry.json()['source']['provider'],'Open Food Facts')

    async def test_rate_limit_invalid_queries_and_network_failure(self):
        off_search.cache.clear();off_search.requests.clear()
        for params in [{'q':'x'},{'q':'  '},{'q':'test','lang':'xx'},{'q':'test','limit':100}]:
            self.assertEqual((await self.client.get('/products/search',params=params)).status_code,422)
        original=httpx.AsyncClient
        with patch.object(httpx,'AsyncClient',lambda **kw:original(transport=httpx.MockTransport(lambda req:httpx.Response(503)),**kw)):
            for i in range(8):
                self.assertEqual((await self.client.get('/products/search',params={'q':'food'+str(i)})).status_code,502)
            response=await self.client.get('/products/search',params={'q':'another'})
            self.assertEqual(response.status_code,429);self.assertEqual(response.headers['retry-after'],'60')
        off_search.requests.clear()
