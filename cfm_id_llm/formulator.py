"""A0-A6 draft generator and deterministic evidence audit. No core route calls."""
from __future__ import annotations
from pydantic import ValidationError
from .audit import DraftEvidenceError, audit_draft
from .prompts import SYSTEM_PROMPT, make_user_prompt
from .providers.base import LLMProvider
from .schemas import BusinessCase, DraftProblemSpec, FormulationReport


class DraftValidationError(ValueError):
    """A provider output failed schema or quote-grounding validation."""


class ProblemFormulator:
    def __init__(self, provider: LLMProvider, *, system_prompt: str | None = None,
                 prompt_version: str | None = None):
        self.provider = provider
        self.system_prompt = system_prompt or SYSTEM_PROMPT
        self.prompt_version = prompt_version

    def formulate(self, case: BusinessCase) -> FormulationReport:
        # Treat all model output as untrusted. No automatic repairs or hidden fallback guesses.
        raw = self.provider.generate_json(system_prompt=self.system_prompt,
                                          user_prompt=make_user_prompt(case))
        try:
            draft = DraftProblemSpec.model_validate(raw)
            return audit_draft(case, draft, provider=self.provider.name,
                               prompt_version=self.prompt_version)
        except (ValidationError, DraftEvidenceError, ValueError) as exc:
            raise DraftValidationError(f"Provider returned an invalid untrusted draft: {exc}") from exc
