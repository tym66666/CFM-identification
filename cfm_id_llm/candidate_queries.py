"""Standalone v0.11 per-query exploratory Identification Candidate Reasoner.

This module deliberately does NOT import the mathematical Core. A trusted, in-process
integration owns the live theorem result and scientific approvals. Raw JSON, CLI
arguments, hashes, and LLM responses cannot turn themselves into production Core
coverage receipts. A mock-only port exists for explicitly labeled offline previews.

The CandidateDraftV03 mathematical vocabulary is reused, not recertified. In
particular, a NOT_POINT world pair is only a proposed sketch, NEVER a proof.
"""
from __future__ import annotations

from typing import Literal, Protocol, runtime_checkable

from pydantic import Field, ValidationError, model_validator

from .audit import fingerprint_business_case
from .candidate_schemas import CandidateDraftV03, CandidateAuditIssueV03
from .candidate_query_prompts import (
    CANDIDATE_SYSTEM_PROMPT_V011, PROMPT_VERSION_V011, make_candidate_prompt_v011,
)
from .orchestration_schemas import canonical_sha256
from .providers.base import LLMProvider
from .quality import MultiQueryQualityReportV010, audit_business_quality
from .schemas import BusinessCase, PopulationInformationLevel, StrictModel, TargetKind

_SHA = r"^[0-9a-f]{64}$"
COVERAGE_GAP_CODES = frozenset({
    "THEOREM_BACKEND_UNAVAILABLE", "NO_REGISTERED_THEOREM",
    "OFF_SUPPORT_ALTERNATE_THEOREM",
})


class CandidateSafetyError(ValueError):
    """The complete case/draft/review envelope is stale or inconsistent."""


class BusinessQueryReviewV011(StrictModel):
    """Explicit EXTERNAL business approval, never created by model inference.

    Hashes are binding checks, not proof of reviewer identity or independent
    scientific admission. v0.10 hashes are used, NOT v0.9 legacy draft hashes.
    """
    schema_version: Literal["cfm-id-candidate-business-review-v0.11"] = "cfm-id-candidate-business-review-v0.11"
    case_id: str
    input_sha256: str = Field(pattern=_SHA)
    draft_sha256: str = Field(pattern=_SHA)
    confirmed_query_ids: list[str] = Field(min_length=1, max_length=8)
    reviewed_by: str = Field(min_length=3, max_length=150)
    decision: Literal["CONFIRMED"]
    review_note: str = Field(min_length=10, max_length=2500)

    @model_validator(mode="after")
    def unique_queries(self):
        if len(self.confirmed_query_ids) != len(set(self.confirmed_query_ids)):
            raise ValueError("Duplicate query review")
        return self

    def fingerprint(self) -> str:
        return canonical_sha256(self)


class ApprovedA4ReferenceV011(StrictModel):
    """Projection of a separate SCIENTIFIC approval, supplied by trusted code.

    Population level is OPTIONAL because current v2.9.1 source IDs and operator
    types do not always provide an A0 PopulationInformationLevel mapping. Never
    invent that mapping. Only an exact level/operator pair can be 'REVIEWED'.
    """
    source_id: str = Field(min_length=1, max_length=180)
    operator: str = Field(min_length=1, max_length=2500)
    typed_source_sha256: str = Field(pattern=_SHA)
    level: PopulationInformationLevel | None = None


class ApprovedA5LicenseV011(StrictModel):
    name: str = Field(min_length=1, max_length=180)
    typed_assumption_sha256: str = Field(pattern=_SHA)


class TrustedScienceScopeV011(StrictModel):
    """Source/assumption SCOPE, not a theorem or a claim these hold in reality."""
    scientific_review_sha256: str = Field(pattern=_SHA)
    a4_sources: list[ApprovedA4ReferenceV011] = Field(default_factory=list, max_length=30)
    a5_licenses: list[ApprovedA5LicenseV011] = Field(default_factory=list, max_length=50)

    @model_validator(mode="after")
    def unique_bindings(self):
        a4 = [(a.source_id, a.typed_source_sha256) for a in self.a4_sources]
        a5 = [(a.name, a.typed_assumption_sha256) for a in self.a5_licenses]
        if len(set(a4)) != len(a4) or len(set(a5)) != len(a5):
            raise ValueError("Duplicate scientific reference")
        return self

    def fingerprint(self) -> str:
        return canonical_sha256(self)


class CoreCoverageV011(StrictModel):
    """Trusted *adapter's* observation of a query's actual theorem route outcome.

    This schema alone does not authenticate Core execution. Gateway MUST obtain
    it by calling a trusted in-process port, NEVER by accepting a client-supplied
    'production outcome' JSON. The standalone CLI only has mock previews.
    """
    case_id: str
    input_sha256: str = Field(pattern=_SHA)
    draft_sha256: str = Field(pattern=_SHA)
    query_id: str
    target_sha256: str = Field(pattern=_SHA)
    business_review_sha256: str = Field(pattern=_SHA)
    source_mode: Literal["PRODUCTION", "MOCK"]
    core_version: str = Field(min_length=3, max_length=120)
    adapter_id: str = Field(min_length=3, max_length=120)
    status: Literal[
        "POINT", "PARTIAL", "NOT_POINT", "NO_USEFUL_ID", "NEEDS_INPUT", "UNSUPPORTED",
        "NO_ADAPTER", "INCOMPATIBLE", "ERROR", "CORE_VERIFICATION_FAILED",
        "AWAITING_HUMAN_REVIEW",
    ]
    fallback: Literal["ELIGIBLE_NOT_EXECUTED", "BLOCKED", "NOT_NEEDED"] = "BLOCKED"
    reason_code: str = Field(default="", max_length=180)
    # These are produced by the scientific/typed Core bridge, never by the LLM.
    # For v2.9.1 these correspond to formal_target_fingerprint_v29(inquiry)
    # and ApprovedScienceBindingV291.scope_digest respectively.
    formal_target_sha256: str | None = Field(default=None, pattern=_SHA)
    business_math_crosswalk_sha256: str | None = Field(default=None, pattern=_SHA)
    science_scope: TrustedScienceScopeV011 | None = None

    @model_validator(mode="after")
    def basic_status_constraints(self):
        if self.fallback == "ELIGIBLE_NOT_EXECUTED" and self.status != "UNSUPPORTED":
            raise ValueError("Only UNSUPPORTED can be candidate eligible")
        if self.source_mode == "PRODUCTION":
            if self.science_scope is None:
                raise ValueError("Production coverage needs bound scientific review")
            if self.formal_target_sha256 is None or self.business_math_crosswalk_sha256 is None:
                raise ValueError("Production must bind the exact typed target and approved crosswalk")
            if self.core_version.upper().startswith(("MOCK", "TEST_", "NOT_CONNECTED")):
                raise ValueError("Mock identity must not masquerade as production")
        return self

    def fingerprint(self) -> str:
        return canonical_sha256(self)


@runtime_checkable
class TrustedCoveragePortV011(Protocol):
    """Implemented only by an authorized, local integration calling the real Core.

    Important: an arbitrary object satisfying this Protocol is not security proof.
    Host app must securely control who can install this port and its review input.
    """
    @property
    def mode(self) -> Literal["PRODUCTION", "MOCK"]: ...

    def lookup(self, *, case: BusinessCase, quality: MultiQueryQualityReportV010,
               review: BusinessQueryReviewV011, query_id: str) -> CoreCoverageV011: ...


class MockCoveragePortV011:
    """Offline-only test port. Cannot be promoted by setting a JSON flag."""
    mode: Literal["MOCK"] = "MOCK"

    def __init__(self, entries: dict[str, CoreCoverageV011]):
        if any(x.source_mode != "MOCK" for x in entries.values()):
            raise ValueError("Mock port can only hold MOCK outcomes")
        self.entries = entries
        self.calls: list[str] = []

    def lookup(self, *, case: BusinessCase, quality: MultiQueryQualityReportV010,
               review: BusinessQueryReviewV011, query_id: str) -> CoreCoverageV011:
        self.calls.append(query_id)
        return self.entries[query_id]


class CandidateProposalV011(StrictModel):
    schema_version: Literal["cfm-id-candidate-proposal-v0.11"] = "cfm-id-candidate-proposal-v0.11"
    query_id: str
    target_sha256: str = Field(pattern=_SHA)
    semantics_sha256: str = Field(pattern=_SHA)
    science_scope_sha256: str = Field(pattern=_SHA)
    # The same restricted mathematical A4/A5 language as the v0.3 reasoner.
    proposal: CandidateDraftV03
    proposed_validation_checks: list[str] = Field(min_length=1, max_length=12)
    known_core_coverage_gap: str = Field(min_length=5, max_length=1000)


class CandidateQueryReportV011(StrictModel):
    schema_version: Literal["cfm-id-candidate-query-report-v0.11"] = "cfm-id-candidate-query-report-v0.11"
    query_id: str
    target_sha256: str = Field(pattern=_SHA)
    status: Literal[
        "BLOCKED", "UNVERIFIED_CANDIDATE", "UNDETERMINED_UNVERIFIED",
        "REJECTED_UNSAFE_OUTPUT", "PROVIDER_FAILED",
    ]
    reason_code: str
    mode: Literal["NOT_RUN", "TRUSTED_CORE_GAP", "MOCK_PREVIEW"] = "NOT_RUN"
    coverage_sha256: str | None = Field(default=None, pattern=_SHA)
    science_scope_sha256: str | None = Field(default=None, pattern=_SHA)
    candidate: CandidateProposalV011 | None = None
    issues: list[CandidateAuditIssueV03] = Field(default_factory=list, max_length=30)
    verification_level: Literal["LLM_UNVERIFIED"] = "LLM_UNVERIFIED"
    estimation_handoff_allowed: Literal[False] = False
    mathematical_certificate: Literal[None] = None

    @model_validator(mode="after")
    def safe_claims(self):
        successful = {"UNVERIFIED_CANDIDATE", "UNDETERMINED_UNVERIFIED"}
        if self.status in successful:
            if not self.candidate or self.mode == "NOT_RUN" or not self.coverage_sha256:
                raise ValueError("Candidate needs a bound coverage receipt")
            is_unknown = self.candidate.proposal.claimed_identification == "UNDETERMINED"
            if is_unknown != (self.status == "UNDETERMINED_UNVERIFIED"):
                raise ValueError("Candidate verdict and output status disagree")
        elif self.candidate is not None:
            raise ValueError("Rejected and blocked outputs cannot carry valid candidates")
        return self


class CandidateBatchReportV011(StrictModel):
    schema_version: Literal["cfm-id-candidate-batch-report-v0.11"] = "cfm-id-candidate-batch-report-v0.11"
    gateway_version: Literal["0.11.0"] = "0.11.0"
    case_id: str
    input_sha256: str = Field(pattern=_SHA)
    draft_sha256: str = Field(pattern=_SHA)
    business_review_sha256: str = Field(pattern=_SHA)
    prompt_version: str = PROMPT_VERSION_V011
    provider: str
    results: list[CandidateQueryReportV011] = Field(min_length=1, max_length=8)
    mathematical_verification: Literal["NOT_PERFORMED"] = "NOT_PERFORMED"
    estimation_handoff_allowed: Literal[False] = False

    @model_validator(mode="after")
    def unique_queries(self):
        if len({x.query_id for x in self.results}) != len(self.results):
            raise ValueError("Candidate query IDs not unique")
        return self


def audit_proposal_v011(candidate: CandidateProposalV011, *, query, outcome: CoreCoverageV011) -> list[CandidateAuditIssueV03]:
    """Deterministic identity and permission checks; NOT mathematical proof checks."""
    problems: list[CandidateAuditIssueV03] = []

    def flag(code: str, message: str):
        problems.append(CandidateAuditIssueV03(code=code, detail=message))

    if candidate.query_id != query.query_id:
        flag("QUERY_CHANGED", "Candidate switched to another business inquiry")
    if candidate.target_sha256 != canonical_sha256(query.target):
        flag("TARGET_HASH_CHANGED", "Candidate changed the original business causal target")
    if candidate.semantics_sha256 != canonical_sha256(query.semantics):
        flag("SEMANTICS_HASH_CHANGED", "Candidate changed reviewed intervention/comparison/policy semantics")
    scope = outcome.science_scope
    if scope is None:
        flag("SCIENTIFIC_SCOPE_MISSING", "There is no independently supplied scientific scope")
        return problems
    if candidate.science_scope_sha256 != scope.fingerprint():
        flag("SCIENTIFIC_SCOPE_CHANGED", "Candidate changed the scientific source/assumption binding")
    p = candidate.proposal
    if p.target_kind != query.target.kind:
        flag("TARGET_KIND_CHANGED", "Candidate used a different estimand family")
    if p.target_description != query.target.description.value:
        flag("TARGET_DESCRIPTION_CHANGED", "Candidate rewrote the reviewed business target")
    approved = {x.name for x in scope.a5_licenses}
    if unknown := set(p.admitted_assumptions_used) - approved:
        flag("UNADMITTED_A5_USED", "Candidate invoked A5 assumptions not present in approved science scope: " + ", ".join(sorted(unknown)))
    if p.a4_used.source == "REVIEWED_OPERATOR":
        matched = any(x.operator == p.a4_used.operator and x.level is not None and
                      x.level == p.a4_used.level for x in scope.a4_sources)
        if not matched:
            flag("A4_OPERATOR_NOT_APPROVED", "A4 claim is not an exact typed/level scientific source in this scope")
    if p.a4_used.source == "UNRESOLVED" and p.claimed_identification != "UNDETERMINED":
        if p.scope != "IF_ADDITIONAL_REQUIREMENTS" or not any(
                r.kind == "A4_INFORMATION" for r in p.additional_requirements):
            flag("A4_CONDITIONAL_REQUIRED", "Missing population information requires explicit conditional A4")
    if p.a4_used.source == "ADDITIONAL_OPERATOR":
        if any(x.operator == p.a4_used.operator and x.level == p.a4_used.level for x in scope.a4_sources):
            flag("A4_ALREADY_APPROVED", "Use reviewed operator, not an invented new information source")
    if p.claimed_identification in ("POINT", "PARTIAL") and not p.candidate_expression:
        flag("CANDIDATE_FORMULA_MISSING", "Exploratory mathematical claim requires a proposed expression")
    return problems


class CandidateReasonerV011:
    """One-shot per-query candidate analysis on a *trusted* Core coverage gap."""
    def __init__(self, provider: LLMProvider, core_port: TrustedCoveragePortV011):
        self.provider = provider
        self.core_port = core_port

    def run(self, *, case: BusinessCase, quality: MultiQueryQualityReportV010,
            business_review: BusinessQueryReviewV011, allow_mock_preview: bool = False) -> CandidateBatchReportV011:
        if quality.case_id != case.case_id or quality.input_sha256 != fingerprint_business_case(case):
            raise CandidateSafetyError("Business data changed or case ID mismatched")
        if quality.draft_sha256 != canonical_sha256(quality.draft):
            raise CandidateSafetyError("Multi-query draft hash no longer matches")
        fresh = audit_business_quality(case, quality.draft, provider=quality.provider,
                                       prompt_version=quality.prompt_version)
        if fresh != quality:
            raise CandidateSafetyError("A0 report inconsistent with newly recomputed provenance audit")
        if (business_review.case_id != case.case_id or
                business_review.input_sha256 != quality.input_sha256 or
                business_review.draft_sha256 != quality.draft_sha256):
            raise CandidateSafetyError("Business approval is stale or for another version")
        query_ids = {q.query_id for q in quality.draft.queries}
        if not set(business_review.confirmed_query_ids).issubset(query_ids):
            raise CandidateSafetyError("Business approval named a nonexistent inquiry")
        if self.core_port.mode not in ("PRODUCTION", "MOCK"):
            raise CandidateSafetyError("Unrecognized Core port mode")
        reviewed = set(business_review.confirmed_query_ids)
        statuses = {q.query_id: q for q in quality.query_quality}
        reports = []
        for query in quality.draft.queries:
            target_hash = canonical_sha256(query.target)

            def blocked(reason: str, *, issue: CandidateAuditIssueV03 | None = None):
                return CandidateQueryReportV011(query_id=query.query_id, target_sha256=target_hash,
                    status="BLOCKED", reason_code=reason, issues=[issue] if issue else [])

            if query.query_id not in reviewed:
                reports.append(blocked("QUERY_NOT_BUSINESS_APPROVED"))
                continue
            if statuses[query.query_id].business_status != "FORMALIZATION_READY":
                reports.append(blocked("BUSINESS_FORMULATION_NOT_READY"))
                continue
            if query.target.kind == TargetKind.UNRESOLVED:
                reports.append(blocked("TARGET_UNRESOLVED"))
                continue
            if self.core_port.mode == "MOCK" and not allow_mock_preview:
                reports.append(blocked("MOCK_PREVIEW_NOT_AUTHORIZED"))
                continue
            try:
                core = self.core_port.lookup(case=case, quality=quality, review=business_review,
                                             query_id=query.query_id)
            except Exception:
                reports.append(blocked("CORE_COVERAGE_LOOKUP_FAILED"))
                continue
            if not isinstance(core, CoreCoverageV011):
                reports.append(blocked("INVALID_TRUSTED_PORT_RESULT"))
                continue
            if (core.case_id != case.case_id or core.input_sha256 != quality.input_sha256 or
                    core.draft_sha256 != quality.draft_sha256 or
                    core.business_review_sha256 != business_review.fingerprint() or
                    core.query_id != query.query_id or core.target_sha256 != target_hash):
                reports.append(blocked("CORE_COVERAGE_BINDING_MISMATCH"))
                continue
            if ((self.core_port.mode == "PRODUCTION") != (core.source_mode == "PRODUCTION")):
                reports.append(blocked("CORE_PORT_MODE_MISMATCH"))
                continue
            if core.status != "UNSUPPORTED" or core.fallback != "ELIGIBLE_NOT_EXECUTED":
                reports.append(blocked("NOT_A_COVERAGE_GAP"))
                continue
            if core.reason_code not in COVERAGE_GAP_CODES:
                reports.append(blocked("UNAPPROVED_COVERAGE_GAP_REASON"))
                continue
            if core.science_scope is None:
                reports.append(blocked("SCIENTIFIC_BINDING_REQUIRED"))
                continue
            if self.core_port.mode == "PRODUCTION" and (
                core.science_scope.scientific_review_sha256 == "0" * 64 or
                not core.science_scope.a4_sources or not core.science_scope.a5_licenses):
                reports.append(blocked("PRODUCTION_SCIENTIFIC_ADMISSION_INCOMPLETE"))
                continue
            mode: Literal["TRUSTED_CORE_GAP", "MOCK_PREVIEW"] = (
                "TRUSTED_CORE_GAP" if self.core_port.mode == "PRODUCTION" else "MOCK_PREVIEW")
            envelope = dict(query_id=query.query_id, target_sha256=target_hash,
                            mode=mode, coverage_sha256=core.fingerprint(),
                            science_scope_sha256=core.science_scope.fingerprint())
            try:
                output = self.provider.generate_json(
                    system_prompt=CANDIDATE_SYSTEM_PROMPT_V011,
                    user_prompt=make_candidate_prompt_v011(quality, query, core),
                )
            except Exception as exc:
                reports.append(CandidateQueryReportV011(**envelope, status="PROVIDER_FAILED",
                    reason_code="MODEL_PROVIDER_FAILED",
                    issues=[CandidateAuditIssueV03(code="PROVIDER_FAILURE", detail="Provider failure: " + type(exc).__name__)]))
                continue
            try:
                draft = CandidateProposalV011.model_validate(output)
            except (ValidationError, ValueError, TypeError):
                reports.append(CandidateQueryReportV011(**envelope, status="REJECTED_UNSAFE_OUTPUT",
                    reason_code="INVALID_CANDIDATE_SCHEMA",
                    issues=[CandidateAuditIssueV03(code="INVALID_CANDIDATE_SCHEMA",
                                                       detail="LLM output failed strict schema validation")]))
                continue
            problems = audit_proposal_v011(draft, query=query, outcome=core)
            if problems:
                reports.append(CandidateQueryReportV011(**envelope, status="REJECTED_UNSAFE_OUTPUT",
                    reason_code="CANDIDATE_BINDING_OR_PERMISSION_REJECTED", issues=problems))
                continue
            state = ("UNDETERMINED_UNVERIFIED" if draft.proposal.claimed_identification == "UNDETERMINED"
                     else "UNVERIFIED_CANDIDATE")
            reports.append(CandidateQueryReportV011(**envelope, status=state,
                reason_code="EXPLORATORY_MATH_ONLY_NOT_CERTIFIED", candidate=draft))
        return CandidateBatchReportV011(case_id=case.case_id,
            input_sha256=quality.input_sha256, draft_sha256=quality.draft_sha256,
            business_review_sha256=business_review.fingerprint(), provider=self.provider.name,
            results=reports)
