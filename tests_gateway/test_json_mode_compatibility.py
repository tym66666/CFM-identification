"""Opting out of remote JSON mode must not relax local acceptance or retry."""
import io
import json
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
from cfm_id_llm.providers import OpenAICompatibleChatProvider, ProviderError, MockProvider
from cfm_id_llm.quality_formulator import A0QualityFormulatorV010, A0QualityValidationError
from cfm_id_llm.schemas import BusinessCase
from cfm_id_llm import quality_cli
from evaluation import nbib_semantic_eval as nbib

class Response(io.BytesIO):
    status=200

def envelope(content, finish='stop'):
    return json.dumps({'choices':[{'message':{'content':content},'finish_reason':finish}]}).encode()

class JsonModeCompatibilityTests(unittest.TestCase):
    def provider(self,wire,**kw):
        self.calls=[]
        def transport(req,**options):
            self.calls.append(json.loads(req.data))
            return Response(wire)
        return OpenAICompatibleChatProvider(model='offline-test',api_key='OFFLINE_ONLY',
                                             transport=transport,**kw)
    def generate(self,p):
        return p.generate_json(system_prompt='只返回 JSON',user_prompt='原始业务材料')

    def test_default_keeps_mode_and_opt_out_preserves_messages(self):
        p=self.provider(envelope('{}'))
        self.assertEqual(self.generate(p),{})
        before=self.calls[0]
        self.assertEqual(before['response_format'],{'type':'json_object'})
        self.assertTrue(p.last_diagnostics['json_mode_sent'])
        p=self.provider(envelope('{}'),json_mode=False)
        self.assertEqual(self.generate(p),{})
        after=self.calls[0]
        self.assertNotIn('response_format',after)
        before.pop('response_format')
        self.assertEqual(before,after)
        self.assertFalse(p.last_diagnostics['json_mode_sent'])

    def test_off_still_rejects_non_object_or_non_json(self):
        for content in ['not json','[]','null','~~~json\n{}\n~~~']:
            with self.subTest(content=content):
                p=self.provider(envelope(content),json_mode=False)
                with self.assertRaises(ProviderError):
                    self.generate(p)
                self.assertEqual(len(self.calls),1)

    def test_off_still_rejects_truncation_and_missing_done(self):
        for wire,stream,code in [
            (envelope('{}','length'),False,'INCOMPLETE_COMPLETION'),
            (b'data: {"choices":[{"delta":{"content":"{}"},"finish_reason":"stop"}]}\n\n',
             True,'INCOMPLETE_STREAM')]:
            with self.subTest(stream=stream):
                p=self.provider(wire,json_mode=False,stream=stream)
                with self.assertRaises(ProviderError) as caught:self.generate(p)
                self.assertEqual(caught.exception.code,code)
                self.assertEqual(len(self.calls),1)

    def test_off_preserves_a0_target_and_quote_rejections(self):
        entry={'case_id':'LOCAL','business_question':'想知道全员推广后的团队表现。',
               'expected':[{'kind':'FIXED_POLICY_VALUE','quote':'全员推广后的团队表现'}]}
        case=BusinessCase(case_id='LOCAL',business_question=entry['business_question'])
        for error in ['target','quote']:
            with self.subTest(error=error):
                raw=nbib.make_reference_only_fixture(entry)
                if error=='target':raw['shared_draft']['target']['description']['value']='另一个目标'
                else:raw['queries'][0]['business_goal']['evidence'][0]['quote']='来源不存在的引文'
                p=self.provider(envelope(json.dumps(raw,ensure_ascii=False)),json_mode=False)
                with self.assertRaises(A0QualityValidationError) as caught:
                    A0QualityFormulatorV010(p).formulate(case)
                expected='A0_SCHEMA_REJECTED' if error=='target' else 'A0_PROVENANCE_OR_AUDIT_REJECTED'
                self.assertEqual(caught.exception.code,expected)
                self.assertEqual(len(self.calls),1)

    def test_cli_forwards_explicit_off(self):
        p=self.provider(envelope('{}'),json_mode=False)
        with tempfile.TemporaryDirectory() as tmp:
            output=Path(tmp)/'result.json'
            with patch.object(quality_cli,'OpenAICompatibleChatProvider',return_value=p) as ctor:
                with patch('sys.stderr',new_callable=io.StringIO):
                    rc=quality_cli.main(['--question','希望了解全员推广后的团队表现',
                        '--provider','openai-chat','--model','offline-test','--allow-external',
                        '--json-mode','off','--format','json','--output',str(output)])
            self.assertEqual(rc,2)
            self.assertFalse(ctor.call_args.kwargs['json_mode'])
            self.assertFalse(json.loads(output.read_text(encoding='utf8'))['core_called'])

    def test_nbib_forwards_explicit_off(self):
        p=MockProvider({})
        with patch.object(nbib,'OpenAICompatibleChatProvider',return_value=p) as ctor:
            result,_=nbib.evaluate(provider_name='openai-chat',model='offline-test',
                max_cases=1,allow_external=True,allow_document_sharing=True,json_mode=False)
        self.assertFalse(ctor.call_args.kwargs['json_mode'])
        self.assertFalse(result['cases'][0]['schema_and_quote_checks_passed'])

    def test_invalid_option_types_fail_before_transport(self):
        for value in (None,0,1,'off'):
            with self.subTest(value=value),self.assertRaises(ValueError):
                self.provider(envelope('{}'),json_mode=value)
            self.assertEqual(self.calls,[])

    def test_transport_failure_never_falls_back_or_retries(self):
        calls=[]
        def fail(req,**kw):
            calls.append(1)
            raise TimeoutError('private diagnostic detail')
        p=OpenAICompatibleChatProvider(model='offline-test',api_key='OFFLINE_ONLY',
            json_mode=False,transport=fail)
        with self.assertRaises(ProviderError) as caught:self.generate(p)
        self.assertEqual(caught.exception.code,'TIMEOUT')
        self.assertEqual(calls,[1])
        self.assertNotIn('private diagnostic detail',str(caught.exception))

if __name__=='__main__':unittest.main()

