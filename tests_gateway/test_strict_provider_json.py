"""Malformed JSON must not silently alter a requested goal; no network."""
import io
import json
import sys
import unittest

from cfm_id_llm.providers import OpenAICompatibleChatProvider, ProviderError


class StrictJsonTests(unittest.TestCase):
    def provider(self, wire, stream=False):
        self.calls = 0
        def transport(request, **kwargs):
            self.calls += 1
            return io.BytesIO(wire)
        return OpenAICompatibleChatProvider(model="offline", api_key="PRIVATE_SENTINEL",
                                            transport=transport, stream=stream,
                                            json_mode=False, allow_json_fence=True)

    def content(self, content, stream):
        if stream:
            envelope = {"choices": [{"index": 0, "delta": {"content": content}, "finish_reason": "stop"}]}
            return b"data: " + json.dumps(envelope).encode() + b"\n\ndata: [DONE]\n\n"
        return json.dumps({"choices": [{"message": {"content": content}, "finish_reason": "stop"}]}).encode()

    def rejected(self, wire, code, stream=False):
        p = self.provider(wire, stream)
        with self.assertRaises(ProviderError) as caught:
            p.generate_json(system_prompt="s", user_prompt="u")
        self.assertEqual(caught.exception.code, code)
        self.assertEqual(self.calls, 1)
        self.assertNotIn("PRIVATE_SENTINEL", str(caught.exception) + json.dumps(caught.exception.diagnostics))

    def test_duplicate_goal_or_nested_field_rejected_in_both_modes(self):
        for stream in (False, True):
            for content in (
                '{"questions":{"s05":1,"s05":2}}',
                '{"goal":{"own":0,"own":1}}',
                '{"PRIVATE_SENTINEL":0,"PRIVATE_SENTINEL":1}',
                '```json\n{"q":1,"q":2}\n```',
            ):
                with self.subTest(stream=stream, content=content):
                    self.rejected(self.content(content, stream), "DUPLICATE_JSON_KEY", stream)

    def test_nonfinite_literals_and_overflow_rejected(self):
        for stream in (False, True):
            for value in ("NaN", "Infinity", "-Infinity", "1e999"):
                with self.subTest(stream=stream, value=value):
                    self.rejected(self.content('{"value":' + value + '}', stream), "NON_FINITE_JSON", stream)

    def test_duplicate_transport_fields_rejected(self):
        self.rejected(b'{"choices":[],"choices":[]}', "DUPLICATE_JSON_KEY")
        self.rejected(b'data: {"choices":[],"choices":[]}\n\n', "DUPLICATE_JSON_KEY", True)

    def test_valid_nested_json_remains_compatible(self):
        expected = {"questions": {"s05": {"value": 0.125, "ids": ["01"], "note": None}}}
        for stream in (False, True):
            p = self.provider(self.content(json.dumps(expected), stream), stream)
            self.assertEqual(p.generate_json(system_prompt="s", user_prompt="u"), expected)
            self.assertEqual(self.calls, 1)

    def test_python_integer_decoder_limit_error_is_sanitized(self):
        old_digits = sys.get_int_max_str_digits()
        try:
            # Hosts may disable the integer guard. Restore the runtime setting.
            sys.set_int_max_str_digits(4300)
            self.rejected(self.content('{"x":' + "9" * 5000 + '}', False), "MALFORMED_RESPONSE")
        finally:
            sys.set_int_max_str_digits(old_digits)


if __name__ == "__main__":
    unittest.main()
