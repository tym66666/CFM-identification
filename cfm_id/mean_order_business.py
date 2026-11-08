"""Opt-in business-to-mean-order bridge, preserving the existing R2 reviews.

The business reader proposes targets and order semantics. Numeric A4/base A5
remain separate inputs; one new explicit review binds both original endpoints,
the full candidate, exact sources, and the expanded mathematical contract.
"""
from copy import deepcopy
from typing import Literal
from pydantic import Field,field_validator
from cfm_id_bridge.scientific_binding import sha
from pfn_pipeline.identification_business import FixedPolicyInquiryV21
from pfn_pipeline.identification_policy_r2 import REQUIRED,_normalized_inputs,_validate_study_target
from pfn_pipeline._internal.identification.schemas import CompleteRandomizationDesignV1
from . import fixed_comparison as comparison, question_bound_assignment as ids
from . import mean_order as backend, mean_order_reading as reading
from .mean_order_contract import MeanOrderProblem, ReviewedMeanOrder, Hash, input_digest
from .bounded_policy_contract import StrictRecord
from .assignment_review import validate_assignment_review
from .intent_submission import _context_snapshot,_validate_policy
from .mean_order_solver import analyze

VERSION='mean-order-business-1'
SIDES=('first','second')
DERIVED={'first','second','weights','node_orders'}


class ScienceDeclaration(StrictRecord):
    study_sha256: Hash
    treatment_variable: str=Field(min_length=1)
    outcome_variable: str=Field(min_length=1)
    # Exact model keys are enforced before any merge. Target and order fields
    # can only come from the current candidate, never from this declaration.
    model: dict


class ReviewedMeanOrderBusiness(ReviewedMeanOrder):
    intake_version: Literal['mean-order-business-1']
    query_id: str
    bundle_sha256: Hash
    candidate_sha256: Hash
    science_sha256: Hash
    ordered_target_sha256: Hash
    order_sources_sha256: Hash
    endpoint_bindings_sha256: Hash
    confirmed_node_modes: dict[str,Literal['NONE','OWN','PEERS','BOTH']]
    axis_decisions: dict[str,Literal['CONFIRMED','PENDING','REJECTED']]
    reviewed_order_source_meaning_and_outcome: Literal[True]
    reviewed_original_comparison_and_endpoint_chain: Literal[True]

    @field_validator('reviewed_order_source_meaning_and_outcome',
                     'reviewed_original_comparison_and_endpoint_chain',mode='before')
    @classmethod
    def explicit_boolean(cls,v):
        if type(v) is not bool or v is not True:raise ValueError('EXPLICIT_SEPARATE_REVIEW_REQUIRED')
        return v


def axis_key(node,axis):
    import json
    return json.dumps([node,axis],ensure_ascii=False,separators=(',',':'))


def _science(value):
    d=ScienceDeclaration.model_validate(value.model_dump() if type(value) is ScienceDeclaration else value)
    if set(d.model)!=set(MeanOrderProblem.model_fields)-DERIVED:
        raise ValueError('EXACT_SCIENCE_ONLY_FIELDS_REQUIRED_NO_TARGET_OVERRIDE')
    return d


def _compile(bundle,raw,science,query_id):
    comp,orders=reading.split(raw); d=_science(science)
    _,_,_,targets=comparison.project(bundle,comp)
    if set(bundle['question_slots'])!={query_id} or query_id not in targets:
        raise ValueError('EXACT_SINGLE_COMPLETE_COMPARISON_REQUIRED')
    parsed=reading.project(bundle,orders)
    if parsed['state']!='REVIEW_REQUIRED':raise ValueError('ORDER_READING_NOT_COMPLETE')
    target=targets[query_id]
    p=MeanOrderProblem.model_validate(dict(d.model,first=target['first'],second=target['second'],
        weights=target['unit_weights'],node_orders=parsed['proposed_node_orders']))
    if p.node_order!=target['node_order']:raise ValueError('SCIENCE_AND_PUBLIC_ROSTER_DIFFER')
    return p,d,parsed,target


def _endpoints(p,d,context,query_id):
    if type(context) is not dict or set(context)!=set(SIDES):raise ValueError('BOTH_REVIEWED_ENDPOINTS_REQUIRED')
    original=[]
    for side in SIDES:
        q=context[side].core_port.bindings[query_id].inquiry
        if type(q) is not FixedPolicyInquiryV21 or q.r1b_sources or len(q.r2_sources)!=1:
            raise ValueError('EXACT_COMMON_R2_MEAN_ENDPOINTS_REQUIRED')
        st,target,sig,suff,sources=_normalized_inputs(q.study,q.target,q.r2_signature,q.r2_sufficiency,q.r2_sources,q.assumptions)
        _validate_study_target(st,target,sig,suff)
        if len(q.assumptions)!=len(REQUIRED) or {a.name for a in q.assumptions}!=set(REQUIRED):
            raise ValueError('BASE_ENDPOINT_EXTRA_CONDITIONS_NOT_ADAPTED')
        if (sha(st)!=d.study_sha256 or list(st.node_order)!=p.node_order
            or {frozenset(e) for e in st.undirected_edges}!={frozenset(e) for e in p.undirected_edges}
            or type(st.design()) is not CompleteRandomizationDesignV1 or st.design().m!=p.quota
            or st.context_reference!=p.context or st.outcome_kind!=p.outcome_kind
            or st.treatment_variable!=d.treatment_variable or st.outcome_variable!=d.outcome_variable
            or sig.grouping!='strict_majority_ties_low' or set(suff.covered_nodes)!=set(p.node_order)
            or list(target.policy_assignment)!=getattr(p,side) or list(target.unit_weights)!=p.weights):
            raise ValueError('ORDER_MODEL_AND_REVIEWED_ENDPOINT_SCIENCE_DIFFER')
        s=sources[0]
        if (s.operator!='NODE_SIGNATURE_MEANS' or s.availability!='EXACT_POPULATION_VALUE'
            or s.admission not in ('ADMITTED','CERTIFIED') or s.source_id!=p.a4_source
            or s.provenance!=p.a4_provenance or s.study_scope_digest!=st.shared_scope_digest
            or s.protocol_digest!=st.protocol_digest or s.signature_fingerprint!=sig.signature_fingerprint
            or s.node_order!=st.node_order or s.context!=st.context_reference or s.outcome!=st.outcome_variable
            or set(s.outcome_nodes)!=set(st.node_order)
            or set(s.signature_cells)!={(v.node,v.own,v.exposure) for v in p.values}):
            raise ValueError('EXACT_COMMON_A4_SOURCE_REQUIRED')
        original.append(q)
    for name in ('study','assumptions','r2_signature','r2_sufficiency','r2_sources'):
        if sha(getattr(original[0],name))!=sha(getattr(original[1],name)):
            raise ValueError('COMMON_BASE_SCIENCE_REQUIRED')


def worksheet(bundle,raw,*,query_id,science,packet,context):
    p,d,parsed,target=_compile(bundle,raw,science,query_id)
    if type(packet) is not dict or set(packet)!=set(SIDES):raise ValueError('BOTH_ORIGINAL_PACKETS_REQUIRED')
    _endpoints(p,d,context,query_id)
    return dict(version=p.version,problem_sha256=input_digest(p),intake_version=VERSION,query_id=query_id,
        bundle_sha256=sha(bundle),candidate_sha256=sha(raw),science_sha256=sha(d),ordered_target_sha256=sha(target),
        order_sources_sha256=sha(parsed['resolved_sources']),
        endpoint_bindings_sha256=sha({s:dict(packet=packet[s],context=_context_snapshot(context[s])) for s in SIDES}))


def prepare(bundle,raw,*,query_id,science=None,packet=None,context=None):
    out=dict(entry='MEAN_ORDER_BUSINESS_SYNTHETIC',intake_version=VERSION,state='REVIEW_REQUIRED',
        reading_candidate=deepcopy(raw),core_called=False,bounded_backend_called=False,bounded_certificate_replayed=False,
        scientific_approval=False,production_admission=False,estimation_handoff_allowed=False,business_route_registered=False)
    try:
        comp,orders=reading.split(raw)
        if set(bundle['question_slots'])!={query_id}:return dict(out,state='UNSUPPORTED',reason_code='SINGLE_COMPARISON_ONLY')
        comparison_view=comparison.preview(bundle,comp); order_view=reading.project(bundle,orders)
        out.update(comparison_view=comparison_view,order_view=order_view)
        if comparison_view['state']!='REVIEW_REQUIRED':
            return dict(out,state=comparison_view['state'],reason_code=comparison_view.get('reason_code'))
        if order_view['state']!='REVIEW_REQUIRED':
            return dict(out,state=order_view['state'],reason_code='ORDER_SEMANTICS_REQUIRE_CLARIFICATION_OR_ADAPTATION')
        if science is None:return dict(out,reason_code='SEPARATE_SCIENTIFIC_DECLARATION_REQUIRED')
        p,d,_,target=_compile(bundle,raw,science,query_id)
        out.update(proposed_model=p.model_dump(),proposed_target=target)
        if packet is None or context is None:
            return dict(out,reason_code='EXISTING_BUSINESS_AND_SCIENCE_CHAIN_REQUIRED')
        out['worksheet']=worksheet(bundle,raw,query_id=query_id,science=d,packet=packet,context=context)
    except (ValueError,TypeError,KeyError,AttributeError):
        out.update(state='CHECK_BLOCKED',reason_code='INVALID_SOURCE_OR_MEAN_ORDER_BUSINESS_BINDING')
    return out


def submit(bundle,raw,*,query_id,science=None,packet=None,context=None,assignment_review=None,
           review=None,synthetic_protocol_selected=False):
    out=prepare(bundle,raw,query_id=query_id,science=science,packet=packet,context=context)
    if out['state']!='REVIEW_REQUIRED':return out
    if (synthetic_protocol_selected is not True or 'worksheet' not in out or review is None
        or assignment_review is None):return out
    try:
        if type(review) is not ReviewedMeanOrderBusiness:raise ValueError('SEPARATE_BUSINESS_ORDER_REVIEW_REQUIRED')
        r=ReviewedMeanOrderBusiness.model_validate(review.model_dump())
        if any(getattr(r,k)!=v for k,v in out['worksheet'].items()):raise ValueError('BUSINESS_ORDER_REVIEW_STALE')
        p,d,_,target=_compile(bundle,raw,science,query_id)
        expected_axes={axis_key(n,a) for n in p.node_order for a in ('OWN','PEERS')}
        if set(r.axis_decisions)!=expected_axes or 'PENDING' in r.axis_decisions.values():
            return dict(out,state='REVIEW_REQUIRED',reason_code='EACH_AXIS_NEEDS_INDEPENDENT_REVIEW')
        if 'REJECTED' in r.axis_decisions.values():raise ValueError('ORDER_AXIS_NOT_ADMITTED')
        if r.confirmed_node_modes!={n.node:n.mode for n in p.node_orders}:raise ValueError('INDEPENDENT_ORDER_SEMANTICS_DISAGREE')
        if type(assignment_review) is not dict or set(assignment_review)!=set(SIDES):
            raise ValueError('BOTH_ORIGINAL_ASSIGNMENT_REVIEWS_REQUIRED')
        comp,_=reading.split(raw); resolved,_,_,targets=comparison.project(bundle,comp)
        facts={}
        for side in SIDES:
            facts[side]=validate_assignment_review(bundle,comp,packet[side],context[side],assignment_review[side],contract=ids.CONTRACT)
            _validate_policy(bundle,resolved['reading'],packet[side],context[side],comparison._endpoint_targets(targets,side))
        analyze(p)  # Material gate precedes Core calls and numerical optimization.
        diagnostics={}
        for side in SIDES:
            c=context[side];out['core_called']=True
            coverage=c.core_port.lookup(case=c.case,quality=c.quality,review=c.business_review,query_id=query_id)
            row=deepcopy(c.core_port.last_real_results[query_id]);diagnostics[side]=row
            permitted=(coverage.status=='POINT' and row['route']=='R2_MEAN_SIGNATURE' and row['verification_level']=='CORE_REPLAY_VERIFIED') or (
                coverage.status in ('UNSUPPORTED','NEEDS_INPUT') and row['reason_code'] in
                ('ZERO_POLICY_SIGNATURE_SUPPORT','A4_SIGNATURE_INFORMATION_INSUFFICIENT'))
            if not permitted:raise ValueError('BASE_ENDPOINT_SCIENCE_CHAIN_NOT_ADMITTED')
        # Project only already externally confirmed flags; no new approval is
        # invented and no candidate field is repaired or replaced with a gold.
        math_review=ReviewedMeanOrder.model_validate({k:getattr(r,k) for k in ReviewedMeanOrder.model_fields})
        result=backend.submit(p,review=math_review,synthetic_protocol_selected=True)
        for k in ('state','reason_code','bounded_backend_called','bounded_certificate_replayed','bounded_result','incompatibility_certificate'):
            if k in result:out[k]=result[k]
        out.update(assignment_fact_review_receipts=facts,endpoint_assessment=diagnostics,
            business_order_review_sha256=sha(r),synthetic_review_checked=True)
    except backend.MeanOrderUnavailable as exc:
        out.update(state=exc.state,reason_code=exc.reason)
    except (ValueError,TypeError,KeyError,AttributeError,RuntimeError):
        out.update(state='CHECK_BLOCKED',reason_code='BUSINESS_ORDER_REVIEW_OR_ENDPOINT_CHAIN_REJECTED')
    return out
