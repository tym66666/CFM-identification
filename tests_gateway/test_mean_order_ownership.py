"""Field ownership revisions keep exact scientific and certificate gates."""
from copy import deepcopy
import json
import pytest
from jsonschema import Draft202012Validator
from cfm_id import business_intake as intake, business_dispatch as dispatch, fact_source_review as sources
from cfm_id_llm import mean_order_ownership as ownership, network_contrast_reading as wire
from cfm_id_llm.network_policy_reading import reference_catalog
from examples.network_mean_order_dispatch_reference import setup as previous_setup
from examples.business_dispatch_reference import approve
from examples.network_contrast_dispatch_reference import approval_records
from tests_gateway.test_fact_source_review import record


def setup(**kwargs):
    s, old_entry, opts = previous_setup(**kwargs)
    s = intake.configure_network_fact_contract(s, ownership.PROFILE)
    qr = approve(dispatch.prepare_reader(s, 'q1')['query_worksheet'])
    e = dispatch.prepare_reader(s, 'q1', query_review=qr)
    raw = deepcopy(opts['candidate'])
    raw['reference_context'] = reference_catalog(e['bundle'], binding=e['fact_binding_sha256'])['context']
    return s, e, dict(query_review=qr, candidate=raw, request_sha256=e['request_sha256'])


def test_request_schema_review_and_recheck_share_one_owner():
    s, e, o = setup()
    text = json.dumps(e['request'], ensure_ascii=False)
    for old in ('关系同时完整保留在additional_restrictions', '额外关系完整保留在additional_restrictions'):
        assert old not in text
    body = json.JSONDecoder().raw_decode(e['request']['user'])[0]
    Draft202012Validator(body['output_schema']).validate(o['candidate'])
    paths = ['/additional_restrictions', '/bounded_model/no_additional_coupling_constraints', '/study/context']
    rules = wire.field_constraints(paths, request=e['request'], profile=ownership.PROFILE)
    for path in paths:
        assert any(r['field_path']==path and r['description']==ownership.ROLES[path] for r in rules)
    assert '会进入数学目标' in body['output_schema']['$defs']['Study']['properties']['context']['description']


@pytest.mark.parametrize('mode,expected', [('BOTH',['1/5','1']),('OWN',['-1/5','1']),('NONE',['-1','1'])])
def test_assumption_ladder_replays_without_new_math(mode, expected):
    s, e, o = setup(mode=mode)
    raw = deepcopy(o['candidate'])
    o['source_review'] = record(sources.prepare(e, raw))
    plan = dispatch.inspect_methods(s, 'q1', **o)
    result = dispatch.execute(s, 'q1', **o, **approval_records(plan))
    assert result['state']=='PARTIAL' and result['mathematical_claim']['interval']==expected
    assert result['independent_replay'] and result['mathematical_claim']['sharp'] and o['candidate']==raw


def test_supported_point_still_requires_independent_science_and_replay():
    s, e, o = setup(supported=True)
    o['source_review'] = record(sources.prepare(e, o['candidate']))
    plan = dispatch.inspect_methods(s, 'q1', **o)
    assert not dispatch.execute(s, 'q1', **o, research_protocol_selected=True)['backend_called']
    reviews = approval_records(plan)
    result = dispatch.execute(s, 'q1', **o, **reviews)
    assert result['state']=='POINT' and result['independent_replay']
    reviews['native_reviews'][plan['methods'][0]['method']]['science_review'].decisions[
        next(iter(reviews['native_reviews'][plan['methods'][0]['method']]['science_review'].decisions))] = 'REJECTED'
    assert not dispatch.execute(s, 'q1', **o, **reviews)['backend_called']


@pytest.mark.parametrize('defect,expected', [('missing','NEEDS_INPUT'),('extra','ADAPTER_NOT_CONNECTED'),
    ('duplicate','READING_RECHECK_REQUIRED'),('citation','READING_RECHECK_REQUIRED'),('format','CHECK_BLOCKED')])
def test_diagnostics_do_not_erase_restrictions_or_waive_sources(defect, expected):
    s, e, o = setup(negative='missing_peer' if defect=='missing' else None)
    c = o['candidate']
    if defect in ('duplicate','extra'):
        c['additional_restrictions'] = [dict(source_ids=c['mean_order_model']['order_reading']['claims'][0]['source_ids'],
            text='本人均值非减。' if defect=='duplicate' else '另要求两家对象的潜在结果均值相等。')]
    if defect=='format':
        c['mean_order_model']['order_reading']['claims'][0].update(relation='NOT_ASSUMED')
    else:
        w = sources.prepare(e, c); review = record(w)
        if defect in ('duplicate','extra'):
            check = w['fields']['/additional_restrictions/0']['ownership_check']
            assert check['shared_source_is_not_duplicate_proof']
        if defect=='duplicate': review['decisions']['/additional_restrictions/0']['field_role']='REJECTED'
        if defect=='citation': review['decisions']['/study']['source_coverage']='REJECTED'
        o['source_review']=review
    before=deepcopy(c)
    result=dispatch.execute(s,'q1',**o,research_protocol_selected=True)
    assert result['state']==expected and not result['backend_called'] and c==before
    if defect in ('duplicate','citation'):
        diagnostic=result['source_review_diagnostics']
        assert not diagnostic['explanation_only_waiver_granted']
        assert diagnostic['citation_only_count']==int(defect=='citation')
        if defect=='citation':assert diagnostic['issues'][0]['use']=='MIXED_STUDY_RECORD_CONTEXT_ENTERS_TARGET'


def test_old_request_profile_stays_distinct_and_old_approvals_are_stale():
    s, e, o=previous_setup()
    old=deepcopy(e['request'])
    plan=dispatch.inspect_methods(s,'q1',**o); reviews=approval_records(plan)
    changed=intake.configure_network_fact_contract(s,ownership.PROFILE)
    assert not dispatch.execute(changed,'q1',**o,**reviews)['backend_called']
    assert dispatch.prepare_reader(s,'q1',query_review=o['query_review'])['request']==old
