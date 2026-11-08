"""Versioned LLM formulation with exact source checks; never invokes ID math core."""
from __future__ import annotations
from pydantic import ValidationError
from .schemas import BusinessCase
from .providers.base import LLMProvider
from .multiquery_prompts import SYSTEM_PROMPT_V09, PROMPT_VERSION_V09, make_multiquery_user_prompt
from .multiquery import MultiQueryDraftV09, MultiQueryReportV09, audit_multiquery


class MultiQueryValidationError(ValueError):
    """The untrusted model output was not valid, not evidence-grounded, or inconsistent."""


class MultiQueryFormulatorV09:
    def __init__(self, provider: LLMProvider, *, system_prompt: str = SYSTEM_PROMPT_V09,
                 prompt_version: str = PROMPT_VERSION_V09):
        self.provider = provider
        self.system_prompt = system_prompt
        self.prompt_version = prompt_version

    def formulate(self, case: BusinessCase) -> MultiQueryReportV09:
        raw = self.provider.generate_json(system_prompt=self.system_prompt,
                                          user_prompt=make_multiquery_user_prompt(case))
        try:
            draft = MultiQueryDraftV09.model_validate(raw)
            return audit_multiquery(case, draft, provider=self.provider.name,
                                    prompt_version=self.prompt_version)
        except (ValidationError, ValueError) as exc:
            # Do not echo private document payload or raw model output in exceptions.
            raise MultiQueryValidationError(f"Untrusted multi-query response rejected ({type(exc).__name__})") from None
