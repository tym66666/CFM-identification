"""Integrated v3.0 trusted theorem coverage port for Gateway v0.12.

No imports from the mathematics repository occur at module import time. It is an
optional external dependency, never vendored into the independent Gateway.

This adapter derives production receipts ONLY from run_verified_multiquery_v29.
The review/crosswalk contracts are content bindings, NOT cryptographic reviewer
identity authentication or proof that external A4/A5 assumptions are true.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Literal, Mapping

from pydantic import Field, model_validator

from .audit import fingerprint_business_case
from .candidate_queries import (
    ApprovedA4ReferenceV011, ApprovedA5LicenseV011,
    BusinessQueryReviewV011, CandidateSafetyError, CoreCoverageV011,
    TrustedScienceScopeV011,
)
from .multiquery import HumanMultiQueryReviewV09, approve_multiquery
from .orchestration_schemas import canonical_sha256
from .quality import MultiQueryQualityReportV010, audit_business_quality
from .schemas import BusinessCase, StrictModel, TargetKind

_SHA = r"^[0-9a-f]{64}$"


class MathematicalCoreNotInstalledV012(ImportError):
    """A separately installed mathematical repository is needed for real-Core use."""


class ApprovedBusinessMathCrosswalkV012(StrictModel):
    """Explicit, separately human-reviewed A0-v0.10 -> typed A1 binding.

    An automatically generated review *worksheet* lacks the two required
    confirmation flags, so it cannot be parsed as this approved record.
    """
    schema_version: Literal["cfm-id-approved-business-math-crosswalk-v0.12"] = (
        "cfm-id-approved-business-math-crosswalk-v0.12"
    )
    case_id: str = Field(min_length=1, max_length=180)
    input_sha256: str = Field(pattern=_SHA)
    draft_sha256: str = Field(pattern=_SHA)
    query_id: str = Field(pattern=r"^q[1-9][0-9]{0,2}$")
    business_target_sha256: str = Field(pattern=_SHA)
    business_semantics_sha256: str = Field(pattern=_SHA)
    business_review_sha256: str = Field(pattern=_SHA)
    v29_business_review_sha256: str = Field(pattern=_SHA)
    scientific_admission_sha256: str = Field(pattern=_SHA)
    formal_target_sha256: str = Field(pattern=_SHA)
    formal_target_coordinates: dict
    a4_sources_sha256: str = Field(pattern=_SHA)
    a5_licenses_sha256: str = Field(pattern=_SHA)
    approved_theorem_route: str = Field(min_length=4)
    approved_business_quote: str = Field(min_length=4)
    reviewed_by: str = Field(min_length=3)
    review_evidence: str = Field(min_length=10)
    reviewer_confirmed_business_to_math: Literal[True]
    reviewer_confirmed_a4_a5_and_route: Literal[True]

    @model_validator(mode="after")
    def no_empty_coordinates(self):
        if not self.formal_target_coordinates:
            raise ValueError("Crosswalk needs real Core target coordinates")
        return self

    def fingerprint(self) -> str:
        return canonical_sha256(self)


def v29_review_from_v011(review: BusinessQueryReviewV011, *, legacy_draft_sha256: str) -> HumanMultiQueryReviewV09:
    """Translate an *existing explicit business approval*, never approve for user."""
    return HumanMultiQueryReviewV09(
        case_id=review.case_id, input_sha256=review.input_sha256,
        draft_sha256=legacy_draft_sha256, confirmed_query_ids=review.confirmed_query_ids,
        reviewed_by=review.reviewed_by, review_note=review.review_note,
        decision=review.decision,
    )


def unapproved_crosswalk_worksheet_v012(
    *, case: BusinessCase, quality: MultiQueryQualityReportV010,
    business_review: BusinessQueryReviewV011, query_id: str, formal_binding,
    reviewer: str, evidence: str,
) -> dict:
    """For *external* reviewers. Never constitutes an approval by calling it."""
    from cfm_id_bridge.bridge import formal_target_fingerprint_v29
    from cfm_id_bridge.scientific_binding import (
        scientific_target_coordinates, actual_scientific_sources,
        actual_scientific_licenses,
    )
    query = next(q for q in quality.draft.queries if q.query_id == query_id)
    approval = formal_binding.admission.approved_scientific_binding
    if approval is None:
        raise CandidateSafetyError("Unapproved scientific binding cannot create a crosswalk worksheet")
    return dict(
        case_id=case.case_id, input_sha256=fingerprint_business_case(case),
        draft_sha256=quality.draft_sha256, query_id=query_id,
        business_target_sha256=canonical_sha256(query.target),
        business_semantics_sha256=canonical_sha256(query.semantics),
        business_review_sha256=business_review.fingerprint(),
        v29_business_review_sha256=canonical_sha256(v29_review_from_v011(business_review, legacy_draft_sha256=quality.legacy_audit.draft_sha256)),
        scientific_admission_sha256=canonical_sha256(formal_binding.admission),
        formal_target_sha256=formal_target_fingerprint_v29(formal_binding.inquiry),
        formal_target_coordinates=scientific_target_coordinates(formal_binding.inquiry),
        a4_sources_sha256=canonical_sha256(actual_scientific_sources(formal_binding.inquiry)),
        a5_licenses_sha256=canonical_sha256(actual_scientific_licenses(formal_binding.inquiry)),
        approved_theorem_route=approval.approved_theorem_route,
        approved_business_quote=query.target.description.evidence[0].quote,
        reviewed_by=reviewer, review_evidence=evidence,
        # IMPORTANT: there are deliberately NO confirmation flags here.
    )


def _conservative_target_match(query, coordinates: dict) -> None:
    """Detect a small class of provable semantic contradictions, not general NLU."""
    import re
    if query.target.kind != TargetKind.FIXED_POLICY_VALUE:
        return
    if coordinates.get("classification") != "FIXED_POLICY":
        raise CandidateSafetyError("Fixed-policy query bound to non-policy coordinates")
    natural = " ".join((query.business_goal.value or "", query.target.description.value or "",
                        query.semantics.policy_assignment.value or ""))
    if re.search(r"全员|全部.{0,5}(?:开通|使用|处理|推广)|所有.{0,8}(?:开通|使用|处理)|all[ -]treated|every(?:one| employee| unit)|whole team", natural, re.I):
        z = coordinates.get("assignment")
        if not isinstance(z, (tuple, list)) or not z or any(x != 1 for x in z):
            raise CandidateSafetyError("All-treated business target contradicts formal policy coordinates")
    if len(coordinates.get("node_order", [])) != len(coordinates.get("assignment", [])):
        raise CandidateSafetyError("Policy and node order dimensions differ")


def _comparison_endpoint_target_match(*, case, query, coordinates, query_id, source):
    """Select an explicitly bound endpoint; never infer approval from model text.

    The original comparison sentence remains intact. Its complete source and
    raw reading are independently bound in the enclosing materials/joint review.
    This verifies a structural projection, not natural-language entailment.
    The optional mathematics adapter is imported only for this explicit path.
    """
    from cfm_id import fixed_comparison as comparison

    try:
        if (type(source) is not dict
                or set(source) != {'bundle', 'raw', 'query_id', 'side'}
                or source['query_id'] != query_id
                or source['side'] not in ('first', 'second')
                or query.target.kind != TargetKind.FIXED_POLICY_VALUE
                or coordinates.get('classification') != 'FIXED_POLICY'):
            raise ValueError('EXPLICIT_COMPARISON_ENDPOINT_SOURCE_REQUIRED')
        bundle, raw = source['bundle'], source['raw']
        if type(bundle) is not dict or type(raw) is not dict:
            raise ValueError('COMPLETE_COMPARISON_SOURCE_REQUIRED')
        goal = bundle['question_slots'][query_id]
        if (case.case_id != bundle['case_id']
                or case.business_question != '\n'.join(bundle['documents'].values())
                or any(claim.value != goal or claim.basis != 'EXPLICIT_TEXT'
                    or not any(e.source_id == 'business_question' and e.quote == goal
                               for e in claim.evidence)
                    for claim in (query.business_goal, query.target.description,
                                  query.semantics.policy_assignment))):
            raise ValueError('ORIGINAL_COMPARISON_BUSINESS_SOURCE_MISMATCH')
        _, _, _, targets = comparison.project(bundle, raw)
        view = comparison.preview(bundle, raw)
        if (query_id not in targets
                or view.get('assignment_review', {}).get('state') != 'REVIEW_REQUIRED'):
            raise ValueError('COMPLETE_COMPARISON_AND_ASSIGNMENT_REQUIRED')
        target = targets[query_id]
        expected = dict(classification='FIXED_POLICY', node_order=target['node_order'],
                        assignment=target[source['side']], unit_weights=target['unit_weights'])
        if any(coordinates.get(k) != v for k, v in expected.items()):
            raise ValueError('COMPARISON_ENDPOINT_AND_FORMAL_COORDINATES_DIFFER')
    except (ValueError, TypeError, KeyError, AttributeError) as exc:
        raise CandidateSafetyError("Bound comparison endpoint rejected") from exc


class RealCoreCoveragePortV012:
    """Trusted local adapter to the *actual* v2.9.2 Bridge; not a JSON receipt parser.

    Every lookup revalidates the source, human approvals, science and exact typed
    inquiry, then executes the real Core. No cached or user-supplied Core status
    is accepted. To use with a different mathematical release, adapt explicitly.
    """
    mode: Literal["PRODUCTION"] = "PRODUCTION"

    def __init__(self, *, bindings: Mapping[str, object],
                 crosswalks: Mapping[str, ApprovedBusinessMathCrosswalkV012],
                 comparison_endpoint_sources: Mapping[str, dict] | None = None):
        if set(bindings) != set(crosswalks):
            raise CandidateSafetyError("Each supplied typed binding needs an approved crosswalk")
        if not all(isinstance(v, ApprovedBusinessMathCrosswalkV012)
                   for v in crosswalks.values()):
            raise CandidateSafetyError("Only fully approved structured crosswalks can be used")
        # A deliberate trusted-code constructor, never built from an LLM response.
        self.bindings = dict(bindings)
        self.crosswalks = dict(crosswalks)
        if comparison_endpoint_sources is not None and not isinstance(comparison_endpoint_sources, Mapping):
            raise CandidateSafetyError("Comparison endpoint sources must be explicitly mapped")
        sources = dict(comparison_endpoint_sources or {})
        if not set(sources).issubset(bindings):
            raise CandidateSafetyError("Comparison endpoint source has no typed query binding")
        # Sources are not approvals. Freeze caller objects; every lookup still
        # revalidates their projection and all existing independent approvals.
        self.comparison_endpoint_sources = deepcopy(sources)
        self.calls: list[str] = []
        # Diagnostics only; NEVER accepted as authoritative inputs.
        self.last_real_results: dict[str, dict] = {}

    def lookup(self, *, case: BusinessCase, quality: MultiQueryQualityReportV010,
               review: BusinessQueryReviewV011, query_id: str) -> CoreCoverageV011:
        try:
            from cfm_id_bridge.bridge import (FormalQueryBindingV29,
                formal_target_fingerprint_v29, run_verified_multiquery_v29)
            from cfm_id_bridge.scientific_binding import (
                scientific_target_coordinates, actual_scientific_sources,
                actual_scientific_licenses, verify_approved_science_v291)
        except ImportError as exc:
            raise MathematicalCoreNotInstalledV012(
                "Real Core not installed: install Causal-IDFM v3.0 trusted mathematics; "
                "no Mock replacement is permitted"
            ) from exc
        if query_id not in self.bindings:
            raise CandidateSafetyError("Missing exact typed binding for query")
        if quality.case_id != case.case_id or quality.input_sha256 != fingerprint_business_case(case):
            raise CandidateSafetyError("Stale business source")
        if quality.draft_sha256 != canonical_sha256(quality.draft):
            raise CandidateSafetyError("Stale v0.10 formulation")
        if audit_business_quality(case, quality.draft, provider=quality.provider,
                                  prompt_version=quality.prompt_version) != quality:
            raise CandidateSafetyError("A0 audit changed")
        if (review.case_id != case.case_id or review.input_sha256 != quality.input_sha256
                or review.draft_sha256 != quality.draft_sha256
                or query_id not in review.confirmed_query_ids):
            raise CandidateSafetyError("Missing or stale query-level business approval")
        query = next((q for q in quality.draft.queries if q.query_id == query_id), None)
        if query is None:
            raise CandidateSafetyError("Unknown query")
        qstate = next(x for x in quality.query_quality if x.query_id == query_id)
        if qstate.business_status != "FORMALIZATION_READY":
            raise CandidateSafetyError("Business formulation is not ready")
        binding = self.bindings[query_id]
        if not isinstance(binding, FormalQueryBindingV29):
            raise CandidateSafetyError("Expected a trusted typed FormalQueryBindingV29 instance")
        # v3.0: the current Core requires two independent approval objects.
        # The Gateway must never synthesize either approval from an LLM draft,
        # from the scientific crosswalk, or from the typed theorem inquiry.
        if binding.business_intent is None or binding.evidence_manifest is None:
            raise CandidateSafetyError("Current Core requires independent v2.9.2 business intent and evidence manifest")
        science = binding.admission
        approved = science.approved_scientific_binding
        if approved is None:
            raise CandidateSafetyError("Missing separate scientific approval")
        # v2.9.1 original schema defaults these to True; treat omission as DENIAL.
        if (approved.reviewer_confirmed_exact_coordinates is not True or
                approved.reviewer_confirmed_sources_and_licenses is not True or
                not {"reviewer_confirmed_exact_coordinates", "reviewer_confirmed_sources_and_licenses"}.issubset(
                    approved.model_fields_set)):
            raise CandidateSafetyError("Scientific reviewer confirmation was not explicitly supplied")
        crosswalk = self.crosswalks[query_id]
        if (crosswalk.reviewer_confirmed_business_to_math is not True or
                crosswalk.reviewer_confirmed_a4_a5_and_route is not True or
                not {"reviewer_confirmed_business_to_math", "reviewer_confirmed_a4_a5_and_route"}.issubset(
                    crosswalk.model_fields_set)):
            raise CandidateSafetyError("Crosswalk reviewer confirmation has not explicitly occurred")
        reviewer_v09 = v29_review_from_v011(review, legacy_draft_sha256=quality.legacy_audit.draft_sha256)
        if (crosswalk.query_id != query_id or crosswalk.case_id != case.case_id
                or crosswalk.input_sha256 != quality.input_sha256
                or crosswalk.draft_sha256 != quality.draft_sha256
                or crosswalk.business_target_sha256 != canonical_sha256(query.target)
                or crosswalk.business_semantics_sha256 != canonical_sha256(query.semantics)
                or crosswalk.business_review_sha256 != review.fingerprint()
                or crosswalk.v29_business_review_sha256 != canonical_sha256(reviewer_v09)
                or crosswalk.scientific_admission_sha256 != canonical_sha256(science)):
            raise CandidateSafetyError("Business/science crosswalk became stale")
        coords = scientific_target_coordinates(binding.inquiry)
        if (crosswalk.formal_target_sha256 != formal_target_fingerprint_v29(binding.inquiry)
                or crosswalk.formal_target_coordinates != coords
                or crosswalk.a4_sources_sha256 != canonical_sha256(actual_scientific_sources(binding.inquiry))
                or crosswalk.a5_licenses_sha256 != canonical_sha256(actual_scientific_licenses(binding.inquiry))
                or crosswalk.approved_theorem_route != approved.approved_theorem_route
                or crosswalk.approved_business_quote not in [e.quote for e in query.target.description.evidence]
                or approved.business_review_sha256 != canonical_sha256(reviewer_v09)):
            raise CandidateSafetyError("Approved crosswalk does not match actual typed coordinates or science")
        if query_id in self.comparison_endpoint_sources:
            _comparison_endpoint_target_match(case=case, query=query, coordinates=coords,
                query_id=query_id, source=self.comparison_endpoint_sources[query_id])
        else:
            _conservative_target_match(query, coords)
        reviewed = approve_multiquery(case, quality.legacy_audit, reviewer_v09)
        from cfm_id_bridge.business_intent import verify_business_intent_v292
        from cfm_id_bridge.evidence import verify_science_evidence_v292
        try:
            verify_business_intent_v292(binding.business_intent, reviewed, query.as_v09(), binding.inquiry)
            verify_science_evidence_v292(binding.evidence_manifest, science, binding.inquiry)
            verify_approved_science_v291(science, binding.inquiry, reviewed, query.as_v09())
        except (ValueError, TypeError, KeyError) as exc:
            raise CandidateSafetyError("Independent v2.9.2 review/evidence binding rejected") from exc
        self.calls.append(query_id)
        outcome = run_verified_multiquery_v29(case, reviewed, (binding,))
        entry = next((r for r in outcome.results if r.query_id == query_id), None)
        if entry is None:
            raise CandidateSafetyError("Real Bridge omitted the requested query")
        if entry.status == "POINT" and entry.verification_level != "CORE_REPLAY_VERIFIED":
            raise CandidateSafetyError("POINT without independent replay")
        if entry.status == "CORE_ERROR":
            mapped = "ERROR"
        elif entry.status in CoreCoverageV011.model_fields["status"].annotation.__args__:
            mapped = entry.status
        else:
            mapped = "ERROR"
        scope = TrustedScienceScopeV011(
            scientific_review_sha256=canonical_sha256(approved),
            a4_sources=[ApprovedA4ReferenceV011(**s) for s in approved.approved_a4_sources],
            a5_licenses=[ApprovedA5LicenseV011(**s) for s in approved.approved_a5_licenses],
        )
        self.last_real_results[query_id] = {
            "status": entry.status, "reason_code": entry.reason_code,
            "fallback": entry.fallback, "route": entry.route,
            "verification_level": entry.verification_level,
        }
        return CoreCoverageV011(
            case_id=case.case_id, input_sha256=quality.input_sha256,
            draft_sha256=quality.draft_sha256, query_id=query_id,
            target_sha256=canonical_sha256(query.target),
            business_review_sha256=review.fingerprint(), source_mode="PRODUCTION",
            core_version="v3.0-real-core-v2.9.2-math", adapter_id="cfm-id-v3-trusted-v292",
            status=mapped, fallback=entry.fallback, reason_code=entry.reason_code or "",
            formal_target_sha256=formal_target_fingerprint_v29(binding.inquiry),
            business_math_crosswalk_sha256=crosswalk.fingerprint(),
            science_scope=scope,
        )
