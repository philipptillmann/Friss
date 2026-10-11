import unittest
import json
from uuid import uuid4
import test_api as support
from app import main

class HealthDayTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp=support.ApiTests.asyncSetUp
    asyncTearDown=support.ApiTests.asyncTearDown
    payload=support.ApiTests.payload

    async def test_day_export_reservation_confirmation_and_changes(self):
        a=self.payload(timestamp='2026-10-04T00:15:00+02:00')
        b=self.payload(timestamp='2026-10-04T23:45:00+02:00',quantity={'value':500,'unit':'ml'})
        for e in [a,b]: await self.client.post('/entries',json=e)
        body={'day':'2026-10-04','timezone':'Europe/Berlin'}
        response=await self.client.post('/health-days/prepare',json=body)
        self.assertEqual(response.status_code,200)
        batch=response.json()
        self.assertEqual(batch['samples'],[{'identifier':'dietaryWater','value':750,'unit':'ml','timestamp':'2026-10-04T12:00:00+02:00'}])
        self.assertEqual((await self.client.post('/health-days/prepare',json=body)).status_code,409)
        self.assertEqual((await self.client.get('/health-export/pending')).json(),[])
        self.assertEqual((await self.client.post('/health-export/'+a['id']+'/claim')).status_code,409)
        ack={'export_token':batch['export_token'],'success':True}
        self.assertEqual((await self.client.post('/health-export/'+a['id']+'/ack',json=ack)).status_code,409)
        url='/health-days/'+batch['id']+'/ack'
        self.assertEqual((await self.client.post(url,json={**ack,'export_token':'wrong'})).status_code,409)
        self.assertEqual((await self.client.post(url,json=ack)).json()['status'],'confirmed')
        self.assertEqual((await self.client.post(url,json=ack)).status_code,200)
        days=(await self.client.get('/health-days',params={'tz':'Europe/Berlin'})).json()
        self.assertFalse(days[0]['changed'])
        await self.client.delete('/entries/'+a['id'])
        days=(await self.client.get('/health-days',params={'tz':'Europe/Berlin'})).json()
        self.assertTrue(days[0]['changed'])
        self.assertEqual((await self.client.get('/health-days/'+batch['id'])).json()['samples'],batch['samples'])
        # Recreating an ID cannot evade a historical export reservation.
        await self.client.post('/entries',json=a)
        self.assertEqual((await self.client.post('/health-export/'+a['id']+'/claim')).status_code,409)
        self.assertEqual((await self.client.post('/health-days/prepare',json={'day':'2026-10-03','timezone':'America/New_York'})).status_code,409)

    async def test_blocked_days_auth_and_goals(self):
        self.assertEqual((await self.client.get('/health-days',headers={'Authorization':'bad'})).status_code,401)
        self.assertEqual((await self.client.get('/health-days',params={'tz':'invalid'})).status_code,422)
        await self.client.post('/entries',json=self.payload(type='text',drink=None,quantity=None,description='unknown meal'))
        body={'day':'2026-10-04','timezone':'Europe/Berlin'}
        self.assertEqual((await self.client.post('/health-days/prepare',json=body)).json()['detail'],'unresolved')
        with main.db() as c:
            c.execute('DELETE FROM entries')
            e={'id':str(uuid4()),'timestamp':'2026-10-04T12:00:00+02:00','type':'item','status':'processed','health_status':'pending','source':{'provider':'BLS'},'nutrients':{'dietaryProtein':{'value':12,'unit':'g'}}}
            c.execute('INSERT INTO entries VALUES(?,?,?)',(e['id'],'test',json.dumps(e)))
        self.assertEqual((await self.client.post('/health-days/prepare',json=body)).json()['detail'],'bls_units')
        settings=(await self.client.get('/settings')).json()
        settings['goals']={'energy_kcal':2100,'protein_g':120,'carbohydrates_g':250,'fat_g':60}
        response=await self.client.put('/settings',json=settings)
        self.assertEqual(response.status_code,200)
        settings=response.json()
        self.assertEqual((await self.client.get('/settings')).json()['goals']['energy_kcal'],2100)
        settings['goals']['energy_kcal']=0
        self.assertEqual((await self.client.put('/settings',json=settings)).status_code,422)
