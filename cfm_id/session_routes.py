"""Closed business-session adapters. Native approvals and mathematics stay separate.

No examples, reference answers, model credentials, or dynamic module loading.
Native execution contexts must be supplied by trusted calling code, never restored
from an arbitrary saved result. This module does not create a scientific review.
"""
from copy import deepcopy
from . import session_policy_routes as policy_routes
from .capability_registry import session_lanes

NETWORK, = session_lanes('NETWORK_EFFECTS')
MEAN_ORDER, = session_lanes('MEAN_ORDER')
DAG = session_lanes('DAG')
LANES = session_lanes()


def require_lane(lane):
    if type(lane) is not str or lane not in LANES:
        raise ValueError('EXPLICIT_SESSION_LANE_REQUIRED')


def public_bundle(lane, bundle):
    require_lane(lane)
    if lane == MEAN_ORDER or lane in policy_routes.LANES:
        from .workflows.mean_order import public_bundle as validate
        return validate(bundle)
    if lane in DAG:
        from cfm_id_llm.dag_reading import public_bundle as validate
        return validate(bundle)
    allowed = {'case_id','synthetic','documents','tables','file_inventory','structure',
               'active_goal_document','question_slots','original_business_unchanged',
               'revision_kind','probability_binding','question_clarifications'}
    if type(bundle) is not dict or not set(bundle) <= allowed:
        raise ValueError('PUBLIC_NETWORK_MATERIAL_FIELDS_REQUIRED')
    if not {'case_id','documents','question_slots','structure'} <= set(bundle):
        raise ValueError('PUBLIC_NETWORK_MATERIALS_REQUIRED')
    for field in ('documents','question_slots'):
        if type(bundle[field]) is not dict or not bundle[field] or any(
                type(k) is not str or not k.strip() or type(v) is not str or not v.strip()
                for k,v in bundle[field].items()):
            raise ValueError('PUBLIC_TEXT_REQUIRED')
    return deepcopy(bundle)


def request(lane, bundle):
    bundle = public_bundle(lane, bundle)
    if lane in policy_routes.LANES:
        return policy_routes.request(lane,bundle)
    if lane == NETWORK:
        from .business_entry import prepare_request
        return prepare_request(bundle, 'D1_EFFECTS')
    if lane == MEAN_ORDER:
        from .workflows.mean_order import make_request
        return make_request(bundle)
    from .dag_business import reading_contract
    return reading_contract(lane)[0](bundle)


def inspect(lane, bundle, candidate):
    bundle = public_bundle(lane, bundle)
    if lane in policy_routes.LANES:
        result = policy_routes.inspect(lane,bundle,candidate)
    elif lane == NETWORK:
        from .business_entry import preview
        result = preview(bundle, candidate, 'D1_EFFECTS')
    elif lane == MEAN_ORDER:
        from .workflows.mean_order import inspect_candidate
        result = inspect_candidate(bundle, candidate)
    else:
        from .dag_business import inspect_candidate
        result = inspect_candidate(bundle, candidate, route_id=lane)
    if result['state'] in ('POINT','CORE_POINT','PARTIAL','INCOMPATIBLE') or any(
            result.get(k) is True for k in ('core_called','backend_called','independent_replay',
                'bounded_backend_called','production_admission','estimation_handoff_allowed')):
        raise ValueError('INSPECTION_CROSSED_REVIEW_BOUNDARY')
    return result


def questions(lane, native):
    items = [dict(query_id=None, text=q) for q in native.get('clarification_questions', [])]
    if lane == NETWORK or lane in policy_routes.LANES:
        for qid, row in native.get('intent_condition_review', {}).items():
            for field in row.get('missing_conditions', []):
                items.append(dict(query_id=qid, text='请先核对原材料，再补充本题尚未明确的目标字段：'+field+'；也可以说明仍未决定。'))
        if native.get('reason_code') == 'EXPLICIT_INDEPENDENCE_PROBABILITIES_AND_EXPOSURE_REQUIRED':
            items.append(dict(query_id=None, text='请先核对原试点方案：同一轮各单位如何共同抽签，各自中签概率是多少，同伴使用状态如何定义？请说明实际规则，不必将其改成独立抽签。'))
        if lane in policy_routes.LANES:
            items.extend(dict(query_id=None,text=q) for q in native.get('assignment_review',{}).get('questions',[]))
    seen = set(); result=[]
    for row in items:
        key=(row['query_id'], row['text'])
        if key not in seen: seen.add(key); result.append(row)
    return result


def submit(lane, bundle, candidate, native_submission):
    """Invoke the original review boundary; the caller already selected research.

    The outer session review is never translated into native approval flags.
    Native contracts retain their synthetic/external-research restrictions.
    """
    require_lane(lane)
    if type(native_submission) is not dict:
        raise ValueError('NATIVE_SUBMISSION_REQUIRED')
    if lane in policy_routes.LANES:
        return policy_routes.submit(lane,bundle,candidate,native_submission)
    if lane == NETWORK:
        allowed={'packet','context','submission_review'}
        if set(native_submission) != allowed: raise ValueError('NATIVE_NETWORK_FIELDS_REQUIRED')
        from .intent_submission import submit as execute
        return execute(bundle,candidate,'D1_EFFECTS',**native_submission,synthetic_protocol_selected=True)
    if lane == MEAN_ORDER:
        allowed={'science','packet','context','assignment_review','review','factored_review'}
        if set(native_submission) != allowed: raise ValueError('NATIVE_MEAN_ORDER_FIELDS_REQUIRED')
        from .workflows.mean_order import submit_reviewed
        return submit_reviewed(bundle,candidate,**native_submission,synthetic_protocol_selected=True)
    if set(native_submission) != {'reading_review','science_review'}:
        raise ValueError('NATIVE_DAG_FIELDS_REQUIRED')
    from .dag_business import submit_reviewed
    return submit_reviewed(bundle,candidate,**native_submission,research_protocol_selected=True,route_id=lane)


def submission_snapshot(lane, native_submission):
    """Bind the actual native A4/A5/reviews, not mutable Core diagnostic caches."""
    from cfm_id_bridge.scientific_binding import canonical_data
    from .intent_submission import _context_snapshot
    require_lane(lane)
    if type(native_submission) is not dict: raise ValueError('NATIVE_SUBMISSION_REQUIRED')
    if lane in policy_routes.LANES:
        return policy_routes.snapshot(lane,native_submission)
    value=dict(native_submission)
    if lane==NETWORK:
        if set(value)!={'packet','context','submission_review'}: raise ValueError('NATIVE_NETWORK_FIELDS_REQUIRED')
        value['context']=_context_snapshot(value['context'])
    elif lane==MEAN_ORDER:
        if set(value)!={'science','packet','context','assignment_review','review','factored_review'}:
            raise ValueError('NATIVE_MEAN_ORDER_FIELDS_REQUIRED')
        if type(value['context']) is not dict or set(value['context'])!={'first','second'}:
            raise ValueError('TWO_NATIVE_ENDPOINT_CONTEXTS_REQUIRED')
        value['context']={k:_context_snapshot(v) for k,v in value['context'].items()}
    elif set(value)!={'reading_review','science_review'}: raise ValueError('NATIVE_DAG_FIELDS_REQUIRED')
    return canonical_data(dict(lane=lane,native_submission=value))


def submission_digest(lane, native_submission):
    from cfm_id_bridge.scientific_binding import sha
    return sha(submission_snapshot(lane,native_submission))


def published_evidence(lane, native, *, native_submission):
    """Only live native results enter here; stored session files cannot supply them."""
    state = native['state']
    if state not in ('POINT','CORE_POINT','PARTIAL','INCOMPATIBLE'):
        return None, None
    if native.get('production_admission') is not False or native.get('estimation_handoff_allowed') is not False:
        raise ValueError('NATIVE_RESEARCH_BOUNDARY_CHANGED')
    if lane in policy_routes.LANES:
        return policy_routes.published(lane,native,native_submission)
    if lane == NETWORK:
        from pfn_pipeline.identification_business import identify_network_business_query,replay_verified_business_outcome
        queries=native.get('query_views',[])
        if state!='CORE_POINT' or not queries or any(
                q.get('state')!='CORE_POINT' or q.get('certificate_replayed') is not True
                or q.get('proof',{}).get('verification_status')!='VERIFIED' for q in queries):
            raise ValueError('NETWORK_PROOF_REQUIRED')
        query_ids=[q['query_id'] for q in queries]
        if len(set(query_ids))!=len(query_ids) or set(query_ids)!=set(native_submission['context'].core_port.bindings):
            raise ValueError('EXACT_REVIEWED_QUERY_SET_REQUIRED')
        proof={q['query_id']:deepcopy(q['proof']) for q in queries}
        claims=[]
        for q in queries:
            # Verify the new public boundary against the reviewed inquiry, not
            # merely a JSON flag or an expression copied by an outer caller.
            inquiry=native_submission['context'].core_port.bindings[q['query_id']].inquiry
            actual=identify_network_business_query(inquiry)
            if actual.route!=q['route'] or replay_verified_business_outcome(actual) is not True or actual.result.summary()!=q['proof']:
                raise ValueError('NETWORK_PUBLIC_CLAIM_EVIDENCE_MISMATCH')
            results=q['proof']['results']
            if not results or any(r.get('status')!='POINT' or r.get('verification_status')!='VERIFIED' for r in results):
                raise ValueError('NETWORK_QUERY_PROOF_REQUIRED')
            claims.append(dict(query_id=q['query_id'], route=q['route'],
                functionals=[dict(target_fingerprint=r['target_fingerprint'],expression=r['identified_functional']) for r in results]))
        return dict(kind='POINT',representation='PER_QUERY_OBSERVED_FUNCTIONALS',queries=claims), proof
    if lane == MEAN_ORDER:
        from .mean_order_contract import MeanOrderProblem
        from .research_route_adapters import MeanOrderRoute
        result=native['result']; adapter=MeanOrderRoute()
        evidence=adapter.certificate(result)
        problem=MeanOrderProblem.model_validate(result['proposed_model'])
        claim=adapter.claim(evidence)
    else:
        from .dag_business import route_contract
        problem_type,_,_,adapter_type,_=route_contract(lane)
        adapter=adapter_type(); evidence=native['certificate']; claim=native['mathematical_claim']
        problem=problem_type.model_validate(native['proposed_problem'])
    if claim['kind']!=state or adapter.verify_claim(evidence,claim) is not True or adapter.replay(problem,evidence) is not True:
        raise ValueError('SESSION_PUBLICATION_REPLAY_FAILED')
    return deepcopy(claim),deepcopy(evidence)
