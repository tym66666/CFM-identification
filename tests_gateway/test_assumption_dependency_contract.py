"""One rule in schema, parser, source review and explicit recheck; no repair."""
from copy import deepcopy
import json
import pytest
from jsonschema import Draft202012Validator
from cfm_id import business_dispatch as d,fact_source_review as source,fact_reading_revision as revision
from cfm_id_llm import policy_assumption_dependencies as owner
from cfm_id_llm.fact_reading_contracts import contract_for_entry
from cfm_id_llm.wire_type_diagnostics import diagnose
from tests_gateway.test_policy_reading_contracts import setup as mean
from examples.network_contrast_dispatch_reference import setup as contrast
from examples.network_dispatch_reference import approval_records
from tests_gateway.test_fact_source_review import record
from tests_gateway.test_fact_reading_revision import feedback


def setup(family='mean',partial=False):
    return (mean('partial' if partial else 'r1b',owner.CONTRACT) if family=='mean' else
            contrast('partial' if partial else 'point',profile=owner.CONTRACT))


@pytest.mark.parametrize('family',['mean','contrast'])
@pytest.mark.parametrize('case',['absent','adopted','proposed','undecided','rejected','conflict',
    'absent_dependency','absent_source','absent_scope','missing_source','missing_definition'])
def test_four_boundaries_agree(family,case):
    s,e,o=setup(family);raw=o['candidate'];sf=raw['mean_sufficiency']
    refs=list(sf['source_ids']);nodes=raw['study']['nodes']
    sf.update(status='NOT_STATED',source_ids=[],definition_refs=[],covered_nodes=[],scope='UNKNOWN')
    statuses=dict(adopted='ADOPTED',proposed='PROPOSED',undecided='UNDECIDED',rejected='NOT_ADOPTED',conflict='CONFLICTING')
    if case in statuses:sf.update(status=statuses[case],source_ids=refs)
    if case=='absent_dependency':sf['definition_refs']=['study']
    if case=='absent_source':sf['source_ids']=refs
    if case=='absent_scope':sf.update(scope='ALL_BINARY_ASSIGNMENTS',covered_nodes=nodes)
    if case=='missing_source':sf.update(status='ADOPTED',definition_refs=['study'])
    if case=='missing_definition':sf.update(status='ADOPTED',source_ids=refs,scope='ALL_BINARY_ASSIGNMENTS',covered_nodes=nodes)
    valid=case in ('absent',*statuses)
    before=deepcopy(raw);schema=json.JSONDecoder().raw_decode(e['request']['user'])[0]['output_schema']
    assert Draft202012Validator(schema).is_valid(raw)==valid
    parser=contract_for_entry(e)
    if valid:
        decoded=parser.parse(e['bundle'],raw,binding=e['fact_binding_sha256'])
        assert not diagnose(e,raw)
        sheet=source.prepare(e,raw)
        assert sheet['fields']['/mean_sufficiency']['combination_rules']==owner.rule_sheet()
        # Passing a wire/reading check never grants scientific review.
        assert not d.execute(s,'q1',**o,research_protocol_selected=True)['backend_called']
    else:
        with pytest.raises(ValueError):parser.parse(e['bundle'],raw,binding=e['fact_binding_sha256'])
        with pytest.raises(ValueError):source.prepare(e,raw)
        assert any(r['field_path']=='/mean_sufficiency' for r in diagnose(e,raw))
    assert raw==before


@pytest.mark.parametrize('family,partial',[('mean',False),('mean',True),('contrast',False),('contrast',True)])
def test_existing_point_partial_and_refused_review_remain_native(family,partial):
    s,e,o=setup(family,partial);raw=deepcopy(o['candidate'])
    o['source_review']=record(source.prepare(e,raw));plan=d.inspect_methods(s,'q1',**o)
    reviews=approval_records(plan);result=d.execute(s,'q1',**o,**reviews)
    assert result['state']==('PARTIAL' if partial else 'POINT') and result['independent_replay']
    rejected=deepcopy(o['source_review']);rejected['decisions']['/mean_sufficiency']['source_coverage']='REJECTED'
    denied=d.execute(s,'q1',**dict(o,source_review=rejected),**reviews)
    assert not denied['backend_called'] and not denied['independent_replay'] and raw==o['candidate']


def test_recheck_uses_schema_rule_without_answer_and_old_contract_is_unchanged():
    s,e,o=setup();sf=o['candidate']['mean_sufficiency']
    sf.update(status='NOT_STATED',source_ids=[],scope='UNKNOWN',covered_nodes=[],definition_refs=['study'])
    before=deepcopy(o['candidate']);w=revision.prepare_recheck(s,'q1',**o)['feedback_worksheet']
    f=feedback(w,path='/mean_sufficiency',kind='WIRE_FORMAT_ERROR',doc='study')
    r=revision.prepare_recheck(s,'q1',**o,feedback=f)
    assert r['state']=='READY_TO_READ' and not r['backend_called']
    assert r['reading_revision']['steps'][0]['candidate']==before==o['candidate']
    assert 'ABSENT_ASSUMPTION_HAS_NO_DEPENDENCIES' in r['request']['user']
    a,b,old=mean('r1b','network-policy-scopes-1')
    old['candidate']['mean_sufficiency'].update(sf)
    schema=json.JSONDecoder().raw_decode(b['request']['user'])[0]['output_schema']
    assert Draft202012Validator(schema).is_valid(old['candidate'])
    with pytest.raises(ValueError,match='DIRECT_CLAIM_SOURCE_REQUIRED'):
        contract_for_entry(b).parse(b['bundle'],old['candidate'],binding=b['fact_binding_sha256'])
