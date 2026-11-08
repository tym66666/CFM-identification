"""Opt-in bounded-policy submission after the unchanged business/POINT chain.

The LLM still reads only the existing FIXED_POLICY public question. A separate
synthetic review binds numeric A4 values, scientific bounds and the complete
mean-only model. No automatic fallback, assumption approval or provider call.
"""
from copy import deepcopy

from cfm_id_bridge.scientific_binding import sha
from . import question_bound_assignment as ids
from .intent_submission import _context_snapshot, submit as submit_point
from .bounded_policy_contract import (
    VERSION, BoundedMeanInformation, ReviewedBoundedPolicy,
    BoundedPolicyUnavailable, validate_model,
)
from .bounded_policy_solver import solve
from .bounded_policy_verify import replay


def worksheet(bundle, raw, *, query_id, packet, context, information):
    """Unapproved fingerprints only, never a scientific approval generator."""
    ids.resolve_reading(bundle, raw)
    if query_id not in bundle['question_slots']:
        raise ValueError('CURRENT_QUERY_REQUIRED')
    inquiry = context.core_port.bindings[query_id].inquiry
    return dict(version=VERSION, query_id=query_id, bundle_sha256=sha(bundle),
        reading_sha256=sha(raw), context_sha256=sha(_context_snapshot(context)),
        packet_sha256=sha(packet), inquiry_sha256=sha(inquiry),
        information_sha256=sha(information))


def _state(out, qid, state, reason):
    for view in out['query_views']:
        if view['query_id'] == qid:
            view.update(state=state, reason_code=reason, bounded_certificate_replayed=False)
    if 'point_assessment' in out:
        _result_row(out, qid, dict(query_id=qid, status=state, reason_code=reason,
            bounded_certificate_replayed=False))
    states = {v['state'] for v in out['query_views']}
    out['state'] = next(iter(states)) if len(states) == 1 else 'MIXED'
    out['reason_code'] = reason
    return out


def _result_row(out, qid, row):
    # Keep the active result coherent; the untouched Core output is separately
    # retained in point_assessment, never relabeled as a PARTIAL certificate.
    results = out.setdefault('identification', {}).setdefault('results', [])
    out['identification']['results'] = [row if r['query_id'] == qid else r for r in results]


def submit(bundle, raw, *, query_id, packet=None, context=None, information=None,
           bounded_review=None, submission_review=None, assignment_review=None,
           synthetic_protocol_selected=False):
    out = ids.preview(bundle, raw)
    out.update(bounded_version=VERSION, bounded_backend_called=False,
               bounded_certificate_replayed=False)
    if 'question_binding' not in out or out['assignment_review']['state'] != 'REVIEW_REQUIRED':
        return out
    view = next((v for v in out['query_views'] if v['query_id'] == query_id), None)
    if view is None:
        out.update(state='CHECK_BLOCKED', reason_code='CURRENT_QUERY_REQUIRED')
        return out
    if view['state'] != 'REVIEW_REQUIRED':
        return out
    if synthetic_protocol_selected is not True or packet is None or context is None:
        return _state(out, query_id, 'REVIEW_REQUIRED', 'INDEPENDENT_SCIENTIFIC_CONTEXT_REQUIRED')
    if information is None:
        return _state(out, query_id, 'NEEDS_INPUT', 'EXPLICIT_A4_VALUES_AND_BOUNDS_REQUIRED')
    if bounded_review is None or submission_review is None or assignment_review is None:
        return _state(out, query_id, 'REVIEW_REQUIRED', 'SEPARATE_BOUNDED_AND_EXISTING_REVIEWS_REQUIRED')
    try:
        if type(information) is not BoundedMeanInformation or type(bounded_review) is not ReviewedBoundedPolicy:
            raise ValueError('SEPARATE_TYPED_BOUNDED_REVIEW_REQUIRED')
        reviewed = ReviewedBoundedPolicy.model_validate(bounded_review.model_dump())
        expected = worksheet(bundle, raw, query_id=query_id, packet=packet,
                             context=context, information=information)
        if any(getattr(reviewed, k) != v for k, v in expected.items()):
            raise ValueError('BOUNDED_REVIEW_STALE')
        inquiry = context.core_port.bindings[query_id].inquiry
        validate_model(inquiry, information)
    except BoundedPolicyUnavailable as exc:
        return _state(out, query_id, exc.state, exc.reason)
    except (ValueError, TypeError, KeyError, AttributeError, ZeroDivisionError):
        return _state(out, query_id, 'CHECK_BLOCKED', 'BOUNDED_INFORMATION_OR_REVIEW_REJECTED')
    base = submit_point(bundle, raw, 'FIXED_POLICY', packet=packet, context=context,
        submission_review=submission_review, assignment_review=assignment_review,
        synthetic_protocol_selected=True, contract=ids.CONTRACT)
    # Every original A1/A4/A5/material/assignment/route review remains in force.
    out.update(base)
    out['point_assessment'] = deepcopy(base)
    selected = next(v for v in base['query_views'] if v['query_id'] == query_id)
    allowed = (selected['state'] == 'CORE_POINT' and selected.get('route') == 'R2_MEAN_SIGNATURE'
        or selected['state'] == 'UNSUPPORTED' and selected.get('reason_code') == 'ZERO_POLICY_SIGNATURE_SUPPORT')
    if not base.get('core_called') or not allowed:
        return out
    out['bounded_backend_called'] = True
    try:
        certificate = solve(inquiry, information)
        if not replay(certificate, inquiry=inquiry, information=information):
            raise ValueError('INDEPENDENT_BOUNDED_REPLAY_FAILED')
    except BoundedPolicyUnavailable as exc:
        return _state(out, query_id, exc.state, exc.reason)
    except (ValueError, TypeError, KeyError, AttributeError, ZeroDivisionError):
        return _state(out, query_id, 'CHECK_BLOCKED', 'BOUNDED_PROOF_REJECTED')
    out['bounded_certificate_replayed'] = True
    out['bounded_result'] = certificate
    out['bounded_review_receipt'] = dict(expected, review_sha256=sha(reviewed),
        approval_kind='SEPARATE_SYNTHETIC_ASSERTION_NOT_IDENTITY_AUTHENTICATION')
    _result_row(out, query_id, dict(query_id=query_id, status=certificate['status'],
        route='BOUNDED_POLICY_MEAN_D2_E1', identified_interval=[certificate['lower'],certificate['upper']],
        bounded_certificate_sha256=certificate['certificate_sha256'],
        bounded_certificate_replayed=True, verification_level='FINITE_MEAN_MODEL_REPLAY'))
    for view in out['query_views']:
        if view['query_id'] == query_id:
            view.update(state=certificate['status'], route='BOUNDED_POLICY_MEAN_D2_E1',
                reason_code=None, bounded_certificate_replayed=True,
                identified_interval=[certificate['lower'], certificate['upper']],
                sharp=True, informative=certificate['informative'])
    states = {v['state'] for v in out['query_views']}
    out['state'] = next(iter(states)) if len(states) == 1 else 'MIXED'
    out['reason_code'] = None
    return out
