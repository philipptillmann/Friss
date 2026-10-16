import unittest
from unittest.mock import patch
import test_api as support
from app import main,authentication

class APIKeyTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp=support.ApiTests.asyncSetUp
    asyncTearDown=support.ApiTests.asyncTearDown
    async def test_reveal_requires_auth_and_is_not_cached(self):
        response=await self.client.post('/auth/api-key',headers={'Authorization':'bad'})
        self.assertEqual(response.status_code,401);self.assertNotIn(main.KEY,response.text)
        response=await self.client.post('/auth/api-key')
        self.assertEqual(response.status_code,200);self.assertEqual(response.json()['api_key'],main.KEY)
        self.assertEqual(response.headers['cache-control'],'no-store')
        self.assertEqual(response.headers['pragma'],'no-cache')

    async def test_password_login_and_missing_key(self):
        password='a-test-password'
        with patch.object(authentication,'PASSWORD_HASH',authentication.encode_password(password)):
            self.client.headers.pop('Authorization',None)
            self.client.headers['Origin']='http://test'
            self.assertEqual((await self.client.post('/auth/login',json={'password':password})).status_code,200)
            self.assertEqual((await self.client.post('/auth/api-key')).json()['api_key'],main.KEY)
            with patch.object(main,'KEY',''):
                self.assertEqual((await self.client.post('/auth/api-key')).json(),{'configured':False,'api_key':None})
            self.assertEqual((await self.client.post('/auth/api-key',headers={'Origin':'https://elsewhere.example'})).status_code,403)
