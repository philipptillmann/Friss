import json
import unittest
from pathlib import Path
import httpx
from uuid import uuid4
import test_api as support
from app import main,json_import
from fastapi import HTTPException,FastAPI

class JSONImportTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp=support.ApiTests.asyncSetUp
    asyncTearDown=support.ApiTests.asyncTearDown
    payload=support.ApiTests.payload

    async def prepare(self):
        food={'bls_code':'JSON_TEST','name_de':'Testmilch','name_en':'Test milk','nutrients':{'dietaryEnergyConsumed':60,'dietaryProtein':3}}
        with main.db() as c:c.execute('INSERT INTO foods VALUES(?,?,?)',('JSON_TEST',json.dumps(food),'testmilch test milk'))
        own={'id':str(uuid4()),'name_de':'Eigene Milch','name_en':'Own milk','version':0,'nutrients':{'dietaryEnergyConsumed':{'value':70,'unit':'kcal'}}}
        await self.client.post('/manual-ingredients',json=own)
        raw='```json\n'+json.dumps({'schema':'friss-meal-v1','title':'Breakfast','items':[{'name':'Testmilch','quantity':{'value':150,'unit':'g'},'notes':'Estimated from photo'},{'name':'Eigene Milch','quantity':None}]},ensure_ascii=False)+'\n```'
        return raw,own

    async def test_preview_commit_idempotency_originals_and_details(self):
        raw,own=await self.prepare()
        preview=await self.client.post('/json-import/preview',json={'raw':raw,'lang':'de'})
        self.assertEqual(preview.status_code,200);items=preview.json()['items']
        self.assertEqual(items[0]['matches'][0]['id'],'JSON_TEST')
        self.assertTrue(any(m['id']==own['id'] for m in items[1]['matches']))
        self.assertEqual((await self.client.get('/entries')).json(),[])
        chosen=[{k:v for k,v in item.items() if k!='matches'} for item in items]
        chosen[0]['bls_code']='JSON_TEST';chosen[1]['manual_id']=own['id']
        body={'id':str(uuid4()),'raw':raw,'lang':'de','timestamp':'2026-10-12T18:00:00+02:00','items':chosen}
        saved=await self.client.post('/json-import/commit',json=body)
        self.assertEqual(saved.status_code,201);self.assertEqual(saved.json()['count'],2)
        self.assertEqual((await self.client.post('/json-import/commit',json=body)).json(),saved.json())
        entries=(await self.client.get('/entries')).json();self.assertEqual(len(entries),2)
        first=next(e for e in entries if e.get('bls_code')=='JSON_TEST')
        self.assertEqual(first['nutrients']['dietaryEnergyConsumed']['value'],90)
        self.assertEqual(first['capture_method'],'json_import')
        self.assertEqual(first['import_context']['notes'],'Estimated from photo')
        self.assertEqual((main.DATA/'originals'/f"import-{body['id']}.txt").read_text(),raw)
        self.assertTrue((main.DATA/'originals'/f"{first['id']}.json").exists())
        self.assertEqual(next(e for e in entries if e['type']=='manual')['status'],'needs_review')
        different={**body,'timestamp':'2026-10-12T19:00:00+02:00'}
        self.assertEqual((await self.client.post('/json-import/commit',json=different)).status_code,409)
        for e in entries:await self.client.delete('/entries/'+e['id'])
        await self.client.delete('/manual-ingredients/'+own['id'],params={'version':0})
        self.assertEqual((await self.client.post('/json-import/commit',json=body)).json(),saved.json())
        self.assertEqual((await self.client.get('/entries')).json(),[]) # Never recreate deleted entries on retry.

    async def test_recipe_target_unassigned_food_and_ml_not_converted(self):
        raw,own=await self.prepare()
        recipe={'id':str(uuid4()),'name':'JSON recipe','servings':2}
        await self.client.post('/recipes',json=recipe)
        chosen=[{'name':'Testmilch','quantity':{'value':100,'unit':'ml'},'bls_code':'JSON_TEST'},{'name':'Testmilch','quantity':{'value':100,'unit':'g'}}]
        body={'id':str(uuid4()),'raw':raw,'timestamp':'2026-10-12T18:00:00+02:00','recipe_id':recipe['id'],'items':chosen}
        result=await self.client.post('/json-import/commit',json=body);self.assertEqual(result.status_code,201)
        self.assertEqual((await self.client.get('/entries')).json(),[])
        ingredients=(await self.client.get('/recipes/'+recipe['id'])).json()['ingredients']
        self.assertEqual(len(ingredients),2);self.assertTrue(all(i['status']=='needs_review' for i in ingredients))
        unassigned=next(i for i in ingredients if i['type']=='text')
        self.assertNotIn('food',unassigned) # Must not silently match the unique BLS candidate.
        resolved=await self.client.post('/entries/'+unassigned['id']+'/resolve',json={'bls_code':'JSON_TEST','quantity':{'value':100,'unit':'g'}})
        self.assertEqual(resolved.json()['status'],'processed')

    async def test_atomic_failure_can_resume_without_duplicate_entries(self):
        raw,_=await self.prepare()
        body={'id':str(uuid4()),'raw':raw,'timestamp':'2026-10-12T18:00:00+02:00','items':[{'name':'Testmilch','quantity':{'value':100,'unit':'g'},'bls_code':'JSON_TEST'}]*2}
        calls=0
        original=main.process
        async def fail_second(entry):
            nonlocal calls
            calls+=1
            if calls==2:raise RuntimeError('Simulated interruption')
            await original(entry)
        isolated=FastAPI()
        json_import.install(isolated,main.db,main.auth,main.Entry,fail_second,lambda:main.DATA,main.normalize)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=isolated),base_url='http://test',headers=self.client.headers) as client:
            with self.assertRaises(RuntimeError):await client.post('/json-import/commit',json=body)
        self.assertEqual((await self.client.get('/entries')).json(),[])
        result=await self.client.post('/json-import/commit',json=body)
        self.assertEqual(result.status_code,201);self.assertEqual(len((await self.client.get('/entries')).json()),2)

    async def test_validation_authentication_and_no_writes_on_invalid_reference(self):
        raw,_=await self.prepare()
        self.assertEqual((await self.client.post('/json-import/preview',json={'raw':raw},headers={'Authorization':'bad'})).status_code,401)
        body={'id':str(uuid4()),'raw':raw,'timestamp':'2026-10-12T18:00:00+02:00','items':[{'name':'Test','bls_code':'MISSING'},{'name':'Test'}]}
        self.assertEqual((await self.client.post('/json-import/commit',json=body)).status_code,422)
        self.assertEqual((await self.client.get('/entries')).json(),[])
        self.assertFalse((main.DATA/'originals'/f"import-{body['id']}.txt").exists())
        body['items']=[{'name':'Test'}]
        self.assertEqual((await self.client.post('/json-import/commit',json=body)).status_code,422)
        body['timestamp']='2026-10-12T18:00:00'
        self.assertEqual((await self.client.post('/json-import/commit',json=body)).status_code,422)

class JSONFormatTests(unittest.TestCase):
    def test_format_numbers_duplicates_and_fences(self):
        valid=json.dumps({'schema':'friss-meal-v1','items':[{'name':'Rice','quantity':None}]})
        self.assertEqual(json_import.parse(valid).items[0].name,'Rice')
        self.assertEqual(json_import.parse('```json\n'+valid+'\n```').items[0].name,'Rice')
        for raw in ['[]','{}',valid.replace('friss-meal-v1','other'),'{"schema":"friss-meal-v1","schema":"friss-meal-v1","items":[]}',valid.replace('null','{"value":NaN,"unit":"g"}'),valid.replace('null','{"value":-1,"unit":"g"}'),valid.replace('null','{"value":1,"unit":"portion"}'),valid.replace('Rice',''),valid.replace('Rice','\\ud800')]:
            with self.assertRaises(HTTPException):json_import.parse(raw)
        with self.assertRaises(HTTPException):json_import.parse('x'*262145)
