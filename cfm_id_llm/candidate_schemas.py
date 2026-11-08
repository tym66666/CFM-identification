"""v0.3 untrusted LLM candidate contracts, independent of ID-Library releases.

A candidate is **never** a CoreDecision, mathematical certificate, estimate, or
estimator capability claim. JSON schema validation checks shape, not proof.
"""
from __future__ import annotations

from typing import Literal
from pydantic import Field, model_validator

from .schemas import StrictModel, TargetKind, PopulationInformationLevel
from .orchestration_schemas import canonical_sha256

_SHA = r"^[0-9a-f]{64}$"

CandidateClaim = Literal["POINT", "PARTIAL", "NOT_POINT", "UNDETERMINED"]
CandidateScope = Literal["AS_REVIEWED", "IF_ADDITIONAL_REQUIREMENTS"]
RequirementKind = Literal["A4_INFORMATION", "A5_ASSUMPTION", "A6_VALIDITY_SUPPORT", "TARGET_DEFINITION", "OTHER"]


class CandidateRequirementV03(StrictModel):
    """A *new requirement*, not a verified or admitted fact."""
    kind: RequirementKind
    description: str = Field(min_length=5, max_length=1200)
    why_needed: str = Field(min_length=5, max_length=1200)


class CandidateA4UseV03(StrictModel):
    """Separate observable-law claims from causal assumption claims."""
    source: Literal["REVIEWED_OPERATOR", "ADDITIONAL_OPERATOR", "UNRESOLVED"]
    level: PopulationInformationLevel | None = None
    operator: str | None = Field(default=None, max_length=2500)

    @model_validator(mode="after")
    def enforce_source(self):
        if self.source == "UNRESOLVED":
            if self.level is not None or self.operator is not None:
                raise ValueError("Unresolved A4 must not supply a fabricated observable operator")
        elif self.level in (None, PopulationInformationLevel.UNRESOLVED) or not self.operator:
            raise ValueError("Named A4 operators require a concrete level and symbolic description")
        return self


class ObservationalEquivalenceSketchV03(StrictModel):
    """An LLM-proposed pair of worlds; NOT independent counterexample verification."""
    world_a: str = Field(min_length=5, max_length=2500)
    world_b: str = Field(min_length=5, max_length=2500)
    why_observables_match: str = Field(min_length=5, max_length=2500)
    why_targets_differ: str = Field(min_length=5, max_length=2500)


class CandidateDraftV03(StrictModel):
    schema_version: Literal["cfm-id-candidate-draft-v0.3"] = "cfm-id-candidate-draft-v0.3"
    target_kind: TargetKind
    target_description: str = Field(min_length=3, max_length=2500)
    claimed_identification: CandidateClaim
    scope: CandidateScope
    a4_used: CandidateA4UseV03
    # Only A5 assumption NAMES explicitly admitted in HumanReviewV02 go here.
    admitted_assumptions_used: list[str] = Field(default_factory=list, max_length=30)
    additional_requirements: list[CandidateRequirementV03] = Field(default_factory=list, max_length=12)
    candidate_expression: str | None = Field(default=None, max_length=8000)
    # Mandatory for a NOT_POINT candidate, but still not mathematical proof.
    nonidentification_witness: ObservationalEquivalenceSketchV03 | None = None
    reasoning_steps: list[str] = Field(min_length=1, max_length=12)
    caveats: list[str] = Field(default_factory=list, max_length=12)
    suggested_checks: list[str] = Field(default_factory=list, max_length=12)

    @model_validator(mode="after")
    def guard_syntax(self):
        if len(self.admitted_assumptions_used) != len(set(self.admitted_assumptions_used)):
            raise ValueError("Duplicate admitted assumptions")
        if self.claimed_identification in ("POINT", "PARTIAL") and not self.candidate_expression:
            raise ValueError("POINT/PARTIAL candidates need an explicit symbolic formula or set")
        if self.claimed_identification in ("NOT_POINT", "UNDETERMINED") and self.candidate_expression is not None:
            raise ValueError("NOT_POINT/UNDETERMINED must not fabricate an identified expression")
        if self.claimed_identification == "NOT_POINT" and self.nonidentification_witness is None:
            raise ValueError("NOT_POINT requires a proposed observational-equivalence witness")
        if self.claimed_identification != "NOT_POINT" and self.nonidentification_witness is not None:
            raise ValueError("Counterexample witness only belongs to NOT_POINT")
        if self.scope == "IF_ADDITIONAL_REQUIREMENTS" and not self.additional_requirements:
            raise ValueError("Conditional answer must list the additional requirements")
        if self.scope == "AS_REVIEWED" and self.additional_requirements:
            raise ValueError("Additional conditions cannot masquerade as previously reviewed facts")
        if self.a4_used.source == "ADDITIONAL_OPERATOR":
            if self.scope != "IF_ADDITIONAL_REQUIREMENTS":
                raise ValueError("Extra A4 requires conditional scope")
            if not any(r.kind == "A4_INFORMATION" for r in self.additional_requirements):
                raise ValueError("Extra A4 must be explained as an unconfirmed requirement")
        return self


class CandidateAuditIssueV03(StrictModel):
    code: str = Field(min_length=2, max_length=100)
    detail: str = Field(min_length=5, max_length=1500)


class CandidateReportV03(StrictModel):
    schema_version: Literal["cfm-id-candidate-report-v0.3"] = "cfm-id-candidate-report-v0.3"
    gateway_version: Literal["0.3.0"] = "0.3.0"
    case_id: str
    input_sha256: str = Field(pattern=_SHA)
    draft_sha256: str = Field(pattern=_SHA)
    confirmed_problem_sha256: str = Field(pattern=_SHA)
    routing_sha256: str = Field(pattern=_SHA)
    provider: str = Field(min_length=1, max_length=250)
    prompt_version: str = Field(min_length=1, max_length=150)
    execution_mode: Literal["CORE_UNSUPPORTED", "MOCK_PREVIEW"]
    status: Literal[
        "UNVERIFIED_CANDIDATE", "UNDETERMINED_UNVERIFIED", "REJECTED_UNSAFE_OUTPUT", "PROVIDER_FAILED"
    ]
    candidate: CandidateDraftV03 | None = None
    issues: list[CandidateAuditIssueV03] = Field(default_factory=list, max_length=30)
    explanation: str = Field(min_length=5, max_length=2500)
    # These are intentionally not mutable API switches.
    verification_level: Literal["LLM_UNVERIFIED"] = "LLM_UNVERIFIED"
    estimation_handoff_allowed: Literal[False] = False
    mathematical_certificate: Literal[None] = None

    @model_validator(mode="after")
    def safe_envelope(self):
        if self.status in ("UNVERIFIED_CANDIDATE", "UNDETERMINED_UNVERIFIED"):
            if self.candidate is None:
                raise ValueError("Successful candidate report requires candidate data")
            if (self.status == "UNDETERMINED_UNVERIFIED") != (self.candidate.claimed_identification == "UNDETERMINED"):
                raise ValueError("Status and candidate claim are inconsistent")
        elif self.candidate is not None:
            raise ValueError("Rejected/failed reports must not expose a candidate as a valid result")
        return self

    def fingerprint(self) -> str:
        return canonical_sha256(self)
