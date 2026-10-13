import unittest
from pathlib import Path
from unittest.mock import AsyncMock,patch
from uuid import uuid4
import httpx
from fastapi import HTTPException
import test_api as support
from app import fddb_import as importer
URL='https://fddb.info/db/de/lebensmittel/naturprodukt_zimt_gemahlen_1053/index.html?nomobile=1'
HTML=Path('tests/fixtures/fddb-cinnamon.html').read_text()

def page(rows,basis='100 g'):
    return "<h1 id='fddb-headline1'>Test food</h1><h2>Nährwerte für "+basis+'</h2>'+''.join("<div><div class='sidrow'><span>"+n+'</span></div><div>'+v+'</div></div>' for n,v in rows)

class FDDBParserTests(unittest.TestCase):
    def test_real_cinnamon_and_units(self):
        result=importer.parse(HTML,URL);n=result['nutrients']
        self.assertEqual(result['name_de'],'Zimt, gemahlen')
        self.assertEqual(n['dietaryEnergyConsumed'],{'value':272,'unit':'kcal'})
        self.assertEqual(n['dietaryCarbohydrates']['value'],56) # No USDA subtraction.
        self.assertEqual(n['dietaryFiber']['value'],24)
        self.assertEqual(n['dietaryWater'],{'value':8,'unit':'g'})
        self.assertEqual(n['dietaryIodine'],{'value':5,'unit':'mcg'})
        self.assertEqual(n['dietaryCalcium']['value'],1228)
        self.assertNotIn('dietaryVitaminC',n)
        self.assertEqual(result['source']['provider'],'FDDB')
        self.assertIsNone(result['source']['carbohydrate_conversion'])

    def test_decimal_unknown_percent_and_portion_scope(self):
        html=page([('Protein','1,25 g'),('Vitamin B12','2,5 μg'),('Kalzium','1.228,5 mg'),('Wassergehalt','8,5%'),('Fett','k. A.'),('Brennwert','418,4 kJ')])
        html+='<h2>Zusammensetzung</h2>'+page([('Protein','999 g')]).split('</h2>')[1]
        n=importer.parse(html,URL)['nutrients']
        self.assertEqual(n['dietaryProtein']['value'],1.25)
        self.assertEqual(n['dietaryVitaminB12']['value'],2.5)
        self.assertEqual(n['dietaryCalcium']['value'],1228.5)
        self.assertEqual(n['dietaryWater']['value'],8.5)
        self.assertAlmostEqual(n['dietaryEnergyConsumed']['value'],100)
        self.assertNotIn('dietaryFatTotal',n)
        for html in [page([('Protein','1 g')],'100 ml'),page([('Protein','k. A.')]),page([('Protein','1 g'),('Protein','2 g')]),page([('Wassergehalt','101%')])]:
            with self.assertRaises(HTTPException):importer.parse(html,URL)

    def test_urls(self):
        self.assertEqual(importer.canonical_url(URL+'&tracking=1#x'),URL)
        for url in ['http://fddb.info/db/de/lebensmittel/x/index.html','https://fddb.info.evil/db/de/lebensmittel/x/index.html','https://user@fddb.info/db/de/lebensmittel/x/index.html','https://fddb.info:8443/db/de/lebensmittel/x/index.html','https://fddb.info/db/de/lebensmittel/%2e%2e/index.html','https://fddb.info/db/de/lexikon/x/index.html']:
            with self.assertRaises(HTTPException):importer.canonical_url(url)

class FDDBApiTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp=support.ApiTests.asyncSetUp
    asyncTearDown=support.ApiTests.asyncTearDown
    payload=support.ApiTests.payload
    async def test_preview_save_intake_and_provenance(self):
        with patch.object(importer,'fetch',AsyncMock(return_value=HTML)) as fetch:
            self.assertEqual((await self.client.post('/manual-ingredients/import',json={'url':URL},headers={'Authorization':'bad'})).status_code,401)
            fetch.assert_not_awaited()
            r=await self.client.post('/manual-ingredients/import',json={'url':URL});self.assertEqual(r.status_code,200)
            fetch.assert_awaited_once_with(URL)
        self.assertEqual((await self.client.get('/manual-ingredients')).json(),[])
        draft=r.json();body={k:draft[k] for k in ['name_de','name_en','notes','nutrients','ethanol_g_per100','source']}
        body.update(id=str(uuid4()),version=0)
        r=await self.client.post('/manual-ingredients',json=body);self.assertEqual(r.status_code,201)
        self.assertEqual(r.json()['source']['url'],URL)
        entry=(await self.client.post('/entries',json=self.payload(type='manual',drink=None,manual_id=body['id'],quantity={'value':5,'unit':'g'}))).json()
        self.assertEqual(entry['status'],'processed')
        self.assertAlmostEqual(entry['nutrients']['dietaryEnergyConsumed']['value'],13.6)
        self.assertEqual(entry['manual_snapshot']['source']['provider'],'FDDB')
        self.assertAlmostEqual(entry['nutrients']['dietaryCarbohydrates']['value'],2.8)

    async def test_fetch_rejects_redirect_blocks_and_oversize(self):
        original=httpx.AsyncClient
        for status,headers,content,expected in [(200,{'Content-Type':'text/html'},HTML.encode(),None),(302,{'Location':'http://127.0.0.1'},b'',502),(403,{},b'',502),(404,{},b'',404),(200,{'Content-Type':'application/json'},b'{}',422),(200,{'Content-Type':'text/html'},b'x'*(2*1024*1024+1),422)]:
            transport=httpx.MockTransport(lambda request:httpx.Response(status,headers=headers,content=content))
            with patch.object(importer.httpx,'AsyncClient',lambda **kw:original(transport=transport,**kw)):
                if expected:
                    with self.assertRaises(HTTPException) as ctx:await importer.fetch(URL)
                    self.assertEqual(ctx.exception.status_code,expected)
                else:self.assertIn('fddb-headline1',await importer.fetch(URL))
