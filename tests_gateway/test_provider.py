from __future__ import annotations
import io
import json
import unittest
from urllib.error import HTTPError, URLError
from cfm_id_llm.providers import MockProvider, OpenAICompatibleChatProvider, ProviderError


class FakeHTTP:
    def __init__(self, data: bytes):
        self.data=data
    def read(self, cap):
        return self.data
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False


class ProviderTests(unittest.TestCase):
    def test_mock_deep_copy(self):
        p=MockProvider({'x':{'val':1}})
        a=p.generate_json(system_prompt='s',user_prompt='u')
        a['x']['val']=2
        b=p.generate_json(system_prompt='s',user_prompt='u')
        self.assertEqual(b['x']['val'],1)
        self.assertEqual(p.calls,2)

    def test_real_provider_no_key_is_rejected(self):
        with self.assertRaises(ValueError):
            self._construct_no_key()

    @staticmethod
    def _construct_no_key():
        from unittest.mock import patch
        with patch.dict('os.environ', {'CFM_ID_LLM_API_KEY':'', 'OPENAI_API_KEY':''}):
            return OpenAICompatibleChatProvider(model='test', api_key=None)

    def test_http_rejected_nonlocal(self):
        with self.assertRaises(ValueError):
            OpenAICompatibleChatProvider(model='test',api_key='secret',base_url='http://example.org/v1')

    def test_local_http_allowed(self):
        p=OpenAICompatibleChatProvider(model='test',api_key='secret',base_url='http://localhost:9000/v1',
                                       transport=lambda *a,**kw: FakeHTTP(b'{"choices":[{"message":{"content":"{}"}}]}'))
        self.assertEqual(p.generate_json(system_prompt='s',user_prompt='u'),{})

    def test_openai_compatible_json_response(self):
        captured=[]
        def transport(req,*,timeout):
            captured.append((req,timeout))
            return FakeHTTP(json.dumps({'choices':[{'message':{'content':'{"target":"ok"}'}}]}).encode())
        p=OpenAICompatibleChatProvider(model='tester',api_key='secret',base_url='https://endpoint.example/v1', transport=transport)
        self.assertEqual(p.generate_json(system_prompt='s',user_prompt='u'),{'target':'ok'})
        body=json.loads(captured[0][0].data)
        self.assertEqual(body['response_format'],{'type':'json_object'})
        self.assertEqual(body['model'],'tester')
        self.assertEqual(captured[0][0].get_header('Authorization'),'Bearer secret')

    def test_bad_response_json(self):
        p=OpenAICompatibleChatProvider(model='tester',api_key='secret',
           transport=lambda *a,**kw: FakeHTTP(b'{"choices":[{"message":{"content":"not-json"}}]}'))
        with self.assertRaises(ProviderError):p.generate_json(system_prompt='s',user_prompt='u')

    def test_http_error_does_not_leak_key(self):
        def err(*a,**kw):raise HTTPError('https://example.test',401,'bad auth',{},io.BytesIO(b'secret-token'))
        p=OpenAICompatibleChatProvider(model='tester',api_key='secret-token',transport=err)
        with self.assertRaises(ProviderError) as cm:p.generate_json(system_prompt='s',user_prompt='u')
        self.assertNotIn('secret-token',str(cm.exception))
        self.assertIn('401',str(cm.exception))

    def test_refusal_fails_closed(self):
        p=OpenAICompatibleChatProvider(model='tester',api_key='secret',
          transport=lambda *a,**kw: FakeHTTP(b'{"choices":[{"message":{"refusal":"no","content":"{}"}}]}'))
        with self.assertRaises(ProviderError):p.generate_json(system_prompt='s',user_prompt='u')


if __name__ == '__main__':unittest.main()
