"""Explicit synthetic comparison entry; no change to Core/default routing.

Both original endpoint scientific reviews and a separate ordered joint review
are required. No LLM candidate or interval algebra supplies scientific consent.
"""
from copy import deepcopy
from typing import Literal
from pydantic import field_validator
from cfm_id_bridge.scientific_binding import sha
from . import fixed_comparison as comparison
from . import question_bound_assignment as ids
from .assignment_review import validate_assignment_review
from .intent_submission import _context_snapshot, _validate_policy
from .bounded_policy_contract import StrictRecord, Hash, Text, BoundedPolicyUnavailable, fail
from .bounded_contrast_contract import VERSION, SIDES, validate_pair, target_coordinates
from .bounded_contrast_solver import solve, analyze
from .bounded_contrast_verify import replay

ROUTE = 'BOUNDED_POLICY_CONTRAST_D2_E1'


class ReviewedBoundedContrast(StrictRecord):
    version: Literal['bounded-policy-contrast-1']
    query_id: str
    bundle_sha256: Hash
    reading_sha256: Hash
    ordered_target_sha256: Hash
    endpoint_bindings_sha256: Hash
    information_sha256: Hash
    reviewer: Text
    evidence: Text
    reviewed_direction_and_common_population: Literal[True]
    reviewed_complete_common_a4_model: Literal[True]
    reviewed_scientific_bounds_and_no_extra_constraints: Literal[True]
    synthetic_fixture: Literal[True]

    @field_validator('reviewed_direction_and_common_population',
        'reviewed_complete_common_a4_model', 'reviewed_scientific_bounds_and_no_extra_constraints',
        'synthetic_fixture', mode='before')
    @classmethod
    def explicit_true(cls, value):
        if type(value) is not bool or value is not True:
            raise ValueError('EXPLICIT_JOINT_SCIENTIFIC_REVIEW_REQUIRED')
        return value


def _inquiries(context):
    if type(context) is not dict or set(context) != set(SIDES):
        fail('CHECK_BLOCKED', 'EXACT_TWO_ENDPOINT_CONTEXTS_REQUIRED')
    return context


def worksheet(bundle, raw, *, query_id, packet, context, information):
    """Unapproved bindings only; original comparison and both endpoints retained."""
    if set(bundle['question_slots']) != {query_id}:
        fail('UNSUPPORTED', 'SINGLE_ORDERED_COMPARISON_REQUIRED')
    _, _, _, targets = comparison.project(bundle, raw)
    if query_id not in targets:
        fail('NEEDS_INPUT', 'COMPLETE_ORDERED_COMPARISON_REQUIRED')
    _inquiries(context)
    if type(packet) is not dict or set(packet) != set(SIDES):
        fail('CHECK_BLOCKED', 'EXACT_TWO_ENDPOINT_PACKETS_REQUIRED')
    inquiries = {s: context[s].core_port.bindings[query_id].inquiry for s in SIDES}
    validate_pair(inquiries, information)
    if targets[query_id] != target_coordinates(inquiries):
        fail('CHECK_BLOCKED', 'ACTUAL_COMPARISON_AND_REVIEWED_TARGETS_DIFFER')
    return dict(version=VERSION, query_id=query_id, bundle_sha256=sha(bundle),
        reading_sha256=sha(raw), ordered_target_sha256=sha(targets[query_id]),
        endpoint_bindings_sha256=sha({s:dict(packet=packet[s],context=_context_snapshot(context[s])) for s in SIDES}),
        information_sha256=sha(information))


def prepare(bundle, raw, *, query_id, packet=None, context=None, information=None):
    out = comparison.preview(bundle, raw)
    out.update(entry=ROUTE, bounded_version=VERSION, bounded_backend_called=False,
        bounded_certificate_replayed=False, scientific_approval=False,
        production_admission=False, estimation_handoff_allowed=False)
    if set(bundle['question_slots']) != {query_id}:
        return dict(out, state='UNSUPPORTED', reason_code='SINGLE_ORDERED_COMPARISON_REQUIRED')
    if out['state'] != 'REVIEW_REQUIRED':
        return out
    if packet is None or context is None or information is None:
        return dict(out, reason_code='SEPARATE_COMMON_MODEL_AND_REVIEW_REQUIRED')
    try:
        out['worksheet'] = worksheet(bundle, raw, query_id=query_id, packet=packet,
                                     context=context, information=information)
    except BoundedPolicyUnavailable as exc:
        out.update(state=exc.state, reason_code=exc.reason)
    except (ValueError, TypeError, KeyError, AttributeError):
        out.update(state='CHECK_BLOCKED', reason_code='INVALID_CONTRAST_BINDING')
    return out


def submit(bundle, raw, *, query_id, packet=None, context=None, information=None,
           assignment_review=None, joint_review=None, synthetic_protocol_selected=False):
    out = prepare(bundle, raw, query_id=query_id, packet=packet, context=context, information=information)
    if out['state'] != 'REVIEW_REQUIRED':
        return out
    if (synthetic_protocol_selected is not True or 'worksheet' not in out
            or joint_review is None or assignment_review is None):
        return out
    try:
        if type(joint_review) is not ReviewedBoundedContrast:
            fail('CHECK_BLOCKED', 'SEPARATE_TYPED_CONTRAST_REVIEW_REQUIRED')
        reviewed = ReviewedBoundedContrast.model_validate(joint_review.model_dump())
        if any(getattr(reviewed, k) != v for k, v in out['worksheet'].items()):
            fail('CHECK_BLOCKED', 'CONTRAST_REVIEW_STALE')
        if type(assignment_review) is not dict or set(assignment_review) != set(SIDES):
            fail('CHECK_BLOCKED', 'BOTH_ORIGINAL_ASSIGNMENT_REVIEWS_REQUIRED')
        resolved, _, _, targets = comparison.project(bundle, raw)
        fact_receipts = {}
        for side in SIDES:
            fact_receipts[side] = validate_assignment_review(bundle, raw, packet[side], context[side],
                assignment_review[side], contract=ids.CONTRACT)
            _validate_policy(bundle, resolved['reading'], packet[side], context[side],
                comparison._endpoint_targets(targets, side))
        inquiries = {s: context[s].core_port.bindings[query_id].inquiry for s in SIDES}
        analyze(inquiries, information)  # Full compatibility/completeness before any result production.
        endpoint_assessment = {}
        for side in SIDES:
            c = context[side]
            coverage = c.core_port.lookup(case=c.case,quality=c.quality,review=c.business_review,query_id=query_id)
            row = deepcopy(c.core_port.last_real_results[query_id])
            out['core_called'] = True
            # These are diagnostic endpoint limitations, never proofs of the contrast.
            allowed = (coverage.status == 'POINT' and row['route'] == 'R2_MEAN_SIGNATURE'
                       and row['verification_level'] == 'CORE_REPLAY_VERIFIED') or (
                coverage.status in ('UNSUPPORTED', 'NEEDS_INPUT') and row['reason_code'] in
                ('ZERO_POLICY_SIGNATURE_SUPPORT', 'A4_SIGNATURE_INFORMATION_INSUFFICIENT'))
            if not allowed:
                fail('CHECK_BLOCKED', 'ENDPOINT_SCIENTIFIC_CHAIN_NOT_ADMITTED')
            endpoint_assessment[side] = row
        out.update(point_assessment=endpoint_assessment, assignment_fact_review_receipts=fact_receipts)
        out['bounded_backend_called'] = True
        certificate = solve(inquiries, information)
        if not replay(certificate, inquiries=inquiries, information=information):
            fail('CHECK_BLOCKED', 'INDEPENDENT_CONTRAST_REPLAY_FAILED')
        out.update(state=certificate['status'], reason_code=None, bounded_result=certificate,
            bounded_certificate_replayed=True, joint_review_sha256=sha(reviewed))
        for view in out['query_views']:
            view.update(state=certificate['status'], reason_code=None, route=ROUTE,
                identified_interval=[certificate['lower'],certificate['upper']],
                sharp=True, informative=certificate['informative'], bounded_certificate_replayed=True)
        out['identification'] = dict(results=[dict(query_id=query_id, status=certificate['status'], route=ROUTE,
            identified_interval=[certificate['lower'],certificate['upper']],
            bounded_certificate_sha256=certificate['certificate_sha256'], bounded_certificate_replayed=True)])
    except BoundedPolicyUnavailable as exc:
        out.update(state=exc.state, reason_code=exc.reason)
    except (ValueError, TypeError, KeyError, AttributeError, RuntimeError):
        out.update(state='CHECK_BLOCKED', reason_code='CONTRAST_OR_SCIENCE_REVIEW_REJECTED')
    if not out['bounded_certificate_replayed']:
        for view in out.get('query_views', []):
            view.update(state=out['state'], reason_code=out.get('reason_code'), bounded_certificate_replayed=False)
    return out
