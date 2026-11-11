"""Shared definitions never supply a direct claim or waive owner review."""
from copy import deepcopy
import json,pytest
from cfm_id import business_dispatch as d, fact_source_review as sources
from cfm_id_llm import shared_fact_definitions as shared
from cfm_id_llm.fact_reading_contracts import contract_for_entry
from examples.network_contrast_dispatch_reference import setup as contrast
from tests_gateway.test_policy_reading_contracts import setup as mean
from tests_gateway.test_fact_source_review import record
from examples.network_dispatch_reference import approval_records

def setup(family,partial):
    return (mean('partial' if partial else 'r1b',shared.PROFILE) if family=='mean' else contrast('partial' if partial else 'point',profile=shared.PROFILE))

@pytest.mark.parametrize('family,partial',[('mean',False),('mean',True),('contrast',False),('contrast',True)])
def test_shared_owner_and_native_point_partial_replay(family,partial):
    s,e,o=setup(family,partial);raw=deepcopy(o['candidate'])
    body=json.JSONDecoder().raw_decode(e['request']['user'])[0]
    assert body['shared_definition_contract']['version']==shared.PROFILE
    assert '同一字段需要多份材料时在本字段列出相关来源' not in e['request']['system']
    assert e['request']['system'].count('name: network-fact-reading')==1
    w=sources.prepare(e,raw)
    assert w['fields']['/information/0']['declared_definition_owners']['study']['definition']==raw['study']
    assert w['fields']['/information/0']['citation_groups']['source_ids']==raw['information'][0]['source_ids']
    o['source_review']=record(w);p=d.inspect_methods(s,'q1',**o)
    assert p['state']=='REVIEW_REQUIRED',p
    r=d.execute(s,'q1',**o,**approval_records(p))
    assert r['state']==('PARTIAL' if partial else 'POINT') and r['independent_replay']
    assert raw==o['candidate']
    # Rejecting common definitions prevents all dependent execution, even if
    # direct policy/probability references themselves are perfectly valid.
    o['source_review']['decisions']['/study']['source_coverage']='REJECTED'
    blocked=d.execute(s,'q1',**o,research_protocol_selected=True)
    assert not blocked['backend_called'] and blocked['state']=='READING_RECHECK_REQUIRED'

def test_shared_definition_does_not_repair_missing_probability_claim():
    s,e,o=setup('mean',False);o['candidate']['assignment']['source_ids']=[]
    w=sources.prepare(e,o['candidate'])
    assert w['fields']['/assignment']['citation_groups']['source_ids']==[]
    assert w['fields']['/assignment']['declared_definition_owners']['study']['source_ids']
    review=record(w);review['decisions']['/assignment']['source_coverage']='REJECTED'
    r=d.execute(s,'q1',**dict(o,source_review=review),research_protocol_selected=True)
    assert not r['backend_called'] and o['candidate']['assignment']['source_ids']==[]


def test_fixed_quota_probability_description_matches_schema_and_local_ownership():
    from jsonschema import Draft202012Validator
    from cfm_id_llm.network_design_reading import PROBABILITIES_DESCRIPTION, missing_assignment
    from cfm_id_llm.network_policy_reading import Assignment
    _,e,o=setup('mean',True)
    schema=json.JSONDecoder().raw_decode(e['request']['user'])[0]['output_schema']
    definition=dict(schema['$defs']['Assignment'],**{'$defs':schema['$defs']})
    assert definition['properties']['probabilities']['description']==PROBABILITIES_DESCRIPTION
    a=deepcopy(o['candidate']['assignment'])
    assert a['kind']=='UNIFORM_FIXED_QUOTA' and a['probabilities'] is None
    Draft202012Validator(definition).validate(a)
    assert not missing_assignment(Assignment.model_validate(a),o['candidate']['study']['nodes'])
    wrong=dict(a,probabilities={n:'1/2' for n in o['candidate']['study']['nodes']})
    assert list(Draft202012Validator(definition).iter_errors(wrong))
    with pytest.raises(ValueError,match='CONFLICTING_DESIGN_FIELDS'):Assignment.model_validate(wrong)
    missing=dict(a,kind='INDEPENDENT_BERNOULLI',fixed_count=None)
    assert 'assignment.probabilities' in missing_assignment(Assignment.model_validate(missing),o['candidate']['study']['nodes'])

def test_old_profile_keeps_record_local_evidence_and_new_rechecks_keep_contract():
    s,e,o=mean('r1b','network-source-selections-mean-orders-1')
    old=sources.prepare(e,o['candidate'])
    assert all('declared_definition_owners' not in v for v in old['fields'].values())
    s,e,o=setup('mean',False)
    rules=contract_for_entry(e).public_constraints(e,['/information'])
    assert any(shared.EVIDENCE_RULE==r['description'] for r in rules)


@pytest.mark.parametrize('family',['mean','contrast'])
def test_located_residual_recheck_keeps_public_role_rules_not_private_answers(family):
    from cfm_id.fact_reading_revision import prepare_recheck
    s,e,o=setup(family,True)
    o['candidate']['additional_restrictions']=[dict(text='逐对象界限已列明。',
        source_ids=o['candidate']['bounded_model']['source_ids'])]
    before=deepcopy(o['candidate']);path='/additional_restrictions/0'
    sheet=prepare_recheck(s,'q1',**o)['feedback_worksheet']
    feedback=dict(version=sheet['version'],binding_sha256=sheet['binding_sha256'],
        authority=sheet['expected_authority'],reviewer='Private reviewer',
        evidence='Private feedback for a located source comparison.',
        issues=[dict(field_path=path,kind='OMITTED_OR_MISREAD',
            source_ids=[next(iter(sheet['source_catalog']))],
            reason='PRIVATE_ANSWER_MUST_NOT_BE_FORWARDED')])
    revised=prepare_recheck(s,'q1',**o,feedback=feedback)
    assert revised['state']=='READY_TO_READ'
    user=revised['request']['user']
    assert shared.RESTRICTION_RULE in user and 'PRIVATE_ANSWER_MUST_NOT_BE_FORWARDED' not in user
    contract=contract_for_entry(e)
    for p in [path,path+'/text']:
        rules=contract.public_constraints(e,[p])
        assert any(r['description']==shared.RESTRICTION_RULE for r in rules)
    rules=contract.public_constraints(e,['/unresolved/0'])
    assert any(r['description']==shared.GAPS for r in rules)
    rules=contract.public_constraints(e,['/additional_restrictions_other/0'])
    assert not any(r['description']==shared.RESTRICTION_RULE for r in rules)
    assert revised['bundle']==e['bundle'] and o['candidate']==before

def test_explicit_network_evidence_and_distribution_labels_are_lossless():
    from jsonschema import Draft202012Validator
    s,e,o=setup('mean',False);old=deepcopy(o['candidate']);raw=deepcopy(old)
    raw['study']['network_source_ids']=list(raw['study']['source_ids'])
    reverse={v:k for k,v in shared.LAW_NAMES.items()}
    for row in raw['information']:row['operator']=reverse.get(row['operator'],row['operator'])
    schema=json.JSONDecoder().raw_decode(e['request']['user'])[0]['output_schema']
    Draft202012Validator(schema).validate(raw)
    c=contract_for_entry(e)
    assert c.parse_candidate(e,raw)==c.parse_candidate(e,old)
    w=sources.prepare(e,raw)
    assert w['fields']['/study']['citation_groups']['network_source_ids']==raw['study']['network_source_ids']
    malformed=deepcopy(raw);malformed['study']['network_source_ids']=['s9999']
    with pytest.raises(ValueError,match='UNKNOWN_OR_DUPLICATE_SHORT_SOURCE'):sources.prepare(e,malformed)
    # Old spellings are compatibility input only, not a model's current schema.
    if reverse.get(old['information'][0]['operator']):
        assert list(Draft202012Validator(schema).iter_errors(old))

def test_empty_bounds_are_not_a_model_and_other_reader_families_keep_their_contract():
    s,e,o=setup('mean',True);raw=deepcopy(o['candidate'])
    raw['bounded_model']['bounds']=[]
    with pytest.raises(ValueError):contract_for_entry(e).parse_candidate(e,raw)
    for family in ('NETWORK_RANDOMIZED_EFFECT_FACTS','NETWORK_OBSERVATIONAL_POLICY_FACTS'):
        assert shared.add_review_definitions({}, {}, {'network_fact_contract':shared.PROFILE,'reader_id':family}, {}) is None
