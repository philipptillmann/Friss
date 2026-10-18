import asyncio
import base64
import io
import json
import stat
import unittest
from unittest.mock import patch
from uuid import uuid4
from pathlib import Path
import zipfile
import test_api as support
from app import main,backups

class BackupTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp=support.ApiTests.asyncSetUp
    asyncTearDown=support.ApiTests.asyncTearDown
    payload=support.ApiTests.payload

    async def exported(self):
        r=await self.client.get('/backups/export');self.assertEqual(r.status_code,200,r.text if r.status_code!=200 else '')
        self.assertEqual(r.headers['cache-control'],'no-store')
        with zipfile.ZipFile(io.BytesIO(r.content)) as z:return r.content,json.loads(z.read('backup.json'))

    def zip(self,doc,files=None):
        out=io.BytesIO()
        with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
            z.writestr('backup.json',json.dumps(doc))
            for k,v in (files or {}).items():z.writestr(k,v)
        return out.getvalue()

    async def restore(self,content):
        return await self.client.post('/backups/restore',content=content,headers={'Content-Type':'application/zip','X-Friss-Restore':'replace'})

    async def test_full_roundtrip_originals_images_learning_health_and_credentials(self):
        p=self.payload();await self.client.post('/entries',json=p)
        recipe={'id':str(uuid4()),'name':'Drink','category':'drink','servings':1}
        await self.client.post('/recipes',json=recipe)
        own={'id':str(uuid4()),'name_de':'Milch','version':0,'nutrients':{'dietaryProtein':{'value':3,'unit':'g'}}}
        self.assertEqual((await self.client.post('/manual-ingredients',json=own)).status_code,201)
        settings=(await self.client.get('/settings')).json();settings['buttons'].reverse()
        await self.client.put('/settings',json=settings)
        (main.DATA/'bls').mkdir();(main.DATA/'bls'/'de.json').write_text('{"original":"BLS"}')
        photo=main.DATA/'originals'/'photo.jpeg';photo.write_bytes(b'original-photo')
        with main.db() as c:
            c.execute('INSERT INTO button_images VALUES(?,?)',(settings['buttons'][0]['id'],b'image-bytes'))
            c.execute('INSERT INTO search_selections VALUES(?,?,?,?,?,?)',(str(uuid4()),'milk','en','off','4001234567890',json.dumps({'source':'off','id':'4001234567890','label':'Milk'})))
            c.execute('INSERT INTO sessions VALUES(?,?,?)',('private-session',99999999999,'private-password-version'))
        health=(await self.client.post('/health-days/prepare',json={'day':'2026-10-04','timezone':'Europe/Berlin'})).json()
        archive,doc=await self.exported()
        self.assertEqual(set(doc['tables']),set(backups.TABLES));self.assertNotIn('sessions',doc['tables'])
        self.assertNotIn(main.KEY,json.dumps(doc));self.assertNotIn('private-session',json.dumps(doc))
        inspection=await self.client.post('/backups/inspect',content=archive)
        self.assertEqual(inspection.status_code,200,inspection.text)
        self.assertEqual(inspection.json()['counts']['entries'],1)
        photo.write_bytes(b'changed');(main.DATA/'originals'/'new.txt').write_text('new')
        with main.db() as c:c.execute('DELETE FROM entries');c.execute('DELETE FROM button_images');c.execute('DELETE FROM recipes')
        result=await self.restore(archive);self.assertEqual(result.status_code,200,result.text)
        self.assertTrue((main.DATA/result.json()['recovery_backup']).exists())
        self.assertEqual(photo.read_bytes(),b'original-photo');self.assertFalse((main.DATA/'originals'/'new.txt').exists())
        self.assertEqual((main.DATA/'bls'/'de.json').read_text(),'{"original":"BLS"}')
        self.assertEqual(main.load_entry(p['id'])['quantity']['value'],250)
        self.assertEqual((await self.client.get('/recipes')).json()[0]['category'],'drink')
        self.assertEqual((await self.client.get('/health-days/'+health['id'])).json(),health)
        with main.db() as c:
            self.assertEqual(c.execute('SELECT content FROM button_images').fetchone()[0],b'image-bytes')
            self.assertEqual(c.execute('SELECT count(*) FROM search_selections').fetchone()[0],1)
            self.assertEqual(c.execute('SELECT token FROM sessions').fetchone()[0],'private-session')
        after_doc=(await self.exported())[1];self.assertEqual(after_doc['tables'],doc['tables'])

    async def test_validation_confirmation_auth_and_rollback(self):
        p=self.payload();await self.client.post('/entries',json=p)
        archive,doc=await self.exported()
        self.assertEqual((await self.client.get('/backups/export',headers={'Authorization':'bad'})).status_code,401)
        self.assertEqual((await self.client.post('/backups/restore',content=archive)).status_code,422)
        # Valid JSON but conflicting primary keys: insert fails, transaction rolls back.
        doc['tables']['entries'].append(doc['tables']['entries'][0]);doc['files']={}
        failed=await self.restore(self.zip(doc));self.assertEqual(failed.status_code,422,failed.text)
        self.assertEqual(main.load_entry(p['id'])['quantity']['value'],250)
        self.assertTrue((main.DATA/'originals'/(p['id']+'.json')).exists())
        self.assertEqual((await self.restore(b'not a zip')).status_code,422)
        for file in ['../evil','files/originals/../evil','/evil','files/originals//evil','files/originals/a\\b']:
            bad=self.zip(doc,{file:b'bad'});self.assertEqual((await self.client.post('/backups/inspect',content=bad)).status_code,422)
        clean=json.loads(json.dumps(doc));clean['schema']='future';self.assertEqual((await self.restore(self.zip(clean))).status_code,422)
        clean['schema']=backups.SCHEMA;clean['tables'].pop('foods');self.assertEqual((await self.restore(self.zip(clean))).status_code,422)
        self.assertEqual((await self.client.get('/health')).status_code,200)

    async def test_filesystem_failure_rolls_back_database_and_folders(self):
        p=self.payload();await self.client.post('/entries',json=p)
        archive,_=await self.exported();original=main.DATA/'originals'/(p['id']+'.json');original.write_text('current-original')
        await self.client.patch('/entries/'+p['id']+'/amount',json={'quantity':{'value':500,'unit':'ml'},'revision':1})
        rename=Path.rename
        def fail(path,target):
            if path.name=='bls' and path.parent.name.startswith('.restore-'):raise OSError('simulated rename failure')
            return rename(path,target)
        with patch.object(Path,'rename',fail):r=await self.restore(archive)
        self.assertEqual(r.status_code,422,r.text)
        self.assertEqual(original.read_text(),'current-original')
        self.assertEqual(main.load_entry(p['id'])['quantity']['value'],500)
        self.assertEqual((await self.client.get('/health')).status_code,200)

    async def test_attachment_checksum_and_maintenance_gate(self):
        (main.DATA/'originals'/'test.txt').write_text('hello');archive,doc=await self.exported()
        bad=self.zip(doc,{'files/originals/test.txt':b'wrong'})
        self.assertEqual((await self.client.post('/backups/inspect',content=bad)).status_code,422)
        gate=main.app.state.backup_gate;gate.closed=True
        self.assertEqual((await self.client.get('/health')).status_code,503);gate.closed=False
        gate.active=2;entered=asyncio.Event()
        async def work():
            async with gate.exclusive():entered.set()
        task=asyncio.create_task(work());await asyncio.sleep(0)
        self.assertFalse(entered.is_set());self.assertTrue(gate.closed)
        async with gate.condition:gate.active=1;gate.condition.notify_all()
        await task;gate.active=0;self.assertTrue(entered.is_set());self.assertFalse(gate.closed)
