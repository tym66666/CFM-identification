import io
import json
import ssl
import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError

from cfm_id_llm.providers.base import ProviderError
from cfm_id_llm.providers.reasoning_stream import (
    ReasoningStreamProviderV036, _TimedConnection, _TimedHandler,
)


def event(body):
    return b"data: " + json.dumps(body).encode() + b"\n\n"


def wire():
    return (
        b": heartbeat\n\n"
        + event({"model": "test-model", "choices": [{"delta": {"reasoning_content": "PRIVATE_TRACE"}}]})
        + event({"choices": [{"delta": {"content": '{"ok":true}'}, "finish_reason": "stop"}]})
        + event({"choices": [], "usage": {"prompt_tokens": 12, "completion_tokens": 7}})
        + b"data: [DONE]\n\n"
    )


class ReasoningStreamTests(unittest.TestCase):
    def provider(self, data=None, **kw):
        self.sent = []
        def transport(req, *, timeout):
            self.sent.append((json.loads(req.data), timeout))
            return io.BytesIO(wire() if data is None else data)
        return ReasoningStreamProviderV036(
            model="offline", api_key="AUTH_TEST_SENTINEL",
            transport=transport, **kw)

    def run_request(self, p):
        return p.generate_json(system_prompt="JSON", user_prompt="test")

    def test_enabled_request_explicit_effort_stream_and_budget(self):
        p = self.provider()
        self.assertEqual(self.run_request(p), {"ok": True})
        body, timeout = self.sent[0]
        self.assertEqual(body["thinking"], {"type": "enabled"})
        self.assertEqual(body["reasoning_effort"], "high")
        self.assertEqual(body["max_tokens"], 16384)
        self.assertEqual(body["stream_options"], {"include_usage": True})
        self.assertTrue(body["stream"])
        self.assertEqual(timeout, 900)

    def test_disabled_request_does_not_send_effort(self):
        p = self.provider(thinking="disabled")
        self.run_request(p)
        self.assertEqual(self.sent[0][0]["thinking"], {"type": "disabled"})
        self.assertNotIn("reasoning_effort", self.sent[0][0])

    def test_metadata_contains_counts_without_auth_or_reasoning_text(self):
        p = self.provider()
        self.run_request(p)
        d = p.progress()
        self.assertEqual(d["reasoning_characters"], len("PRIVATE_TRACE"))
        self.assertEqual(d["usage"], {"prompt_tokens": 12, "completion_tokens": 7})
        self.assertIn("first_body_line_seconds", d)
        self.assertIn("first_reasoning_seconds", d)
        self.assertIn("first_content_seconds", d)
        self.assertNotIn("PRIVATE_TRACE", json.dumps(d))
        self.assertNotIn("AUTH_TEST_SENTINEL", json.dumps(d))

    def test_read_timeout_keeps_partial_diagnostics_and_does_not_retry(self):
        class Broken(io.BytesIO):
            def readline(self, n):
                line = super().readline(n)
                if not line:
                    raise TimeoutError("SECRET_PRIVATE_TRACE")
                return line
        p = self.provider()
        p._native_transport = lambda req, timeout: Broken(
            event({"choices": [{"delta": {"reasoning_content": "abc"}}]}))
        with self.assertRaises(ProviderError) as cm:
            self.run_request(p)
        self.assertEqual(cm.exception.code, "TIMEOUT")
        self.assertEqual(p.progress()["reasoning_characters"], 3)
        self.assertNotIn("SECRET_PRIVATE_TRACE", str(cm.exception))
        self.assertEqual(p._send_count, 1)

    def test_length_finish_rejected_even_if_json_is_complete(self):
        p = self.provider(event({"choices": [{"delta": {"content": "{}"}, "finish_reason": "length"}]}))
        with self.assertRaises(ProviderError) as cm:
            self.run_request(p)
        self.assertEqual(cm.exception.code, "INCOMPLETE_COMPLETION")
        self.assertEqual(len(self.sent), 1)

    def test_incomplete_stream_never_accepts_partial_json(self):
        p = self.provider(event({"choices": [{"delta": {"content": "{}"}, "finish_reason": "stop"}]}))
        with self.assertRaises(ProviderError) as cm:
            self.run_request(p)
        self.assertEqual(cm.exception.code, "INCOMPLETE_STREAM")

    def test_budget_hook_sees_final_request_and_can_block_before_network(self):
        seen = []
        def guard(req):
            seen.append(json.loads(req.data))
            raise ProviderError("blocked", code="BUDGET_BLOCKED")
        p = self.provider(before_send=guard)
        with self.assertRaises(ProviderError):
            self.run_request(p)
        self.assertEqual(len(self.sent), 0)
        self.assertEqual(p.progress()["transport_calls"], 0)
        self.assertEqual(seen[0]["reasoning_effort"], "high")

    def test_connection_switches_to_read_timeout_only_after_tls(self):
        connected = Mock()
        conn = _TimedConnection("example.org", timeout=999,
                                connect_seconds=23, read_seconds=871, connected=connected)
        self.assertEqual(conn.timeout, 23)
        sock = Mock()
        def connect(self):
            self.sock = sock
        with patch("http.client.HTTPSConnection.connect", connect):
            conn.connect()
        sock.settimeout.assert_called_once_with(871)
        connected.assert_called_once_with()
        self.assertEqual(conn.timeout, 871)
        # Python 3.11 builds the default TLS context in HTTPSConnection;
        # newer versions may already create it in HTTPSHandler. Inspect the
        # connection produced by the handler, without opening a socket.
        handler = _TimedHandler(23, 871, connected)
        with patch.object(handler, 'do_open', side_effect=lambda factory, req, **kw:
                          factory('example.org', **kw)):
            secured = handler.https_open(Mock())
        self.assertTrue(secured._context.check_hostname)
        self.assertEqual(secured._context.verify_mode, ssl.CERT_REQUIRED)

    def test_http_failure_sanitized_no_body_no_retry(self):
        p = self.provider()
        def fail(*args, **kw):
            raise HTTPError("https://example.org", 400, "SECRET", {}, io.BytesIO(b"PRIVATE_TRACE"))
        p._native_transport = fail
        with self.assertRaises(ProviderError) as cm:
            self.run_request(p)
        self.assertEqual(cm.exception.code, "HTTP_ERROR")
        self.assertEqual(p.progress()["http_status"], 400)
        self.assertNotIn("PRIVATE_TRACE", json.dumps(p.progress()))
        self.assertEqual(p._send_count, 1)

    def test_repeat_attempt_on_same_instance_blocked(self):
        p = self.provider()
        self.run_request(p)
        with self.assertRaises(ProviderError) as cm:
            self.run_request(p)
        self.assertEqual(cm.exception.code, "REPEAT_REQUEST_BLOCKED")
        self.assertEqual(len(self.sent), 1)
        self.assertEqual(p.progress()["transport_calls"], 0)

    def test_invalid_transport_options_rejected(self):
        for kw in (dict(total_seconds=0), dict(read_seconds=float("inf")),
                   dict(connect_seconds=True), dict(reasoning_effort="unknown"),
                   dict(thinking=None), dict(stream=False), dict(max_completion_tokens=100)):
            with self.assertRaises(ValueError):
                self.provider(**kw)


if __name__ == "__main__":
    unittest.main()
