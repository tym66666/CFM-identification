import io,json,unittest
from copy import deepcopy
from cfm_id.structured_business_reading import StructuredBusinessReader
from cfm_id_llm.providers.base import ProviderError
from examples.bounded_policy_intake_fixture import make_case

class ReaderTests(unittest.TestCase):
    def fixture(self):
        return make_case(['甲','乙','丙'],[('甲','乙')],1,[1,1,1],['乙'])
    def transport(self,raw,calls):
        def send(req,**kw):
            calls.append(json.loads(req.data))
            return io.BytesIO(json.dumps(dict(object='response',status='completed',output=[
                dict(type='message',role='assistant',content=[dict(type='output_text',text=json.dumps(raw))])
            ])).encode())
        return send
    def reader(self,b,raw,calls,**kw):
        return StructuredBusinessReader(b,model='offline',api_key='not-a-real-key',
            base_url='https://example.invalid/v1',transport=self.transport(raw,calls),**kw)
    def test_complete_reading_is_only_unapproved_preview_and_frozen_bundle(self):
        b,raw,*_=self.fixture();calls=[];reader=self.reader(b,raw,calls)
        frozen=reader.request();b['documents']['goal.txt']='changed after construction'
        view=reader.read_once()
        self.assertEqual(view['state'],'REVIEW_REQUIRED');self.assertFalse(view['core_called'])
        self.assertEqual(view['reading_candidate'],raw);self.assertEqual(reader.request(),frozen)
        self.assertEqual(calls[0]['text']['format']['schema'],json.loads(frozen['user'])['output_schema'])
        self.assertFalse(calls[0]['store']);self.assertEqual(len(calls),1)
    def test_unknown_policy_preserved_without_repair(self):
        b,raw,*_=self.fixture();raw['reading']['questions']['q1']['first']['甲']=None
        calls=[];view=self.reader(b,raw,calls).read_once()
        self.assertEqual(view['state'],'NEEDS_INPUT')
        self.assertIsNone(view['reading_candidate']['reading']['questions']['q1']['first']['甲'])
    def test_bad_hierarchy_observed_but_rejected_once(self):
        b,raw,*_=self.fixture();raw['reading']['reported_assignment']=raw.pop('reported_assignment')
        calls=[];seen=[];reader=self.reader(b,raw,calls,final_content_observer=seen.append)
        with self.assertRaises(ProviderError) as ctx:reader.read_once()
        self.assertEqual(ctx.exception.code,'LOCAL_VALIDATION_FAILED')
        self.assertEqual(len(calls),1);self.assertEqual(json.loads(seen[0]),raw)

if __name__=='__main__':unittest.main()

