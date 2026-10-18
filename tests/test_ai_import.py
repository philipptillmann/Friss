import json
from pathlib import Path
import unittest
import test_api as support
from app import main

class AIImportTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp=support.ApiTests.asyncSetUp
    asyncTearDown=support.ApiTests.asyncTearDown

    def body(self):
        return {'timestamp':'2026-10-18T20:00:00+02:00','original_message':'500 g Bolognese',
                'ai':{'title':'Spaghetti Bolognese','quantity':{'value':500,'unit':'g'},'notes':'Estimated',
                      'nutrients':{'dietaryEnergyConsumed':{'value':775,'unit':'kcal'},'dietaryProtein':{'value':37.5,'unit':'g'},'dietaryVitaminA':{'value':140,'unit':'µg'}}}}

    async def test_save_totals_metadata_retry_and_time(self):
        body=self.body();body['ai']=json.dumps(body['ai'])
        r=await self.client.post('/json-import',json=body)
        self.assertEqual(r.status_code,201,r.text)
        result=r.json();self.assertEqual(result['count'],1)
        again=await self.client.post('/json-import',json=body)
        self.assertEqual(again.json(),result)
        with main.db() as c:
            self.assertEqual(c.execute('SELECT count(*) FROM entries').fetchone()[0],1)
            e=json.loads(c.execute('SELECT payload FROM entries WHERE id=?',(result['entry_ids'][0],)).fetchone()[0])
        self.assertEqual(e['nutrients']['dietaryEnergyConsumed']['value'],775)
        self.assertEqual(e['quantity']['value'],500)
        self.assertEqual(e['timestamp'],body['timestamp'])
        self.assertEqual(e['import_context']['original_message'],body['original_message'])
        self.assertEqual(e['status'],'processed')
        self.assertEqual(json.loads((main.DATA/'originals'/('request-'+result['id']+'.json')).read_text()),body)
        e['quantity']['value']=250
        await main.process(e)
        self.assertEqual(e['nutrients']['dietaryEnergyConsumed']['value'],387.5)

    async def test_object_and_unknown_quantity(self):
        body=self.body();body['ai'].pop('quantity')
        r=await self.client.post('/json-import',json=body)
        self.assertEqual(r.status_code,201,r.text)
        self.assertEqual(r.json()['needs_review'],0)
        with main.db() as c:e=json.loads(c.execute('SELECT payload FROM entries').fetchone()[0])
        self.assertIsNone(e['quantity'])
        self.assertEqual(e['nutrients']['dietaryProtein']['value'],37.5)

    async def test_validation_no_partial_entries_and_auth(self):
        for change in ['badjson','unit','key','timezone','empty']:
            body=self.body()
            if change=='badjson':body['ai']='{"title":"Broken"'
            if change=='unit':body['ai']['nutrients']['dietaryEnergyConsumed']['unit']='g'
            if change=='key':body['ai']['nutrients']['imaginary']={'value':1,'unit':'g'}
            if change=='timezone':body['timestamp']='2026-10-18T20:00:00'
            if change=='empty':body['ai']['nutrients']={}
            r=await self.client.post('/json-import',json=body)
            self.assertEqual(r.status_code,422,(change,r.text))
        r=await self.client.post('/json-import',json=self.body(),headers={'Authorization':'Bearer wrong'})
        self.assertEqual(r.status_code,401)
        with main.db() as c:self.assertEqual(c.execute('SELECT count(*) FROM entries').fetchone()[0],0)

    async def test_documented_example_and_key_order_retry(self):
        body=json.loads(Path('docs/examples/ai-meal.json').read_text())
        first=await self.client.post('/json-import',json=body)
        self.assertEqual(first.status_code,201,first.text)
        body['ai']['nutrients']=dict(reversed(list(body['ai']['nutrients'].items())))
        second=await self.client.post('/json-import',json=body)
        self.assertEqual(first.json(),second.json())
        self.assertEqual(first.json()['nutrients']['dietaryEnergyConsumed']['value'],775)
