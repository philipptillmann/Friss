import os
import tempfile
import unittest
from pathlib import Path
from uuid import uuid4
import httpx
from app import main

class ApiTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        main.DATA=Path(self.tmp.name)
        main.KEY='test-key-'+'x'*32
        self.life=main.lifespan(main.app)
        await self.life.__aenter__()
        self.client=httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app),base_url='http://test',headers={'Authorization':'Bearer '+main.KEY})
    async def asyncTearDown(self):
        await self.client.aclose()
        await self.life.__aexit__(None,None,None)
        self.tmp.cleanup()
    def payload(self,**kwargs):
        return {'id':str(uuid4()),'timestamp':'2026-10-04T15:31:06+02:00','type':'drink','drink':'water','quantity':{'value':250,'unit':'ml'},**kwargs}
    async def test_auth(self):
        self.assertEqual((await self.client.get('/entries',headers={'Authorization':'bad'})).status_code,401)
    async def test_idempotency_and_conflict(self):
        p=self.payload(); first=await self.client.post('/entries',json=p)
        self.assertEqual(first.status_code,201)
        self.assertEqual(first.json()['nutrients']['dietaryWater']['value'],250)
        self.assertEqual((await self.client.post('/entries',json=p)).json(),first.json())
        p['quantity']['value']=300
        self.assertEqual((await self.client.post('/entries',json=p)).status_code,409)
    async def test_health_claim_ack(self):
        p=self.payload(); await self.client.post('/entries',json=p)
        url='/health-export/'+p['id']
        claimed=(await self.client.post(url+'/claim')).json()
        self.assertEqual((await self.client.post(url+'/claim')).status_code,409)
        self.assertEqual((await self.client.get('/health-export/pending')).json(),[])
        result=await self.client.post(url+'/ack',json={'export_token':claimed['export_token'],'success':False})
        self.assertEqual(result.json()['health_status'],'needs_review')
    async def test_unknown_quantity_and_photo_immutability(self):
        p=self.payload(type='picture',quantity=None,drink=None)
        e=(await self.client.post('/entries',json=p)).json()
        self.assertEqual(e['status'],'needs_review')
        url='/entries/'+p['id']+'/photo'
        self.assertEqual((await self.client.put(url,content=b'\xff\xd8\xfftest')).status_code,200)
        self.assertEqual((await self.client.put(url,content=b'\xff\xd8\xffchanged')).status_code,409)
    async def test_invalid_time_and_quantity(self):
        self.assertEqual((await self.client.post('/entries',json=self.payload(timestamp='2026-10-04T15:00:00'))).status_code,422)
        self.assertEqual((await self.client.post('/entries',json=self.payload(quantity={'value':0,'unit':'g'}))).status_code,422)
    async def test_bls_unit_guard(self):
        import json
        food={'bls_code':'TEST','name_de':'Apfel','name_en':'Apple','nutrients':{'dietaryEnergyConsumed':58,'dietaryVitaminB6':57.61,'dietaryVitaminC':'TR'}}
        with main.db() as c:
            c.execute('INSERT INTO foods VALUES(?,?,?)',('TEST',json.dumps(food),'apfel apple'))
        p=self.payload(type='item',drink=None,bls_code='TEST',quantity={'value':180,'unit':'g'})
        e=(await self.client.post('/entries',json=p)).json()
        self.assertAlmostEqual(e['nutrients']['dietaryEnergyConsumed']['value'],104.4)
        self.assertNotIn('dietaryVitaminB6',e['nutrients'])
        self.assertEqual((await self.client.post('/health-export/'+p['id']+'/claim')).status_code,409)
        self.assertEqual((await self.client.get('/foods',params={'q':'Apple','lang':'en'})).json()[0]['display_name'],'Apple')

    async def test_dashboard_and_date_filter(self):
        response=await self.client.get('/',headers={'Authorization':'bad'})
        self.assertEqual(response.status_code,200)
        self.assertIn('Dashboard',response.text)
        self.assertIn('>Passwort</label>',response.text)
        self.assertNotIn('API-Schlüssel',response.text)
        self.assertIn('app.js?v=1.2.2',response.text)
        self.assertEqual(response.headers['cache-control'],'no-store')
        self.assertEqual((await self.client.get('/entries',headers={'Authorization':'bad'})).status_code,401)
        await self.client.post('/entries',json=self.payload())
        response=await self.client.get('/entries',params={'start':'2026-10-04T00:00:00+02:00','end':'2026-10-05T00:00:00+02:00'})
        self.assertEqual(len(response.json()),1)
        response=await self.client.get('/entries',params={'start':'2026-10-05T00:00:00+02:00'})
        self.assertEqual(response.json(),[])
        self.assertEqual((await self.client.get('/entries',params={'start':'2026-10-04T00:00:00'})).status_code,422)

    async def test_password_session_logout_and_csrf(self):
        from app import authentication as a
        old=a.PASSWORD_HASH
        a.PASSWORD_HASH=a.encode_password('a long test password')
        try:
            self.client.headers.pop('Authorization')
            self.assertEqual((await self.client.get('/health')).status_code,401)
            self.assertEqual((await self.client.post('/auth/login',json={'password':'a long test password'})).status_code,403)
            headers={'Origin':'http://test'}
            self.assertEqual((await self.client.post('/auth/login',json={'password':'wrong'},headers=headers)).status_code,401)
            response=await self.client.post('/auth/login',json={'password':'a long test password'},headers=headers)
            self.assertEqual(response.status_code,200)
            self.assertIn('HttpOnly',response.headers['set-cookie'])
            self.assertIn('Max-Age=2592000',response.headers['set-cookie'])
            self.assertEqual((await self.client.get('/health')).status_code,200)
            self.assertEqual((await self.client.post('/entries',json=self.payload(),headers={'Origin':'http://evil'})).status_code,403)
            self.assertEqual((await self.client.post('/entries',json=self.payload(),headers=headers)).status_code,201)
            with main.db() as c: c.execute('UPDATE sessions SET expires=0')
            self.assertEqual((await self.client.get('/health')).status_code,401)
            await self.client.post('/auth/login',json={'password':'a long test password'},headers=headers)
            self.assertEqual((await self.client.post('/auth/logout',headers=headers)).status_code,200)
            self.assertEqual((await self.client.get('/health')).status_code,401)
        finally: a.PASSWORD_HASH=old

    async def test_password_change_and_rate_limit(self):
        from app import authentication as a
        old=a.PASSWORD_HASH
        a.PASSWORD_HASH=a.encode_password('a long test password')
        try:
            self.client.headers.pop('Authorization')
            headers={'Origin':'http://test'}
            await self.client.post('/auth/login',json={'password':'a long test password'},headers=headers)
            a.PASSWORD_HASH=a.encode_password('a different password')
            self.assertEqual((await self.client.get('/health')).status_code,401)
            for _ in range(10):
                self.assertEqual((await self.client.post('/auth/login',json={'password':'wrong'},headers=headers)).status_code,401)
            self.assertEqual((await self.client.post('/auth/login',json={'password':'wrong'},headers=headers)).status_code,429)
        finally: a.PASSWORD_HASH=old

if __name__=='__main__': unittest.main()
