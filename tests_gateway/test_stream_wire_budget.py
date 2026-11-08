"""Wire-limit regression: long SSE framing, preserved privacy and hard caps."""
import io,json,unittest
from cfm_id_llm.providers.openai_chat import OpenAICompatibleChatProvider
from cfm_id_llm.providers.reasoning_stream import ReasoningStreamProviderV036
from cfm_id_llm.providers.base import ProviderError
def event(x):return b'data: '+json.dumps(x).encode()+b'\n\n'
def body():
 return (event({'choices':[{'delta':{'reasoning_content':'PRIVATE_TEST_TRACE'*1000}}]})*130+
  event({'choices':[{'delta':{'content':'{"ok":true}'},'finish_reason':'stop'}]})+b'data: [DONE]\n\n')
class StreamWireBudget(unittest.TestCase):
 def make(self,cls,wire,**kwargs):
  self.sent=0
  def transport(*args,**kw):self.sent+=1;return io.BytesIO(wire)
  return cls(model='offline',api_key='AUTH_TEST_SENTINEL',transport=transport,**kwargs)
 def run_request(self,p):return p.generate_json(system_prompt='JSON',user_prompt='offline')
 def test_reasoning_stream_over_two_megabytes_completes_once(self):
  wire=body();self.assertGreater(len(wire),2000000);self.assertLess(len(wire),8000000)
  p=self.make(ReasoningStreamProviderV036,wire)
  self.assertEqual(self.run_request(p),{'ok':True});self.assertEqual(self.sent,1)
  self.assertGreater(p.progress()['response_bytes'],2000000)
  self.assertNotIn('PRIVATE_TEST_TRACE',json.dumps(p.progress()))
  self.assertNotIn('AUTH_TEST_SENTINEL',json.dumps(p.progress()))
 def test_ordinary_stream_keeps_existing_default_cap(self):
  p=self.make(OpenAICompatibleChatProvider,body(),stream=True)
  with self.assertRaises(ProviderError) as cm:self.run_request(p)
  self.assertEqual(cm.exception.code,'RESPONSE_TOO_LARGE');self.assertEqual(self.sent,1)
 def test_explicit_small_cap_still_stops_heartbeats(self):
  p=self.make(ReasoningStreamProviderV036,b': heartbeat\n\n'*20,max_stream_wire_bytes=50)
  with self.assertRaises(ProviderError) as cm:self.run_request(p)
  self.assertEqual(cm.exception.code,'RESPONSE_TOO_LARGE');self.assertEqual(self.sent,1)
 def test_larger_wire_cap_does_not_relax_event_or_final_content_caps(self):
  for wire in [b'data: '+b'x'*65536+b'\n\n',
   b''.join(event({'choices':[{'delta':{'content':'x'*10000}}]}) for _ in range(36))]:
   p=self.make(ReasoningStreamProviderV036,wire)
   with self.assertRaises(ProviderError) as cm:self.run_request(p)
   self.assertEqual(cm.exception.code,'RESPONSE_TOO_LARGE')
 def test_limit_validation_and_per_instance_isolation(self):
  for v in [0,-1,True,1.5,32000001]:
   with self.assertRaises(ValueError):self.make(ReasoningStreamProviderV036,b'',max_stream_wire_bytes=v)
  a=self.make(ReasoningStreamProviderV036,b'',max_stream_wire_bytes=4000000)
  b=self.make(OpenAICompatibleChatProvider,b'')
  self.assertEqual(a.max_stream_wire_bytes,4000000);self.assertEqual(b.max_stream_wire_bytes,2000000)
if __name__=='__main__':unittest.main()

