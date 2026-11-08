from copy import deepcopy
import json
import pytest
from jsonschema import Draft202012Validator
from cfm_id import business_intake as intake,business_dispatch as dispatch
from cfm_id_llm import local_role_ownership as contract,owned_effect_reading as wire
from cfm_id_llm.requested_change_contract import POSITIONS
from tests_gateway import test_ordered_comparison_contract as old
from tests_gateway.test_requested_change_contract import converted
from tests_gateway.test_inline_evidence_slots import receive
from tests_gateway.test_business_field_review import sheet,record,submit
from examples.network_effect_dispatch_reference import approval_records

def owned(raw,quantity='REDUCTION'):
 raw=converted(raw,quantity)
 for q in raw['queries']:
  if q['kind'] not in old.ordered.LOCAL_KINDS:continue
  shared=q['semantics'].pop('neighbor_exposure');r=q['comparison_request']
  if q['kind']=='SPILLOVER_EFFECT':
   shared=dict(state='STATED',value='自己未启用',refs=r['refs'])
   for role in ('reference','evaluated'):r[role]['value']=r[role]['value'].replace('自己未启用且','')
  r['shared_condition']=shared
 return raw

def setup(monkeypatch,kind='DIRECT_EFFECT',reverse=False,quantity='REDUCTION',count=False,network_contract=None):
 def received(case,raw,short=True):
  s=receive(case,owned(raw,quantity),short=short,profile=contract.CONTRACT)
  return intake.configure_network_fact_contract(s,network_contract) if network_contract else s
 monkeypatch.setattr(old,'received',received)
 s,e,o=old.execution(kind,reverse);r=o['candidate'];t=r['target'];first,second=POSITIONS[quantity]
 a,b=t.pop('first'),t.pop('second');t.pop('operation');t.update({first:a,second:b},definition_refs=['study'])
 r['version']=wire.VERSION;r['assignment']['definition_refs']=['study']
 for arm in (a,b):arm['definition_refs']=['study','exposure']
 for info in r['information']:info['definition_refs']=['study'] if info['outcome_nodes'] else []
 if count:r['study']['outcome_kind']='COUNT'
 return s,e,o

@pytest.mark.parametrize('kind',['DIRECT_EFFECT','SPILLOVER_EFFECT'])
@pytest.mark.parametrize('reverse',[False,True])
@pytest.mark.parametrize('quantity',['INCREASE','REDUCTION'])
def test_owned_fields_count_and_real_native_replay(monkeypatch,kind,reverse,quantity):
 s,e,o=setup(monkeypatch,kind,reverse,quantity,count=True);raw=deepcopy(o['candidate'])
 w=sheet(s);assert 'queries.q1.semantics.neighbor_exposure' not in w['fields']
 assert 'queries.q1.comparison_request.shared_condition' in w['fields']
 body=json.JSONDecoder().raw_decode(e['request']['user'])[0]
 Draft202012Validator.check_schema(body['output_schema']);assert Draft202012Validator(body['output_schema']).is_valid(raw)
 p=dispatch.inspect_methods(s,'q1',**o);assert p['state']=='REVIEW_REQUIRED'
 assert p['facts']['study']['outcome_kind']=='COUNT'
 assert not p['evidence_dependencies']['source_entailment_verified']
 assert not dispatch.execute(s,'q1',**o,research_protocol_selected=True)['backend_called']
 r=dispatch.execute(s,'q1',**o,**approval_records(p))
 assert r['state']=='POINT' and r['independent_replay']
 domain=r['mathematical_claim']['target']['outcome_domain_embedding']
 assert domain['business_kind']=='COUNT' and not domain['distributional_continuity_assumed']
 assert not domain['sharp_bound_or_nonidentification_transfer'] and o['candidate']==raw

@pytest.mark.parametrize('defect',['missing_shared','duplicate_neighbor','bad_shared_refs','shared_na','shared_unknown_value'])
def test_a0_bad_or_duplicate_owners_block(defect):
 case,_,raw=old.local_fixture();raw=owned(raw);q=raw['queries'][0];r=q['comparison_request']
 if defect=='missing_shared':r.pop('shared_condition')
 elif defect=='duplicate_neighbor':q['semantics']['neighbor_exposure']=r['shared_condition']
 elif defect=='bad_shared_refs':r['shared_condition']['refs']=['invented']
 elif defect=='shared_na':r['shared_condition']='NOT_APPLICABLE'
 else:r['shared_condition']['state']='UNKNOWN'
 s=receive(case,raw,short=False,profile=contract.CONTRACT)
 assert 'report' not in intake.inspect(s)
 assert dispatch.prepare_reader(s,'q1')['request'] is None

@pytest.mark.parametrize('kind',['DIRECT_EFFECT','SPILLOVER_EFFECT'])
@pytest.mark.parametrize('state',['UNKNOWN','MISSING'])
def test_missing_shared_condition_cannot_be_inferred(kind,state):
 case,_,raw=old.local_fixture(kind);raw=owned(raw);r=raw['queries'][0]['comparison_request']
 r['shared_condition']='UNKNOWN' if state=='UNKNOWN' else dict(state='MISSING',reason='共同条件尚未决定',refs=r['refs'])
 s=receive(case,raw,profile=contract.CONTRACT);before=deepcopy(s.candidate)
 assert 'report' in intake.inspect(s) and dispatch.prepare_reader(s,'q1')['request'] is None
 assert s.candidate==before

@pytest.mark.parametrize('bad',['missing_dependency','unknown_dependency','duplicate_dependency','no_direct','uncited_definition','foreign_source','count_wrong_type'])
def test_dependencies_and_count_are_not_automatic_repairs(monkeypatch,bad):
 s,e,o=setup(monkeypatch,count=True);r=o['candidate'];arm=r['target']['reference']
 if bad=='missing_dependency':arm['definition_refs']=[]
 elif bad=='unknown_dependency':arm['definition_refs']=['target']
 elif bad=='duplicate_dependency':arm['definition_refs']*=2
 elif bad=='no_direct':arm['source_ids']=[]
 elif bad=='uncited_definition':r['exposure']['source_ids']=[]
 elif bad=='foreign_source':r['study']['source_ids']=['invented']
 else:r['study']['outcome_kind']='count'
 before=deepcopy(r);p=dispatch.inspect_methods(s,'q1',**o)
 assert p['state']=='CHECK_BLOCKED' and not p['backend_called'] and r==before

@pytest.mark.parametrize('bad',['source_rejected','science_pending','science_refused','finite_sample','real_bound','categorical'])
def test_unchanged_review_and_information_boundaries(monkeypatch,bad):
 s,e,o=setup(monkeypatch,count=True);raw=o['candidate']
 if bad=='science_refused':raw['scientific_statements']['consistency']['status']='NOT_ADOPTED'
 if bad=='finite_sample':
  for info in raw['information']:info.update(operator='FINITE_SAMPLE',availability='FINITE_SAMPLE',arm_cells=[])
 if bad=='real_bound':raw['additional_restrictions']=[dict(text='An additional mean upper bound',source_ids=raw['study']['source_ids'])]
 if bad=='categorical':raw['study']['outcome_kind']='OTHER'
 p=dispatch.inspect_methods(s,'q1',**o);reviews={}
 if p.get('methods'):
  reviews=approval_records(p);pair=next(iter(reviews['native_reviews'].values()))
  if bad=='source_rejected':pair['reading_review'].decisions['source_entailment']='REJECTED'
  if bad=='science_pending':pair['science_review'].decisions['finite_conditional_first_moments']='PENDING'
 r=dispatch.execute(s,'q1',**o,**(reviews or dict(research_protocol_selected=True)))
 assert not r['backend_called'] and not r['independent_replay']

def test_shared_owner_change_invalidates_old_review():
 case,_,raw=old.local_fixture();s=receive(case,owned(raw),profile=contract.CONTRACT)
 q=submit(s,record(sheet(s)))['query_review'];new=deepcopy(s.candidate)
 new['queries'][0]['comparison_request']['shared_condition']['value']='另一同伴条件'
 changed=intake.receive_candidate(s,new,request_sha256=s.request_sha256)
 assert dispatch.prepare_reader(changed,'q1',query_review=q)['request'] is None

def test_count_mean_formula_matches_integer_world_with_fractional_expectations(monkeypatch):
 from fractions import Fraction as F
 from itertools import product
 s,e,o=setup(monkeypatch,count=True);p=dispatch.inspect_methods(s,'q1',**o)
 r=dispatch.execute(s,'q1',**o,**approval_records(p));c=p['facts'];nodes=c['study']['nodes'];t=c['target']
 means={};masses={}
 for n in t['population']:
  i=nodes.index(n);neighbors={nodes.index(v) for edge in c['study']['edges'] if n in edge for v in edge if v!=n}
  for arm in (t['first'],t['second']):
   mass=num=F(0)
   for z in product((0,1),repeat=len(nodes)):
    if (z[i],int(2*sum(z[j] for j in neighbors)>len(neighbors)))!=(arm['own'],arm['exposure']):continue
    probability=F(1)
    for j,node in enumerate(nodes):
     rate=F(c['assignment']['probabilities'][node]);probability*=rate if z[j] else 1-rate
    y=2*i+sum((j+1)*x for j,x in enumerate(z))+z[0]*z[-1]
    assert type(y) is int and y>=0
    mass+=probability;num+=probability*y
   key=(n,arm['own'],arm['exposure']);means[key]=num/mass;masses[key]=mass
 expected=sum((means[(n,t['first']['own'],t['first']['exposure'])]-means[(n,t['second']['own'],t['second']['exposure'])] for n in t['population']),F(0))/len(t['population'])
 actual=F(0)
 for a in r['certificate']['results'][0]['constituent_arms']:
  key=(a['node_id'],a['own_treatment'],a['exposure_state'])
  assert F(a['joint_support'])==masses[key];actual+=F(a['coefficient'])*means[key]
 assert actual==expected and any(x.denominator>1 for x in means.values())

@pytest.mark.parametrize('network_contract',[None,'network-source-selections-dependencies-1','network-source-selections-alignment-1'])
def test_recheck_preserves_dependency_and_count_contract(monkeypatch,network_contract):
 from cfm_id.fact_reading_revision import prepare_recheck
 s,e,o=setup(monkeypatch,count=True,network_contract=network_contract);w=prepare_recheck(s,'q1',**o)['feedback_worksheet']
 f=dict(version=w['version'],binding_sha256=w['binding_sha256'],authority=w['expected_authority'],reviewer='Independent test reviewer',evidence='Original field and definitions recheck; no answer supplied.',issues=[dict(field_path='/target/reference',kind='OMITTED_OR_MISREAD',source_ids=list(w['source_catalog'])[:1],reason='PRIVATE_NOT_SENT')])
 revised=prepare_recheck(s,'q1',**o,feedback=f)
 assert revised['effect_fact_contract']==wire.VERSION and 'PRIVATE_NOT_SENT' not in revised['request']['user']
 assert 'evidence_dependency_contract' in revised['request']['user'] and 'shared_condition' in revised['request']['user']
 assert 'source_dependency_contract' not in revised['request']['user']
 assert any('PROPOSED' in r['description'] for r in w['public_field_constraints'])

@pytest.mark.parametrize('kind',['point','partial','dag'])
def test_other_routes_unaffected(monkeypatch,kind):
 monkeypatch.setattr(old,'received',lambda case,raw,short=True:receive(case,owned(raw),short=short,profile=contract.CONTRACT))
 if kind=='dag':old.test_dag_retains_original_wire_and_native_replay()
 else:old.test_complete_policy_contrast_preserves_business_roles_and_replay(kind)
