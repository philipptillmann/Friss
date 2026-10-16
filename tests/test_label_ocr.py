import io
import shutil
import subprocess
import unittest
from unittest.mock import patch,AsyncMock
from PIL import Image,ImageDraw,ImageFont
from fastapi import HTTPException
from app import label_ocr
import test_api as support

LABEL='''Nutrition per 100 g
Energy 840 kJ / 200 kcal
Fat 10 g
of which saturated fat 3.5 g
Carbohydrates 20 g
of which sugars 4 g
Fibre 2 g
Protein 6 g
Salt 1.25 g
Vitamin B12 2.5 µg
'''
class LabelParserTests(unittest.TestCase):
    def test_eu_values_units_salt_and_missing(self):
        n=label_ocr.parse(LABEL)['nutrients']
        self.assertEqual(n['dietaryEnergyConsumed']['value'],200)
        self.assertEqual(n['dietaryFatTotal']['value'],10)
        self.assertEqual(n['dietaryFatSaturated']['value'],3.5)
        self.assertEqual(n['dietaryCarbohydrates']['value'],20)
        self.assertEqual(n['dietarySodium']['value'],500)
        self.assertEqual(n['dietaryVitaminB12']['unit'],'mcg')
        self.assertNotIn('dietaryVitaminC',n)
        german=label_ocr.parse('Pro 100 g\nBrennwert 418,4 kJ\nEiweiß 4,5 g\nKohlenhydrate 12 g\ndavon Zucker 3,2 g\nFett < 1 g\nCalcium 120 mg')
        self.assertAlmostEqual(german['nutrients']['dietaryEnergyConsumed']['value'],100)
        self.assertEqual(german['nutrients']['dietaryProtein']['value'],4.5)
        self.assertNotIn('dietaryFatTotal',german['nutrients'])

    def test_unsafe_basis_ambiguous_columns_and_conflicts(self):
        for text in ['Per serving\nFat 2 g','Per 100 ml\nFat 2 g','Nutrition Facts per 100 g\nTotal carbohydrate 20 g','Per 100 g / per portion\nFat 2 g 1 g']:
            self.assertEqual(label_ocr.parse(text)['nutrients'],{})
        data=label_ocr.parse('Per 100 g\nFat 10 g 5 g\nProtein 4 g\nProtein 6 g\nCarbohydrates 123 g')
        self.assertEqual(data['nutrients'],{})

    def test_image_validation_timeout_and_missing_binary(self):
        with self.assertRaises(HTTPException):label_ocr.scan(b'not an image')
        image=Image.new('RGB',(100,100),'white');out=io.BytesIO();image.save(out,format='PNG')
        for error,code in [(FileNotFoundError(),503),(subprocess.TimeoutExpired('tesseract',25),422)]:
            with patch.object(label_ocr.subprocess,'run',side_effect=error):
                with self.assertRaises(HTTPException) as ctx:label_ocr.scan(out.getvalue())
                self.assertEqual(ctx.exception.status_code,code)

    @unittest.skipUnless(shutil.which('tesseract'),'Tesseract is not installed')
    def test_actual_printed_label_ocr(self):
        image=Image.new('RGB',(1100,650),'white');draw=ImageDraw.Draw(image)
        font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',36)
        for i,line in enumerate(LABEL.replace('µg','mcg').splitlines()):draw.text((35,25+i*52),line,font=font,fill='black')
        out=io.BytesIO();image.save(out,format='PNG')
        result=label_ocr.scan(out.getvalue())
        self.assertEqual(result['basis'],'100g')
        self.assertEqual(result['nutrients']['dietaryEnergyConsumed']['value'],200)
        self.assertEqual(result['nutrients']['dietaryFatTotal']['value'],10)

class LabelApiTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp=support.ApiTests.asyncSetUp
    asyncTearDown=support.ApiTests.asyncTearDown
    async def test_auth_preview_and_no_ingredient_created(self):
        result=label_ocr.parse(LABEL)
        with patch.object(label_ocr,'run_in_threadpool',AsyncMock(return_value=result)) as scan:
            self.assertEqual((await self.client.post('/manual-ingredients/scan-label',content=b'image',headers={'Authorization':'bad'})).status_code,401)
            scan.assert_not_awaited()
            response=await self.client.post('/manual-ingredients/scan-label',content=b'image')
            self.assertEqual(response.status_code,200)
            self.assertEqual(response.json()['nutrients']['dietaryProtein']['value'],6)
        self.assertEqual((await self.client.get('/manual-ingredients')).json(),[])
