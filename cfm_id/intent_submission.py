"""Reviewed submission of intent-separated readings to existing typed Core routes.

This is a synthetic acceptance adapter, not automatic scientific approval.
The outer review binds the actual model response, including intent and partial
conditions; the established inner reviews still check target, A4, A5 and route.
"""
from copy import deepcopy
from typing import Literal

from pydantic import Field
from cfm_id_llm.schemas import StrictModel
from cfm_id_llm.orchestration_schemas import canonical_sha256
from cfm_id_llm.trusted_core import RealCoreCoveragePortV012
from cfm_id_bridge.scientific_binding import (
    sha, scientific_target_coordinates, actual_scientific_sources, actual_scientific_licenses,
)
import cfm_id.workflows.legacy_network.question_intent as intent
import cfm_id.workflows.legacy_network.condition_evidence as evidence
import cfm_id.workflows.legacy_network.frozen_reading_base as fields
import cfm_id.workflows.legacy_network.evidence_entries as entries
import cfm_id.workflows.legacy_network.staged_d1_d2 as staged
from cfm_id_llm.readers import fixed_policy_base as fixed
from cfm_id.serialization import canonical_hash
from cfm_id.workflows.legacy_network.review_context import ReviewedMaterialsContextV035


class ReviewedIntentSubmissionV057(StrictModel):
    entry: str
    bundle_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    reading_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    projection_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    envelope_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    packet_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    context_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    reviewer: str = Field(min_length=3)
    evidence: str = Field(min_length=12)
    reviewed_intent_and_conditions: Literal[True]
    synthetic_fixture: Literal[True]


def reviewed_projection(bundle, raw, entry, envelope=None):
    """Deterministic wire conversion only; no facts, permissions or labels added."""
    if entry == 'FIXED_POLICY':
        if envelope is not None:
            raise ValueError('FIXED_POLICY_HAS_NO_STAGED_READING')
        return fixed.project(bundle, raw)[0]
    projected, _ = intent.project_intents(bundle, raw)
    if fields.cross_field_issues(projected):
        raise ValueError('CROSS_FIELD_REJECTED')
    projected, receipt = evidence.project_evidence(bundle, projected)
    if not receipt['passed']:
        raise ValueError('TARGET_CONDITION_EVIDENCE_REJECTED')
    if entry == 'STAGED_CORE_PEERS':
        return entries.staged.compose_reading(bundle, envelope, projected)
    if entry == 'D2_ARM' and envelope is not None:
        projected = staged.compose(bundle, entry, envelope, projected)
    if entry == 'D1_EFFECTS':
        return projected
    return entries.transfer.project_reading(bundle, projected, entry)[0]


def _context_snapshot(context):
    if type(context) is not ReviewedMaterialsContextV035 or type(context.core_port) is not RealCoreCoveragePortV012:
        raise ValueError('REAL_REVIEWED_CONTEXT_REQUIRED')
    # Snapshot semantic/scientific contracts, not internal numerical arrays in
    # batch caches. The real port independently revalidates/replays the inquiry.
    bindings = {q: dict(admission=b.admission, business_intent=b.business_intent,
        evidence_manifest=b.evidence_manifest, target=scientific_target_coordinates(b.inquiry),
        sources=actual_scientific_sources(b.inquiry), licenses=actual_scientific_licenses(b.inquiry))
        for q,b in context.core_port.bindings.items()}
    snapshot = dict(case=context.case, quality=context.quality, review=context.business_review,
        approval=context.approval, bindings=bindings,
        crosswalks=context.core_port.crosswalks)
    # Keep historical empty-source snapshots byte-for-byte compatible. Explicit
    # endpoint provenance is part of assignment and joint review bindings.
    if context.core_port.comparison_endpoint_sources:
        snapshot['comparison_endpoint_sources'] = deepcopy(context.core_port.comparison_endpoint_sources)
    return snapshot


def submission_worksheet(bundle, raw, entry, packet, context, envelope=None):
    """Return an UNAPPROVED worksheet. Required review flags are absent."""
    return dict(entry=entry, bundle_sha256=sha(bundle), reading_sha256=sha(raw),
        projection_sha256=sha(reviewed_projection(bundle, raw, entry, envelope)),
        envelope_sha256=sha(envelope), packet_sha256=sha(packet),
        context_sha256=sha(_context_snapshot(context)))


def _validate_policy(bundle, raw, packet, context, targets):
    from pfn_pipeline.identification_business import FixedPolicyInquiryV21, ObservationalPolicyInquiryV23
    from pfn_pipeline.network_inquiry_shadow import fixed_policy_target_from_context
    a = context.approval
    expected = (canonical_hash(bundle), canonical_hash(raw), canonical_hash(packet),
        canonical_sha256(context.case), canonical_sha256(context.quality), context.business_review.fingerprint())
    actual = (a.bundle_sha256, a.model_draft_sha256, a.science_packet_sha256,
        a.gateway_case_sha256, a.gateway_quality_sha256, a.gateway_review_sha256)
    if expected != actual or 'reviewed_materials_to_gateway' not in a.model_fields_set:
        raise ValueError('STALE_MATERIALS_REVIEW')
    ids = list(targets)
    if (a.reviewed_query_ids != ids or context.business_review.confirmed_query_ids != ids
            or [q.query_id for q in context.quality.draft.queries] != ids
            or set(context.core_port.bindings) != set(ids)):
        raise ValueError('EXACT_READY_QUERY_REVIEW_REQUIRED')
    if packet.get('mode') != 'SYNTHETIC_BENCHMARK_ONLY' or packet.get('bundle_sha256') != canonical_hash(bundle):
        raise ValueError('INDEPENDENT_SYNTHETIC_PACKET_REQUIRED')
    for qid, coords in targets.items():
        binding = context.core_port.bindings[qid]
        inquiry, science = binding.inquiry, binding.admission
        if (type(inquiry) not in (FixedPolicyInquiryV21, ObservationalPolicyInquiryV23)
                or science.is_synthetic_fixture is not True):
            raise ValueError('REVIEWED_FIXED_POLICY_FAMILY_REQUIRED')
        p = packet['queries'][qid]
        if (p['study_sha256'] != sha(inquiry.study)
                or p['a4_sources_sha256'] != sha(actual_scientific_sources(inquiry))
                or p['a5_licenses_sha256'] != sha(actual_scientific_licenses(inquiry))):
            raise ValueError('EXACT_SCIENCE_PACKET_REQUIRED')
        if (not p.get('a4_reference') or not p.get('a5_reference')
                or science.a4_population_operator_reference != p['a4_reference']
                or science.a5_assumption_reference != p['a5_reference']):
            raise ValueError('EXPLICIT_SCIENCE_REFERENCE_REQUIRED')
        if list(inquiry.study.node_order) != coords['node_order']:
            raise ValueError('ROSTER_MISMATCH')
        # Construct A1 from the model's coordinates, not from a reference answer.
        rebuilt = fixed_policy_target_from_context(inquiry.study, tuple(coords['assignment']),
            unit_weights=tuple(coords['unit_weights']), authority=inquiry.target.authority)
        if sha(rebuilt) != sha(inquiry.target):
            raise ValueError('READING_AND_REVIEWED_TARGET_MISMATCH')


def submit(bundle, raw, entry, envelope=None, packet=None, *, context=None,
           submission_review=None, synthetic_protocol_selected=False,
           contract='intent-v0561', assignment_review=None):
    from .business_entry import preview
    if entry == 'FIXED_COMPARISON':
        if contract != 'fixed-assignment-id' or envelope is not None:
            raise ValueError('EXPLICIT_QUESTION_BOUND_COMPARISON_REQUIRED')
        from .fixed_comparison import submit as comparison_submit
        return comparison_submit(bundle, raw, packet=packet, context=context,
            submission_review=submission_review, assignment_review=assignment_review,
            synthetic_protocol_selected=synthetic_protocol_selected)
    if contract in ('fixed-assignment', 'fixed-assignment-id'):
        # Gate before the historical any(query REVIEW_REQUIRED) check: a complete
        # target is never permission to bypass missing original assignment facts.
        out = preview(bundle, raw, entry, envelope, contract=contract)
        if contract == 'fixed-assignment-id' and 'question_binding' not in out:
            return out
        facts_view = out['assignment_review']
        if facts_view['state'] != 'REVIEW_REQUIRED':
            return out
        target_ready = out['target_reading_state'] == 'REVIEW_REQUIRED' or any(
            q['state'] == 'REVIEW_REQUIRED' for q in out.get('query_views', []))
        if (not target_ready or not synthetic_protocol_selected or packet is None
                or context is None or submission_review is None or assignment_review is None):
            return out
        from .assignment_review import validate_assignment_review
        try:
            receipt = validate_assignment_review(bundle, raw, packet, context, assignment_review, contract=contract)
        except (ValueError, TypeError, KeyError, AttributeError):
            out.update(state='CHECK_BLOCKED', reason_code='ASSIGNMENT_FACTS_REVIEW_REJECTED')
            return out
        # Keep all established A1/A4/A5, material, route, and replay checks. The
        # original model goal is passed unchanged; no reference reading is used.
        submitted = raw
        if contract == 'fixed-assignment-id':
            from .question_bound_assignment import resolve_reading
            submitted, source_view = resolve_reading(bundle, raw)
        result = submit(bundle, submitted['reading'], entry, envelope, packet, context=context,
            submission_review=submission_review, synthetic_protocol_selected=True)
        result.update(contract=contract, reading_candidate=deepcopy(raw),
            assignment_review=deepcopy(facts_view), assignment_fact_review_receipt=receipt)
        result['assignment_review']['state'] = 'REVIEWED'
        if contract == 'fixed-assignment-id':
            result['question_binding'] = source_view
        return result
    if contract != 'intent-v0561':
        raise ValueError('UNSUPPORTED_SUBMISSION_CONTRACT')
    out = preview(bundle, raw, entry, envelope)
    ready = out['state'] == 'REVIEW_REQUIRED' or any(
        q['state'] == 'REVIEW_REQUIRED' for q in out.get('query_views', []))
    if not ready or not synthetic_protocol_selected or packet is None or context is None or submission_review is None:
        return out
    try:
        if type(submission_review) is not ReviewedIntentSubmissionV057:
            raise ValueError('SEPARATE_INTENT_SUBMISSION_REVIEW_REQUIRED')
        record = ReviewedIntentSubmissionV057.model_validate(submission_review.model_dump())
        expected = submission_worksheet(bundle, raw, entry, packet, context, envelope)
        if any(getattr(record, k) != v for k, v in expected.items()):
            raise ValueError('INTENT_SUBMISSION_REVIEW_STALE')
        projected = reviewed_projection(bundle, raw, entry, envelope)
        if entry == 'FIXED_POLICY':
            _validate_policy(bundle, raw, packet, context, projected)
    except (ValueError, TypeError, KeyError, AttributeError):
        out.update(state='CHECK_BLOCKED', reason_code='INTENT_OR_SCIENCE_REVIEW_REJECTED')
        return out
    if entry != 'FIXED_POLICY':
        if entry == 'D1_EFFECTS': consumer = entries.d1.identify_submission
        elif entry == 'STAGED_CORE_PEERS': consumer = entries.peers.identify_submission
        else: consumer = entries.transfer._entry(entry)[2]
        result = consumer(bundle, projected, packet, context=context, synthetic_protocol_selected=True)
        result.update(reading_candidate=deepcopy(raw), projected_reading=deepcopy(projected),
            intent_condition_review=out['intent_condition_review'], submission_version='intent-submission-v0.57')
        return result
    from pfn_pipeline.identification_business import identify_network_business_query, replay_verified_business_outcome
    out['identification'] = {'results': []}
    for view in out['query_views']:
        qid = view['query_id']
        if qid not in projected:
            continue
        before = len(context.core_port.calls)
        try:
            coverage = context.core_port.lookup(case=context.case, quality=context.quality,
                review=context.business_review, query_id=qid)
            result = identify_network_business_query(context.core_port.bindings[qid].inquiry)
            verified = (coverage.status == result.status == 'POINT'
                and context.core_port.last_real_results[qid]['verification_level'] == 'CORE_REPLAY_VERIFIED'
                and replay_verified_business_outcome(result) is True)
            if coverage.status != result.status:
                raise ValueError('CORE_RECEIPT_DISAGREES')
            view.update(state='CORE_POINT' if verified else result.status, route=result.route,
                reason_code=result.reason_code, certificate_replayed=verified)
            out['identification']['results'].append(dict(query_id=qid, status=result.status,
                core=result.summary(), certificate_replay=verified))
        except (ValueError, TypeError, KeyError, RuntimeError):
            view.update(state='CHECK_BLOCKED', reason_code='REVIEWED_CORE_LOOKUP_REJECTED')
        view['core_called'] = len(context.core_port.calls) > before
    out['core_called'] = any(q['core_called'] for q in out['query_views'])
    out['review_receipts'] = deepcopy(context.core_port.last_real_results)
    states = {q['state'] for q in out['query_views']}
    out['state'] = next(iter(states)) if len(states) == 1 else 'MIXED'
    out['submission_version'] = 'intent-submission-v0.57'
    return out
