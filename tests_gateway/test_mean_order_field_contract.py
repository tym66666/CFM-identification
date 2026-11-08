"""Public/local reading contract parity, without changing identification math."""
from copy import deepcopy
import json
import pytest
from pydantic import ValidationError
from jsonschema import Draft202012Validator
from cfm_id import business_dispatch as dispatch, mean_order
from cfm_id import fact_reading_revision as revision, fact_source_review as sources
from cfm_id_llm import network_contrast_reading as reader
from cfm_id_llm.mean_order_field_contract import NULL_RULE, combination_schema
from cfm_id_llm.network_mean_order_reading import PROFILE
from cfm_id_llm.fact_reading_contracts import contract_for_entry
from cfm_id_llm.wire_type_diagnostics import diagnose
from examples.network_mean_order_dispatch_reference import setup
from tests_gateway.test_fact_reading_revision import feedback


def body(e):return json.JSONDecoder().raw_decode(e['request']['user'])[0]


@pytest.mark.parametrize('level,scope',[(None,None),('CONDITIONAL_MEAN',None),(None,'ALL_BINARY_ASSIGNMENTS'),('UNKNOWN','UNKNOWN')])
def test_not_assumed_schema_parser_and_diagnostic_agree(level,scope):
    s,e,o=setup(mode='NONE');raw=o['candidate']
    raw['mean_order_model']['order_reading']['claims'][0].update(level=level,scope=scope)
    before=deepcopy(raw);bad=level is not None or scope is not None
    errors=list(Draft202012Validator(body(e)['output_schema']).iter_errors(raw))
    assert bool(errors)==bad
    if bad:
        with pytest.raises(ValidationError):contract_for_entry(e).parse_candidate(e,raw)
        rows=diagnose(e,raw)
        assert rows==[dict(field_path='/mean_order_model/order_reading/claims/0',
            error_code=NULL_RULE['code'],description=NULL_RULE['description'],combination=combination_schema())]
        r=dispatch.execute(s,'q1',**o,research_protocol_selected=True)
        assert r['state']=='CHECK_BLOCKED' and not r['backend_called']
    else:
        contract_for_entry(e).parse_candidate(e,raw)
        assert diagnose(e,raw)==[]
    assert raw==before


@pytest.mark.parametrize('kind,state',[
    ('undecided','NEEDS_INPUT'),('not_assumed','REVIEW_REQUIRED'),
    ('unmentioned','NEEDS_INPUT'),('extra_constraint','ADAPTER_NOT_CONNECTED'),
    ('unknown_completeness','NEEDS_INPUT'),('no_effect','ADAPTER_NOT_CONNECTED')])
def test_readings_keep_distinct_admission_meanings(monkeypatch,kind,state):
    s,e,o=setup();r=o['candidate']['mean_order_model']['order_reading'];c=r['claims'][1]
    if kind=='undecided':c['relation']='UNKNOWN'
    elif kind=='not_assumed':c.update(relation='NOT_ASSUMED',level=None,scope=None)
    elif kind=='unmentioned':r['claims'].pop()
    elif kind=='extra_constraint':r['other_restriction_source_ids']=c['source_ids'][:1]
    elif kind=='unknown_completeness':o['candidate']['mean_order_model']['no_additional_constraints_beyond_declared_orders']['value']=None
    else:c['relation']='NO_EFFECT'
    before=deepcopy(o['candidate']);Draft202012Validator(body(e)['output_schema']).validate(before)
    monkeypatch.setattr(mean_order,'submit',lambda *a,**k:pytest.fail('No independent approval'))
    p=dispatch.inspect_methods(s,'q1',**o)
    assert p['state']==state and not p['backend_called']
    assert o['candidate']==before
    if kind=='extra_constraint':assert p['mean_order_reading']['unsupported_restrictions']==['ADDITIONAL_RESTRICTION_REQUIRES_ADAPTER']


def test_schema_roles_reappear_in_source_review_and_explicit_recheck():
    s,e,o=setup(mode='NONE');schema=body(e)['output_schema'];defs=schema['$defs']
    assert defs['OrderClaim']['allOf']==[combination_schema()]
    assert '尚未决定' in defs['OrderClaim']['properties']['relation']['description']
    assert '无约束' in defs['OrderReading']['properties']['other_restriction_source_ids']['description']
    assert '不等于冲突' in defs['OrderReading']['properties']['reported_conflict']['description']
    sheet=sources.prepare(e,o['candidate'])
    path='/mean_order_model/order_reading/claims/0'
    assert any(r.get('combination')==combination_schema() for r in sheet['fields'][path]['public_field_constraints'])
    rules=contract_for_entry(e).public_constraints(e,[path])
    assert any(r.get('combination')==combination_schema() for r in rules)
    raw=deepcopy(o['candidate']);raw['mean_order_model']['order_reading']['claims'][0]['scope']='ALL_BINARY_ASSIGNMENTS'
    options=dict(o,candidate=raw);w=revision.prepare_recheck(s,'q1',**options)['feedback_worksheet']
    request=revision.prepare_recheck(s,'q1',**options,feedback=feedback(w,path=path,kind='WIRE_FORMAT_ERROR',doc='orders'))
    assert request['state']=='READY_TO_READ'
    context=json.loads(request['request']['user'].split('独立复查定位（不是新增事实）：\n')[1])
    assert context['wire_format_constraints'][0]['combination']==combination_schema()
    assert 'PRIVATE_REASON_NOT_SENT' not in request['request']['user']
    assert not request['backend_called'] and context['previous_candidate']==raw


def test_roster_dependencies_cover_scalar_bounds_and_covered_nodes_without_inheritance():
    _,e,o=setup();rows=contract_for_entry(e).public_constraints(e,['/bounded_model/bounds/0','/mean_sufficiency'])
    for path in ['/bounded_model/bounds/*/source_ids','/mean_sufficiency/source_ids']:
        assert any(r['field_path']==path and '名册' in r['description'] for r in rows)
    raw=deepcopy(o['candidate']);raw['mean_order_model']['order_reading']['claims'][0]['source_ids']=[]
    with pytest.raises(ValueError):contract_for_entry(e).parse_candidate(e,raw)


def test_legacy_wires_and_system_prompt_unchanged_and_no_order_defaults():
    _,e,o=setup()
    for profile in (None,'network-source-selections-alignment-1'):
        req=reader.make_request(e['bundle'],binding=e['fact_binding_sha256'],profile=profile)
        assert req==reader._base_make_request(e['bundle'],binding=e['fact_binding_sha256'],profile=profile)
        assert 'mean_order_model' not in body(dict(request=req))['output_schema']['properties']
        with pytest.raises(ValueError):reader.reading_model(profile).model_validate(o['candidate'])
    legacy=reader.make_request(e['bundle'],binding=e['fact_binding_sha256'],profile='network-source-selections-alignment-1')
    assert legacy['system']==e['request']['system']
    raw=deepcopy(o['candidate']);raw.pop('mean_order_model')
    assert 'mean_order_model' not in contract_for_entry(e).parse_candidate(e,raw)


@pytest.mark.parametrize('problem',['definition_citation','duplicate_order'])
def test_reviewed_reading_errors_stop_without_repairing_the_candidate(monkeypatch,problem):
    """Reviewer-detected semantic errors, not automatic natural-language detection."""
    from tests_gateway.test_fact_source_review import record
    s,e,o=setup();raw=o['candidate'];claim=raw['mean_order_model']['order_reading']['claims'][0]
    if problem=='duplicate_order':
        raw['additional_restrictions']=[dict(text='本店安排不变，增加邻居使用时均值不降低。',
            source_ids=claim['source_ids'])]
        path='/additional_restrictions/0';dimension='field_role'
    else:
        # Nonempty existing quote is valid wire syntax; completeness is reviewed separately.
        claim['source_ids']=claim['source_ids'][-1:]
        path='/mean_order_model/order_reading/claims/0';dimension='source_coverage'
    before=deepcopy(raw);sheet=sources.prepare(e,raw);review=record(sheet)
    assert dimension in sources.DIMENSIONS
    review['decisions'][path][dimension]='REJECTED'
    o['source_review']=review
    monkeypatch.setattr(mean_order,'submit',lambda *a,**k:pytest.fail('Rejected reading must not solve'))
    result=dispatch.execute(s,'q1',**o,research_protocol_selected=True)
    assert result['state']=='READING_RECHECK_REQUIRED'
    assert result['reason_code']=='FACT_SOURCE_REVIEW_REJECTED'
    assert not result['backend_called'] and result['mathematical_claim'] is None
    assert raw==before and review['decisions'][path][dimension]=='REJECTED'


@pytest.mark.parametrize('definition', ['another outcome', 'paraphrased outcome', None])
def test_order_outcome_binding_checked_before_science_without_normalizing(definition,monkeypatch):
    from cfm_id_llm.mean_order_field_contract import OUTCOME_BINDING_RULE
    s,e,o=setup();raw=o['candidate']
    raw['bounded_model']['outcome_definition']=definition
    before=deepcopy(raw)
    assert OUTCOME_BINDING_RULE in body(e)['output_schema']['x-cfm-field-contract']
    rules=contract_for_entry(e).public_constraints(e,['/bounded_model/outcome_definition'])
    assert OUTCOME_BINDING_RULE in rules
    if definition is not None:
        with pytest.raises(ValidationError,match='MEAN_ORDER_OUTCOME_DEFINITION_MISMATCH'):
            contract_for_entry(e).model.model_validate(raw)
        assert diagnose(e,raw)==[OUTCOME_BINDING_RULE]
    else:
        contract_for_entry(e).model.model_validate(raw)  # Unknown remains unknown.
    monkeypatch.setattr(mean_order,'submit',lambda *a,**k:pytest.fail('No approved matching outcome'))
    result=dispatch.execute(s,'q1',**o,research_protocol_selected=True)
    assert not result['backend_called'] and result['state'] not in ('POINT','PARTIAL')
    assert raw==before
