"""Provider contract. Providers return JSON objects, never trusted math."""
from __future__ import annotations
from typing import Any, Protocol


class ProviderError(RuntimeError):
    def __init__(self, message: str, *, code: str = "PROVIDER_ERROR",
                 diagnostics: dict | None = None):
        super().__init__(message)
        self.code = code
        # Provider-owned counters only; never response text, headers or prompts.
        self.diagnostics = dict(diagnostics or {})


class LLMProvider(Protocol):
    name: str
    def generate_json(self, *, system_prompt: str, user_prompt: str) -> dict[str, Any]: ...
