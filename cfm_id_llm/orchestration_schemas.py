"""Gateway v0.2 routing contracts. No Identification Library version is imported.

Only an explicit human review may make a draft eligible for a core attempt.
A human review is a *recorded assertion*, not scientific proof of assumptions.
Only a trusted future core adapter with independent theorem replay can certify math.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Literal
from pydantic import Field, model_validator
from .schemas import DraftProblemSpec, StrictModel


_SHA = r"^[0-9a-f]{64}$"


def canonical_sha256(value: Any) -> str:
    """Stable SHA256 for structured contracts (not a signature)."""
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class HumanReviewV02(StrictModel):
    """Supplied by a real reviewer, NEVER created by an LLM provider automatically."""
    schema_version: Literal["cfm-id-human-review-v0.2"] = "cfm-id-human-review-v0.2"
    input_sha256: str = Field(pattern=_SHA)
    draft_sha256: str = Field(pattern=_SHA)
    reviewed_by: str = Field(min_length=2, max_length=150)
    decision: Literal["CONFIRMED"]
    review_note: str = Field(min_length=5, max_length=2000)
    # Empty means no A5 assumptions were admitted through this human-review record.
    admitted_assumptions: list[str] = Field(default_factory=list, max_length=30)

    @model_validator(mode="after")
    def distinct_assumptions(self):
        if len(self.admitted_assumptions) != len(set(self.admitted_assumptions)):
            raise ValueError("admitted_assumptions must be unique")
        return self


class ConfirmedProblemV02(StrictModel):
    """Audited draft with explicit reviewer binding; not automatically a core TaskSpec."""
    schema_version: Literal["cfm-id-confirmed-v0.2"] = "cfm-id-confirmed-v0.2"
    case_id: str
    input_sha256: str = Field(pattern=_SHA)
    draft_sha256: str = Field(pattern=_SHA)
    draft: DraftProblemSpec
    human_review: HumanReviewV02

    @model_validator(mode="after")
    def match_digests(self):
        if self.draft_sha256 != canonical_sha256(self.draft):
            raise ValueError("Draft contents do not match draft_sha256")
        if self.human_review.draft_sha256 != self.draft_sha256 or self.human_review.input_sha256 != self.input_sha256:
            raise ValueError("Human review fingerprint mismatch")
        names = {assumption.name for assumption in self.draft.assumptions}
        if set(self.human_review.admitted_assumptions) - names:
            raise ValueError("Human review admitted an assumption absent from this draft")
        return self

    def fingerprint(self) -> str:
        return canonical_sha256(self)


# Raw results returned by the *core adapter*; claims are not verified by their types.
MathClaim = Literal["POINT", "PARTIAL", "NOT_POINT", "NO_USEFUL_ID"]
CoreStatus = Literal[
    "POINT", "PARTIAL", "NOT_POINT", "NO_USEFUL_ID",
    "NEEDS_INPUT", "UNSUPPORTED", "NO_ADAPTER", "INCOMPATIBLE", "ERROR",
]
MATH_STATUSES: frozenset[str] = frozenset(("POINT", "PARTIAL", "NOT_POINT", "NO_USEFUL_ID"))


class CoreCapabilitiesV02(StrictModel):
    adapter_id: str = Field(min_length=1, max_length=150)
    library_version: str = Field(min_length=1, max_length=150)
    available_routes: list[str] = Field(default_factory=list, max_length=100)
    description: str = Field(default="", max_length=2000)

    @model_validator(mode="after")
    def unique_routes(self):
        if len(self.available_routes) != len(set(self.available_routes)):
            raise ValueError("Duplicate route names in capabilities")
        return self


class CoreDecisionV02(StrictModel):
    """A core's claimed answer. Only replay by a trusted adapter upgrades math status."""
    status: CoreStatus
    problem_sha256: str = Field(pattern=_SHA)
    route_id: str | None = Field(default=None, max_length=150)
    identified_expression: str | None = Field(default=None, max_length=10000)
    certificate: dict[str, Any] | None = None
    reason: str = Field(default="", max_length=2000)
    missing_requirements: list[str] = Field(default_factory=list, max_length=25)

    @model_validator(mode="after")
    def no_bare_math_claims(self):
        if self.status in MATH_STATUSES:
            if not self.route_id or not self.certificate:
                raise ValueError("Mathematical conclusions require route_id and nonempty certificate")
            if self.status in {"POINT", "PARTIAL"} and not self.identified_expression:
                raise ValueError("Identified formulas or set descriptions are required")
        elif self.certificate is not None or self.identified_expression is not None:
            raise ValueError("Nonmathematical core statuses must not carry proof/identified expression")
        return self

    def fingerprint(self) -> str:
        return canonical_sha256(self)


class CoreReplayV02(StrictModel):
    """Replay receipt obtained separately via CorePort.replay_verify()."""
    accepted: bool
    problem_sha256: str = Field(pattern=_SHA)
    decision_sha256: str = Field(pattern=_SHA)
    verifier_id: str = Field(min_length=1, max_length=150)
    details: str = Field(default="", max_length=2000)


FlowStatus = Literal[
    "NEEDS_CLARIFICATION", "AWAITING_HUMAN_REVIEW", "NO_CORE_CONNECTED",
    "MOCK_CORE_RESULT", "CORE_VERIFIED", "CORE_NEEDS_INPUT", "CORE_UNSUPPORTED",
    "CORE_NO_ADAPTER", "CORE_INCOMPATIBLE", "CORE_ERROR", "CORE_VERIFICATION_FAILED",
    "CORE_BINDING_FAILED",
]
VerificationLevel = Literal["NOT_PERFORMED", "MOCK_ONLY", "CORE_REPLAY_VERIFIED", "FAILED"]
FallbackDisposition = Literal[
    "NOT_EVALUATED", "BLOCKED_NEEDS_INPUT", "BLOCKED_SAFETY_FAILURE", "BLOCKED_NO_CORE",
    "MOCK_ONLY", "ELIGIBLE_NOT_IMPLEMENTED", "NOT_NEEDED",
]


class OrchestrationReportV02(StrictModel):
    schema_version: Literal["cfm-id-orchestration-v0.2"] = "cfm-id-orchestration-v0.2"
    gateway_version: Literal["0.2.0"] = "0.2.0"
    case_id: str
    input_sha256: str = Field(pattern=_SHA)
    draft_sha256: str = Field(pattern=_SHA)
    confirmed_problem_sha256: str | None = Field(default=None, pattern=_SHA)
    status: FlowStatus
    core: CoreCapabilitiesV02 | None = None
    core_status: CoreStatus | None = None
    core_route: str | None = None
    candidate_math_claim: MathClaim | None = None
    core_expression: str | None = None
    core_decision_sha256: str | None = Field(default=None, pattern=_SHA)
    core_verifier_id: str | None = Field(default=None, max_length=150)
    core_certificate: dict[str, Any] | None = None
    verification_level: VerificationLevel = "NOT_PERFORMED"
    fallback: FallbackDisposition = "NOT_EVALUATED"
    explanation: str = Field(min_length=1, max_length=4000)
    next_steps: list[str] = Field(default_factory=list, max_length=20)
    # v0.2 NEVER hands over to estimation, even with a future verified core.
    estimation_handoff_allowed: Literal[False] = False

    @model_validator(mode="after")
    def guarded_verification(self):
        if self.status == "CORE_VERIFIED" and self.verification_level != "CORE_REPLAY_VERIFIED":
            raise ValueError("CORE_VERIFIED must have independent core replay")
        if self.status == "MOCK_CORE_RESULT" and self.verification_level != "MOCK_ONLY":
            raise ValueError("Mock cannot be certified")
        if self.verification_level == "CORE_REPLAY_VERIFIED" and self.status != "CORE_VERIFIED":
            raise ValueError("Cannot claim core math certification outside CORE_VERIFIED")
        if self.status == "CORE_VERIFIED" and self.candidate_math_claim not in MATH_STATUSES:
            raise ValueError("Core-verified outcome requires a mathematical claim")
        if self.status not in {"CORE_VERIFIED", "MOCK_CORE_RESULT"} and self.candidate_math_claim is not None:
            raise ValueError("Nonmathematical/failed outcomes cannot carry a mathematical claim")
        if self.status == "CORE_VERIFIED":
            if not self.confirmed_problem_sha256 or not self.core_decision_sha256 or not self.core_verifier_id or not self.core_certificate:
                raise ValueError("Verified result requires bound problem, decision, verifier and certificate")
        if self.status == "MOCK_CORE_RESULT" and self.fallback == "ELIGIBLE_NOT_IMPLEMENTED":
            raise ValueError("Mock results cannot authorize LLM fallback eligibility")
        return self
