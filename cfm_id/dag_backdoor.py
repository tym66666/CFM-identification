"""Explicit reviewed research submission; no LLM, sample fitting or default routing."""
from .dag_backdoor_contract import validate,check_review,Unavailable,digest,VERSION,DECISIONS,ROUTE
from .dag_backdoor_solver import solve
from .dag_backdoor_verify import replay


def prepare(problem):
    result=dict(entry=ROUTE,state='REVIEW_REQUIRED',backend_called=False,certificate_replayed=False,
                review_recorded=False,production_admission=False,estimation_handoff_allowed=False)
    try:
        p=validate(problem)
        result['worksheet']=dict(version=VERSION,problem_sha256=digest(p),is_approval=False,
            decisions={k:'PENDING' for k in DECISIONS})
    except Unavailable as exc:result.update(state=exc.state,reason_code=exc.reason)
    except (ValueError,TypeError):result.update(state='CHECK_BLOCKED',reason_code='INVALID_DAG_CONTRACT')
    return result


def submit(problem,*,review=None,research_protocol_selected=False):
    result=prepare(problem)
    if result['state']!='REVIEW_REQUIRED' or research_protocol_selected is not True:return result
    try:
        p=validate(problem);r=check_review(p,review)
        result.update(review_recorded=True,review_authority=r.authority,backend_called=True)
        certificate=solve(p)
        if not replay(certificate,problem=p):raise ValueError('REPLAY_FAILED')
        result.update(state='POINT',certificate_replayed=True,certificate=certificate)
    except Unavailable as exc:result.update(state=exc.state,reason_code=exc.reason)
    except (ValueError,TypeError,KeyError,AttributeError):result.update(state='CHECK_BLOCKED',reason_code='INVALID_REVIEW_OR_DAG_EVIDENCE')
    return result
