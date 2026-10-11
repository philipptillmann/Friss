import json
import unittest
from uuid import uuid4
import test_api as support
from app import main

class FoodSearchTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp=support.ApiTests.asyncSetUp
    asyncTearDown=support.ApiTests.asyncTearDown

    def food(self,code,de,en):
        payload={'bls_code':code,'name_de':de,'name_en':en,'nutrients':{}}
        with main.db() as c:
            c.execute('INSERT INTO foods VALUES(?,?,?)',(code,json.dumps(payload),main.normalize(de+' '+en)))

    async def pick(self,query,code,lang='de',id=None):
        return await self.client.post('/food-search/selections',json={'id':id or str(uuid4()),'query':query,'lang':lang,'bls_code':code})

    async def results(self,q,lang='de',limit=20):
        return (await self.client.get('/foods',params={'q':q,'lang':lang,'limit':limit})).json()

    async def test_frequency_normalization_and_rank_before_limit(self):
        self.food('ZZ','Haushaltszucker raffiniert','Refined household sugar')
        for i in range(25): self.food(f'A{i:02}','Zuckerzusatz '+str(i),'Sugar additive '+str(i))
        self.assertNotIn('ZZ',[f['bls_code'] for f in await self.results('Zucker')])
        self.assertEqual((await self.pick('  ZUCKER  ','ZZ')).status_code,200)
        self.assertEqual((await self.results('zucker',limit=1))[0]['bls_code'],'ZZ')
        await self.pick('Zucker','A00')
        self.assertEqual((await self.results('Zucker',limit=1))[0]['bls_code'],'A00')
        await self.pick('Zucker','ZZ')
        await self.pick('Zucker','ZZ')
        # Frequency outranks a more recent but less frequent choice.
        await self.pick('Zucker','A00')
        self.assertEqual((await self.results('Zucker',limit=1))[0]['bls_code'],'ZZ')
        # Unrelated terms and the other UI language have independent preferences.
        self.assertEqual((await self.results('Zucker',lang='en',limit=1))[0]['bls_code'],'A00')
        self.assertEqual((await self.results('Zuckerzusatz',limit=1))[0]['bls_code'],'A00')

    async def test_persistence_idempotency_and_validation(self):
        self.food('ZZ','Haushaltszucker','Household sugar')
        id=str(uuid4())
        self.assertEqual((await self.pick('Zucker','ZZ',id=id)).status_code,200)
        self.assertEqual((await self.pick(' zucker ','ZZ',id=id)).status_code,200)
        with main.db() as c:
            self.assertEqual(c.execute('SELECT COUNT(*) FROM food_search_selections').fetchone()[0],1)
        self.assertEqual((await self.pick('Haushalt','ZZ',id=id)).status_code,409)
        self.assertEqual((await self.pick('Milch','ZZ')).status_code,422)
        self.assertEqual((await self.pick('Zucker','missing')).status_code,422)
        self.assertEqual((await self.pick(' ','ZZ')).status_code,422)
        self.assertEqual((await self.client.post('/food-search/selections',json={'id':str(uuid4()),'query':'Zucker','lang':'de','bls_code':'ZZ'},headers={'Authorization':'bad'})).status_code,401)
        await self.life.__aexit__(None,None,None)
        self.life=main.lifespan(main.app)
        await self.life.__aenter__()
        self.assertEqual((await self.results('Zucker',limit=1))[0]['bls_code'],'ZZ')

    async def test_exact_text_relevance_accents_and_literal_wildcards(self):
        self.food('A','Zuckerhaltige Milch','Sugary milk')
        self.food('B','Zucker','Sugar')
        self.food('C','Zucker raffinierte Variante','Refined sugar variant')
        self.food('D','Käse','Cheese')
        self.food('E','Produkt 10% Fett','Product 10% fat')
        self.food('F','Produkt 100 Fett','Product 100 fat')
        self.assertEqual((await self.results('Zucker'))[0]['bls_code'],'B')
        self.assertEqual((await self.results('Kase'))[0]['bls_code'],'D')
        self.assertEqual([f['bls_code'] for f in await self.results('10%')],['E'])
        self.assertEqual(await self.results('_'),[])
        self.assertEqual((await self.client.get('/foods',params={'q':'   '})).status_code,422)
