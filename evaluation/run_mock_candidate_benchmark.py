"""Offline contract benchmark: compares fixed fixtures, NOT mathematical LLM accuracy."""
from __future__ import annotations
import argparse
import copy
import json
from pathlib import Path

from cfm_id_llm.candidate_reasoner import CandidateReasonerV03
from cfm_id_llm.formulator import ProblemFormulator
from cfm_id_llm.mock_core import MockCorePort, MockCoreScenario
from cfm_id_llm.orchestration_schemas import HumanReviewV02
from cfm_id_llm.orchestrator import route_formulation
from cfm_id_llm.providers import MockProvider
from cfm_id_llm.schemas import BusinessCase

ROOT = Path(__file__).resolve().parents[1]


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def set_deep(obj, dotted, value):
    keys=dotted.split('.')
    x=obj
    for k in keys[:-1]: x=x[k]
    x[keys[-1]]=value


def benchmark():
    case=BusinessCase.model_validate(load(ROOT/'examples/weighted_exposure_demo.json'))
    formulation=ProblemFormulator(MockProvider(load(ROOT/'examples/weighted_exposure_demo_mock_response.json'))).formulate(case)
    review=HumanReviewV02.model_validate(load(ROOT/'examples/TEST_ONLY_review_for_weighted_exposure.json'))
    core=MockCorePort(MockCoreScenario(status='UNSUPPORTED'))
    route=route_formulation(case,formulation,human_review=review,core=core)
    base=load(ROOT/'examples/weighted_exposure_demo_mock_candidate.json')
    tests=load(ROOT/'evaluation/candidate_cases.json')
    outputs=[]
    for test in tests:
        fixture=copy.deepcopy(base)
        for key,value in test['change'].items(): set_deep(fixture,key,value)
        report=CandidateReasonerV03(MockProvider(fixture)).run(
            case=case, formulation=formulation, human_review=review,
            routing=route, allow_mock_preview=True)
        outputs.append({'case_id':test['id'],'expected':test['expected'],
                        'actual':report.status,'passed':report.status==test['expected'],
                        'verification_level':report.verification_level,
                        'handoff_allowed':report.estimation_handoff_allowed})
    return {'benchmark':'MOCK_CANDIDATE_CONTRACT_V03',
            'real_llm_accuracy':'NOT_MEASURED',
            'real_math_theorems_executed':0,
            'cases':len(outputs), 'passed':sum(x['passed'] for x in outputs),
            'results':outputs}


def main(argv=None):
    p=argparse.ArgumentParser(description='Offline mocked LLM candidate-contract test')
    p.add_argument('--output',help='write JSON to file')
    args=p.parse_args(argv)
    result=benchmark()
    raw=json.dumps(result,indent=2,ensure_ascii=False)+'\n'
    if args.output:Path(args.output).write_text(raw,encoding='utf-8')
    else:print(raw)
    return 0 if result['passed']==result['cases'] else 1

if __name__=='__main__':raise SystemExit(main())
