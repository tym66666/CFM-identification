"""Strict v2.9 integration boundary. NO automatic LLM-to-TaskSpec inference.

LLM proposals and even a general human business approval are NOT scientific A4/A5
licenses.  FormalBusinessInquiry objects are constructed separately by trusted
scientific Python or by explicitly supported, audited constructors.  Core alone
issues and independently replays mathematical certification.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from pydantic import Field, model_validator

from cfm_id_llm.audit import fingerprint_business_case
from cfm_id_llm.multiquery import (
    ReviewedMultiQueryV09, audit_multiquery,
)
from cfm_id_llm.orchestration_schemas import canonical_sha256
from cfm_id_llm.schemas import BusinessCase, StrictModel, TargetKind
from .scientific_binding import ApprovedScienceBindingV291, verify_approved_science_v291
from .business_intent import ApprovedBusinessIntentV292, verify_business_intent_v292
from .evidence import ReviewedScientificEvidenceV292, verify_science_evidence_v292

from pfn_pipeline.identification_business import (
    ArmInquiryV21, EffectsInquiryV21, FixedPolicyInquiryV21, FinitePolicyInquiryV21,
    ObservationalPolicyInquiryV23, ObservationalEffectsInquiryV26,
    ObservationalExposureAdjustedEffectsInquiryV27P2,
    ObservationalNodewiseAdjustedEffectsInquiryV28, VerifiedBusinessOutcomeV21,
    identify_network_business_query, replay_verified_business_outcome,
)

FormalInquiry = (ArmInquiryV21 | EffectsInquiryV21 | FixedPolicyInquiryV21 |
                 FinitePolicyInquiryV21 | ObservationalPolicyInquiryV23 |
                 ObservationalEffectsInquiryV26 |
                 ObservationalExposureAdjustedEffectsInquiryV27P2 |
                 ObservationalNodewiseAdjustedEffectsInquiryV28)

_FAMILIES = {
    "R1A_ARM": ArmInquiryV21,
    "R1A_EFFECT": EffectsInquiryV21,
    "R1B_FIXED_POLICY": FixedPolicyInquiryV21,
    "R2_FIXED_POLICY": FixedPolicyInquiryV21,
    "R1B_FINITE_POLICY": FinitePolicyInquiryV21,
    "R3_POLICY": ObservationalPolicyInquiryV23,
    "R3_P_STANDARDIZED": ObservationalEffectsInquiryV26,
    "R3_EXPOSURE_ADJUSTED": ObservationalExposureAdjustedEffectsInquiryV27P2,
    "R3_NODEWISE_ADJUSTED": ObservationalNodewiseAdjustedEffectsInquiryV28,
}

_KIND_ALLOWED = {
    "R1A_ARM": frozenset((TargetKind.NETWORK_DESIGN_STANDARDIZED_ARM_MEAN,)),
    "R1A_EFFECT": frozenset((TargetKind.DIRECT_EFFECT, TargetKind.SPILLOVER_EFFECT, TargetKind.TOTAL_EFFECT)),
    "R1B_FIXED_POLICY": frozenset((TargetKind.FIXED_POLICY_VALUE,)),
    "R2_FIXED_POLICY": frozenset((TargetKind.FIXED_POLICY_VALUE,)),
    "R1B_FINITE_POLICY": frozenset((TargetKind.STOCHASTIC_POLICY_VALUE,)),
    "R3_POLICY": frozenset((TargetKind.FIXED_POLICY_VALUE,)),
    "R3_P_STANDARDIZED": frozenset((TargetKind.DIRECT_EFFECT, TargetKind.SPILLOVER_EFFECT, TargetKind.TOTAL_EFFECT)),
    "R3_EXPOSURE_ADJUSTED": frozenset((TargetKind.DIRECT_EFFECT, TargetKind.SPILLOVER_EFFECT, TargetKind.TOTAL_EFFECT)),
    "R3_NODEWISE_ADJUSTED": frozenset((TargetKind.DIRECT_EFFECT, TargetKind.SPILLOVER_EFFECT, TargetKind.TOTAL_EFFECT)),
}
_EFFECT_TO_TARGET = {
    "DIRECT": TargetKind.DIRECT_EFFECT,
    "SPILLOVER": TargetKind.SPILLOVER_EFFECT,
    "TOTAL": TargetKind.TOTAL_EFFECT,
}


class ScientificAdmissionV29(StrictModel):
    """Second, human-scientific approval, NOT generated from a Gateway response.

    The reviewer must inspect the actual mathematical target, source/assumptions,
    and the separate typed inquiry. These declarations are *not* authenticated
    signatures or proof of the truth of a study protocol.
    """
    schema_version: Literal["causal-idfm-science-admission-v2.9"] = "causal-idfm-science-admission-v2.9"
    case_id: str = Field(min_length=1)
    input_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    draft_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    query_id: str = Field(pattern=r"^q[1-9][0-9]{0,2}$")
    target_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    formal_family: Literal[
        "R1A_ARM", "R1A_EFFECT", "R1B_FIXED_POLICY", "R2_FIXED_POLICY", "R1B_FINITE_POLICY",
        "R3_POLICY", "R3_P_STANDARDIZED", "R3_EXPOSURE_ADJUSTED", "R3_NODEWISE_ADJUSTED"
    ]
    math_target_description: str = Field(min_length=18, max_length=2500)
    formal_target_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    math_target_crosswalk_confirmed: Literal[True]
    scientific_reviewer: str = Field(min_length=3, max_length=200)
    evidence_reference: str = Field(min_length=8, max_length=500)
    a4_population_operator_reference: str = Field(min_length=8, max_length=500)
    a4_scientifically_admitted: Literal[True]
    a5_assumption_reference: str = Field(min_length=8, max_length=500)
    a5_scientifically_admitted: Literal[True]
    scientific_review_note: str = Field(min_length=20, max_length=3000)
    is_synthetic_fixture: bool = False
    # Required for v2.9.1 POINT. Legacy v2.9 records are readable but NOT sufficient.
    approved_scientific_binding: ApprovedScienceBindingV291 | None = None


@dataclass(frozen=True)
class FormalQueryBindingV29:
    """Trusted scientific typed core input; never create from an LLM target alone."""
    admission: ScientificAdmissionV29
    inquiry: FormalInquiry
    business_intent: ApprovedBusinessIntentV292 | None = None
    evidence_manifest: ReviewedScientificEvidenceV292 | None = None

    def __post_init__(self):
        if type(self.inquiry) is not _FAMILIES[self.admission.formal_family]:
            raise ValueError("Formal family does not match actual typed inquiry class")
        if self.admission.formal_target_fingerprint != formal_target_fingerprint_v29(self.inquiry):
            raise ValueError("Independent scientific target fingerprint does not match actual core target")
        if self.admission.formal_family == "R1B_FIXED_POLICY":
            if (self.inquiry.r2_signature is not None or
                self.inquiry.r2_sufficiency is not None or self.inquiry.r2_sources):
                raise ValueError("R1b science review cannot secretly authorize a different R2 theorem")
        if self.admission.formal_family == "R2_FIXED_POLICY":
            if (self.inquiry.r2_signature is None or
                self.inquiry.r2_sufficiency is None or not self.inquiry.r2_sources):
                raise ValueError("R2 requires separately supplied typed mean-signature A5 and A4")


def formal_target_fingerprint_v29(inquiry: FormalInquiry) -> str:
    """Exact core-owned A1 coordinate binding, not LLM-authored prose.

    This hash binds mathematical coordinates and the core source network, but it
    does not authenticate who wrote the scientific record or whether A4/A5 hold.
    """
    if type(inquiry) is ArmInquiryV21:
        return inquiry.task.target_fingerprint
    if type(inquiry) is FixedPolicyInquiryV21:
        return inquiry.target.target_digest
    if type(inquiry) is ObservationalPolicyInquiryV23:
        return inquiry.target.target_digest
    if type(inquiry) is FinitePolicyInquiryV21:
        return canonical_sha256(dict(
            family="R1B_FINITE_POLICY", probabilities=inquiry.policy_probabilities,
            component_digests=[x.target_fingerprint for x in inquiry.components]))
    if type(inquiry) in (EffectsInquiryV21, ObservationalEffectsInquiryV26,
                         ObservationalExposureAdjustedEffectsInquiryV27P2,
                         ObservationalNodewiseAdjustedEffectsInquiryV28):
        if len(inquiry.requests) != 1:
            raise ValueError("Exactly one typed mathematical effect per Gateway query")
        req=inquiry.requests[0]
        scope=(inquiry.study.shared_scope_digest if hasattr(inquiry, "study")
               else inquiry.batch.source_task.network_exposure_fingerprint
               if hasattr(inquiry.batch, "source_task") else inquiry.batch.batch_sha256)
        return canonical_sha256(dict(
            family=type(inquiry).__name__, scope=scope, kind=req.kind,
            weights=[(n,str(w)) for n,w in req.node_weights],
            reference_exposure=req.reference_exposure,
            comparison_exposure=req.comparison_exposure,
            spillover_own_treatment=req.spillover_own_treatment,
            cohort_authority=req.cohort_authority,
            cohort_evidence=req.cohort_evidence,
        ))
    raise TypeError("Unrecognized core business inquiry")


class QueryBridgeResultV29(StrictModel):
    query_id: str
    business_target: str
    status: Literal[
        "AWAITING_HUMAN_REVIEW", "NEEDS_INPUT", "NO_ADAPTER", "UNSUPPORTED",
        "INCOMPATIBLE", "CORE_ERROR", "CORE_VERIFICATION_FAILED", "POINT"
    ]
    route: str | None = None
    reason_code: str | None = None
    math_review_sha256: str | None = None
    business_intent_sha256: str | None = None
    scientific_evidence_sha256: str | None = None
    core_outcome_sha256: str | None = None
    verification_level: Literal["NOT_PERFORMED", "CORE_REPLAY_VERIFIED", "FAILED"] = "NOT_PERFORMED"
    identification: dict | None = None
    fallback: Literal["BLOCKED", "NOT_NEEDED", "ELIGIBLE_NOT_EXECUTED"] = "BLOCKED"
    estimation_handoff_allowed: Literal[False] = False

    @model_validator(mode="after")
    def mathematical_safety(self):
        if self.status == "POINT":
            if (self.verification_level != "CORE_REPLAY_VERIFIED" or not self.route
                    or not self.core_outcome_sha256 or not self.math_review_sha256
                    or not self.identification or self.fallback != "NOT_NEEDED"):
                raise ValueError("POINT requires theorem result, scientific review and independent replay")
        elif self.verification_level == "CORE_REPLAY_VERIFIED" or self.identification is not None:
            raise ValueError("Unverified/nonpoint query cannot contain verified mathematical payload")
        if self.fallback == "ELIGIBLE_NOT_EXECUTED" and self.status != "UNSUPPORTED":
            raise ValueError("Only actual core UNSUPPORTED can become fallback-eligible")
        return self


class IntegrationReportV29(StrictModel):
    schema_version: Literal["causal-idfm-integration-v2.9.2"] = "causal-idfm-integration-v2.9.2"
    release_version: Literal["2.9.2"] = "2.9.2"
    math_baseline: Literal["v2.8-postrelease-P1.1"] = "v2.8-postrelease-P1.1"
    gateway_baseline: Literal["v0.9.0"] = "v0.9.0"
    case_id: str
    input_sha256: str
    draft_sha256: str
    verified_query_count: int
    results: list[QueryBridgeResultV29]
    estimation_handoff_allowed: Literal[False] = False

    @model_validator(mode="after")
    def bind_results(self):
        if len(set(r.query_id for r in self.results)) != len(self.results):
            raise ValueError("Duplicate query results")
        if self.verified_query_count != sum(r.status == "POINT" for r in self.results):
            raise ValueError("Incorrect verified-query count")
        return self


def _infer_target_consistency(q, binding: FormalQueryBindingV29) -> None:
    family = binding.admission.formal_family
    if q.target.kind not in _KIND_ALLOWED[family]:
        raise ValueError("Business target kind incompatible with typed mathematical family")
    formal = binding.inquiry
    if family == "R1A_ARM":
        # Arm means are not direct/spillover *contrasts*. Do not silently re-label.
        pass
    elif family in {"R1A_EFFECT", "R3_P_STANDARDIZED", "R3_EXPOSURE_ADJUSTED", "R3_NODEWISE_ADJUSTED"}:
        if len(formal.requests) != 1 or _EFFECT_TO_TARGET.get(formal.requests[0].kind) != q.target.kind:
            raise ValueError("A single business effect requires exactly one same-kind formal contrast")
    elif family in {"R1B_FIXED_POLICY", "R2_FIXED_POLICY", "R3_POLICY"}:
        if formal.target.kind != "FIXED_FULL_ASSIGNMENT_POLICY_MEAN":
            raise ValueError("Business fixed-policy intent must bind to an exact fixed-assignment policy")
    # Other parameter-level interpretation (exposure states, weights, node order)
    # MUST be separately checked and recorded by the scientific reviewer.


_ALLOWED_THEOREM_ROUTES = {
    "R1A_ARM": frozenset(("R1A_RANDOMIZED_ARM",)),
    "R1A_EFFECT": frozenset(("R1A_COMPOSITION",)),
    "R1B_FIXED_POLICY": frozenset(("R1B_FULL_ASSIGNMENT",)),
    "R2_FIXED_POLICY": frozenset(("R2_MEAN_SIGNATURE",)),
    "R1B_FINITE_POLICY": frozenset(("R1B_FINITE_POLICY",)),
    "R3_POLICY": frozenset(("R3_FULL_ASSIGNMENT", "R3_MEAN_SIGNATURE")),
    "R3_P_STANDARDIZED": frozenset(("R3_P_STANDARDIZED_EFFECTS",)),
    "R3_EXPOSURE_ADJUSTED": frozenset(("R3_EXPOSURE_ADJUSTED_EFFECTS",)),
    "R3_NODEWISE_ADJUSTED": frozenset(("R3_NODEWISE_EXPOSURE_ADJUSTED_EFFECTS",)),
}

_RESOLVABLE_BY_INDEPENDENT_A4_ADMISSION = {"A4_POPULATION_INFORMATION_OPEN"}


def run_verified_multiquery_v29(
    case: BusinessCase, reviewed: ReviewedMultiQueryV09,
    bindings: tuple[FormalQueryBindingV29, ...] = (),
) -> IntegrationReportV29:
    """Run formally bound inquiries through the REAL v2.8 P1.1 core and replay.

    Stale approvals and fabricated source quotes are rejected before any theorem
    call. Queries with unresolved business contradictions do not reach the core.
    A4-only openness may be independently resolved by a scientist's typed and
    explicitly admitted population operator; it never becomes a business fact.
    """
    report = reviewed.report
    if report.case_id != case.case_id or report.input_sha256 != fingerprint_business_case(case):
        raise ValueError("Business documents changed: stale review")
    if report.draft_sha256 != canonical_sha256(report.draft):
        raise ValueError("Draft changed: stale review")
    if reviewed.human_review.draft_sha256 != report.draft_sha256:
        raise ValueError("Human review bound to a different draft")
    if report != audit_multiquery(case, report.draft, provider=report.provider,
                                  prompt_version=report.prompt_version):
        raise ValueError("Audit mismatch: input or report was modified")
    qmap = {q.query_id: q for q in report.draft.queries}
    bmap: dict[str, FormalQueryBindingV29] = {}
    for binding in bindings:
        qid = binding.admission.query_id
        if qid in bmap or qid not in qmap:
            raise ValueError("Duplicate or nonexistent formal-query binding")
        bmap[qid] = binding
    confirmed = set(reviewed.human_review.confirmed_query_ids)
    audits = {a.query_id: a for a in report.query_audits}
    results: list[QueryBridgeResultV29] = []
    for qid, q in qmap.items():
        kw = dict(query_id=qid, business_target=q.target.kind.value)
        if qid not in confirmed:
            results.append(QueryBridgeResultV29(**kw, status="AWAITING_HUMAN_REVIEW",
                                                 reason_code="QUERY_NOT_HUMAN_CONFIRMED"))
            continue
        blockers = {issue.code for issue in audits[qid].issues if issue.severity == "BLOCKING"}
        if blockers - _RESOLVABLE_BY_INDEPENDENT_A4_ADMISSION or q.clarifying_questions:
            results.append(QueryBridgeResultV29(**kw, status="NEEDS_INPUT",
                                                 reason_code="UNRESOLVED_BUSINESS_AUDIT"))
            continue
        binding = bmap.get(qid)
        if binding is None:
            results.append(QueryBridgeResultV29(
                **kw, status="NEEDS_INPUT" if blockers else "NO_ADAPTER",
                reason_code="A4_SCIENTIFIC_ADMISSION_REQUIRED" if blockers
                            else "NO_TRUSTED_FORMAL_BINDING"))
            continue
        a = binding.admission
        if (a.case_id != case.case_id or a.input_sha256 != report.input_sha256 or
            a.draft_sha256 != report.draft_sha256 or a.target_sha256 != canonical_sha256(q.target)):
            results.append(QueryBridgeResultV29(**kw, status="INCOMPATIBLE",
                                                 reason_code="STALE_SCIENTIFIC_ADMISSION"))
            continue
        try:
            _infer_target_consistency(q, binding)
        except (ValueError, TypeError):
            results.append(QueryBridgeResultV29(**kw, status="INCOMPATIBLE",
                                                 reason_code="BUSINESS_MATH_TARGET_MISMATCH"))
            continue
        # Independent BUSINESS approval precedes SCIENTIFIC approval. An A1
        # contract cannot be inferred from the scientific worksheet or theorem.
        try:
            if binding.business_intent is None:
                raise ValueError('V292_INDEPENDENT_BUSINESS_INTENT_REQUIRED')
            business_intent_digest = verify_business_intent_v292(binding.business_intent, reviewed, q, binding.inquiry)
        except (ValueError, TypeError, KeyError):
            results.append(QueryBridgeResultV29(**kw, status="INCOMPATIBLE",
                reason_code="V292_BUSINESS_TARGET_CONTRACT_REJECTED"))
            continue
        # The actual A4/A5 operator snapshots must be tied to separate, recorded
        # evidence references (integrity, NOT scientific truth or authentication).
        try:
            evidence_digest = verify_science_evidence_v292(binding.evidence_manifest,a,binding.inquiry)
        except (ValueError, TypeError, KeyError):
            results.append(QueryBridgeResultV29(**kw, status='INCOMPATIBLE',
                reason_code='V292_EVIDENCE_BINDING_REJECTED'))
            continue
        # Fail closed BEFORE calling the mathematical core. An old v2.9 boolean
        # confirmation or free-text scientific summary cannot authorize POINT.
        try:
            approved = verify_approved_science_v291(a, binding.inquiry, reviewed, q)
        except (ValueError, TypeError, KeyError):
            results.append(QueryBridgeResultV29(**kw, status="INCOMPATIBLE",
                reason_code="V291_SCIENTIFIC_BINDING_REJECTED"))
            continue
        admission_sha = canonical_sha256(a)
        try:
            outcome: VerifiedBusinessOutcomeV21 = identify_network_business_query(binding.inquiry)
        except Exception:
            results.append(QueryBridgeResultV29(**kw, status="CORE_ERROR", math_review_sha256=admission_sha,
                                                 reason_code="CORE_THREW_BEFORE_CERTIFICATION"))
            continue
        if outcome.status != "POINT":
            status = "NEEDS_INPUT" if outcome.status == "NEEDS_INPUT" else "UNSUPPORTED"
            reason = outcome.reason_code or "CORE_ROUTE_UNAVAILABLE"
            # Conservative: an unrecognized A4/A5 or support failure is NOT a
            # general permission to ask an LLM to bypass the theorem contract.
            coverage_gap = reason in {
                "THEOREM_BACKEND_UNAVAILABLE", "NO_REGISTERED_THEOREM",
                "OFF_SUPPORT_ALTERNATE_THEOREM",
            }
            results.append(QueryBridgeResultV29(
                **kw, status=status, math_review_sha256=admission_sha,
                reason_code=reason,
                fallback="ELIGIBLE_NOT_EXECUTED" if status == "UNSUPPORTED" and coverage_gap else "BLOCKED"))
            continue
        if (outcome.route not in _ALLOWED_THEOREM_ROUTES[a.formal_family] or
                outcome.route != approved.approved_theorem_route):
            results.append(QueryBridgeResultV29(**kw, status="INCOMPATIBLE",
                                                 math_review_sha256=admission_sha,
                                                 reason_code="CORE_ROUTE_DIFFERS_FROM_SCIENTIFIC_ADMISSION"))
            continue
        try:
            if replay_verified_business_outcome(outcome) is not True:
                raise ValueError("Independent theorem replay failed")
            summary = outcome.summary()
            # theorem-owned summary, not LLM-authored text, with independent core replay
            if summary.get("status") != "POINT" or summary.get("route") != outcome.route:
                raise ValueError("Core summary/route mismatch")
        except Exception:
            results.append(QueryBridgeResultV29(**kw, status="CORE_VERIFICATION_FAILED",
                                                 math_review_sha256=admission_sha,
                                                 verification_level="FAILED",
                                                 reason_code="INDEPENDENT_THEOREM_REPLAY_FAILED"))
            continue
        results.append(QueryBridgeResultV29(**kw, status="POINT", route=outcome.route,
                                            math_review_sha256=admission_sha,
                                            business_intent_sha256=business_intent_digest,
                                            scientific_evidence_sha256=evidence_digest,
                                            core_outcome_sha256=canonical_sha256(summary),
                                            verification_level="CORE_REPLAY_VERIFIED",
                                            identification=summary, fallback="NOT_NEEDED"))
    return IntegrationReportV29(case_id=case.case_id, input_sha256=report.input_sha256,
                                draft_sha256=report.draft_sha256,
                                verified_query_count=sum(x.status == "POINT" for x in results),
                                results=results)
