import io
import unittest
from unittest.mock import patch
import httpx
from PIL import Image
import zxingcpp
import test_api as support

def barcode(code,fmt=zxingcpp.BarcodeFormat.EAN13):
    bitmap=zxingcpp.write_barcode(fmt,code[:-1] if fmt==zxingcpp.BarcodeFormat.EAN8 else code,width=600,height=200)
    data=memoryview(bitmap)
    return Image.frombytes('L',(data.shape[1],data.shape[0]),data.tobytes())

def encoded(image):
    out=io.BytesIO();image.save(out,format='JPEG');return out.getvalue()

class BarcodeScanTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        await support.ApiTests.asyncSetUp(self)
        # This sandbox cannot wake the event loop from worker threads. Decode
        # real images inline in tests; production still uses the thread pool.
        async def inline(fn,*args): return fn(*args)
        self.worker_patch=patch('app.barcode_scan.run_in_threadpool',side_effect=inline)
        self.worker_patch.start()
    async def asyncTearDown(self):
        self.worker_patch.stop()
        await support.ApiTests.asyncTearDown(self)
    payload=support.ApiTests.payload

    async def test_retail_formats_rotation_and_multiple(self):
        for code,fmt in [('4006381333931',zxingcpp.BarcodeFormat.EAN13),('96385074',zxingcpp.BarcodeFormat.EAN8),('012345678905',zxingcpp.BarcodeFormat.UPCA)]:
            response=await self.client.post('/barcode-scan',content=encoded(barcode(code,fmt).rotate(90,expand=True)))
            self.assertEqual(response.status_code,200)
            self.assertIn(code,response.json()['barcodes'])
        first=barcode('4006381333931');second=barcode('5901234123457')
        combined=Image.new('L',(max(first.width,second.width),first.height+second.height+80),255)
        combined.paste(first,(0,0));combined.paste(second,(0,first.height+80))
        result=await self.client.post('/barcode-scan',content=encoded(combined))
        self.assertEqual(set(result.json()['barcodes']),{'4006381333931','5901234123457'})
        self.assertEqual((await self.client.get('/entries')).json(),[])

    async def test_invalid_blank_and_auth(self):
        self.assertEqual((await self.client.post('/barcode-scan',content=b'no image')).status_code,422)
        self.assertEqual((await self.client.post('/barcode-scan',content=encoded(Image.new('RGB',(200,200),'white')))).status_code,422)
        self.assertEqual((await self.client.post('/barcode-scan',content=b'x',headers={'Authorization':'bad'})).status_code,401)
        self.assertEqual((await self.client.post('/barcode-scan',content=b'x'*(10*1024*1024+1))).status_code,413)

    async def test_scanned_code_open_food_facts_and_quantity(self):
        result=await self.client.post('/barcode-scan',content=encoded(barcode('4006381333931')))
        code=result.json()['barcodes'][0]
        def lookup(request):
            self.assertIn('/product/'+code+'.json',str(request.url))
            return httpx.Response(200,json={'status':1,'product':{'product_name':'Test food','nutriments':{'energy-kcal_100g':200,'proteins_100g':10}}})
        upstream=httpx.AsyncClient(transport=httpx.MockTransport(lookup))
        with patch('app.main.httpx.AsyncClient',return_value=upstream):
            response=await self.client.post('/entries',json=self.payload(type='barcode',drink=None,barcode=code,quantity={'value':150,'unit':'g'}))
        entry=response.json()
        self.assertEqual(entry['status'],'processed')
        self.assertEqual(entry['nutrients']['dietaryEnergyConsumed'],{'value':300,'unit':'kcal'})
        self.assertEqual(entry['nutrients']['dietaryProtein'],{'value':15,'unit':'g'})
