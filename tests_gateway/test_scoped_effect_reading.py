from copy import deepcopy
import json
import pytest
from jsonschema import Draft202012Validator
from cfm_id import business_dispatch as dispatch,business_intake as intake
from cfm_id_llm import scoped_role_contract as contract,scoped_effect_reading as wire
from tests_gateway import test_owned_effect_reading as prior
from tests_gateway.test_business_field_review import sheet,record,submit
from examples.network_effect_dispatch_reference import approval_records


def setup(monkeypatch,**kwargs):
 monkeypatch.setattr(prior,'contract',contract)
 s,e,o=prior.setup(monkeypatch,**kwargs)
 raw=o['candidate'];raw['version']=wire.VERSION;raw['target'].pop('kind')
 for info in raw['information']:
  info['scope_status']='DECLARED' if info['outcome_nodes'] else 'UNSPECIFIED'
  info['scope_source_ids']=list(info['source_ids']) if info['outcome_nodes'] else []
 return s,e,o


@pytest.mark.parametrize('kind',['DIRECT_EFFECT','SPILLOVER_EFFECT'])
@pytest.mark.parametrize('reverse',[False,True])
@pytest.mark.parametrize('quantity',['INCREASE','REDUCTION'])
def test_reviewed_kind_keeps_original_evidence_and_native_point(monkeypatch,kind,reverse,quantity):
 s,e,o=setup(monkeypatch,kind=kind,reverse=reverse,quantity=quantity,count=True)
 original=deepcopy(o['candidate']);body=json.JSONDecoder().raw_decode(e['request']['user'])[0]
 Draft202012Validator.check_schema(body['output_schema']);assert Draft202012Validator(body['output_schema']).is_valid(original)
 assert 'kind' not in body['output_schema']['$defs']['Target']['properties']
 assert set(wire.Target.model_fields)==set(prior.wire.Target.model_fields)-{'kind'}
 p=dispatch.inspect_methods(s,'q1',**o);assert p['state']=='REVIEW_REQUIRED'
 origin=p['target_kind_origin'];assert origin['kind']==kind and origin['reviewed_target']==e['selected_query']['target']
 assert origin['query_review_sha256']==dispatch.sha(e['query_review']) and origin['raw_goal_source_refs']
 assert not origin['scientific_approval'] and not origin['model_outputs_kind']
 assert not dispatch.execute(s,'q1',**o,research_protocol_selected=True)['backend_called']
 r=dispatch.execute(s,'q1',**o,**approval_records(p));assert r['state']=='POINT' and r['independent_replay']
 assert o['candidate']==original and p['facts']['study']['outcome_kind']=='COUNT'


@pytest.mark.parametrize('defect',['model_kind','unknown_nonempty_nodes','unknown_cells','unknown_scope_sources','known_no_nodes','known_no_scope_sources','duplicate_scope_sources','foreign_scope_source','bad_scope_enum','missing_scope_status','scope_cannot_supply_type_evidence'])
def test_scope_shape_and_source_contract_reject_without_repair(monkeypatch,defect):
 s,e,o=setup(monkeypatch);r=o['candidate'];info=r['information'][0]
 if defect=='model_kind':r['target']['kind']='DIRECT_EFFECT'
 elif defect=='unknown_nonempty_nodes':info.update(scope_status='UNSPECIFIED',arm_cells=[],scope_source_ids=[])
 elif defect=='unknown_cells':info.update(scope_status='UNSPECIFIED',outcome_nodes=[],scope_source_ids=[])
 elif defect=='unknown_scope_sources':info.update(scope_status='UNSPECIFIED',outcome_nodes=[],arm_cells=[])
 elif defect=='known_no_nodes':info.update(outcome_nodes=[],arm_cells=[])
 elif defect=='known_no_scope_sources':info['scope_source_ids']=[]
 elif defect=='duplicate_scope_sources':info['scope_source_ids']*=2
 elif defect=='foreign_scope_source':info['scope_source_ids']=['foreign']
 elif defect=='bad_scope_enum':info['scope_status']='ALL_STUDY'
 elif defect=='scope_cannot_supply_type_evidence':info['source_ids']=[]
 else:info.pop('scope_status')
 before=deepcopy(r);p=dispatch.inspect_methods(s,'q1',**o)
 assert p['state']=='CHECK_BLOCKED' and not p['backend_called'] and r==before


@pytest.mark.parametrize('known_scope',[False,True])
def test_finite_records_never_become_population_information(monkeypatch,known_scope):
 s,e,o=setup(monkeypatch);info=o['candidate']['information'][0]
 info.update(operator='FINITE_SAMPLE',availability='FINITE_SAMPLE',arm_cells=[])
 if not known_scope:info.update(outcome_nodes=[],scope_status='UNSPECIFIED',scope_source_ids=[],definition_refs=[])
 p=dispatch.inspect_methods(s,'q1',**o);r=dispatch.execute(s,'q1',**o,research_protocol_selected=True)
 assert r['state']=='NEEDS_INPUT' and not r['backend_called']
 assert p['facts']['information'][0]['outcome_nodes']==info['outcome_nodes']
 assert not p['information_scope_evidence']['automatic_scope_inference']


@pytest.mark.parametrize('bad',['scope_entailment_rejected','scientific_pending','scientific_refused','extra_restriction'])
def test_valid_wire_still_requires_source_and_scientific_review(monkeypatch,bad):
 s,e,o=setup(monkeypatch,count=True);r=o['candidate'];source=r['study']['source_ids'][0]
 if bad=='scientific_refused':r['scientific_statements']['consistency']['status']='NOT_ADOPTED'
 if bad=='extra_restriction':r['additional_restrictions']=[dict(text='真正的额外结果上界需要单独模型处理，不能删掉以获得POINT。',source_ids=[source])]
 p=dispatch.inspect_methods(s,'q1',**o);reviews={}
 if p.get('methods'):
  reviews=approval_records(p);pair=next(iter(reviews['native_reviews'].values()))
  if bad=='scope_entailment_rejected':pair['reading_review'].decisions['source_entailment']='REJECTED'
  if bad=='scientific_pending':pair['science_review'].decisions['finite_conditional_first_moments']='PENDING'
 result=dispatch.execute(s,'q1',**o,**(reviews or dict(research_protocol_selected=True)))
 assert not result['backend_called'] and not result['independent_replay']


@pytest.mark.parametrize('axis',['field_role','value_state','source_coverage'])
def test_a0_kind_review_rejection_prevents_fact_request(monkeypatch,axis):
 s,e,o=setup(monkeypatch);sh=sheet(s);rr=record(sh);rr['decisions']['queries.q1.kind'][axis]='REJECTED'
 rejected=submit(s,rr);assert rejected['state']=='CHECK_BLOCKED'
 assert dispatch.prepare_reader(s,'q1',query_review=rejected.get('query_review'))['request'] is None


def test_changed_a0_kind_cannot_reuse_old_approval(monkeypatch):
 s,e,o=setup(monkeypatch);raw=deepcopy(s.candidate);raw['queries'][0]['kind']='SPILLOVER_EFFECT'
 new=intake.receive_candidate(s,raw,request_sha256=s.request_sha256)
 result=dispatch.prepare_reader(new,'q1',query_review=e['query_review'])
 assert result['request'] is None and not result['backend_called']


@pytest.mark.parametrize('network_contract',[None,'network-source-selections-dependencies-1','network-source-selections-alignment-1'])
def test_recheck_keeps_kind_origin_and_explicit_coverage(monkeypatch,network_contract):
 from cfm_id.fact_reading_revision import prepare_recheck
 s,e,o=setup(monkeypatch,count=True,network_contract=network_contract)
 w=prepare_recheck(s,'q1',**o)['feedback_worksheet']
 f=dict(version=w['version'],binding_sha256=w['binding_sha256'],authority=w['expected_authority'],reviewer='Independent fixture reviewer',evidence='Locate actual scope statement; no answer supplied.',issues=[dict(field_path='/information/0',kind='OMITTED_OR_MISREAD',source_ids=list(w['source_catalog'])[:1],reason='PRIVATE_NOT_SENT')])
 revised=prepare_recheck(s,'q1',**o,feedback=f)
 assert revised['effect_fact_contract']==wire.VERSION and 'PRIVATE_NOT_SENT' not in revised['request']['user']
 body=json.JSONDecoder().raw_decode(revised['request']['user'])[0]
 assert 'kind' not in body['output_schema']['$defs']['Target']['properties']
 assert body['information_scope_contract']['version']==wire.VERSION


@pytest.mark.parametrize('kind',['point','partial','dag'])
def test_other_routes_keep_original_contract(monkeypatch,kind):
 monkeypatch.setattr(prior,'contract',contract)
 prior.test_other_routes_unaffected(monkeypatch,kind)
