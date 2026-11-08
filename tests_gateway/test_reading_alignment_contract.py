from copy import deepcopy
import json
import pytest
from cfm_id import business_intake as intake,business_dispatch as dispatch
from cfm_id_llm import reading_alignment_contract as guide,network_effect_reading as reader
from cfm_id_llm import compact_unified_contract as unified, business_field_contract as fields
from examples.network_effect_dispatch_reference import setup,approval_records
from examples.business_dispatch_reference import approve
from tests_gateway.test_source_dependencies import types
from tests_gateway.test_fact_reading_revision import feedback
from cfm_id.fact_reading_revision import prepare_recheck

def configured():
    s,_,o,_=setup();s=intake.configure_network_fact_contract(s,guide.NETWORK_CONTRACT)
    q=approve(dispatch.prepare_reader(s,'q1')['query_worksheet']);e=dispatch.prepare_reader(s,'q1',query_review=q)
    raw=deepcopy(o['candidate']);raw['reference_context']=reader.reference_catalog(e['bundle'],binding=e['fact_binding_sha256'])['context']
    return s,e,dict(query_review=q,candidate=raw,request_sha256=e['request_sha256'])

def test_guidance_does_not_change_wire_sources_or_candidate():
    s,e,o=configured();base=reader.make_request(e['bundle'],binding=e['fact_binding_sha256'])
    b=json.loads(base['user']);n=json.JSONDecoder().raw_decode(e['request']['user'])[0]
    assert types(b['output_schema'])==types(n['output_schema']) and b['source_catalog']==n['source_catalog']
    assert guide.apply(guide.apply(base))==guide.apply(base)
    rows=guide.field_constraints(['/scientific_statements/consistency/status'],request=e['request'])
    assert len(rows)==1 and guide.SCIENCE in rows[0]['description']
    assert reader.parse(e['bundle'],o['candidate'],binding=e['fact_binding_sha256'])
    assert not n['reading_alignment_contract']['scientific_approval']

@pytest.mark.parametrize('status,expected',[('ADOPTED','POINT'),('PROPOSED','POINT'),('UNDECIDED','NEEDS_INPUT'),('NOT_ADOPTED','ADAPTER_NOT_CONNECTED'),('CONFLICTING','READING_RECHECK_REQUIRED'),('NOT_STATED','NEEDS_INPUT')])
def test_each_statement_remains_independent_and_needs_science_review(status,expected):
    s,e,o=configured();raw=o['candidate'];raw['scientific_statements']['consistency']['status']=status
    if status=='NOT_STATED':raw['scientific_statements']['consistency']['source_ids']=[]
    before=deepcopy(raw);p=dispatch.inspect_methods(s,'q1',**o)
    if expected=='POINT':
        pending=dispatch.execute(s,'q1',**o,research_protocol_selected=True)
        assert not pending['backend_called']
        r=dispatch.execute(s,'q1',**o,**approval_records(p))
        assert r['independent_replay']
    else:r=dispatch.execute(s,'q1',**o,research_protocol_selected=True);assert not r['backend_called']
    assert r['state']==expected and raw==before

def test_recheck_uses_current_science_role_without_private_answer():
    s,e,o=configured();w=prepare_recheck(s,'q1',**o)['feedback_worksheet']
    r=prepare_recheck(s,'q1',**o,feedback=feedback(w,path='/scientific_statements/consistency/status',doc='science'))
    public=json.loads(r['request']['user'].split('独立复查定位（不是新增事实）：\n')[1])
    assert public['public_field_constraints']==guide.field_constraints(['/scientific_statements/consistency/status'],request=e['request'])
    assert 'PRIVATE_REASON_NOT_SENT' not in r['request']['user']
    assert public['previous_candidate']==o['candidate']

@pytest.mark.parametrize('kind',['point','partial'])
def test_contrast_schema_is_reannotated_after_target_replacement(kind):
    from examples.network_contrast_dispatch_reference import setup as contrast,approval_records as approvals
    s,e,o=contrast(kind,profile=guide.NETWORK_CONTRACT);p=dispatch.inspect_methods(s,'q1',**o)
    paths={r['field_path'] for r in guide.field_constraints([''],request=e['request'])}
    assert '/target/first/source_ids' in paths and '/target/assignment/source_ids' not in paths
    r=dispatch.execute(s,'q1',**o,**approvals(p));assert r['state']==kind.upper() and r['independent_replay']

def test_a0_direction_roles_shared_without_schema_type_or_parser_changes():
    from cfm_id_llm.compact_formulator import make_compact_request
    from cfm_id_llm.compact_reference_contract import split_user
    from tests_gateway.test_target_summary_contract import fixture
    case,_=fixture()
    old,new=[split_user(make_compact_request(case,a0_response_contract=p)[1])[2]
        for p in (unified.FOCUSED_CONTRACT,guide.A0_CONTRACT)]
    assert types(old)==types(new)
    assert guide.DIRECTION==new['$defs']['ComparisonOrder']['properties']['operation']['description']
    assert guide.DIRECTION in unified.recheck_field_roles(['/queries/0/comparison_order'],contract=guide.A0_CONTRACT)[0]['field_role']
    assert guide.A0_GUIDANCE in unified.system_prompt(contract=guide.A0_CONTRACT)

def test_old_review_invalidated_and_missing_citations_not_repaired():
    old,e,o,p=setup();new=intake.configure_network_fact_contract(old,guide.NETWORK_CONTRACT)
    assert dispatch.prepare_reader(new,'q1',query_review=o['query_review'])['state']=='CHECK_BLOCKED'
    s,e,o=configured();o['candidate']['target']['first']['source_ids']=[];before=deepcopy(o['candidate'])
    r=dispatch.execute(s,'q1',**o,research_protocol_selected=True)
    assert not r['backend_called'] and o['candidate']==before
