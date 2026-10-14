import json
import unittest
import test_api as support
from app import main

class EntryDetailsTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp=support.ApiTests.asyncSetUp
    asyncTearDown=support.ApiTests.asyncTearDown
    payload=support.ApiTests.payload

    async def test_time_edit_preserves_original_and_values(self):
        p=self.payload()
        entry=(await self.client.post('/entries',json=p)).json()
        original=(main.DATA/'originals'/f"{p['id']}.json").read_text()
        details=(await self.client.get('/entries/'+p['id']+'/details')).json()
        self.assertEqual(details['type'],'drink')
        self.assertEqual(details['contributions'],entry['nutrients'])
        path='/entries/'+p['id']+'/time'
        self.assertEqual((await self.client.patch(path,json={'timestamp':'2026-10-05T13:10:00'})).status_code,422)
        self.assertEqual((await self.client.patch(path,json={'timestamp':'2026-10-05T13:10:00+02:00'},headers={'Authorization':'bad'})).status_code,401)
        changed=(await self.client.patch(path,json={'timestamp':'2026-10-05T13:10:00+02:00'})).json()
        self.assertEqual(changed['nutrients'],entry['nutrients'])
        self.assertEqual(changed['original_timestamp'],entry['timestamp'])
        self.assertEqual(changed['revision'],2)
        self.assertEqual((main.DATA/'originals'/f"{p['id']}.json").read_text(),original)
        old=await self.client.get('/entries',params={'start':'2026-10-04T00:00:00+02:00','end':'2026-10-05T00:00:00+02:00'})
        self.assertEqual(old.json(),[])
        # Retry a timestamp update without creating another revision.
        self.assertEqual((await self.client.patch(path,json={'timestamp':changed['timestamp']})).json()['revision'],2)

    async def test_exported_time_changes_mark_batch_changed(self):
        p=self.payload()
        await self.client.post('/entries',json=p)
        batch=(await self.client.post('/health-days/prepare',json={'day':'2026-10-04','timezone':'Europe/Berlin'})).json()
        await self.client.post('/health-days/'+batch['id']+'/ack',json={'export_token':batch['export_token'],'success':True})
        result=await self.client.patch('/entries/'+p['id']+'/time',json={'timestamp':'2026-10-04T20:15:00+02:00'})
        self.assertEqual(result.status_code,200)
        self.assertEqual(result.json()['health_status'],'synced')
        days=(await self.client.get('/health-days',params={'tz':'Europe/Berlin'})).json()
        self.assertTrue(days[0]['changed'])
        self.assertEqual((await self.client.get('/health-days/'+batch['id'])).json()['samples'],batch['samples'])

    async def test_bls_detail_source_units_and_portion_contribution(self):
        food={'bls_code':'DETAIL_TEST','name_de':'Detail','name_en':'Detail','nutrients':{'dietaryEnergyConsumed':200,'dietaryProtein':10,'dietaryVitaminB6':8,'dietaryVitaminC':'TR'}}
        with main.db() as c:
            c.execute('INSERT INTO foods VALUES(?,?,?)',('DETAIL_TEST',json.dumps(food),'detail'))
        p=self.payload(type='item',drink=None,bls_code='DETAIL_TEST',quantity={'value':150,'unit':'g'})
        await self.client.post('/entries',json=p)
        details=(await self.client.get('/entries/'+p['id']+'/details')).json()
        self.assertEqual(details['contributions']['dietaryEnergyConsumed'],{'value':300,'unit':'kcal'})
        self.assertEqual(details['contributions']['dietaryVitaminB6'],{'value':12,'unit':'mcg'})
        self.assertEqual(details['contributions']['dietaryVitaminC']['qualifier'],'TR')
        unknown=self.payload(type='item',drink=None,bls_code='DETAIL_TEST',quantity=None)
        await self.client.post('/entries',json=unknown)
        details=await self.client.get('/entries/'+unknown['id']+'/details')
        self.assertEqual(details.status_code,200)
        self.assertEqual(details.json()['contributions'],{})

    async def test_copy_snapshot_time_health_and_idempotency(self):
        from uuid import uuid4
        p=self.payload()
        e=(await self.client.post('/entries',json=p)).json()
        e.update(health_status='synced',export_token='old-token',recipe_snapshot={'name':'Frozen recipe'},drinking_water_ml=12)
        main.save_entry(e)
        body={'id':str(uuid4()),'timestamp':'2026-10-15T07:30:00+02:00'}
        path='/entries/'+e['id']+'/copy'
        r=await self.client.post(path,json=body);self.assertEqual(r.status_code,201)
        copy=r.json()
        self.assertEqual(copy['nutrients'],e['nutrients'])
        self.assertEqual(copy['recipe_snapshot'],e['recipe_snapshot'])
        self.assertEqual(copy['health_status'],'pending');self.assertNotIn('export_token',copy)
        self.assertEqual(copy['timestamp'],body['timestamp'])
        self.assertEqual(copy['copied_from']['id'],e['id'])
        self.assertEqual(main.load_entry(e['id'])['health_status'],'synced')
        self.assertTrue((main.DATA/'originals'/f"{copy['id']}.json").exists())
        await self.client.delete('/entries/'+e['id'])
        self.assertEqual((await self.client.post(path,json=body)).json(),copy)
        self.assertEqual((await self.client.post(path,json={**body,'timestamp':'2026-10-16T07:30:00+02:00'})).status_code,409)

    async def test_copy_validation_and_recipe_ingredient(self):
        from uuid import uuid4
        e=(await self.client.post('/entries',json=self.payload())).json()
        path='/entries/'+e['id']+'/copy'
        body={'id':str(uuid4()),'timestamp':'2026-10-15T07:30:00'}
        self.assertEqual((await self.client.post(path,json=body)).status_code,422)
        body['timestamp']+='Z'
        self.assertEqual((await self.client.post(path,json=body,headers={'Authorization':'bad'})).status_code,401)
        e['recipe_id']=str(uuid4());main.save_entry(e)
        self.assertEqual((await self.client.post(path,json=body)).status_code,422)
