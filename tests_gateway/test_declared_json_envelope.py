"""Declared envelope compatibility does not relax JSON or stream completeness."""
import io,json,unittest
from cfm_id_llm.providers import OpenAICompatibleChatProvider,ProviderError
class Response(io.BytesIO):
    status=200
def stream(content,done=True,reason='stop'):
    event={'choices':[{'index':0,'delta':{'content':content},'finish_reason':reason}]}
    return ('data: '+json.dumps(event)+'\n\n'+('data: [DONE]\n\n' if done else '')).encode()
class DeclaredJSONEnvelopeTests(unittest.TestCase):
    def run_content(self,text,*,allowed=False,done=True,reason='stop'):
        p=OpenAICompatibleChatProvider(model='offline',api_key='LOCAL_TEST_SENTINEL',stream=True,
            allow_json_fence=allowed,transport=lambda *args,**kwargs:Response(stream(text,done,reason)))
        return p.generate_json(system_prompt='offline',user_prompt='offline'),p.last_diagnostics
    def test_default_rejects_fence(self):
        with self.assertRaises(ProviderError):self.run_content('```json\n{}\n```')
    def test_opt_in_accepts_only_declared_single_json_envelope(self):
        for text in ['{}','```json\n{}\n```',' \r\n```json\r\n{"x":"好"}\r\n```\n']:
            with self.subTest(text=text):
                result,d=self.run_content(text,allowed=True)
                self.assertIsInstance(result,dict)
                self.assertIn(d['json_envelope_received'],['bare','single_json_fence'])
    def test_no_preamble_suffix_multiple_blocks_or_missing_fence(self):
        for text in ['Here:\n```json\n{}\n```','```json\n{}\n```\nDone',
                     '```json\n{}\n```\n```json\n{}\n```','```json\n{}','```python\n{}\n```']:
            with self.subTest(text=text),self.assertRaises(ProviderError):self.run_content(text,allowed=True)
    def test_inner_json_never_repaired(self):
        for text in ['```json\n{"x":1,}\n```','```json\n[]\n```','```json\n{bad}\n```']:
            with self.subTest(text=text),self.assertRaises(ProviderError):self.run_content(text,allowed=True)
    def test_stream_finish_and_done_still_required(self):
        for done,reason in [(False,'stop'),(True,'length')]:
            with self.subTest(done=done,reason=reason),self.assertRaises(ProviderError):
                self.run_content('```json\n{}\n```',allowed=True,done=done,reason=reason)
    def test_boolean_option_is_strict(self):
        with self.assertRaises(ValueError):
            OpenAICompatibleChatProvider(model='offline',api_key='LOCAL',allow_json_fence='yes')
if __name__=='__main__':unittest.main()

