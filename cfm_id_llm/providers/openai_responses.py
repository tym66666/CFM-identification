"""Opt-in, non-streaming Responses transport with mandatory local validation.

``text.format=json_schema`` is a generation constraint, not a proof or a
substitute for local validation. ``local_validator`` must reject invalid input
by raising (or returning False). A successful return value is ignored: this
provider returns the original decoded JSON, never a repaired/normalized answer.
The validator receives a defensive copy. Semantic review, scientific assumption
approval, and identification/certificate replay remain downstream duties.

The optional observer receives only the decoded final-answer JSON text, before
local validation. It can therefore preserve structurally invalid answers, but
not malformed JSON, reasoning, headers, or provider error bodies. Final answers
can contain sensitive business data: the caller controls secure storage. The
authentication key is redacted from observer text. Observer errors fail closed.

No retries, fallback, redirects, tools, SSE, SDK, or new dependency. ``timeout``
is a socket timeout, not a strict end-to-end deadline; use a bounded parent
process when a hard elapsed-time limit is required. A custom transport is a
trusted test/ledger hook and must also disable redirects and retries.
"""
from __future__ import annotations

from copy import deepcopy
from http.client import HTTPException
import json
import re
import time
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request

from .base import ProviderError
from .openai_chat import OpenAICompatibleChatProvider, _CONTENT_LIMIT


class OpenAICompatibleResponsesProvider(OpenAICompatibleChatProvider):
    """Explicit import only; existing Chat defaults and CLI remain unchanged."""

    def __init__(self, *, model: str, schema: dict[str, Any], schema_name: str,
                 local_validator: Callable[[dict[str, Any]], Any],
                 api_key: str | None = None,
                 base_url: str = "https://api.openai.com/v1",
                 timeout: float = 60.0, max_output_tokens: int | None = None,
                 reasoning_effort: str | None = None,
                 thinking: str | None = None,
                 max_response_bytes: int = 2_000_000,
                 final_content_observer: Callable[[str], Any] | None = None,
                 transport: Callable[..., Any] | None = None):
        if not isinstance(schema, dict) or not schema:
            raise ValueError("An explicit nonempty JSON Schema object is required")
        if not isinstance(schema_name, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", schema_name):
            raise ValueError("schema_name must contain 1 to 64 letters/digits/underscores/hyphens")
        if not callable(local_validator):
            raise ValueError("A local validator is required; server schema support is not validation")
        if final_content_observer is not None and not callable(final_content_observer):
            raise ValueError("final_content_observer must be callable")
        if max_output_tokens is not None and (type(max_output_tokens) is not int or max_output_tokens <= 0):
            raise ValueError("max_output_tokens must be a positive integer")
        if reasoning_effort not in (None, "none", "minimal", "low", "medium", "high", "xhigh"):
            raise ValueError("Unsupported reasoning effort")
        if type(max_response_bytes) is not int or not 0 < max_response_bytes <= 32_000_000:
            raise ValueError("max_response_bytes must be an integer from 1 to 32000000")
        try:
            # Freeze caller-owned schema; strict serialization rejects NaN/cycles.
            self._schema_json = json.dumps(schema, ensure_ascii=False, allow_nan=False)
        except (TypeError, ValueError, RecursionError):
            raise ValueError("Schema must be finite JSON data") from None
        # Reuse the existing endpoint security, no-redirect opener, key loading,
        # and strict JSON decoder. The Chat request implementation is not used.
        super().__init__(model=model, api_key=api_key, base_url=base_url,
                         timeout=timeout, allow_json_fence=False, transport=transport,
                         thinking=thinking)
        self.schema_name = schema_name
        self.max_output_tokens = max_output_tokens
        self.reasoning_effort = reasoning_effort
        self.max_response_bytes = max_response_bytes
        self._local_validator = local_validator
        self._final_content_observer = final_content_observer
        self.name = "openai-responses-compatible:" + self.model

    def _observe_metadata(self, body):
        """Allowlisted counters only. Never retain reasoning, IDs or headers."""
        for field, key, allowed in (
                ('thinking', 'type', ('enabled', 'disabled')),
                ('reasoning', 'effort', ('none', 'minimal', 'low', 'medium', 'high', 'xhigh')),
                ('incomplete_details', 'reason', ('max_output_tokens', 'content_filter'))):
            item = body.get(field)
            if isinstance(item, dict) and isinstance(item.get(key), str):
                value = item[key]
                self.last_diagnostics['returned_' + field + '_' + key] = value if value in allowed else 'other'
        model = body.get("model")
        if (isinstance(model, str) and re.fullmatch(r"[A-Za-z0-9_.:/-]{1,128}", model)
                and self.api_key not in model):
            self.last_diagnostics["returned_model"] = model
        usage = body.get("usage")
        if not isinstance(usage, dict):
            return
        safe = {}
        for name in ("input_tokens", "output_tokens", "total_tokens"):
            if type(usage.get(name)) is int and usage[name] >= 0:
                safe[name] = usage[name]
        for parent, name in (("input_tokens_details", "cached_tokens"),
                             ("output_tokens_details", "reasoning_tokens")):
            details = usage.get(parent)
            if isinstance(details, dict) and type(details.get(name)) is int and details[name] >= 0:
                safe[name] = details[name]
        if safe:
            self.last_diagnostics["usage"] = safe

    def _final_text(self, body):
        if not isinstance(body, dict) or body.get("object") != "response":
            self._fail("MALFORMED_RESPONSE", "Expected a Responses response object")
        self._observe_metadata(body)
        status = body.get("status")
        self.last_diagnostics["response_status"] = (
            status if status in ("completed", "incomplete", "failed", "queued", "in_progress", "cancelled")
            else "other")
        if status != "completed" or body.get("error") is not None or body.get("incomplete_details") is not None:
            self._fail("INCOMPLETE_COMPLETION", "Response did not complete normally")
        output = body.get("output")
        if not isinstance(output, list) or not output:
            self._fail("MALFORMED_RESPONSE", "Response has no final assistant message")
        message = None
        for index, item in enumerate(output):
            if not isinstance(item, dict):
                self._fail("MALFORMED_RESPONSE", "Invalid output item")
            kind = item.get("type")
            if kind == "reasoning":
                # No reasoning strings are observed, returned or stored.
                continue
            if kind != "message":
                self._fail("UNSUPPORTED_OUTPUT", "Tool and non-message output is unsupported")
            if message is not None or index != len(output) - 1:
                self._fail("AMBIGUOUS_OUTPUT", "Exactly one final assistant message is required")
            if item.get("role") != "assistant":
                self._fail("UNSUPPORTED_OUTPUT", "Final message must be from the assistant")
            if item.get("status", "completed") != "completed":
                self._fail("INCOMPLETE_COMPLETION", "Assistant message did not complete normally")
            message = item
        if message is None:
            self._fail("MALFORMED_RESPONSE", "Response has no final assistant message")
        parts = message.get("content")
        if not isinstance(parts, list) or not parts:
            self._fail("NON_TEXT_CONTENT", "Assistant message has no final text")
        chunks = []
        for part in parts:
            if not isinstance(part, dict):
                self._fail("NON_TEXT_CONTENT", "Invalid final content part")
            if part.get("type") == "refusal":
                self._fail("MODEL_REFUSAL", "Model refused to formulate this request")
            if part.get("type") != "output_text" or not isinstance(part.get("text"), str):
                self._fail("NON_TEXT_CONTENT", "Only output_text content is supported")
            chunks.append(part["text"])
        content = "".join(chunks)
        self.last_diagnostics.update(content_characters=len(content), content_bytes=len(content.encode("utf-8")))
        if self.last_diagnostics["content_bytes"] > _CONTENT_LIMIT:
            self._fail("RESPONSE_TOO_LARGE", "Final content exceeded size limit")
        return content

    def generate_json(self, *, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.model, "instructions": system_prompt, "input": user_prompt,
            "stream": False, "store": False,
            "text": {"format": {"type": "json_schema", "name": self.schema_name,
                                "schema": json.loads(self._schema_json), "strict": True}},
        }
        if self.max_output_tokens is not None:
            payload["max_output_tokens"] = self.max_output_tokens
        if self.reasoning_effort is not None:
            payload["reasoning"] = {"effort": self.reasoning_effort}
        # Explicit vendor extension, e.g. LongCat's thinking switch. Omitted by
        # default; reasoning.effort alone does not attest that thinking is off.
        if self.thinking is not None:
            payload["thinking"] = {"type": self.thinking}
        req = Request(self.base_url + "/responses",
                      data=json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8"),
                      headers={"Content-Type": "application/json",
                               "Authorization": "Bearer " + self.api_key}, method="POST")
        started = time.monotonic()
        self.last_diagnostics = {
            "api": "responses", "stream": False, "json_schema_sent": True,
            "output_token_parameter": "max_output_tokens" if self.max_output_tokens is not None else None,
            "output_token_limit": self.max_output_tokens,
            "reasoning_effort_sent": self.reasoning_effort,
            "thinking_type_sent": self.thinking,
            "transport_calls": 1, "response_bytes": 0,
            "content_characters": 0, "content_bytes": 0,
            "max_response_bytes": self.max_response_bytes,
            "local_validation_passed": False, "stage": "transport", "status": "started",
        }
        d = self.last_diagnostics
        error = None
        try:
            with self._transport(req, timeout=self.timeout) as resp:
                status = getattr(resp, "status", None)
                if type(status) is int:
                    d["http_status"] = status
                    if not 200 <= status < 300:
                        self._fail("HTTP_ERROR", "LLM HTTP request failed")
                d["headers_seconds"] = round(time.monotonic() - started, 3)
                d["stage"] = "response"
                wire = resp.read(self.max_response_bytes + 1)
                d["response_bytes"] = len(wire)
                if len(wire) > self.max_response_bytes:
                    self._fail("RESPONSE_TOO_LARGE", "LLM response exceeded size limit")
                body = self._decode_json(wire.decode("utf-8"))
                content = self._final_text(body)
                d["stage"] = "json"
                parsed = self._json_object(content)
            if self._final_content_observer is not None:
                d["stage"] = "observer"
                try:
                    self._final_content_observer(content.replace(self.api_key, "[REDACTED]"))
                except Exception:
                    self._fail("FINAL_CONTENT_OBSERVER_FAILED", "Final-content observer failed")
            d["stage"] = "local_validation"
            try:
                accepted = self._local_validator(deepcopy(parsed))
            except Exception:
                self._fail("LOCAL_VALIDATION_FAILED", "Response failed local validation")
            if accepted is False:
                self._fail("LOCAL_VALIDATION_FAILED", "Response failed local validation")
            d.update(stage="complete", status="locally_validated_json_received", local_validation_passed=True)
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
