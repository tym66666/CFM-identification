"""Deterministic fixture-only provider for offline development and CI."""
from __future__ import annotations
import copy
from typing import Any
from .base import ProviderError


class MockProvider:
    name = "mock-fixture"

    def __init__(self, response: dict[str, Any]):
        if not isinstance(response, dict):
            raise ProviderError("Mock response must be a JSON object")
        self._response = copy.deepcopy(response)
        self.calls = 0

    def generate_json(self, *, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        self.calls += 1
        return copy.deepcopy(self._response)
