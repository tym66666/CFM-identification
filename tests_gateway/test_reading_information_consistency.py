"""Structural cross-stage checks, not automatic adjudication of source truth."""
from copy import deepcopy
import pytest
from cfm_id import business_dispatch as d, business_intake as intake
from cfm_id.reading_information_consistency import population_information_conflict
from cfm_id_llm.network_effect_reading import reference_catalog
from tests_gateway.test_local_field_contract import setup
from tests_gateway.test_business_field_review import sheet, record, submit
from examples.network_effect_dispatch_reference import approval_records


def with_state(monkeypatch, state):
    s,e,o=setup(monkeypatch)
    raw=deepcopy(s.candidate)
    refs=raw['common']['treatment']['refs']
    # Explicit synthetic review exercises state binding only, not semantic
    # correctness of this fixture's changed prose. Real replies get source audit.
    claim=(dict(state='MISSING',reason='No population information declared.',refs=refs) if state=='MISSING'
           else dict(state='STATED',value='Declared population means, symbolic rather than numeric.',refs=refs)
           if state=='STATED' else dict(state='UNKNOWN',refs=[]))
    raw['common']['available_information']=claim
    revised=intake.receive_candidate(s,raw,request_sha256=s.request_sha256)
    qr=submit(revised,record(sheet(revised)))['query_review']
    entry=d.prepare_reader(revised,'q1',query_review=qr)
    facts=deepcopy(o['candidate'])
    facts['reference_context']=reference_catalog(entry['bundle'],binding=entry['fact_binding_sha256'])['context']
    return revised,entry,dict(query_review=qr,candidate=facts,request_sha256=entry['request_sha256']),e


@pytest.mark.parametrize('availability',['SYMBOLIC_POPULATION_OPERATOR','EXACT_POPULATION_VALUE'])
@pytest.mark.parametrize('full_scope',[True,False])
def test_reviewed_absence_conflicts_with_population_claim_before_backend(monkeypatch,availability,full_scope):
    s,e,o,old=with_state(monkeypatch,'MISSING');raw=o['candidate'];info=raw['information'][0]
    info['availability']=availability
    if not full_scope:info.update(outcome_nodes=[],arm_cells=[],scope_status='UNSPECIFIED',scope_source_ids=[])
    before=deepcopy(raw);p=d.inspect_methods(s,'q1',**o)
    assert p['state']=='READING_RECHECK_REQUIRED'
    assert p['reason_code']=='POPULATION_INFORMATION_DISAGREES_WITH_REVIEWED_A0'
    assert p['methods']==[] and not p['backend_called']
    receipt=p['reading_consistency_conflict']
    assert receipt['reviewed_a0_claim']==s.candidate['common']['available_information']
    assert receipt['conflicting_fact_paths']==['/information/0']
    assert not receipt['source_absence_proven'] and not receipt['scientific_approval']
    result=d.execute(s,'q1',**o,research_protocol_selected=True)
    assert result['state']==p['state'] and not result['backend_called'] and raw==before


@pytest.mark.parametrize('state',['UNKNOWN','STATED'])
def test_unmentioned_or_stated_information_does_not_become_permission(monkeypatch,state):
    s,e,o,_=with_state(monkeypatch,state);p=d.inspect_methods(s,'q1',**o)
    assert p['state']=='REVIEW_REQUIRED' and 'reading_consistency_conflict' not in p
    assert not d.execute(s,'q1',**o,research_protocol_selected=True)['backend_called']
    r=d.execute(s,'q1',**o,**approval_records(p))
    assert r['state']=='POINT' and r['independent_replay']


@pytest.mark.parametrize('kind',['no_information','finite_sample','unknown_availability'])
def test_reviewed_absence_does_not_confuse_missing_with_conflict(monkeypatch,kind):
    s,e,o,_=with_state(monkeypatch,'MISSING')
    if kind=='no_information':o['candidate']['information']=[]
    elif kind=='finite_sample':o['candidate']['information'][0].update(operator='FINITE_SAMPLE',availability='FINITE_SAMPLE',arm_cells=[])
    else:o['candidate']['information'][0]['availability']='UNKNOWN'
    result=d.execute(s,'q1',**o,research_protocol_selected=True)
    assert result['state']=='NEEDS_INPUT' and not result['backend_called']
    assert 'reading_consistency_conflict' not in result


def test_stale_review_cannot_change_reviewed_information_state(monkeypatch):
    s,e,o,old=with_state(monkeypatch,'MISSING')
    r=d.prepare_reader(s,'q1',query_review=old['query_review'])
    assert r['state']=='CHECK_BLOCKED' and r['request'] is None
    e['reviewed_population_information']=dict(state='STATED')
    # Public inspect reconstructs the entry, never accepts this edited copy.
    assert d.inspect_methods(s,'q1',**o)['reason_code']=='POPULATION_INFORMATION_DISAGREES_WITH_REVIEWED_A0'


@pytest.mark.parametrize('claim',[None,'UNKNOWN',dict(state='UNKNOWN'),dict(state='STATED')])
def test_checker_never_infers_absence_from_unknown_or_legacy_metadata(claim):
    assert population_information_conflict(dict(reviewed_population_information=claim),[dict(availability='SYMBOLIC_POPULATION_OPERATOR')]) is None


def test_recheck_retains_conflict_and_requires_all_change_review(monkeypatch):
    from cfm_id.fact_reading_revision import prepare_recheck
    s,e,o,_=with_state(monkeypatch,'MISSING');w=prepare_recheck(s,'q1',**o)['feedback_worksheet']
    feedback=dict(version=w['version'],binding_sha256=w['binding_sha256'],authority=w['expected_authority'],
        reviewer='Independent synthetic reviewer',evidence='Locate original information statement; no substitute answer.',
        issues=[dict(field_path='/information/0',kind='OMITTED_OR_MISREAD',source_ids=list(w['source_catalog'])[:1],reason='Review the original population information statement.')])
    revised=prepare_recheck(s,'q1',**o,feedback=feedback)
    raw=deepcopy(o['candidate']);raw['reference_context']=reference_catalog(revised['bundle'],binding=revised['fact_binding_sha256'])['context']
    options=dict(o,candidate=raw,request_sha256=revised['request_sha256'],reading_revision=revised['reading_revision'])
    assert d.inspect_methods(s,'q1',**options)['reason_code']=='POPULATION_INFORMATION_DISAGREES_WITH_REVIEWED_A0'
    raw['information'][0].update(operator='FINITE_SAMPLE',availability='FINITE_SAMPLE',arm_cells=[])
    p=d.inspect_methods(s,'q1',**options)
    assert p['reason_code']=='INDEPENDENT_READING_CHANGE_REVIEW_REQUIRED'
    assert not d.execute(s,'q1',**options,research_protocol_selected=True)['backend_called']
