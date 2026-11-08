"""Bounded Chat-Completions JSON/SSE transport; never trusts model math.

No retries, redirects or JSON repairs. Diagnostics contain counters/status only.
"""
from __future__ import annotations
import json
import math
import os
import re
import time
from http.client import HTTPException
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener
from .base import ProviderError

_CONTENT_LIMIT = 350000
_STREAM_WIRE_LIMIT = 2000000
_EVENT_LIMIT = 65536


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if fp is not None:
            fp.close()
        raise HTTPError(req.full_url, code, "Redirect disabled", headers, None)


class OpenAICompatibleChatProvider:
    def __init__(self, *, model: str, api_key: str | None = None,
                 base_url: str = "https://api.openai.com/v1", timeout: float = 60.0,
                 max_completion_tokens: int | None = None, stream: bool = False,
                 max_stream_seconds: float = 300.0, thinking: str | None = None,
                 json_mode: bool = True,
                 allow_json_fence: bool = False,
                 max_tokens: int | None = None,
                 require_finish_reason: bool = False,
                 max_stream_wire_bytes: int | None = None,
                 transport: Callable[..., Any] | None = None):
        if not model.strip():
            raise ValueError("Model name must be supplied explicitly")
        self.model = model.strip()
        self.api_key = api_key or os.getenv("CFM_ID_LLM_API_KEY") or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("No API key: set CFM_ID_LLM_API_KEY or OPENAI_API_KEY")
        parsed = urlparse(base_url)
        localhost = parsed.hostname in {"localhost", "127.0.0.1", "::1"}
        if (not parsed.hostname or
                (parsed.scheme != "https" and not (localhost and parsed.scheme == "http"))):
            raise ValueError("Only HTTPS endpoints or explicit localhost HTTP are permitted")
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("Do not put credentials/query parameters in base_url")
        for value in (timeout, max_stream_seconds):
            if not math.isfinite(value) or value <= 0:
                raise ValueError("Timeouts must be finite and positive")
        if max_completion_tokens is not None and (
                type(max_completion_tokens) is not int or max_completion_tokens <= 0):
            raise ValueError("max_completion_tokens must be a positive integer")
        if max_tokens is not None and (type(max_tokens) is not int or max_tokens <= 0):
            raise ValueError("max_tokens must be a positive integer")
        if max_tokens is not None and max_completion_tokens is not None:
            raise ValueError("Choose exactly one output-token parameter")
        if type(require_finish_reason) is not bool:
            raise ValueError("require_finish_reason must be a boolean")
        if thinking not in (None, "enabled", "disabled"):
            raise ValueError("thinking must be omitted, enabled or disabled")
        if type(json_mode) is not bool:
            raise ValueError("json_mode must be a boolean")
        if type(allow_json_fence) is not bool:
            raise ValueError("allow_json_fence must be a boolean")
        if max_stream_wire_bytes is None:
            max_stream_wire_bytes = _STREAM_WIRE_LIMIT
        if type(max_stream_wire_bytes) is not int or not 0 < max_stream_wire_bytes <= 32000000:
            raise ValueError("max_stream_wire_bytes must be an integer from 1 to 32000000")
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_completion_tokens = max_completion_tokens
        self.max_tokens = max_tokens
        self.require_finish_reason = require_finish_reason
        self.stream = stream
        self.max_stream_seconds = max_stream_seconds
        self.max_stream_wire_bytes = max_stream_wire_bytes
        self.thinking = thinking
        self.json_mode = json_mode
        self.allow_json_fence = allow_json_fence
        self._transport = transport or build_opener(_NoRedirect()).open
        self.name = "openai-chat-compatible:" + self.model
        self.last_diagnostics: dict[str, Any] = {}

    @staticmethod
    def _fail(code: str, message: str):
        raise ProviderError(message, code=code)

    def _finish(self, reason):
        if reason is None:
            return
        self.last_diagnostics["finish_reason"] = reason if reason in (
            "stop", "length", "content_filter", "tool_calls", "function_call") else "other"
        if reason != "stop":
            self._fail("INCOMPLETE_COMPLETION", "Model completion did not finish normally")

    def _observe_metadata(self, body):
        """Allowlisted counters only; never retain reasoning text or headers."""
        model = body.get("model")
        if isinstance(model, str) and re.fullmatch(r"[A-Za-z0-9_.:/-]{1,128}", model):
            self.last_diagnostics["returned_model"] = model
        usage = body.get("usage")
        if isinstance(usage, dict):
            safe = {}
            for name in ("prompt_tokens", "completion_tokens", "total_tokens",
                         "prompt_cache_hit_tokens", "prompt_cache_miss_tokens"):
                if type(usage.get(name)) is int and usage[name] >= 0:
                    safe[name] = usage[name]
            details = usage.get("completion_tokens_details")
            if isinstance(details, dict):
                for name in ("reasoning_tokens", "accepted_prediction_tokens", "rejected_prediction_tokens"):
                    if type(details.get(name)) is int and details[name] >= 0:
                        safe[name] = details[name]
            if safe:
                self.last_diagnostics["usage"] = safe

    def _observe_reasoning(self, value, started):
        if isinstance(value, str) and value:
            d = self.last_diagnostics
            if "first_reasoning_seconds" not in d:
                d["first_reasoning_seconds"] = round(time.monotonic() - started, 3)
            d["reasoning_characters"] = d.get("reasoning_characters", 0) + len(value)

    def _decode_json(self, text):
        # Python's default decoder silently overwrites duplicate fields and
        # accepts NaN/Infinity. Neither is an unambiguous model JSON contract.
        def pairs(items):
            result = {}
            for name, value in items:
                if name in result:
                    self._fail("DUPLICATE_JSON_KEY", "JSON contains duplicate object fields")
                result[name] = value
            return result
        def constant(_value):
            self._fail("NON_FINITE_JSON", "JSON contains a non-finite number")
        def number(value):
            parsed = float(value)
            if not math.isfinite(parsed):
                constant(value)
            return parsed
        try:
            return json.loads(text, object_pairs_hook=pairs,
                              parse_constant=constant, parse_float=number)
        except (ValueError, RecursionError):
            self._fail("MALFORMED_RESPONSE", "Malformed LLM JSON response")

    def _json_object(self, content):
        if not isinstance(content, str):
            self._fail("NON_TEXT_CONTENT", "Model returned a non-text response")
        envelope = 'bare'
        if self.allow_json_fence:
            match = re.fullmatch(r'\s*```json[ \t]*\r?\n(.*?)\r?\n```\s*', content, re.S)
            if match is not None:
                content = match.group(1)
                envelope = 'single_json_fence'
        parsed = self._decode_json(content)
        if not isinstance(parsed, dict):
            self._fail("NON_OBJECT_JSON", "Model must return a JSON object")
        self.last_diagnostics['json_envelope_received'] = envelope
        return parsed

    def _read_stream(self, resp, started):
        content = []
        data = []
        event_bytes = 0
        finished = False
        d = self.last_diagnostics
        while True:
            # Checked at read boundaries; an in-flight read also has timeout.
            # This is not an exact wall-clock cancellation deadline.
            if time.monotonic() - started > self.max_stream_seconds:
                self._fail("STREAM_TIME_LIMIT", "LLM stream exceeded elapsed-time limit")
            line = resp.readline(_EVENT_LIMIT + 1)
            d["response_bytes"] += len(line)
            if time.monotonic() - started > self.max_stream_seconds:
                self._fail("STREAM_TIME_LIMIT", "LLM stream exceeded elapsed-time limit")
            if d["response_bytes"] > self.max_stream_wire_bytes or len(line) > _EVENT_LIMIT:
                self._fail("RESPONSE_TOO_LARGE", "LLM stream exceeded size limit")
            if not line:
                self._fail("INCOMPLETE_STREAM", "LLM stream ended before completion marker")
            line = line.rstrip(b"\r\n")
            if line.startswith(b"data:"):
                value = line[5:]
                if value.startswith(b" "):
                    value = value[1:]
                data.append(value)
                event_bytes += len(value)
                if event_bytes > _EVENT_LIMIT:
                    self._fail("RESPONSE_TOO_LARGE", "LLM stream event exceeded size limit")
            if line or not data:
                continue
            event = b"\n".join(data)
            data = []; event_bytes = 0
            if event == b"[DONE]":
                if not finished:
                    self._fail("INCOMPLETE_STREAM", "LLM stream has no normal finish reason")
                return self._json_object("".join(content))
            chunk = self._decode_json(event.decode("utf-8"))
            if not isinstance(chunk, dict) or "error" in chunk:
                self._fail("MALFORMED_RESPONSE", "LLM stream returned an invalid event")
            self._observe_metadata(chunk)
            d["stream_events"] += 1
            for choice in chunk.get("choices", []):
                if choice.get("index", 0) != 0:
                    continue
                delta = choice.get("delta", {})
                self._observe_reasoning(delta.get("reasoning_content"), started)
                if delta.get("refusal"):
                    self._fail("MODEL_REFUSAL", "Model refused to formulate this request")
                fragment = delta.get("content")
                if fragment is not None:
                    if not isinstance(fragment, str) or (finished and fragment):
                        self._fail("MALFORMED_RESPONSE", "Invalid stream content")
                    if fragment and "first_content_seconds" not in d:
                        d["first_content_seconds"] = round(time.monotonic() - started, 3)
                    content.append(fragment)
                    d["content_characters"] += len(fragment)
                    d["content_bytes"] += len(fragment.encode("utf-8"))
                    if d["content_bytes"] > _CONTENT_LIMIT:
                        self._fail("RESPONSE_TOO_LARGE", "LLM content exceeded size limit")
                reason = choice.get("finish_reason")
                self._finish(reason)
                finished = finished or reason == "stop"

    def generate_json(self, *, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": "system", "content": system_prompt},
                         {"role": "user", "content": user_prompt}],
        }
        # Explicit compatibility option only: local JSON/schema/provenance
        # validation still applies, and a failure never triggers a fallback call.
        if self.json_mode:
            payload["response_format"] = {"type": "json_object"}
        if self.max_completion_tokens is not None:
            payload["max_completion_tokens"] = self.max_completion_tokens
        if self.max_tokens is not None:
            payload["max_tokens"] = self.max_tokens
        if self.stream:
            payload["stream"] = True
        if self.thinking is not None:
            payload["thinking"] = {"type": self.thinking}
        req = Request(self.base_url + "/chat/completions",
                      data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                      headers={"Content-Type": "application/json",
                               "Authorization": "Bearer " + self.api_key}, method="POST")
        started = time.monotonic()
        self.last_diagnostics = {
            "stream": self.stream, "json_mode_sent": self.json_mode,
            "output_token_parameter": ("max_tokens" if self.max_tokens is not None else
                                       "max_completion_tokens" if self.max_completion_tokens is not None else None),
            "output_token_limit": self.max_tokens if self.max_tokens is not None else self.max_completion_tokens,
            "require_finish_reason": self.require_finish_reason,
            "max_stream_wire_bytes": self.max_stream_wire_bytes,
            "transport_calls": 1, "response_bytes": 0,
            "content_characters": 0, "content_bytes": 0, "stream_events": 0,
            "stage": "transport", "status": "started",
        }
        d = self.last_diagnostics
        error = None
        try:
            with self._transport(req, timeout=self.timeout) as resp:
                status = getattr(resp, "status", None)
                if type(status) is int:
                    d["http_status"] = status
                d["headers_seconds"] = round(time.monotonic() - started, 3)
                d["stage"] = "response"
                if self.stream:
                    parsed = self._read_stream(resp, started)
                else:
                    raw = resp.read(_CONTENT_LIMIT + 1)
                    d["response_bytes"] = len(raw)
                    if len(raw) > _CONTENT_LIMIT:
                        self._fail("RESPONSE_TOO_LARGE", "LLM response exceeded size limit")
                    body = self._decode_json(raw.decode("utf-8"))
                    self._observe_metadata(body)
                    choice = body["choices"][0]
                    if self.require_finish_reason and choice.get("finish_reason") is None:
                        self._fail("INCOMPLETE_COMPLETION", "Response has no normal finish reason")
                    self._finish(choice.get("finish_reason"))
                    message = choice["message"]
                    self._observe_reasoning(message.get("reasoning_content"), started)
                    if message.get("refusal"):
                        self._fail("MODEL_REFUSAL", "Model refused to formulate this request")
                    content = message["content"]
                    if isinstance(content, str):
                        d["content_characters"] = len(content)
                        d["content_bytes"] = len(content.encode("utf-8"))
                    parsed = self._json_object(content)
            d.update(stage="complete", status="json_object_received")
            return parsed
        except ProviderError as exc:
            error = exc
        except HTTPError as exc:
            d["http_status"] = exc.code
            exc.close()
            error = ProviderError(f"LLM HTTP request failed: status={exc.code}", code="HTTP_ERROR")
        except (URLError, TimeoutError, OSError, HTTPException) as exc:
            timeout = isinstance(exc, TimeoutError) or (
                isinstance(exc, URLError) and isinstance(exc.reason, TimeoutError))
            error = ProviderError("LLM transport failed", code="TIMEOUT" if timeout else "TRANSPORT_ERROR")
        except (KeyError, TypeError, AttributeError, IndexError, UnicodeError, json.JSONDecodeError):
            error = ProviderError("Malformed LLM JSON response", code="MALFORMED_RESPONSE")
        finally:
            d["elapsed_seconds"] = round(time.monotonic() - started, 3)
        d.update(status="failed", error_code=error.code)
        error.diagnostics = dict(d)
        raise error from None
