"""Independent v0.10 A0 formulator. No mathematical-Core dependencies."""
from __future__ import annotations
from pydantic import BaseModel, ValidationError

from .providers.base import LLMProvider
from .quality_prompts import (
    PROMPT_VERSION_V010, SYSTEM_PROMPT_V010, make_quality_user_prompt,
)
from .quality import MultiQueryDraftV010, MultiQueryQualityReportV010, audit_business_quality
from .schemas import BusinessCase, EvidenceQuote


class A0QualityValidationError(ValueError):
    def __init__(self, message: str, *, code='A0_REJECTED', diagnostics=None):
        super().__init__(message)
        self.code = code
        self.diagnostics = dict(diagnostics or {})


def _schema_diagnostics(exc: ValidationError) -> dict:
    schema = MultiQueryDraftV010.model_json_schema()
    fields = set(schema.get('properties', {}))
    for definition in schema.get('$defs', {}).values():
        fields.update(definition.get('properties', {}))
    codes = {
        'Primary query target must equal shared_draft.target': 'PRIMARY_TARGET_MISMATCH',
        'UNRESOLVED claims must have null value and no evidence': 'UNRESOLVED_CLAIM_CONTRACT',
    }
    errors = exc.errors(include_input=False, include_context=False, include_url=False)
    return {'stage': 'schema', 'issue_count': len(errors), 'issues': [
        {'path': [x if type(x) is int or x in fields else '[unknown_field]' for x in e['loc']],
         'code': codes.get(e['msg'].removeprefix('Value error, '), e['type'])}
        for e in errors[:20]]}


def _provenance_diagnostics(case: BusinessCase, draft: MultiQueryDraftV010) -> dict:
    """Explain a rejection using typed field paths, never source text or IDs.

    Called only after the existing audit rejects the draft. This does not
    replace that audit, repair quotes, or assess whether a quote supports a claim.
    """
    sources = case.source_map()
    issues = []
    count = 0

    def walk(value, path):
        nonlocal count
        if isinstance(value, EvidenceQuote):
            if value.source_id not in sources:
                code, field = 'EVIDENCE_SOURCE_NOT_FOUND', 'source_id'
            elif value.quote not in sources[value.source_id]:
                code, field = 'EVIDENCE_QUOTE_NOT_EXACT', 'quote'
            else:
                return
            count += 1
            if len(issues) < 20:
                issues.append({'path': [*path, field], 'code': code})
        elif isinstance(value, BaseModel):
            for field in type(value).model_fields:
                walk(getattr(value, field), [*path, field])
        elif isinstance(value, list):
            for index, child in enumerate(value):
                walk(child, [*path, index])

    walk(draft, [])
    return {'stage': 'provenance_or_audit', 'issue_count': count,
            'issues': issues, 'issues_truncated': count > len(issues)}


class A0QualityFormulatorV010:
    def __init__(self, provider: LLMProvider, *, system_prompt: str = SYSTEM_PROMPT_V010,
                 prompt_version: str = PROMPT_VERSION_V010):
        self.provider = provider
        self.system_prompt = system_prompt
        self.prompt_version = prompt_version

    def formulate(self, case: BusinessCase) -> MultiQueryQualityReportV010:
        raw = self.provider.generate_json(
            system_prompt=self.system_prompt,
            user_prompt=make_quality_user_prompt(case),
        )
        try:
            draft = MultiQueryDraftV010.model_validate(raw)
        except ValidationError as exc:
            raise A0QualityValidationError(
                'Untrusted A0 response rejected by schema', code='A0_SCHEMA_REJECTED',
                diagnostics=_schema_diagnostics(exc)) from None
        try:
            return audit_business_quality(case, draft, provider=self.provider.name,
                                          prompt_version=self.prompt_version)
        except ValueError:
            # Do not echo a quote, source ID or raw validator message.
            raise A0QualityValidationError(
                'Untrusted A0 response rejected by provenance/audit',
                code='A0_PROVENANCE_OR_AUDIT_REJECTED',
                diagnostics=_provenance_diagnostics(case, draft)) from None
