"""Published wire rules, loaded Skill and unchanged legacy interfaces."""
from copy import deepcopy
import pytest
from jsonschema import Draft202012Validator
from cfm_id import business_intake as intake
from cfm_id_llm import target_first_skill as skill
from cfm_id_llm.compact_reference_contract import split_user
from tests_gateway.test_target_first_operands import operand_fixture as fixture
from tests_gateway.test_inline_evidence_slots import receive

def prepared():
    case,raw=fixture()
    s=receive(case,raw,profile=skill.CONTRACT)
    req=intake.prepare_request(s)
    schema=split_user(req['user_prompt'])[2]
    return s,req,schema

def test_actual_skill_is_loaded_once_and_format_guide_uses_same_schema():
    s,req,schema=prepared()
    assert req['system_prompt'].count('name: causal-business-reading')==1
    assert skill.skill_manifest()['loaded']
    assert 'comparison_request.shared_condition' not in str(schema)
    assert '当前Schema生成的格式速查' in req['user_prompt']
    assert skill.format_guide(schema)['queries[].kind']['choices']==schema['$defs']['TargetKind']['enum']
    Draft202012Validator(schema).validate(s.candidate)
    assert 'report' in intake.inspect(s)

@pytest.mark.parametrize('field',['conditioning_context','outcome','decision_constraints'])
def test_schema_does_not_offer_inapplicable_extension_states(field):
    s,req,schema=prepared();raw=deepcopy(s.candidate)
    raw['queries'][0]['semantics'][field]={'state':'NOT_APPLICABLE'}
    assert not Draft202012Validator(schema).is_valid(raw)
    from cfm_id_llm.compact_reference_contract import catalog
    from cfm_id_llm.quality_formulator import A0QualityValidationError
    with pytest.raises(A0QualityValidationError):
        skill.project(raw,catalog(s.case,s.a0_reference_contract))

@pytest.mark.parametrize('defect',['known_without_value','unknown_with_value','unknown_goal','kind_operation','duplicate_refs'])
def test_public_schema_matches_existing_key_parser_constraints(defect):
    s,req,schema=prepared();raw=deepcopy(s.candidate);q=raw['queries'][0]
    if defect=='known_without_value':q['semantics']['outcome'].pop('value')
    elif defect=='unknown_with_value':q['semantics']['outcome']['state']='UNKNOWN'
    elif defect=='unknown_goal':q['goal']={'state':'UNKNOWN'}
    elif defect=='kind_operation':q['kind']='FIXED_POLICY_VALUE'
    else:q['semantics']['outcome']['refs']*=2
    assert not Draft202012Validator(schema).is_valid(raw)

def test_legacy_requests_have_no_implicitly_injected_skill():
    case,raw=fixture();s=receive(case,raw,profile='target-first-operands-1')
    req=intake.prepare_request(s)
    assert 'name: causal-business-reading' not in req['system_prompt']
    assert '当前Schema生成的格式速查' not in req['user_prompt']

def test_whitespace_missing_reason_is_not_advertised_as_valid():
    s,req,schema=prepared();raw=deepcopy(s.candidate)
    raw['queries'][0]['semantics']['second_arrangement']={'state':'MISSING','reason':'  ','refs':['s0001']}
    assert not Draft202012Validator(schema).is_valid(raw)
    assert 'second_arrangement' in skill.EXTRA_STATE_RULES['NOT_APPLICABLE']
    assert 'NOT_APPLICABLE' not in skill.previous.EXTRA_STATE_RULES

def test_request_has_value_examples_not_meta_objects_and_preserves_text():
    s,req,schema=prepared()
    payload=split_user(req['user_prompt'])[1]
    assert '"shape"' not in split_user(req['user_prompt'])[3]
    assert 'operation不能是列表' in req['user_prompt']
    from cfm_id_llm.compact_reference_contract import catalog
    original=catalog(s.case,s.a0_reference_contract)
    assert [(r['ref'],r['source_id'],r['quote']) for r in payload['source_catalog']]==[(r['ref'],r['source_id'],r['quote']) for r in original]

def test_target_role_definitions_match_schema_and_review():
    s,req,schema=prepared()
    for name,rule in skill.REVIEW_RULES.items():
        owner='CompactQuery' if rule.section=='query' else 'CompactSemantics'
        assert schema['$defs'][owner]['properties'][name]['description']==rule.meaning+' '+rule.excludes
        assert skill.review_definition(rule)['meaning']==rule.meaning
        assert skill.recheck_field_roles(['/queries/0/'+('semantics/' if rule.section=='semantics' else '')+name])[0]['field_role']==rule.meaning+' '+rule.excludes
