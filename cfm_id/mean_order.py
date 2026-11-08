"""Opt-in synthetic mathematical entry. No default/Core/business registration."""
from cfm_id_bridge.scientific_binding import sha
from .mean_order_contract import (VERSION, ReviewedMeanOrder, MeanOrderUnavailable,
                                   validate, input_digest)
from .mean_order_solver import solve, analyze
from .mean_order_verify import replay


def prepare(problem):
    out = dict(entry='MEAN_ORDER_D2_E1_SYNTHETIC', state='REVIEW_REQUIRED',
               core_called=False, bounded_backend_called=False,
               bounded_certificate_replayed=False, scientific_approval=False,
               production_admission=False, estimation_handoff_allowed=False,
               business_route_registered=False, synthetic_review_checked=False)
    try:
        p = validate(problem)
        out['worksheet'] = dict(version=VERSION, problem_sha256=input_digest(p))
    except (ValueError, TypeError, AttributeError):
        out.update(state='CHECK_BLOCKED', reason_code='INVALID_COMPLETE_MEAN_ORDER_CONTRACT')
    return out


def submit(problem, *, review=None, synthetic_protocol_selected=False):
    out = prepare(problem)
    if out['state'] != 'REVIEW_REQUIRED': return out
    if review is None or synthetic_protocol_selected is not True: return out
    try:
        if type(review) is not ReviewedMeanOrder:
            raise ValueError('SEPARATE_TYPED_REVIEW_REQUIRED')
        approved = ReviewedMeanOrder.model_validate(review.model_dump())
        if any(getattr(approved,k) != v for k,v in out['worksheet'].items()):
            raise ValueError('MEAN_ORDER_REVIEW_STALE')
        out.update(synthetic_review_checked=True, review_sha256=sha(approved))
        analyze(problem)  # Missing positive-support A4 stops before optimization.
        out['bounded_backend_called'] = True
        cert = solve(problem)
        if not replay(cert, problem=problem):
            raise ValueError('INDEPENDENT_MEAN_ORDER_REPLAY_FAILED')
        out.update(state=cert['status'], bounded_certificate_replayed=True)
        if cert['status'] == 'INCOMPATIBLE':
            out['incompatibility_certificate'] = cert
        else:
            out['bounded_result'] = cert
    except MeanOrderUnavailable as exc:
        out.update(state=exc.state, reason_code=exc.reason)
    except (ValueError, TypeError, KeyError, AttributeError):
        out.update(state='CHECK_BLOCKED', reason_code='INVALID_REVIEW_OR_MATHEMATICAL_EVIDENCE')
    return out
