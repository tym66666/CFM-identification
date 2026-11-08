import json,unittest
from cfm_id_llm.providers.final_content_observer import FinalContentObservedChatProvider
from cfm_id_llm.providers.base import ProviderError

class Response:
    status=200
    def __init__(self,body):self.body=body
    def read(self,n):return json.dumps(self.body).encode()
    def __enter__(self):return self
    def __exit__(self,*args):pass

class FinalContentObserverTests(unittest.TestCase):
    def run_response(self,content,*,reason="stop",observer=None):
        self.seen=[];self.requests=[]
        def transport(request,*,timeout):
            self.requests.append(json.loads(request.data))
            return Response(dict(model="mock",choices=[dict(finish_reason=reason,message=dict(
                content=content,reasoning_content="PRIVATE_REASONING_FIELD_NEVER_CAPTURE"))]))
        p=FinalContentObservedChatProvider(final_content_observer=observer or self.seen.append,
            api_key="unit-test-key",model="mock",transport=transport,require_finish_reason=True)
        return p.generate_json(system_prompt="system",user_prompt="user")
    def test_valid_json_unchanged(self):
        self.assertEqual(self.run_response('{"x":1}'),{"x":1});self.assertEqual(self.seen,['{"x":1}'])
        self.assertEqual(len(self.requests),1)
    def test_invalid_json_retained_but_not_repaired(self):
        with self.assertRaises(ProviderError) as caught:self.run_response('{"x":[0]*6}')
        self.assertEqual(caught.exception.code,"MALFORMED_RESPONSE")
        self.assertEqual(self.seen,['{"x":[0]*6}']);self.assertEqual(len(self.requests),1)
    def test_api_credential_echo_redacted_in_observer(self):
        self.run_response('{"echo":"unit-test-key"}')
        self.assertEqual(self.seen,['{"echo":"[REDACTED]"}'])
    def test_reasoning_field_not_observed(self):
        self.run_response('{"status":"ok"}')
        self.assertNotIn("PRIVATE_REASONING",str(self.seen))
    def test_incomplete_generation_not_presented_as_final(self):
        with self.assertRaises(ProviderError):self.run_response('{"x":',reason="length")
        self.assertEqual(self.seen,[])
    def test_observer_failure_is_sanitized(self):
        def bad(_):raise RuntimeError("unit-test-key")
        with self.assertRaises(ProviderError) as caught:self.run_response('{"x":1}',observer=bad)
        self.assertEqual(caught.exception.code,"FINAL_CONTENT_OBSERVER_FAILED")
        self.assertNotIn("unit-test-key",str(caught.exception))
if __name__=="__main__":unittest.main()

