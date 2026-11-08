"""Opt-in reasoning transport; same strict JSON/SSE parser, no retries.

Socket connect/read limits are separate. A parent process must enforce the
hard total deadline (DNS and blocking reads cannot be cancelled by this class).
Only timing and counters are exposed; reasoning text is never retained.
"""
from __future__ import annotations

from http.client import HTTPSConnection
import json
import math
import time
from urllib.request import HTTPSHandler, ProxyHandler, build_opener

from .openai_chat import OpenAICompatibleChatProvider, _NoRedirect


class _TimedConnection(HTTPSConnection):
    def __init__(self, *args, connect_seconds, read_seconds, connected, **kwargs):
        kwargs["timeout"] = connect_seconds
        super().__init__(*args, **kwargs)
        self.read_seconds = read_seconds
        self.connected = connected

    def connect(self):
        super().connect()
        self.sock.settimeout(self.read_seconds)
        self.timeout = self.read_seconds
        self.connected()


class _TimedHandler(HTTPSHandler):
    def __init__(self, connect_seconds, read_seconds, connected):
        super().__init__()
        self.options = dict(connect_seconds=connect_seconds,
                            read_seconds=read_seconds, connected=connected)

    def https_open(self, req):
        def connection(*args, **kwargs):
            return _TimedConnection(*args, **kwargs, **self.options)
        return self.do_open(connection, req, context=self._context)


class _ObservedResponse:
    def __init__(self, response, observe):
        self.response = response
        self.observe = observe
        self.status = getattr(response, "status", None)

    def __enter__(self):
        self.response.__enter__()
        return self

    def __exit__(self, *args):
        return self.response.__exit__(*args)

    def readline(self, limit):
        line = self.response.readline(limit)
        if line:
            self.observe()
        return line


class ReasoningStreamProviderV036(OpenAICompatibleChatProvider):
    def __init__(self, *, connect_seconds=30.0, read_seconds=900.0,
                 total_seconds=900.0, thinking="enabled", reasoning_effort="high",
                 max_tokens=16384, max_stream_wire_bytes=8000000,
                 before_send=None, transport=None, **kwargs):
        for value in (connect_seconds, read_seconds, total_seconds):
            if isinstance(value, bool) or not math.isfinite(value) or value <= 0:
                raise ValueError("Timeouts must be finite and positive")
        if thinking not in ("enabled", "disabled"):
            raise ValueError("Select thinking explicitly")
        if reasoning_effort not in ("low", "high", "max"):
            raise ValueError("Unsupported reasoning effort")
        # Avoid accidental configuration overrides or two token parameters.
        forbidden = {"stream", "timeout", "max_stream_seconds", "max_completion_tokens"}
        if forbidden.intersection(kwargs):
            raise ValueError("Use this provider's explicit timeout/token settings")
        self.connect_seconds = connect_seconds
        self.read_seconds = read_seconds
        self.total_seconds = total_seconds
        self.reasoning_effort = reasoning_effort
        self.before_send = before_send
        self._request_started = None
        self._send_count = 0
        self._native_transport = transport or build_opener(
            ProxyHandler(),
            _TimedHandler(connect_seconds, read_seconds, self._connected),
            _NoRedirect(),
        ).open
        super().__init__(stream=True, timeout=read_seconds,
                         max_stream_seconds=total_seconds, thinking=thinking,
                         max_stream_wire_bytes=max_stream_wire_bytes,
                         max_tokens=max_tokens, transport=self._send,
                         require_finish_reason=True, **kwargs)

    def _elapsed(self):
        return round(time.monotonic() - self._request_started, 3)

    def _connected(self):
        self.last_diagnostics["connection_ready_seconds"] = self._elapsed()

    def _received_line(self):
        d = self.last_diagnostics
        d.setdefault("first_body_line_seconds", self._elapsed())
        d["last_body_line_seconds"] = self._elapsed()

    def _send(self, request, *, timeout):
        # The inherited parser initializes this to one before dispatch.
        # A budget refusal or repeated use must report zero new dispatches.
        self.last_diagnostics["transport_calls"] = 0
        if self._send_count:
            self._fail("REPEAT_REQUEST_BLOCKED", "One attempt per provider instance")
        self._send_count += 1
        self._request_started = time.monotonic()
        body = json.loads(request.data)
        if self.thinking == "enabled":
            body["reasoning_effort"] = self.reasoning_effort
        body["stream_options"] = {"include_usage": True}
        request.data = json.dumps(body, ensure_ascii=False).encode("utf8")
        self.last_diagnostics.update(
            thinking_sent=self.thinking,
            reasoning_effort_sent=self.reasoning_effort if self.thinking == "enabled" else None,
            connect_timeout_seconds=self.connect_seconds,
            read_timeout_seconds=self.read_seconds,
            total_limit_seconds=self.total_seconds,
        )
        if self.before_send is not None:
            self.before_send(request)
        self.last_diagnostics["transport_calls"] = 1
        response = self._native_transport(request, timeout=timeout)
        return _ObservedResponse(response, self._received_line)

    def progress(self):
        # Explicit allowlist: do not serialize arbitrary provider/server data.
        d = self.last_diagnostics
        keys = (
            "stream", "http_status", "stage", "status", "error_code", "finish_reason",
            "transport_calls", "response_bytes", "content_characters", "content_bytes",
            "stream_events", "reasoning_characters", "first_reasoning_seconds",
            "first_content_seconds", "headers_seconds", "first_body_line_seconds",
            "last_body_line_seconds", "connection_ready_seconds", "elapsed_seconds",
            "thinking_sent", "reasoning_effort_sent", "returned_model",
            "connect_timeout_seconds", "read_timeout_seconds", "total_limit_seconds",
            "output_token_limit", "output_token_parameter",
            "max_stream_wire_bytes",
        )
        out = {k: d[k] for k in keys if k in d}
        if self._request_started is not None:
            out["wall_seconds"] = self._elapsed()
        if isinstance(d.get("usage"), dict):
            out["usage"] = dict(d["usage"])
        return out
