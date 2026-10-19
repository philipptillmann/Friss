import hashlib
import io
import unittest
from uuid import uuid4
from unittest.mock import patch
import zipfile
from PIL import Image
import test_api as support
from app import main,entry_photos

class EntryPhotoTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp=support.ApiTests.asyncSetUp
    asyncTearDown=support.ApiTests.asyncTearDown
    payload=support.ApiTests.payload

    def image(self,fmt='JPEG',color='red'):
        out=io.BytesIO();Image.new('RGB',(20,12),color).save(out,format=fmt);return out.getvalue()

    async def meal(self):
        body={'timestamp':'2026-10-19T12:00:00+02:00','original_message':'Lunch photo','ai':{'title':'Lunch','quantity':{'value':200,'unit':'g'},'nutrients':{'dietaryEnergyConsumed':{'value':300,'unit':'kcal'}}}}
        r=await self.client.post('/json-import',json=body);self.assertEqual(r.status_code,201,r.text)
        return body,r.json()

    async def test_ai_upload_multiple_retry_view_and_unchanged_nutrition(self):
        body,meal=await self.meal();id=meal['entry_id'];self.assertEqual(id,meal['entry_ids'][0])
        url=meal['photo_upload_url'];self.assertEqual(url,'/entries/'+id+'/photos')
        before=main.load_entry(id)
        for fmt in ['JPEG','PNG','WEBP']:
            raw=self.image(fmt)
            r=await self.client.put(url,content=raw,headers={'Content-Type':'image/'+fmt.lower()});self.assertEqual(r.status_code,200,r.text)
            photo=r.json();self.assertEqual(photo['id'],hashlib.sha256(raw).hexdigest())
            repeat=await self.client.put(url,content=raw);self.assertEqual(repeat.json(),photo)
            original=await self.client.get(photo['url']);self.assertEqual(original.content,raw);self.assertIn('no-store',original.headers['cache-control'])
        self.assertEqual(len((await self.client.get(url)).json()),3)
        self.assertEqual(main.load_entry(id),before,'attaching photos must not change nutrients, timestamps or Health status')
        retry=await self.client.post('/json-import',json=body);self.assertEqual(retry.json(),meal)
        detail=(await self.client.get('/entries/'+id+'/details')).json();self.assertEqual(len(detail['photos']),3)

    async def test_auth_invalid_image_missing_entry_and_limits(self):
        _,meal=await self.meal();url=meal['photo_upload_url'];raw=self.image()
        self.assertEqual((await self.client.put(url,content=raw,headers={'Authorization':'bad'})).status_code,401)
        for bad in [b'',b'{"photo":"base64"}',b'\xff\xd8\xffbroken']:
            self.assertEqual((await self.client.put(url,content=bad)).status_code,422)
        self.assertEqual((await self.client.put('/entries/'+str(uuid4())+'/photos',content=raw)).status_code,404)
        with patch.object(entry_photos,'MAX_BYTES',10):self.assertEqual((await self.client.put(url,content=raw)).status_code,413)
        with patch.object(entry_photos,'MAX_PIXELS',10):self.assertEqual((await self.client.put(url,content=raw)).status_code,422)
        photo=(await self.client.put(url,content=raw)).json()
        for method,path in [('get',url),('get',photo['url'])]:self.assertEqual((await self.client.request(method,path,headers={'Authorization':'bad'})).status_code,401)
        other=self.payload();await self.client.post('/entries',json=other)
        self.assertEqual((await self.client.get('/entries/'+other['id']+'/photos/'+photo['id'])).status_code,404)
        with patch.object(entry_photos,'MAX_PHOTOS',1):
            self.assertEqual((await self.client.put(url,content=raw)).status_code,200)
            self.assertEqual((await self.client.put(url,content=self.image(color='blue'))).status_code,422)
        self.assertEqual(len((await self.client.get(url)).json()),1)

    async def test_photo_copy_and_zip_restore(self):
        _,meal=await self.meal();raw=self.image();photo=(await self.client.put(meal['photo_upload_url'],content=raw)).json()
        copied=(await self.client.post('/entries/'+meal['entry_id']+'/copy',json={'id':str(uuid4()),'timestamp':'2026-10-20T12:00:00+02:00'})).json()
        photos=(await self.client.get('/entries/'+copied['id']+'/photos')).json();self.assertEqual(len(photos),1)
        self.assertEqual((await self.client.get(photos[0]['url'])).content,raw)
        archive=await self.client.get('/backups/export');self.assertEqual(archive.status_code,200)
        with zipfile.ZipFile(io.BytesIO(archive.content)) as z:self.assertTrue(any('-photo-'+photo['id'] in n for n in z.namelist()))
        for path in entry_photos.stored(main.DATA,meal['entry_id']):path.unlink()
        restored=await self.client.post('/backups/restore',content=archive.content,headers={'X-Friss-Restore':'replace'});self.assertEqual(restored.status_code,200,restored.text)
        self.assertEqual((await self.client.get(photo['url'])).content,raw)

    async def test_recipe_duplicate_keeps_ingredient_photos(self):
        recipe={'id':str(uuid4()),'name':'Drink','category':'drink','servings':1}
        await self.client.post('/recipes',json=recipe)
        p=self.payload(recipe_id=recipe['id']);await self.client.post('/entries',json=p)
        raw=self.image('PNG');await self.client.put('/entries/'+p['id']+'/photos',content=raw)
        duplicate=await self.client.post('/recipes/'+recipe['id']+'/duplicate',json={'id':str(uuid4()),'name':'Copy'})
        self.assertEqual(duplicate.status_code,201,duplicate.text)
        ingredient=duplicate.json()['ingredients'][0]
        photos=(await self.client.get('/entries/'+ingredient['id']+'/photos')).json();self.assertEqual(len(photos),1)
        self.assertEqual((await self.client.get(photos[0]['url'])).content,raw)
