"""Reference-only native results; these fixtures are never counted as LLM output."""
from copy import deepcopy
import pytest
from cfm_id import business_intake as intake,business_dispatch as dispatch
from cfm_id import fact_source_review
from cfm_id_llm.compact_reference_contract import request_context
from cfm_id_llm.evidence_refs import build_catalog
from cfm_id_llm.target_first_reading import COMMON_FIELDS,CONTRACT
from tests_gateway.test_fact_source_review import fixture,record as source_record
from tests_gateway.test_business_field_review import sheet,record,submit
from tests_gateway.test_inline_evidence_slots import receive,wire
from examples.network_dispatch_reference import approval_records

def setup_target_first(kind, profile=CONTRACT):
    old,oldentry,opts=fixture(kind)
    original=deepcopy(old.candidate)
    if old.reading_format=='canonical':
        catalog=build_catalog(old.case)
        def claim(c):
            if c['basis']=='UNRESOLVED':return 'UNKNOWN'
            return dict(state='STATED',value=c['value'],refs=list(dict.fromkeys(
                r['ref'] for e in c['evidence'] for r in catalog if r['source_id']==e['source_id'])))
        shared=original['shared_draft']
        original=dict(common={k:claim(v) for section in ('units_variables','structure') for k,v in shared[section].items() if k in COMMON_FIELDS},
            queries=[dict(goal=claim(q['business_goal']),kind=q['target']['kind'],semantics={k:claim(v) for k,v in q['semantics'].items()}) for q in original['queries']])
        for q in original['queries']:
            source='context' if kind=='effect' else 'study'
            q['semantics']['time_horizon']=dict(state='STATED',value=old.case.source_map()[source],refs=[r['ref'] for r in catalog if r['source_id']==source])
    raw=wire(original,operation='INTERVENTION_MINUS_COMPARATOR' if kind in ('contrast_partial','effect') else 'NOT_APPLICABLE')
    raw['common']={k:raw['common'].get(k,'UNRESOLVED' if k=='assignment_family' else 'UNKNOWN') for k in COMMON_FIELDS}
    for q in raw['queries']:
        sem=q['semantics'];sem.pop('policy_assignment',None)
        sem.update(outcome=deepcopy(raw['common']['outcome']),conditioning_context='UNKNOWN',decision_constraints='UNKNOWN')
        if kind=='r3':
            sem['conditioning_context']=dict(state='STATED',value=old.case.source_map()['conditioning'],
                refs=[r['ref'] for r in build_catalog(old.case) if r['source_id']=='conditioning'])
    if profile=='target-first-skill-1':
        for q in raw['queries']:
            sem=q['semantics']
            # Older complete-policy fixtures omitted optional slots. The
            # current Skill wire requires them explicitly, without deriving
            # peer states or a background distribution from a complete policy.
            sem.setdefault('neighbor_exposure','UNKNOWN')
            sem.setdefault('standardization_distribution','UNKNOWN')
            sem['first_arrangement']=sem.pop('intervention')
            sem['second_arrangement']=sem.pop('comparator','NOT_APPLICABLE')
            if q['comparison_order']['operation']=='INTERVENTION_MINUS_COMPARATOR':
                q['comparison_order']['operation']='FIRST_MINUS_SECOND'
    s=receive(old.case,raw,profile=profile)
    if old.network_fact_contract:s=intake.configure_network_fact_contract(s,old.network_fact_contract)
    qreview=submit(s,record(sheet(s)))['query_review'];entry=dispatch.prepare_reader(s,'q1',query_review=qreview)
    assert entry['state']=='READY_TO_READ',entry
    from cfm_id_llm.fact_reading_contracts import contract_for_entry
    refs=contract_for_entry(entry).reference_catalog(entry['bundle'],binding=entry['fact_binding_sha256'])
    candidate=deepcopy(opts['candidate']);candidate['reference_context']=refs['context']
    args=dict(query_review=qreview,candidate=candidate,request_sha256=entry['request_sha256'])
    return s,entry,args


@pytest.mark.parametrize('kind',['partial','contrast_partial','effect','r3'])
def test_target_first_to_existing_native_review_and_replay(kind):
    s,entry,args=setup_target_first(kind)
    candidate=args['candidate']
    args['source_review']=source_record(fact_source_review.prepare(entry,candidate))
    plan=dispatch.inspect_methods(s,'q1',**args)
    assert plan['state']=='REVIEW_REQUIRED',plan
    result=dispatch.execute(s,'q1',**args,**approval_records(plan))
    assert result['state']==('PARTIAL' if 'partial' in kind else 'POINT'),result
    assert result['independent_replay']
    # Explicit rejection remains a block even though this fixture is solvable.
    args['source_review']['decisions']['']['source_coverage']='REJECTED'
    blocked=dispatch.execute(s,'q1',**args,research_protocol_selected=True)
    assert not blocked['backend_called'] and not blocked['independent_replay']
