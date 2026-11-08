"""Explicit citation dependencies never supply missing business/science facts."""
from copy import deepcopy
import json
import pytest
from cfm_id import business_dispatch as d, fact_source_review as source, fact_reading_revision as revision
from cfm_id_llm import policy_evidence_dependencies as wire, fact_reading_contracts as registry
from cfm_id_llm import policy_record_definitions as records
from examples import network_contrast_dispatch_reference as contrast
from examples.network_dispatch_reference import approval_records
from tests_gateway import test_policy_reading_contracts as mean
from tests_gateway.test_fact_source_review import record
from tests_gateway.test_fact_reading_revision import feedback
from tests_gateway._reading_contract_checks import validate_candidate, policy_inputs, contrast_inputs


def setup(family='contrast', kind='point', profile=wire.CONTRACT):
    if family == 'contrast':return contrast.setup(kind, profile=profile)
    return mean.setup('r1b' if kind == 'point' else kind, profile=profile)


@pytest.mark.parametrize('family', ['mean','contrast'])
@pytest.mark.parametrize('kind', ['point','partial'])
@pytest.mark.parametrize('profile', [wire.CONTRACT, records.CONTRACT])
def test_declared_sources_preserve_native_math_and_independent_replay(family,kind,profile):
    s,e,o=setup(family,kind,profile);raw=deepcopy(o['candidate']);validate_candidate(e,raw)
    w=source.prepare(e,raw);path='/target/first' if family=='contrast' else '/target'
    assert w['fields'][path]['explicit_definitions']['study']['source_ids']==raw['study']['source_ids']
    assert w['fields'][path]['citation_groups']['source_ids']==(raw['target']['first'] if family=='contrast' else raw['target'])['source_ids']
    o['source_review']=record(w);p=d.inspect_methods(s,'q1',**o)
    assert not p['evidence_dependencies']['source_entailment_verified']
    assert not d.execute(s,'q1',**o,research_protocol_selected=True)['backend_called']
    r=d.execute(s,'q1',**o,**approval_records(p))
    assert r['state']==kind.upper() and r['independent_replay'] and o['candidate']==raw
    old_s,old_e,old_o=setup(family,kind,profile='network-source-selections-alignment-1')
    old_p=d.inspect_methods(old_s,'q1',**old_o)
    inputs=contrast_inputs if family=='contrast' else policy_inputs
    assert inputs(p,raw['reference_context'])==inputs(old_p,old_o['candidate']['reference_context'])
    # Definition evidence remains separately visible; it is never promoted to
    # an extra population-information table or discarded from the review hash.
    row=next(x for x in p['evidence_dependencies']['resolutions'] if x['field_path']=='/information/0')
    assert row['direct_source_ids']==raw['information'][0]['source_ids']
    assert set(raw['study']['source_ids'])<=set(row['resolved_source_ids'])
    if kind=='partial':assert r['mathematical_claim']['sharp']


@pytest.mark.parametrize('defect', ['missing_dependency','missing_direct_claim','wrong_scope_source','refused_science'])
def test_scientific_scope_definitions_never_establish_scope_or_permission(defect,monkeypatch):
    s,e,o=setup('contrast','partial',records.CONTRACT);raw=o['candidate'];claim=raw['mean_sufficiency']
    if defect=='missing_dependency':claim['definition_refs']=[]
    elif defect=='missing_direct_claim':claim['source_ids']=[]
    elif defect=='wrong_scope_source':claim['source_ids']=raw['study']['source_ids']
    else:raw['scientific_statements']['consistency']['status']='NOT_ADOPTED'
    before=deepcopy(raw)
    monkeypatch.setattr('cfm_id.network_contrast_dispatch._compile_pair',lambda *_:pytest.fail('invalid or refused scope reached math'))
    if defect=='wrong_scope_source':
        review=record(source.prepare(e,raw));review['decisions']['/mean_sufficiency']['source_coverage']='REJECTED'
        options=dict(o,source_review=review)
    else:options=o
    r=d.execute(s,'q1',**options,research_protocol_selected=True)
    expected=('READING_RECHECK_REQUIRED' if defect=='wrong_scope_source' else
              'ADAPTER_NOT_CONNECTED' if defect=='refused_science' else 'CHECK_BLOCKED')
    assert r['state']==expected and not r['backend_called'] and raw==before


def test_scientific_scope_definition_is_visible_bound_and_located_on_recheck():
    s,e,o=setup('contrast','partial',records.CONTRACT);raw=o['candidate'];before=deepcopy(raw)
    w=source.prepare(e,raw);row=w['fields']['/mean_sufficiency']
    assert row['explicit_definitions']['study']['source_ids']==raw['study']['source_ids']
    review=record(w);p=d.inspect_methods(s,'q1',**dict(o,source_review=review))
    dep=next(r for r in p['evidence_dependencies']['resolutions'] if r['field_path']=='/mean_sufficiency')
    assert dep['direct_source_ids']==raw['mean_sufficiency']['source_ids']
    assert dep['definition_refs']==['study'] and not p['evidence_dependencies']['scientific_approval']
    sheet=revision.prepare_recheck(s,'q1',**o)['feedback_worksheet']
    fresh=revision.prepare_recheck(s,'q1',**o,feedback=feedback(sheet,path='/mean_sufficiency',doc='sufficiency'))
    body=json.JSONDecoder().raw_decode(fresh['request']['user'])[0]
    assert body['evidence_dependency_contract']['version']==records.CONTRACT
    constraints=registry.contract_for_entry(fresh).public_constraints(fresh,['/mean_sufficiency'])
    assert any(r['field_path'].startswith('/mean_sufficiency/') for r in constraints)
    raw['study']['source_ids']=raw['target']['source_ids']
    assert d.execute(s,'q1',**o,source_review=review,research_protocol_selected=True)['state']=='CHECK_BLOCKED'
    assert before['mean_sufficiency']==raw['mean_sufficiency']


@pytest.mark.parametrize('defect', ['missing_dependency','unknown_definition','duplicate_dependency','no_direct_claim','foreign_source','stale_context','wrong_name'])
def test_invalid_dependency_cannot_enter_solver(defect,monkeypatch):
    s,e,o=setup();raw=o['candidate'];arm=raw['target']['first']
    if defect=='missing_dependency':arm['definition_refs']=[]
    elif defect=='unknown_definition':arm['definition_refs']=['unregistered']
    elif defect=='duplicate_dependency':arm['definition_refs']*=2
    elif defect=='no_direct_claim':arm['source_ids']=[]
    elif defect=='foreign_source':raw['study']['source_ids']=['foreign']
    elif defect=='stale_context':raw['reference_context']='c000000000000'
    else:arm['population']=['not in the named study']
    before=deepcopy(raw)
    monkeypatch.setattr('cfm_id.network_contrast_dispatch._compile_pair',lambda *_:pytest.fail('invalid wire reached math'))
    r=d.execute(s,'q1',**o,research_protocol_selected=True)
    assert r['state']=='CHECK_BLOCKED' and not r['backend_called'] and raw==before


@pytest.mark.parametrize('defect', ['wrong_definition','wrong_coverage'])
def test_semantically_wrong_current_sources_still_require_review(defect,monkeypatch):
    s,e,o=setup();raw=o['candidate']
    # Current, valid IDs do not establish entailment. A reviewer must reject
    # a coding definition backed only by the question, or unsupported coverage.
    path='/study' if defect=='wrong_definition' else '/information/0'
    if defect=='wrong_definition':raw['study']['source_ids']=raw['target']['source_ids']
    else:raw['information'][0]['source_ids']=raw['study']['source_ids']
    review=record(source.prepare(e,raw));review['decisions'][path]['source_coverage']='REJECTED'
    from tests_gateway.test_fact_source_review import forbid_method_calls
    forbid_method_calls(monkeypatch)
    r=d.execute(s,'q1',**o,source_review=review,research_protocol_selected=True)
    assert r['state']=='READING_RECHECK_REQUIRED' and not r['backend_called']
    assert not r['source_review_receipt']['citations_repaired']


@pytest.mark.parametrize('defect,expected', [('sample','NEEDS_INPUT'),('missing_science','NEEDS_INPUT'),('refused','ADAPTER_NOT_CONNECTED')])
def test_definition_does_not_supply_population_information_or_science(defect,expected):
    s,e,o=setup();raw=o['candidate']
    if defect=='sample':raw['information'][0].update(operator='FINITE_SAMPLE',availability='FINITE_SAMPLE')
    else:raw['scientific_statements']['consistency'].update(status='NOT_STATED' if defect=='missing_science' else 'NOT_ADOPTED',source_ids=[] if defect=='missing_science' else raw['scientific_statements']['consistency']['source_ids'])
    r=d.execute(s,'q1',**o,source_review=record(source.prepare(e,raw)),research_protocol_selected=True)
    assert r['state']==expected and not r['backend_called'] and not r['independent_replay']


def test_shared_definition_change_invalidates_reviews_and_recheck_keeps_contract():
    s,e,o=setup();review=record(source.prepare(e,o['candidate']))
    o['candidate']['study']['source_ids']=o['candidate']['target']['source_ids']
    assert d.execute(s,'q1',**o,source_review=review,research_protocol_selected=True)['state']=='CHECK_BLOCKED'
    w=revision.prepare_recheck(s,'q1',**o)['feedback_worksheet']
    fresh=revision.prepare_recheck(s,'q1',**o,feedback=feedback(w,path='/study',doc='study'))
    body=json.JSONDecoder().raw_decode(fresh['request']['user'])[0]
    assert body['evidence_dependency_contract']['version']==wire.CONTRACT
    assert registry.contract_for_entry(fresh).public_constraints(fresh,['/target/first/definition_refs'])
    assert fresh['request_sha256']!=e['request_sha256']
