"""Offline protocol and rejection regressions. No credentials or real sockets."""
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError
from cfm_id_llm.providers import OpenAICompatibleChatProvider, ProviderError, MockProvider
from cfm_id_llm.quality_formulator import A0QualityFormulatorV010, A0QualityValidationError
from cfm_id_llm.quality_prompts import make_quality_user_prompt, PROMPT_VERSION_V010
from cfm_id_llm.schemas import BusinessCase
from cfm_id_llm import quality_cli
from evaluation import nbib_semantic_eval as nbib

PRIVATE = 'PRIVATE_SOURCE_OR_KEY_SENTINEL'


class Response(io.BytesIO):
    status = 200


def event(value):
    return b'data: ' + json.dumps(value, ensure_ascii=False).encode('utf8') + b'\n\n'


def chunk(text=None, finish=None, **delta):
    if text is not None:
        delta['content'] = text
    return {'choices': [{'index': 0, 'delta': delta, 'finish_reason': finish}]}


def envelope(content='{}', finish='stop'):
    return json.dumps({'choices': [{'message': {'content': content}, 'finish_reason': finish}]}).encode()


class ChatTransportTests(unittest.TestCase):
    def provider(self, wire, **options):
        self.requests = []
        def transport(req, *, timeout):
            self.requests.append((req, timeout))
            return Response(wire)
        return OpenAICompatibleChatProvider(model='test', api_key=PRIVATE, transport=transport, **options)

    def generate(self, provider):
        return provider.generate_json(system_prompt=PRIVATE, user_prompt=PRIVATE)

    def error(self, provider, code):
        with self.assertRaises(ProviderError) as caught:
            self.generate(provider)
        exc = caught.exception
        self.assertEqual(exc.code, code)
        self.assertNotIn(PRIVATE, str(exc) + json.dumps(exc.diagnostics))
        self.assertEqual(exc.diagnostics['transport_calls'], 1)
        return exc

    def test_default_payload_has_no_implicit_extensions(self):
        self.assertEqual(self.generate(self.provider(envelope())), {})
        body = json.loads(self.requests[0][0].data)
        for key in ('stream', 'thinking', 'max_completion_tokens'):
            self.assertNotIn(key, body)

    def test_explicit_parameters_and_unicode_sse(self):
        wire = (b': heartbeat\r\n\r\n' + event(chunk(reasoning_content=PRIVATE)) +
                event(chunk('{"status":')) + event(chunk('"好"}', 'stop')) +
                event({'choices': [], 'usage': {'completion_tokens': 4}}) + b'data: [DONE]\n\n')
        p = self.provider(wire, stream=True, thinking='disabled', timeout=180, max_completion_tokens=2048)
        self.assertEqual(self.generate(p), {'status': '好'})
        body = json.loads(self.requests[0][0].data)
        self.assertEqual(body['thinking'], {'type': 'disabled'})
        self.assertTrue(body['stream'])
        self.assertEqual(body['max_completion_tokens'], 2048)
        self.assertEqual(self.requests[0][1], 180)
        self.assertEqual(p.last_diagnostics['finish_reason'], 'stop')
        self.assertNotIn(PRIVATE, json.dumps(p.last_diagnostics))
        self.assertEqual(p.last_diagnostics['content_characters'], len('{"status":"好"}'))

    def test_multiline_sse_event(self):
        wire = b'data: {"choices":\ndata: [{"index":0,"delta":{"content":"{}"},"finish_reason":"stop"}]}\n\ndata: [DONE]\n\n'
        self.assertEqual(self.generate(self.provider(wire, stream=True)), {})

    def test_parseable_but_truncated_nonstream_is_rejected(self):
        for reason in ('length', 'content_filter', 'tool_calls', PRIVATE):
            with self.subTest(reason=reason):
                self.error(self.provider(envelope(finish=reason)), 'INCOMPLETE_COMPLETION')

    def test_nonstream_missing_finish_reason_remains_compatible(self):
        self.assertEqual(self.generate(self.provider(b'{"choices":[{"message":{"content":"{}"}}]}')), {})

    def test_parseable_stream_requires_stop_and_done(self):
        for wire in (event(chunk('{}')) + b'data: [DONE]\n\n',
                     event(chunk('{}', 'stop')),
                     event(chunk('{}', 'length')) + b'data: [DONE]\n\n'):
            with self.subTest(wire=wire):
                self.error(self.provider(wire, stream=True),
                           'INCOMPLETE_COMPLETION' if b'length' in wire else 'INCOMPLETE_STREAM')

    def test_stream_refusal_or_provider_error_is_not_json(self):
        self.error(self.provider(event(chunk(refusal=PRIVATE)), stream=True), 'MODEL_REFUSAL')
        self.error(self.provider(event({'error': {'message': PRIVATE}}), stream=True), 'MALFORMED_RESPONSE')

    def test_wrong_response_shapes_are_safe_errors(self):
        for wire in (b'[]', b'null', b'{"choices":[{"message":"bad"}]}',
                     b'{"choices":[{"message":{"content":null}}]}',
                     envelope(content='[]'), envelope(content='~~~json\n{}\n~~~')):
            with self.subTest(wire=wire):
                with self.assertRaises(ProviderError) as caught:
                    self.generate(self.provider(wire))
                self.assertNotIn(PRIVATE, str(caught.exception) + json.dumps(caught.exception.diagnostics))
        self.error(self.provider(event({'choices': [PRIVATE]}), stream=True), 'MALFORMED_RESPONSE')

    def test_nonstream_response_size_bound(self):
        self.error(self.provider(b' ' * 350001), 'RESPONSE_TOO_LARGE')

    def test_sse_event_size_bound(self):
        self.error(self.provider(b'data: ' + b'x' * 65536 + b'\n\n', stream=True), 'RESPONSE_TOO_LARGE')

    def test_sse_content_size_bound(self):
        with patch('cfm_id_llm.providers.openai_chat._CONTENT_LIMIT', 3):
            self.error(self.provider(event(chunk('{"x":1}')), stream=True), 'RESPONSE_TOO_LARGE')

    def test_sse_wire_limit_counts_heartbeats(self):
        with patch('cfm_id_llm.providers.openai_chat._STREAM_WIRE_LIMIT', 10):
            self.error(self.provider(b': ping\n\n' * 4, stream=True), 'RESPONSE_TOO_LARGE')

    def test_elapsed_stream_bound_without_real_sleep(self):
        with patch('cfm_id_llm.providers.openai_chat.time.monotonic', side_effect=[0, 0, 2, 2]):
            self.error(self.provider(b'', stream=True, max_stream_seconds=1), 'STREAM_TIME_LIMIT')

    def test_timeout_after_partial_content_is_not_retried(self):
        class Stalled(Response):
            def readline(self, cap):
                value = super().readline(cap)
                if not value:
                    raise TimeoutError(PRIVATE)
                return value
        calls = []
        def transport(*a, **kw):
            calls.append(1)
            return Stalled(event(chunk('{"secret":"')))
        p = OpenAICompatibleChatProvider(model='test', api_key=PRIVATE, stream=True, transport=transport)
        exc = self.error(p, 'TIMEOUT')
        self.assertEqual(len(calls), 1)
        self.assertGreater(exc.diagnostics['content_characters'], 0)
        self.assertEqual(exc.diagnostics['stage'], 'response')
        self.assertEqual(exc.diagnostics['http_status'], 200)

    def test_safe_http_failure_and_no_implicit_retry(self):
        calls = []
        body = Response(PRIVATE.encode())
        def transport(*a, **kw):
            calls.append(1)
            raise HTTPError('https://invalid.test/' + PRIVATE, 429, PRIVATE, {}, body)
        p = OpenAICompatibleChatProvider(model='test', api_key=PRIVATE, transport=transport)
        self.assertEqual(self.error(p, 'HTTP_ERROR').diagnostics['http_status'], 429)
        self.assertEqual(len(calls), 1)
        self.assertTrue(body.closed)

    def test_redirect_is_rejected_and_response_closed(self):
        from cfm_id_llm.providers.openai_chat import _NoRedirect
        response = Response(PRIVATE.encode())
        def transport(req, **kw):
            return _NoRedirect().redirect_request(req, response, 302, PRIVATE, {}, 'https://other.invalid/')
        p = OpenAICompatibleChatProvider(model='test', api_key=PRIVATE, transport=transport)
        self.assertEqual(self.error(p, 'HTTP_ERROR').diagnostics['http_status'], 302)
        self.assertTrue(response.closed)

    def test_wrapped_timeout_and_diagnostics_reset(self):
        calls = []
        def transport(*a, **kw):
            calls.append(1)
            if len(calls) == 1:
                raise URLError(TimeoutError(PRIVATE))
            return Response(envelope())
        p = OpenAICompatibleChatProvider(model='test', api_key=PRIVATE, transport=transport)
        self.error(p, 'TIMEOUT')
        self.assertEqual(self.generate(p), {})
        self.assertNotIn('error_code', p.last_diagnostics)
        self.assertEqual(p.last_diagnostics['transport_calls'], 1)

    def test_invalid_options_fail_before_network(self):
        options = [{'timeout': float('nan')}, {'timeout': float('inf')}, {'timeout': 0},
                   {'max_stream_seconds': -1}, {'max_completion_tokens': 0},
                   {'max_completion_tokens': True}, {'thinking': 'unsupported'}]
        for option in options:
            with self.subTest(option=option), self.assertRaises(ValueError):
                self.provider(envelope(), **option)
            self.assertEqual(self.requests, [])


class A0ContractDiagnosticTests(unittest.TestCase):
    def setUp(self):
        self.entry = {'case_id': 'LOCAL', 'business_question': '希望知道全员推广后的团队表现。',
                      'expected': [{'kind': 'FIXED_POLICY_VALUE', 'quote': '全员推广后的团队表现'}]}
        self.case = BusinessCase(case_id='LOCAL', business_question=self.entry['business_question'])
        self.raw = nbib.make_reference_only_fixture(self.entry)

    def rejected(self, expected):
        with self.assertRaises(A0QualityValidationError) as caught:
            A0QualityFormulatorV010(MockProvider(self.raw)).formulate(self.case)
        self.assertEqual(caught.exception.code, expected)
        self.assertNotIn(PRIVATE, str(caught.exception) + json.dumps(caught.exception.diagnostics))
        return caught.exception.diagnostics

    def test_primary_target_mismatch_remains_rejected(self):
        self.raw['shared_draft']['target']['description']['value'] = PRIVATE
        self.assertEqual(self.rejected('A0_SCHEMA_REJECTED')['issues'][0]['code'], 'PRIMARY_TARGET_MISMATCH')

    def test_unresolved_value_is_not_repaired(self):
        self.raw['queries'][0]['semantics']['comparator']['value'] = PRIVATE
        self.assertEqual(self.rejected('A0_SCHEMA_REJECTED')['issues'][0]['code'], 'UNRESOLVED_CLAIM_CONTRACT')
        self.assertEqual(self.raw['queries'][0]['semantics']['comparator']['value'], PRIVATE)

    def test_null_list_is_not_repaired(self):
        self.raw['queries'][0]['target']['alternatives'] = None
        self.assertEqual(self.rejected('A0_SCHEMA_REJECTED')['issues'][0]['code'], 'list_type')

    def test_unknown_field_name_is_not_echoed(self):
        self.raw[PRIVATE] = PRIVATE
        self.assertEqual(self.rejected('A0_SCHEMA_REJECTED')['issues'][0]['path'], ['[unknown_field]'])

    def test_fabricated_quote_remains_rejected_without_echo(self):
        self.raw['queries'][0]['business_goal']['evidence'][0]['quote'] = PRIVATE
        self.rejected('A0_PROVENANCE_OR_AUDIT_REJECTED')

    def test_user_prompt_exposes_reserved_source_id_without_changing_input(self):
        before = self.case.model_dump_json()
        payload = json.loads(make_quality_user_prompt(self.case).split('\n', 1)[1].split('\n\n只输出 JSON', 1)[0])
        self.assertEqual(payload['business_question_source_id'], 'business_question')
        self.assertEqual(payload['business_question'], self.case.source_map()['business_question'])
        self.assertEqual(before, self.case.model_dump_json())
        self.assertEqual(PROMPT_VERSION_V010, 'cfm-id-a0-query-semantics-v0.10.3')

    def test_cli_writes_redacted_failure_and_passes_explicit_transport_options(self):
        def transport(*a, **kw):
            raise TimeoutError(PRIVATE)
        p = OpenAICompatibleChatProvider(model='test', api_key=PRIVATE, transport=transport)
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'result.json'
            with patch.object(quality_cli, 'OpenAICompatibleChatProvider', return_value=p) as ctor:
                with patch('sys.stderr', new_callable=io.StringIO) as stderr:
                    rc = quality_cli.main(['--question', self.case.business_question,
                        '--provider', 'openai-chat', '--model', 'test', '--allow-external',
                        '--format', 'json', '--output', str(output), '--stream', '--timeout', '180',
                        '--thinking', 'disabled', '--max-completion-tokens', '2048'])
            result = json.loads(output.read_text(encoding='utf8'))
            self.assertEqual(rc, 2)
            self.assertEqual(result['error_code'], 'TIMEOUT')
            self.assertFalse(result['core_called'])
            self.assertFalse(result['estimation_handoff_allowed'])
            self.assertNotIn(PRIVATE, output.read_text(encoding='utf8') + stderr.getvalue())
            self.assertEqual(ctor.call_args.kwargs['timeout'], 180)
            self.assertTrue(ctor.call_args.kwargs['stream'])
            self.assertEqual(ctor.call_args.kwargs['thinking'], 'disabled')

    def test_nbib_input_failure_does_not_reuse_previous_transport_diagnostics(self):
        intake = nbib.load_public_business_case('NBIB-001')
        def transport(*a, **kw):
            raise TimeoutError(PRIVATE)
        p = OpenAICompatibleChatProvider(model='test', api_key=PRIVATE, transport=transport)
        with patch.object(nbib, 'OpenAICompatibleChatProvider', return_value=p):
            with patch.object(nbib, 'load_public_business_case', side_effect=[intake, ValueError(PRIVATE)]):
                result, worksheet = nbib.evaluate(provider_name='openai-chat', model='test',
                    max_cases=2, allow_external=True, allow_document_sharing=True)
        self.assertEqual(result['provider_request_attempts'], 1)
        self.assertEqual(result['cases'][0]['error_code'], 'TIMEOUT')
        self.assertEqual(result['cases'][1]['provider_diagnostics'], {})
        self.assertNotIn(PRIVATE, json.dumps(result))
        self.assertEqual(worksheet['queries'], [])


if __name__ == '__main__':
    unittest.main()
