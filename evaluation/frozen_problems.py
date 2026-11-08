"""Frozen *synthetic benchmark* problems, NOT real human approval of studies.

The mathematical assumptions here are hypothetical test inputs stipulated by
curators. Do not reuse these test review receipts for a real business case.
"""
from __future__ import annotations

from cfm_id_llm.audit import audit_draft, fingerprint_business_case
from cfm_id_llm.mock_core import MockCorePort, MockCoreScenario
from cfm_id_llm.orchestration_schemas import HumanReviewV02, canonical_sha256
from cfm_id_llm.orchestrator import route_formulation
from cfm_id_llm.schemas import BusinessCase, DraftProblemSpec


def _claim(source_id: str, quoted: str, *, value: str, basis='EXPLICIT_TEXT'):
    return {'value':value,'basis':basis,'evidence':[{'source_id':source_id, 'quote':quoted}]}


def make_frozen_input(entry: dict):
    """Build fixed input solely from curator input fields, never from reference gold.

    Returns case, formulation, test-only review, routing. Does not call any LLM.
    All paths are fed to the existing v0.3 audit/confirmation/gating machinery.
    """
    case = BusinessCase.model_validate(entry['business_case'])
    f = entry['fixed_formal_problem']
    sm=case.source_map()
    protocol=sm['protocol']
    info=sm['information']
    assumptions=sm['assumption_contract']
    question=case.business_question
    target=f['target_kind']
    needs_exposure=target in {'NETWORK_DESIGN_STANDARDIZED_ARM_MEAN','DIRECT_EFFECT','SPILLOVER_EFFECT','TOTAL_EFFECT'}
    # Exact quotes and explicit test-fixture assumption contract. No actual protocol authentication.
    draft={
      'target':{'kind':target,'description':_claim('business_question',question,value=f['target_description'])},
      'units_variables': {
          'analysis_unit':_claim('business_question',question,value='网络中研究的员工/节点'),
          'treatment':_claim('protocol',protocol,value='协议指定的二元处理'),
          'outcome':_claim('business_question',question,value='问题中指定的结果指标'),
      },
      'structure': {
          'unit_network':_claim('protocol',protocol,value='题目假定的处理前网络'),
          'network_pretreatment_status':_claim('protocol',protocol,value='给定/处理前网络'),
          'exposure_mapping':(_claim('protocol',protocol,value=f['exposure_description'])
                              if needs_exposure else {'value':None,'basis':'UNRESOLVED','evidence':[]}),
      },
      'information_design': {
          'assignment_family':f['assignment_family'],
          'assignment_law':_claim('protocol',protocol,value=protocol),
          'population_information_level':f['a4_level'],
          'population_observable_operator':_claim('information',info,value=f['a4_operator']),
      },
      'assumptions':[{'name':name,'statement':'本数学基准把该条件作为已设定的假设（并非实证核验）',
                      'status':'PROPOSED','basis':'REPORTED_BY_SOURCE',
                      'evidence':[{'source_id':'assumption_contract','quote':assumptions}]}
                     for name in f['admitted_a5']],
      'validity':{},'ambiguities':[], 'clarifying_questions':[],
      'normalization_notes':['TEST ONLY: hypothetical assumptions have no external scientific certification.'],
    }
    raw=DraftProblemSpec.model_validate(draft)
    formulation=audit_draft(case,raw,provider='FROZEN_BENCHMARK_FIXTURE')
    if formulation.review_status!='DRAFT_READY_FOR_HUMAN_REVIEW':
        raise ValueError(f"Invalid frozen test fixture {entry['id']}: "
                         + ','.join(i.code for i in formulation.issues))
    review=HumanReviewV02(input_sha256=fingerprint_business_case(case),
                          draft_sha256=canonical_sha256(raw),
                          reviewed_by='BENCHMARK_FIXTURE_ONLY',
                          decision='CONFIRMED',
                          review_note='Only a synthetic benchmark fixture; NOT approval of a real causal study',
                          admitted_assumptions=f['admitted_a5'])
    routing=route_formulation(case,formulation,human_review=review,
                             core=MockCorePort(MockCoreScenario(status='UNSUPPORTED')))
    if routing.status != 'MOCK_CORE_RESULT' or routing.fallback!='MOCK_ONLY':
        raise RuntimeError('Expected mock-only unsupported fixture, never production routing')
    return case,formulation,review,routing
