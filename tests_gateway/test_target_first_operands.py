from copy import deepcopy
import pytest
from jsonschema import Draft202012Validator
from cfm_id import business_intake as intake, business_dispatch as dispatch
from cfm_id_llm import target_first_operands as profile
from cfm_id_llm.compact_reference_contract import split_user
from tests_gateway.test_target_first_reading import fixture
from tests_gateway.test_inline_evidence_slots import receive
from tests_gateway.test_business_field_review import sheet,record,submit

def operand_fixture(family='contrast'):
    case,raw=fixture(family)
    for q in raw['queries']:
        sem=q['semantics']
        sem['first_arrangement']=sem.pop('intervention')
        sem['second_arrangement']=sem.pop('comparator')
        op=q['comparison_order']['operation']
        if op=='COMPARATOR_MINUS_INTERVENTION':
            sem['first_arrangement'],sem['second_arrangement']=sem['second_arrangement'],sem['first_arrangement']
        if op in ('COMPARATOR_MINUS_INTERVENTION','INTERVENTION_MINUS_COMPARATOR'):
            q['comparison_order']['operation']='FIRST_MINUS_SECOND'
    return case,raw

@pytest.mark.parametrize('family',['policy','contrast'])
def test_schema_source_ownership_and_literal_projection(family):
    c,r=operand_fixture(family);s=receive(c,r,profile=profile.CONTRACT)
    Draft202012Validator(split_user(intake.prepare_request(s)['user_prompt'])[2]).validate(s.candidate)
    before=deepcopy(s.candidate);w=sheet(s)
    assert 'queries.q1.semantics.first_arrangement' in w['fields']
    assert 'queries.q1.semantics.intervention' not in w['fields']
    assert 'queries.q1.semantics.comparator' not in w['fields']
    reading=intake.inspect(s); assert 'report' in reading,reading
    q=submit(s,record(w))['query_review']
    assert dispatch.prepare_reader(s,'q1',query_review=q)['state']=='READY_TO_READ'
    assert s.candidate==before

def test_reversal_requires_swapping_complete_claims_not_guessing_sign():
    c,r=operand_fixture();s1=receive(c,r,profile=profile.CONTRACT)
    a=intake.inspect(s1)['report']['draft']['queries'][0]['semantics']
    sem=r['queries'][0]['semantics']
    sem['first_arrangement'],sem['second_arrangement']=sem['second_arrangement'],sem['first_arrangement']
    s2=receive(c,r,profile=profile.CONTRACT)
    b=intake.inspect(s2)['report']['draft']['queries'][0]['semantics']
    assert a['intervention']==b['comparator'] and a['comparator']==b['intervention']
    # Source reviewers still have to reject the reversed target if prose did not ask it.
    w=sheet(s2);rev=record(w)
    rev['decisions']['queries.q1.semantics.first_arrangement']['field_role']='REJECTED'
    q=submit(s2,rev)['query_review']
    assert dispatch.prepare_reader(s2,'q1',query_review=q)['state']!='READY_TO_READ'

@pytest.mark.parametrize('defect',['alias','operator'])
def test_bad_wire_not_repaired(defect):
    c,r=operand_fixture()
    if defect=='alias':r['queries'][0]['semantics']['intervention']='UNKNOWN'
    else:r['queries'][0]['comparison_order']['operation']='SECOND_MINUS_FIRST'
    s=receive(c,r,profile=profile.CONTRACT);before=deepcopy(s.candidate)
    assert 'report' not in intake.inspect(s)
    assert s.candidate==before
