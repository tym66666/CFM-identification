"""DAG request provenance constraints and retained epistemic states; offline only."""
from copy import deepcopy
import io,json,unittest
from cfm_id_llm.dag_reading import make_request,parse
from cfm_id_llm.providers.base import ProviderError
from cfm_id_llm.providers.openai_responses import OpenAICompatibleResponsesProvider
from cfm_id.dag_business import inspect_candidate
from evaluation.dag_business_workflow import read_once
from examples.dag_business_reference import cases


class DagRequestContractTests(unittest.TestCase):
    def setUp(self):
        case=cases()[0];self.bundle=case['bundle'];self.wire=case['reference']

    def provider(self,wire):
        request=make_request(self.bundle);self.payload=json.loads(request['user'])
        self.sent=[];self.observed=[]
        response=dict(object='response',status='completed',output=[dict(type='message',role='assistant',
            status='completed',content=[dict(type='output_text',text=json.dumps(wire,ensure_ascii=False))])])
        def transport(req,*,timeout):
            self.sent.append(json.loads(req.data))
            return io.BytesIO(json.dumps(response,ensure_ascii=False).encode('utf8'))
        return OpenAICompatibleResponsesProvider(model='offline-test',api_key='OFFLINE_TEST_TOKEN',
            base_url='https://example.invalid/v1',schema=self.payload['output_schema'],
            schema_name='dag_business_reading',local_validator=lambda candidate:parse(self.bundle,candidate),
            transport=transport,final_content_observer=self.observed.append)

    def test_request_constraints_follow_each_catalog_without_cross_request_state(self):
        a=json.loads(make_request(self.bundle)['user'])
        changed=deepcopy(self.bundle);changed['question']+=' 这是一份新修订的研究提问。'
        b=json.loads(make_request(changed)['user'])
        self.assertNotEqual(set(a['source_catalog']),set(b['source_catalog']))
        for payload in (a,b):
            schema=payload['output_schema'];allowed=schema['$defs']['SourceId']['enum']
            self.assertEqual(set(allowed),set(payload['source_catalog']))
            self.assertEqual(len(allowed),len(set(allowed)));self.assertNotIn('src_0',allowed)
            for field in ('Variable','Relation','Claim','Target','Information','Note'):
                self.assertEqual(schema['$defs'][field]['properties']['source_ids']['items'],
                                 {'$ref':'#/$defs/SourceId'})
            self.assertEqual(schema['properties']['adjustment_source_ids']['items'],
                             {'$ref':'#/$defs/SourceId'})
        self.assertEqual(a,json.loads(make_request(self.bundle)['user']))

    def test_catalog_schema_reaches_transport_without_approving_candidate(self):
        provider=self.provider(self.wire)
        result=read_once(self.bundle,provider,allow_external=True,allow_document_sharing=True)
        self.assertEqual(len(self.sent),1)
        self.assertEqual(self.sent[0]['text']['format']['schema'],self.payload['output_schema'])
        self.assertEqual(result['state'],'REVIEW_REQUIRED')
        self.assertFalse(result['backend_called']);self.assertIsNone(result['certificate'])
        self.assertEqual(json.loads(self.observed[0]),self.wire)

    def test_server_ignoring_enum_cannot_turn_bad_source_into_valid_candidate(self):
        wire=deepcopy(self.wire);wire['target']['source_ids'].append('src_0')
        provider=self.provider(wire);request=make_request(self.bundle)
        with self.assertRaises(ProviderError) as caught:
            provider.generate_json(system_prompt=request['system'],user_prompt=request['user'])
        self.assertEqual(caught.exception.code,'LOCAL_VALIDATION_FAILED')
        self.assertEqual(len(self.sent),1);self.assertEqual(json.loads(self.observed[0]),wire)
        self.assertEqual(inspect_candidate(self.bundle,wire)['state'],'CHECK_BLOCKED')

    def test_unknown_false_and_true_remain_distinct_without_automatic_approval(self):
        for value,state,reason in [(None,'NEEDS_INPUT','FACTS_OR_TARGET_NEED_CLARIFICATION'),
                                   (False,'UNSUPPORTED','NONPOSITIVE_LAW_NOT_ADAPTED'),
                                   (True,'REVIEW_REQUIRED',None)]:
            wire=deepcopy(self.wire);wire['information']['positivity']['value']=value
            result=inspect_candidate(self.bundle,wire)
            self.assertEqual(result['state'],state)
            self.assertEqual(result['wire_candidate'],wire)
            self.assertFalse(result['backend_called']);self.assertIsNone(result['certificate'])
            if value is False:self.assertEqual(result['reason_code'],reason)


if __name__=='__main__':unittest.main()

