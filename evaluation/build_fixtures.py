"""Generate explicit test-only fixture responses to exercise the evaluation harness.

WARNING: Synthetic fixture outputs are constructed from answer references and
MUST NEVER be reported as results of an LLM. They are NOT for model training,
mathematical proof, or benchmark accuracy reporting.
"""
from __future__ import annotations
import json
from pathlib import Path
from cfm_id_llm.schemas import BusinessCase
from .real_benchmark import DEFAULT_DATASET, DEFAULT_FIXTURES, load_benchmark
from .frozen_problems import make_frozen_input


def claim(source,value,quote=None):
    if not quote: quote=source
    return {'value':value,'basis':'EXPLICIT_TEXT','evidence':[{'source_id':source,'quote':quote}]}

def evidence(source_id,quote,value):
    return {'value':value,'basis':'EXPLICIT_TEXT','evidence':[{'source_id':source_id,'quote':quote}]}

def unresolved():
    return {'value':None,'basis':'UNRESOLVED','evidence':[]}


def form_fixture(entry):
    case=BusinessCase.model_validate(entry['business_case'])
    ref=entry['reference']
    sm=case.source_map()
    q=case.business_question
    prot=sm.get('protocol')
    info=sm.get('information')
    out={
       'schema_version':'cfm-id-draft-v0.1',
       'target':{'kind':ref['target_kind'],
                 'description':evidence('business_question',q,q) if ref['target_kind']!='UNRESOLVED' else unresolved(),
                 'alternatives':[]},
       'units_variables':{
           'analysis_unit':evidence('business_question',q,'业务描述中的员工、节点或团体'),
           'treatment':evidence('protocol' if prot else 'business_question',prot or q,'描述中的AI干预'),
           'outcome':evidence('business_question',q,'描述中的销售或结果指标'),
       },
       'structure': {
           'unit_network':(evidence('protocol',prot,'被描述的网络') if prot else unresolved()),
           'exposure_mapping': unresolved(),
       },
       'information_design':{
           'assignment_family':ref['assignment_family'],
           'assignment_law': (evidence('protocol',prot,prot) if ref['assignment_family']!='UNRESOLVED' and prot else unresolved()),
           'population_information_level':ref['a4_level'],
           'population_observable_operator':(evidence('information',info,info) if info and ref['a4_level'] not in ('UNRESOLVED','FINITE_SAMPLE_DESCRIPTION') else unresolved()),
           'sample_data_description':(evidence('information',info,info) if info and ref['a4_level']=='FINITE_SAMPLE_DESCRIPTION' else unresolved()),
       },
       'assumptions':[], 'validity':{},'ambiguities':[], 'clarifying_questions':[],
       'normalization_notes':['MOCK TEST-ONLY fixture synthesized from benchmark reference; not model-generated'],
    }
    if prot and ref['target_kind'] in ('NETWORK_DESIGN_STANDARDIZED_ARM_MEAN','DIRECT_EFFECT','SPILLOVER_EFFECT','TOTAL_EFFECT'):
        if ('S_i' in prot or '暴露' in prot or '邻居' in prot) and entry['id']!='F30':
            out['structure']['exposure_mapping']=evidence('protocol',prot,'描述中的网络暴露映射')
    return out


def candidate_fixture(entry):
    case,formulation,review,routing=make_frozen_input(entry)
    ref=entry['reference']; f=entry['fixed_formal_problem']
    claim_kind=ref['expected_claim']
    scope=ref['scope']
    return {
      'schema_version':'cfm-id-candidate-draft-v0.3',
      'target_kind':f['target_kind'], 'target_description':f['target_description'],
      'claimed_identification':claim_kind,'scope':scope,
      'a4_used':{'source':'REVIEWED_OPERATOR','level':f['a4_level'],'operator':f['a4_operator']},
      'admitted_assumptions_used':f['admitted_a5'],
      'additional_requirements':[
          {'kind':kind,'description':'需要专门核对的本题额外数学条件',
           'why_needed':'这项条件尚未从现有假设及信息直接完成检查'}
           for kind in ref['required_requirement_kinds']
      ],
      'candidate_expression':ref['reference_math'] if claim_kind in ('POINT','PARTIAL') else None,
      'nonidentification_witness':(
         {'world_a':'构造与所有可观测配置一致的潜在结果世界A',
          'world_b':'构造可观测配置不变但目标配置结果不同的潜在结果世界B',
          'why_observables_match':'两者对已观察条件下所有结果一致，从而观察律完全相同',
          'why_targets_differ':ref['reference_math']}
         if claim_kind=='NOT_POINT' else None),
      'reasoning_steps':[ref['rationale']],
      'caveats':['仅为离线FIXTURE，既非大模型推理结果也非数学认证'],
      'suggested_checks':['进行独立数学证明或两个世界的完整可观测等价检查'],
    }


def main():
    data=load_benchmark(DEFAULT_DATASET)
    for stage in ('formulation','candidate'):
        for item in data[stage+'_cases']:
            payload=form_fixture(item) if stage=='formulation' else candidate_fixture(item)
            dest=DEFAULT_FIXTURES / stage / (item['id']+'.json')
            dest.parent.mkdir(parents=True,exist_ok=True)
            dest.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('Generated test-only fixture responses:',len(data['formulation_cases']),len(data['candidate_cases']))


if __name__=='__main__':main()
