"""Offline Responses transport contract; no network or real credentials."""
from copy import deepcopy
import io
import json
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from cfm_id_llm.providers.base import ProviderError
from cfm_id_llm.providers.openai_responses import OpenAICompatibleResponsesProvider


SCHEMA = {"type": "object", "properties": {"goal": {"type": "string"}},
          "required": ["goal"], "additionalProperties": False}
KEY = "PRIVATE_AUTH_SENTINEL"
REASONING = "PRIVATE_REASONING_SENTINEL"


def validate(raw):
    if set(raw) != {"goal"} or not isinstance(raw["goal"], str):
        raise ValueError("LOCAL_PRIVATE_ERROR")


def envelope(content='{"goal":"all"}', **overrides):
    body = {"object": "response", "status": "completed", "model": "test-model",
            "output": [{"type": "reasoning", "content": [{"type": "reasoning_text", "text": REASONING}]},
                       {"type": "message", "status": "completed", "role": "assistant",
                        "content": [{"type": "output_text", "text": content, "annotations": []}]}],
            "usage": {"input_tokens": 9, "output_tokens": 5, "total_tokens": 14,
                      "input_tokens_details": {"cached_tokens": 2},
                      "output_tokens_details": {"reasoning_tokens": 1}}}
    body.update(overrides)
    return body


class ResponsesTests(unittest.TestCase):
    def provider(self, body=None, *, wire=None, **options):
        self.calls = []
        if wire is None:
            wire = json.dumps(envelope() if body is None else body).encode("utf-8")
        def transport(req, *, timeout):
            self.calls.append((req, timeout))
            return io.BytesIO(wire)
        defaults = dict(model="test-model", schema=deepcopy(SCHEMA), schema_name="business_reading",
                        api_key=KEY, base_url="https://endpoint.example/v1/",
                        local_validator=validate, transport=transport)
        defaults.update(options)
        return OpenAICompatibleResponsesProvider(**defaults)

    def call(self, provider):
        return provider.generate_json(system_prompt="SYSTEM_PRIVATE", user_prompt="BUSINESS_PRIVATE")

    def rejected(self, provider, code):
        with self.assertRaises(ProviderError) as cm:
            self.call(provider)
        self.assertEqual(cm.exception.code, code)
        self.assertFalse(provider.last_diagnostics["local_validation_passed"])
        diagnostic = str(cm.exception) + json.dumps(cm.exception.diagnostics)
        for secret in (KEY, REASONING, "SYSTEM_PRIVATE", "BUSINESS_PRIVATE", "LOCAL_PRIVATE_ERROR"):
            self.assertNotIn(secret, diagnostic)
        self.assertEqual(len(self.calls), 1)
        return cm.exception

    def test_payload_is_explicit_responses_schema_with_no_tools_or_storage(self):
        provider = self.provider(timeout=123, max_output_tokens=4096, reasoning_effort="none")
        self.assertEqual(self.call(provider), {"goal": "all"})
        request, timeout = self.calls[0]
        self.assertEqual(request.full_url, "https://endpoint.example/v1/responses")
        self.assertEqual(request.get_header("Authorization"), "Bearer " + KEY)
        self.assertEqual(timeout, 123)
        payload = json.loads(request.data)
        self.assertEqual(payload, {
            "model": "test-model", "instructions": "SYSTEM_PRIVATE", "input": "BUSINESS_PRIVATE",
            "stream": False, "store": False, "max_output_tokens": 4096,
            "reasoning": {"effort": "none"},
            "text": {"format": {"type": "json_schema", "name": "business_reading", "schema": SCHEMA, "strict": True}}})
        self.assertEqual(len(self.calls), 1)

    def test_omitted_optional_parameters_are_omitted(self):
        provider = self.provider()
        self.call(provider)
        payload = json.loads(self.calls[0][0].data)
        self.assertNotIn("reasoning", payload)
        self.assertNotIn("max_output_tokens", payload)
        self.assertNotIn("thinking", payload)

    def test_explicit_vendor_thinking_switch_does_not_replace_effort(self):
        for value in ('enabled', 'disabled'):
            with self.subTest(value=value):
                provider = self.provider(thinking=value, reasoning_effort='none')
                self.assertEqual(self.call(provider), {'goal': 'all'})
                payload = json.loads(self.calls[0][0].data)
                self.assertEqual(payload['thinking'], {'type': value})
                self.assertEqual(payload['reasoning'], {'effort': 'none'})
                self.assertEqual(provider.last_diagnostics['thinking_type_sent'], value)
                self.assertEqual(len(self.calls), 1)

    def test_vendor_switch_is_validated_before_transport(self):
        for value in (True, 0, 'off', '', {'type': 'disabled'}):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    self.provider(thinking=value)
                self.assertEqual(self.calls, [])

    def test_control_echoes_are_allowlisted_and_not_claimed_as_enforced(self):
        provider = self.provider(envelope(thinking={'type': 'enabled', 'text': REASONING},
                                         reasoning={'effort': 'high', 'private': KEY}),
                                 thinking='disabled', reasoning_effort='none')
        self.call(provider)
        d = provider.last_diagnostics
        self.assertEqual(d['thinking_type_sent'], 'disabled')
        self.assertEqual(d['returned_thinking_type'], 'enabled')
        self.assertEqual(d['returned_reasoning_effort'], 'high')
        self.assertNotIn('thinking_disabled_verified', d)
        self.assertNotIn(REASONING, json.dumps(d))
        self.assertNotIn(KEY, json.dumps(d))

    def test_truncation_reason_is_retained_without_private_error_text(self):
        provider = self.provider(envelope(status='incomplete',
            incomplete_details={'reason': 'max_output_tokens', 'message': KEY}), thinking='disabled')
        self.rejected(provider, 'INCOMPLETE_COMPLETION')
        self.assertEqual(provider.last_diagnostics['returned_incomplete_details_reason'], 'max_output_tokens')

    def test_unknown_control_echoes_cannot_leak_strings(self):
        provider = self.provider(envelope(thinking={'type': KEY}, reasoning={'effort': REASONING}))
        self.call(provider)
        self.assertEqual(provider.last_diagnostics['returned_thinking_type'], 'other')
        self.assertEqual(provider.last_diagnostics['returned_reasoning_effort'], 'other')
        self.assertNotIn(KEY, json.dumps(provider.last_diagnostics))
        self.assertNotIn(REASONING, json.dumps(provider.last_diagnostics))

    def test_success_diagnostics_contain_only_allowlisted_metadata(self):
        body = envelope(metadata={"key": KEY}, id=KEY, reasoning={"content": REASONING})
        body["usage"]["private"] = KEY
        provider = self.provider(body)
        self.call(provider)
        d = provider.last_diagnostics
        self.assertEqual(d["usage"], {"input_tokens": 9, "output_tokens": 5, "total_tokens": 14,
                                      "cached_tokens": 2, "reasoning_tokens": 1})
        self.assertEqual(d["returned_model"], "test-model")
        self.assertTrue(d["local_validation_passed"])
        self.assertNotIn(KEY, json.dumps(d))
        self.assertNotIn(REASONING, json.dumps(d))

    def test_untrusted_metadata_values_are_filtered(self):
        body = envelope(model=KEY, usage={"input_tokens": True, "output_tokens": -1,
            "total_tokens": "99", "input_tokens_details": {"cached_tokens": "private"},
            "output_tokens_details": {"reasoning_tokens": False}})
        provider = self.provider(body)
        self.call(provider)
        self.assertNotIn("returned_model", provider.last_diagnostics)
        self.assertNotIn("usage", provider.last_diagnostics)

    def test_schema_is_frozen_against_caller_mutation(self):
        schema = deepcopy(SCHEMA)
        provider = self.provider(schema=schema)
        schema["properties"].clear()
        self.call(provider)
        self.assertEqual(json.loads(self.calls[0][0].data)["text"]["format"]["schema"], SCHEMA)

    def test_validator_cannot_repair_or_replace_actual_answer(self):
        def mutate(raw):
            raw["goal"] = "repaired"
            return {"goal": "another"}
        provider = self.provider(local_validator=mutate)
        self.assertEqual(self.call(provider), {"goal": "all"})

    def test_schema_violation_is_locally_rejected_even_when_server_completed(self):
        observed = []
        provider = self.provider(envelope('{"reading":{"goal":"all"}}'), final_content_observer=observed.append)
        self.rejected(provider, "LOCAL_VALIDATION_FAILED")
        self.assertEqual(observed, ['{"reading":{"goal":"all"}}'])

    def test_validator_false_also_rejects(self):
        self.rejected(self.provider(local_validator=lambda raw: False), "LOCAL_VALIDATION_FAILED")

    def test_observer_only_sees_final_json_and_redacts_auth(self):
        observed = []
        provider = self.provider(envelope(json.dumps({"goal": KEY})), final_content_observer=observed.append)
        self.call(provider)
        self.assertEqual(json.loads(observed[0]), {"goal": "[REDACTED]"})
        self.assertNotIn(REASONING, str(observed))

    def test_observer_error_is_sanitized_and_blocks_validation(self):
        validated = []
        def observer(content):
            raise RuntimeError(KEY + REASONING)
        provider = self.provider(final_content_observer=observer, local_validator=validated.append)
        self.rejected(provider, "FINAL_CONTENT_OBSERVER_FAILED")
        self.assertEqual(validated, [])

    def test_non_completed_status_and_error_envelopes_are_rejected(self):
        for overrides in ({"status": "incomplete"}, {"status": "failed", "error": {"message": KEY}},
                          {"status": "in_progress"}, {"status": None},
                          {"error": {}}, {"incomplete_details": {"reason": "max_output_tokens"}}):
            with self.subTest(overrides=overrides):
                self.rejected(self.provider(envelope(**overrides)), "INCOMPLETE_COMPLETION")

    def test_wrong_envelope_type_is_rejected(self):
        for body in ([], {"status": "completed", "output": []}, envelope(object="chat.completion")):
            with self.subTest(body=body):
                self.rejected(self.provider(body), "MALFORMED_RESPONSE")

    def test_missing_or_ambiguous_final_message_rejected(self):
        base = envelope()
        variants = [([], "MALFORMED_RESPONSE"), ([base["output"][0]], "MALFORMED_RESPONSE"),
                    ([base["output"][1], base["output"][1]], "AMBIGUOUS_OUTPUT"),
                    ([base["output"][1], base["output"][0]], "AMBIGUOUS_OUTPUT")]
        for output, code in variants:
            with self.subTest(code=code, output=output):
                self.rejected(self.provider(envelope(output=output)), code)

    def test_tool_output_cannot_be_silently_ignored(self):
        for kind in ("function_call", "custom_tool_call", "function_call_output", "web_search_call"):
            body = envelope()
            body["output"].insert(0, {"type": kind, "arguments": KEY})
            self.rejected(self.provider(body), "UNSUPPORTED_OUTPUT")

    def test_role_and_message_status_checked(self):
        body = envelope()
        body["output"][-1]["role"] = "user"
        self.rejected(self.provider(body), "UNSUPPORTED_OUTPUT")
        body["output"][-1].update(role="assistant", status="incomplete")
        self.rejected(self.provider(body), "INCOMPLETE_COMPLETION")

    def test_message_status_may_be_omitted_under_completed_envelope(self):
        body = envelope()
        del body["output"][-1]["status"]
        self.assertEqual(self.call(self.provider(body)), {"goal": "all"})

    def test_refusal_and_mixed_content_fail_closed(self):
        for part, code in [({"type": "refusal", "refusal": KEY}, "MODEL_REFUSAL"),
                           ({"type": "output_image", "image": KEY}, "NON_TEXT_CONTENT"),
                           ({"type": "output_text", "text": None}, "NON_TEXT_CONTENT")]:
            body = envelope()
            body["output"][-1]["content"].append(part)
            self.rejected(self.provider(body), code)

    def test_multiple_text_fragments_form_one_strict_json_document(self):
        body = envelope()
        body["output"][-1]["content"] = [{"type": "output_text", "text": '{"goal":'},
                                            {"type": "output_text", "text": '"all"}'}]
        self.assertEqual(self.call(self.provider(body)), {"goal": "all"})

    def test_json_is_strict_without_fence_repair(self):
        for text, code in [('{"goal":"all","goal":"single"}', "DUPLICATE_JSON_KEY"),
                           ('{"nested":{"x":1,"x":2}}', "DUPLICATE_JSON_KEY"),
                           ('{"x":NaN}', "NON_FINITE_JSON"), ('{"x":1e999}', "NON_FINITE_JSON"),
                           ('[]', "NON_OBJECT_JSON"), ('not-json', "MALFORMED_RESPONSE"),
                           ('```json\n{"goal":"all"}\n```', "MALFORMED_RESPONSE")]:
            with self.subTest(text=text):
                observed = []
                self.rejected(self.provider(envelope(text), final_content_observer=observed.append), code)
                self.assertEqual(observed, [])

    def test_duplicate_wire_fields_and_invalid_utf8_are_rejected(self):
        self.rejected(self.provider(wire=b'{"status":"completed","status":"incomplete"}'), "DUPLICATE_JSON_KEY")
        self.rejected(self.provider(wire=b'\xff'), "MALFORMED_RESPONSE")

    def test_wire_limit_checked_before_parse(self):
        self.rejected(self.provider(max_response_bytes=16), "RESPONSE_TOO_LARGE")

    def test_final_content_limit_is_separate_from_wire_limit(self):
        self.rejected(self.provider(envelope(json.dumps({"goal": "a" * 350_001}))), "RESPONSE_TOO_LARGE")

    def test_http_error_no_retry_no_body_leak(self):
        calls = []
        def transport(*args, **kwargs):
            calls.append(1)
            raise HTTPError("https://endpoint.example", 429, KEY, {"Private": KEY}, io.BytesIO(KEY.encode()))
        provider = self.provider(transport=transport)
        with self.assertRaises(ProviderError) as cm:
            self.call(provider)
        self.assertEqual(calls, [1])
        self.assertEqual(cm.exception.code, "HTTP_ERROR")
        self.assertNotIn(KEY, str(cm.exception) + json.dumps(cm.exception.diagnostics))

    def test_timeout_no_retry(self):
        calls = []
        def transport(*args, **kwargs):
            calls.append(1)
            raise URLError(TimeoutError(KEY))
        provider = self.provider(transport=transport)
        with self.assertRaises(ProviderError) as cm:
            self.call(provider)
        self.assertEqual(cm.exception.code, "TIMEOUT")
        self.assertEqual(calls, [1])
        self.assertNotIn(KEY, str(cm.exception) + json.dumps(cm.exception.diagnostics))

    def test_default_opener_contains_no_redirect_handler(self):
        from cfm_id_llm.providers.openai_chat import _NoRedirect
        provider = self.provider(transport=None)
        self.assertTrue(any(isinstance(handler, _NoRedirect) for handler in provider._transport.__self__.handlers))
        fp = io.BytesIO(b"secret")
        with self.assertRaises(HTTPError):
            _NoRedirect().redirect_request(type("Req", (), {"full_url": "https://a.test"})(), fp,
                                          302, "redirect", {}, "https://b.test")
        self.assertTrue(fp.closed)

    def test_constructor_rejects_unsafe_or_unvalidated_configuration(self):
        for kwargs in ({"local_validator": None}, {"schema": {}}, {"schema": {"x": float("nan")}},
                       {"schema_name": "bad name"}, {"schema_name": "x" * 65},
                       {"final_content_observer": 3}, {"max_output_tokens": True}, {"max_output_tokens": 0},
                       {"reasoning_effort": "invalid"}, {"max_response_bytes": 0}, {"max_response_bytes": True},
                       {"timeout": 0}, {"timeout": float("inf")},
                       {"base_url": "http://example.com/v1"}, {"base_url": "https://u:p@example.com/v1"},
                       {"base_url": "https://example.com/v1?key=x"}, {"base_url": "https://example.com/v1#x"}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                self.provider(**kwargs)

    def test_localhost_http_and_env_key_follow_existing_security_contract(self):
        self.assertEqual(self.call(self.provider(base_url="http://localhost:1234/v1")), {"goal": "all"})
        with patch.dict("os.environ", {"CFM_ID_LLM_API_KEY": KEY, "OPENAI_API_KEY": ""}):
            self.assertEqual(self.call(self.provider(api_key=None)), {"goal": "all"})
        with patch.dict("os.environ", {"CFM_ID_LLM_API_KEY": "", "OPENAI_API_KEY": ""}):
            with self.assertRaises(ValueError):
                self.provider(api_key=None)

    def test_diagnostics_reset_between_calls(self):
        provider = self.provider()
        self.call(provider)
        provider.last_diagnostics["unexpected"] = REASONING
        self.call(provider)
        self.assertNotIn("unexpected", provider.last_diagnostics)
        self.assertEqual(provider.last_diagnostics["transport_calls"], 1)


if __name__ == "__main__":
    unittest.main()
