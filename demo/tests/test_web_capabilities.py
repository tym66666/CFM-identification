"""Web coverage of registered business routes. Synthetic fixtures, no LLM score."""
from copy import deepcopy
import pytest
from demo.backend.engine import Engine, Run, dispatch
from demo.backend import capabilities
from demo.backend.review_summary import summarize
from examples import network_dispatch_reference as mean, network_bounded_dispatch_reference as bounded
from examples import network_contrast_dispatch_reference as contrast, network_mean_order_dispatch_reference as order
from examples import network_observational_policy_reference as obs, network_observational_signature_reference as sig
from examples import network_r2_contrast_reference as r2contrast, network_effect_dispatch_reference as effect
from examples import business_dispatch_reference as dag
from examples.dag_business_reference import cases as backdoors
from examples.dag_adjustment_business_reference import cases as adjustments
from examples.dag_frontdoor_business_reference import _case as frontdoor

NAMES=('r1a','r1b','r2','partial_mean','point_contrast','r2_contrast','partial_contrast','mean_order','r3','r3_signature','dag_backdoor','dag_adjustment','dag_frontdoor')

def setup(name):
 if name in ('arm','mixture','observed','stratum','nodewise'):
  from examples.network_extended_reference import setup as extended_setup
  return extended_setup(name)
 if name.startswith('dag_'):
  case={'dag_backdoor':lambda:backdoors()[0],'dag_adjustment':lambda:adjustments()[0],
        'dag_frontdoor':lambda:frontdoor('web_frontdoor','implicit_role')}[name]()
  s,o,p=dag.prepare(case);return s,o,p
 builders={'r1a':effect.setup,'r1b':lambda:mean.setup(design='D1',sufficiency=False),'r2':mean.setup,
  'partial_mean':bounded.setup,'point_contrast':lambda:contrast.setup('point'),'r2_contrast':r2contrast.setup,
  'partial_contrast':lambda:contrast.setup('partial'),'mean_order':order.setup,'r3':obs.setup,'r3_signature':sig.setup}
 s,e,o=builders[name]()[:3]
 return s,o,dispatch.inspect_methods(s,'q1',**o)

def prepare(engine,name):
 s,o,p=setup(name)
 r=Run(owner='fixture',synthetic=True,intake=s,query_id='q1',submission=o,plan=p)
 sheets={'plan':p['plan_worksheet']}
 for row in p['methods']:
  for key,suffix in (('reading_worksheet','reading_review'),('science_worksheet','science_review')):
   if key in row:sheets[row['method']+'.'+suffix]=row[key]
 engine._set_review(r,'science',sheets)
 return r

def approve(r):
 records=deepcopy(r.review_templates)
 for v in records.values():
  v.update(reviewer='Synthetic fixture reviewer',evidence='Independently stipulated reference conditions for web adapter regression only.')
  v['decisions']={k:'ACCEPTED' for k in v['decisions']}
 return dict(kind='science',records=records)

@pytest.mark.parametrize('name',NAMES)
def test_registered_routes_execute_after_browser_shaped_confirmation(tmp_path,name):
 e=Engine(tmp_path);r=prepare(e,name);before=deepcopy(r.review_templates)
 summary=summarize(r)
 assert summary['compact_confirmation_available'],summary
 assert len(summary['cards'])==3 and summary['is_approval'] is False
 assert [x['text'] for x in summary['condition_items']]==summary['cards'][1]['lines']
 assert summary['information_brief']
 assert all(x['term'] for x in summary['condition_items']),summary['condition_items']
 assert r.review_templates==before and r.result is None
 e._review(r,approve(r))
 assert r.result['state']==('PARTIAL' if name in ('partial_mean','partial_contrast','mean_order') else 'POINT'),r.result
 assert r.result['independent_replay'] is True
 assert r.result['web_review_summary']['plan_sha256']==r.plan['plan_sha256']

@pytest.mark.parametrize('name',('r1b','partial_mean','mean_order','r3_signature','dag_frontdoor'))
def test_refusal_and_changed_native_identity_cannot_confirm(tmp_path,name):
 e=Engine(tmp_path);r=prepare(e,name);payload=approve(r)
 key=next(k for k in r.review_templates if k.endswith('.science_review'))
 item=next(iter(payload['records'][key]['decisions']))
 payload['records'][key]['decisions'][item]='REJECTED'
 e._review(r,payload)
 assert not r.result['independent_replay'] and r.result['state'] not in ('POINT','PARTIAL')
 r=prepare(e,name);payload=approve(r)
 identity=capabilities.identity(payload['records'][key]);digest=next(k for k in identity if k.endswith('_sha256'))
 payload['records'][key][digest]='0'*64
 with pytest.raises(ValueError,match='STALE'):e._review(r,payload)


def test_registry_coverage_and_science_explanations_are_complete(tmp_path):
 seen=set();e=Engine(tmp_path)
 for name in (*NAMES,'arm','mixture','observed','stratum','nodewise'):
  r=prepare(e,name);seen.update(m['method'] for m in r.plan['methods'])
  assert not summarize(r)['needs_individual_attention']
 assert seen==set(capabilities.METHODS)
 assert capabilities.reading_config().observational_fact_profile=='mean-signature-definitions'


def test_missing_condition_has_no_science_confirmation_or_native_execution(tmp_path):
 s,_,o,_=effect.setup(sample_only=True)
 e=Engine(tmp_path);r=Run(owner='fixture',synthetic=True,intake=s,query_id='q1',submission=o)
 e._plan(r)
 assert r.result['state']=='NEEDS_INPUT' and not r.result['backend_called']
 assert not r.review_sheets and not r.result['independent_replay']

@pytest.mark.parametrize('bounded_case',(False,True))
def test_fixed_background_policy_requires_every_context_decision(bounded_case):
 from cfm_id import network_policy_dispatch as policy
 from cfm_id.network_contrast_context import SCIENCE_REQUIREMENTS
 from cfm_id_llm import query_conditioning_contract as context
 from examples.business_dispatch_reference import approve as review
 values=bounded.setup() if bounded_case else mean.setup()
 s,e,o=values[:3]
 e=deepcopy(e);e['reviewed_target_context']=dict(conditioning_context={'state':'STATED','value':'同一已登记处理前业务背景','refs':['fixture']},standardization_distribution='UNKNOWN')
 assert context.admission(e['reviewed_target_context'],'NETWORK_FIXED_POLICY_FACTS') is None
 p=policy.inspect_methods(e,o['candidate'])
 assert p['state']=='REVIEW_REQUIRED',p
 assert p['target_conditioning_review']['native_context_field']=='study.context'
 for row in p['methods']:
  assert context.MATCH_DECISION in row['reading_worksheet']['decisions']
  assert set(SCIENCE_REQUIREMENTS)<=set(row['science_worksheet']['decisions'])
 records={row['method']:{'reading_review':review(row['reading_worksheet']),'science_review':review(row['science_worksheet'])} for row in p['methods']}
 result=policy._execute_plan(p,plan_review=review(p['plan_worksheet']),native_reviews=records,research_protocol_selected=True)
 assert result['state']==('PARTIAL' if bounded_case else 'POINT') and result['independent_replay']
 for key in SCIENCE_REQUIREMENTS:
  changed=deepcopy(records)
  for row in changed.values():row['science_review']=row['science_review'].model_copy(update={'decisions':{**row['science_review'].decisions,key:'PENDING'}})
  blocked=policy._execute_plan(p,plan_review=review(p['plan_worksheet']),native_reviews=changed,research_protocol_selected=True)
  assert not blocked['backend_called'] and not blocked['independent_replay']
 context_value=deepcopy(e['reviewed_target_context']);context_value['standardization_distribution']={'state':'STATED','value':'跨地区平均'}
 assert context.admission(context_value,'NETWORK_FIXED_POLICY_FACTS')[0]=='ADAPTER_NOT_CONNECTED'
 context_value['standardization_distribution']='UNKNOWN';context_value['conditioning_context']={'state':'MISSING'}
 assert context.admission(context_value,'NETWORK_FIXED_POLICY_FACTS')[0]=='NEEDS_INPUT'
