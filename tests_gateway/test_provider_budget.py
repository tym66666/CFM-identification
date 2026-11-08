import io
import json
import unittest
from unittest.mock import patch
from contextlib import redirect_stderr
from cfm_id_llm.providers.openai_chat import OpenAICompatibleChatProvider
from cfm_id_llm.providers.base import ProviderError


def event(value):
    return b"data: " + json.dumps(value).encode() + b"\n\n"


class BudgetCompatibilityTests(unittest.TestCase):
    def provider(self, wire, **options):
        self.requests = []
        def transport(request, *, timeout):
            self.requests.append(json.loads(request.data))
            return io.BytesIO(wire)
        return OpenAICompatibleChatProvider(model="offline", api_key="LOCAL_AUTH_SENTINEL",
                                            transport=transport, json_mode=False, **options)

    def test_output_budget_names_are_explicit_and_never_duplicated(self):
        wire = json.dumps({"choices": [{"finish_reason": "stop", "message": {"content": "{}"}}]}).encode()
        for field in ("max_tokens", "max_completion_tokens"):
            p = self.provider(wire, **{field: 64})
            self.assertEqual(p.generate_json(system_prompt="s", user_prompt="u"), {})
            self.assertEqual(self.requests[0][field], 64)
            other = "max_tokens" if field == "max_completion_tokens" else "max_completion_tokens"
            self.assertNotIn(other, self.requests[0])
        for options in ({"max_tokens": 0}, {"max_tokens": True},
                        {"max_tokens": 64, "max_completion_tokens": 64},
                        {"require_finish_reason": "yes"}):
            with self.assertRaises(ValueError):
                self.provider(wire, **options)

    def test_length_finish_never_accepts_even_complete_json_or_retries(self):
        wire = event({"choices": [{"delta": {"content": "{}"}, "finish_reason": "length"}]}) + b"data: [DONE]\n\n"
        p = self.provider(wire, stream=True, max_tokens=1)
        with self.assertRaises(ProviderError) as caught:
            p.generate_json(system_prompt="s", user_prompt="u")
        self.assertEqual(caught.exception.code, "INCOMPLETE_COMPLETION")
        self.assertEqual(p.last_diagnostics["finish_reason"], "length")
        self.assertEqual(len(self.requests), 1)

    def test_nonstream_strict_mode_requires_finish_reason(self):
        wire = b'{"choices":[{"message":{"content":"{}"}}]}'
        p = self.provider(wire, require_finish_reason=True)
        with self.assertRaises(ProviderError) as caught:
            p.generate_json(system_prompt="s", user_prompt="u")
        self.assertEqual(caught.exception.code, "INCOMPLETE_COMPLETION")
        compatible = self.provider(wire)
        self.assertEqual(compatible.generate_json(system_prompt="s", user_prompt="u"), {})

    def test_stream_metadata_retains_counters_not_reasoning_or_arbitrary_usage(self):
        wire = event({"model": "returned-model-v1", "choices": [
            {"delta": {"reasoning_content": "private deliberation"}, "finish_reason": None}]})
        wire += event({"choices": [{"delta": {"content": '{"ok":true}'}, "finish_reason": "stop"}]})
        wire += event({"choices": [], "usage": {"prompt_tokens": 40, "completion_tokens": 9,
            "secret": "DO_NOT_RETAIN", "total_tokens": True, "completion_tokens_details": {"reasoning_tokens": 3}}})
        wire += b"data: [DONE]\n\n"
        p = self.provider(wire, stream=True, max_tokens=32)
        self.assertEqual(p.generate_json(system_prompt="s", user_prompt="u"), {"ok": True})
        d = p.last_diagnostics
        self.assertEqual(d["reasoning_characters"], len("private deliberation"))
        self.assertEqual(d["returned_model"], "returned-model-v1")
        self.assertEqual(d["usage"], {"prompt_tokens": 40, "completion_tokens": 9, "reasoning_tokens": 3})
        serialized = json.dumps(d)
        for text in ("private deliberation", "DO_NOT_RETAIN", "LOCAL_AUTH_SENTINEL"):
            self.assertNotIn(text, serialized)

    def test_nonstream_usage_and_model_are_observed(self):
        wire = json.dumps({"model": "returned-v2", "usage": {"completion_tokens": 3},
            "choices": [{"finish_reason": "stop", "message": {"content": "{}", "reasoning_content": "abc"}}]}).encode()
        p = self.provider(wire, max_tokens=8, require_finish_reason=True)
        p.generate_json(system_prompt="s", user_prompt="u")
        self.assertEqual(p.last_diagnostics["usage"]["completion_tokens"], 3)
        self.assertEqual(p.last_diagnostics["reasoning_characters"], 3)

    def test_cli_budget_options_are_forwarded_and_mutually_exclusive(self):
        from cfm_id_llm.quality_cli import make_parser
        from cfm_id_llm.providers.cli_options import chat_options
        parser = make_parser()
        args = parser.parse_args(["--question", "业务问题", "--max-tokens", "64", "--require-finish-reason"])
        options = chat_options(args)
        self.assertEqual(options["max_tokens"], 64)
        self.assertTrue(options["require_finish_reason"])
        self.assertIsNone(options["max_completion_tokens"])
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            parser.parse_args(["--question", "业务问题", "--max-tokens", "64", "--max-completion-tokens", "64"])

    def test_nbib_evaluate_forwards_budget_without_a_network_call(self):
        from evaluation import nbib_semantic_eval as nbib
        from cfm_id_llm.providers import MockProvider
        fixture = nbib.make_reference_only_fixture(nbib.load_reference()[0])
        provider = MockProvider(fixture)
        with patch.object(nbib, "OpenAICompatibleChatProvider", return_value=provider) as ctor:
            nbib.evaluate(provider_name="openai-chat", model="offline", max_cases=1,
                          allow_external=True, allow_document_sharing=True,
                          max_tokens=64, require_finish_reason=True)
        self.assertEqual(ctor.call_args.kwargs["max_tokens"], 64)
        self.assertTrue(ctor.call_args.kwargs["require_finish_reason"])


if __name__ == "__main__":
    unittest.main()
