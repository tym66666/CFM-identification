"""Explicit scientific-review gate for the finite front-door research route."""
from .dag_frontdoor_contract import validate, check_review, digest, VERSION, ROUTE, DECISIONS, Unavailable
from .dag_frontdoor_solver import solve, CriterionFailure
from .dag_frontdoor_verify import replay


def prepare(problem):
    out = dict(entry=ROUTE, state='REVIEW_REQUIRED', backend_called=False,
               certificate_replayed=False, review_recorded=False,
               production_admission=False, estimation_handoff_allowed=False)
    try:
        p = validate(problem)
        out['worksheet'] = dict(version=VERSION, problem_sha256=digest(p), is_approval=False,
                                decisions={k: 'PENDING' for k in DECISIONS})
    except Unavailable as exc:
        out.update(state=exc.state, reason_code=exc.reason)
    except (ValueError, TypeError, AttributeError):
        out.update(state='CHECK_BLOCKED', reason_code='INVALID_FRONTDOOR_CONTRACT')
    return out


def submit(problem, *, review=None, research_protocol_selected=False):
    out = prepare(problem)
    if out['state'] != 'REVIEW_REQUIRED' or research_protocol_selected is not True:
        return out
    try:
        p = validate(problem)
        r = check_review(p, review)
        out.update(review_recorded=True, review_authority=r.authority, backend_called=True)
        certificate = solve(p)
        if not replay(certificate, problem=p):
            raise ValueError('FRONTDOOR_REPLAY_FAILED')
        out.update(state='POINT', certificate_replayed=True, certificate=certificate)
    except CriterionFailure as exc:
        out.update(state=exc.state, reason_code=exc.reason, criterion_diagnostic=exc.diagnostic)
    except Unavailable as exc:
        out.update(state=exc.state, reason_code=exc.reason)
    except (ValueError, TypeError, KeyError, AttributeError):
        out.update(state='CHECK_BLOCKED', reason_code='INVALID_REVIEW_OR_FRONTDOOR_EVIDENCE')
    return out

