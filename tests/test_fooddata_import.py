import json
import unittest
from pathlib import Path
from unittest.mock import AsyncMock,patch
from uuid import uuid4
import httpx
from fastapi import HTTPException
import test_api as support
from app import fooddata_import as importer

URL='https://fooddata.the50.store/ingredients/2010-spices-cinnamon-ground'
HTML=(Path(__file__).parent/'fixtures/fooddata-cinnamon.html').read_text()

def page(rows,basis='per 100g'):
    return '<h1>Test food</h1><script type="application/ld+json">'+json.dumps({'@type':'Dataset','description':basis,'variableMeasured':[{'name':name,'value':value,'unitText':unit} for name,value,unit in rows]})+'</script>'

class FooddataParserTests(unittest.TestCase):
    def test_actual_cinnamon_data_units_totals_zero_and_unknowns(self):
        data=importer.parse(HTML,URL);n=data['nutrients']
        self.assertEqual(n['dietaryEnergyConsumed'],{'value':247,'unit':'kcal'})
        self.assertEqual(n['dietaryCalcium'],{'value':1002,'unit':'mg'})
        self.assertEqual(n['dietarySelenium'],{'value':3.1,'unit':'mcg'})
        self.assertEqual(n['dietaryVitaminB12'],{'value':0,'unit':'mcg'})
        self.assertEqual(n['dietaryWater'],{'value':10.58,'unit':'g'})
        self.assertEqual(n['dietaryFolate']['value'],6) # Not 18 by adding food + DFE.
        self.assertEqual(n['dietaryVitaminA']['value'],15) # Not beta-carotene.
        self.assertNotIn('dietaryCholesterol',n) # Not published in this payload.
        self.assertNotIn('dietaryCaffeine',n)
        self.assertIsNone(data['ethanol_g_per100'])
        self.assertEqual(len(n),30);self.assertEqual(data['source']['url'],URL)

    def test_conversion_priority_and_uninterpretable_values(self):
        data=importer.parse(page([('Energy',418.4,'KJ'),('Energy',100,'KCAL'),('Vitamin D (D2 + D3), International Units',400,'IU'),('Vitamin B-6',158,'UG'),('Caffeine',.02,'G'),('Alcohol, ethyl',3,'G'),('Vitamin A, IU',3000,'IU'),('Vitamin C, total ascorbic acid','TR','MG'),('Iron, Fe',1,'UNKNOWN')]),URL)
        n=data['nutrients'];self.assertEqual(n['dietaryEnergyConsumed']['value'],100)
        self.assertEqual(n['dietaryVitaminD']['value'],10)
        self.assertAlmostEqual(n['dietaryVitaminB6']['value'],.158)
        self.assertEqual(n['dietaryCaffeine']['value'],20)
        self.assertEqual(data['ethanol_g_per100'],3)
        self.assertNotIn('dietaryVitaminA',n);self.assertNotIn('dietaryVitaminC',n);self.assertNotIn('dietaryIron',n)
        self.assertAlmostEqual(importer.parse(page([('Energy',418.4,'KJ')]),URL)['nutrients']['dietaryEnergyConsumed']['value'],100)
        with self.assertRaises(HTTPException):importer.parse(page([('Protein',2,'G')],basis='per serving'),URL)
        with self.assertRaises(HTTPException):importer.parse(page([('Protein',2,'G'),('Protein',3,'G')]),URL)

    def test_table_only_and_url_restrictions(self):
        html='<h1>Table food</h1><table><tr><th>Nutrient</th><th>Value / 100g</th><th>Unit</th></tr><tr><td>Calcium, Ca</td><td>1,002</td><td>MG</td></tr><tr><td>Protein</td><td>0</td><td>G</td></tr></table>'
        data=importer.parse(html,URL);self.assertEqual(data['nutrients']['dietaryCalcium']['value'],1002)
        self.assertEqual(data['nutrients']['dietaryProtein']['value'],0)
        self.assertEqual(importer.canonical_url(URL+'/?utm_source=iphone#values'),URL)
        for url in ['http://127.0.0.1/','https://fooddata.the50.store.evil/ingredients/2010-test','https://user:pass@fooddata.the50.store/ingredients/2010-test','https://fooddata.the50.store:8443/ingredients/2010-test','https://fooddata.the50.store/../admin','https://fooddata.the50.store/ingredients/%2e%2e','https://fooddata.the50.store/api']:
            with self.assertRaises(HTTPException):importer.canonical_url(url)

class FooddataImportApiTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp=support.ApiTests.asyncSetUp
    asyncTearDown=support.ApiTests.asyncTearDown
    payload=support.ApiTests.payload

    async def test_preview_save_and_meal_preserve_source_water_mass(self):
        with patch.object(importer,'fetch',AsyncMock(return_value=HTML)) as fetch:
            self.assertEqual((await self.client.post('/manual-ingredients/import',json={'url':URL},headers={'Authorization':'bad'})).status_code,401)
            self.assertEqual((await self.client.post('/manual-ingredients/import',json={'url':'https://127.0.0.1/'})).status_code,422)
            fetch.assert_not_awaited()
            result=await self.client.post('/manual-ingredients/import',json={'url':URL});self.assertEqual(result.status_code,200)
            fetch.assert_awaited_once_with(URL)
        self.assertEqual((await self.client.get('/manual-ingredients')).json(),[]) # Preview does not write.
        draft=result.json();ingredient={k:draft[k] for k in ['name_de','name_en','notes','nutrients','ethanol_g_per100','source']}
        ingredient.update(id=str(uuid4()),version=0)
        saved=(await self.client.post('/manual-ingredients',json=ingredient)).json()
        self.assertEqual(saved['source']['url'],URL)
        entry=(await self.client.post('/entries',json=self.payload(type='manual',drink=None,manual_id=ingredient['id'],quantity={'value':5,'unit':'g'}))).json()
        self.assertAlmostEqual(entry['nutrients']['dietaryEnergyConsumed']['value'],12.35)
        self.assertEqual(entry['nutrients']['dietaryWater']['unit'],'g')
        self.assertEqual(entry['manual_snapshot']['source']['url'],URL)
        export=(await self.client.post('/health-export/'+entry['id']+'/claim')).json()
        self.assertNotIn('dietaryWater',export['nutrients'])

    async def test_fetch_success_error_redirect_and_size_bounds(self):
        original=httpx.AsyncClient
        for status,headers,content,expected in [(200,{'Content-Type':'text/html'},HTML.encode(),None),(302,{'Location':'http://127.0.0.1'},b'',502),(404,{},b'',404),(200,{'Content-Type':'application/json'},b'{}',422),(200,{'Content-Type':'text/html'},b'a'*(importer.MAX_BYTES+1),422)]:
            requests=[]
            def handle(request):requests.append(request);return httpx.Response(status,headers=headers,content=content)
            with patch.object(importer.httpx,'AsyncClient',lambda **kwargs:original(transport=httpx.MockTransport(handle),**kwargs)):
                if expected:
                    with self.assertRaises(HTTPException) as caught:await importer.fetch(URL)
                    self.assertEqual(caught.exception.status_code,expected)
                else:self.assertIn('Spices, cinnamon',await importer.fetch(URL))
            self.assertEqual(len(requests),1) # Never follow a redirect.
