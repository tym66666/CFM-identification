"""v0.11 deterministic Candidate Reasoner software probes + UN-SCORED expert review.

Not a real LLM or theorem benchmark. References are synthetic fixtures. The
8 tiny-network Fraction oracles test small independent math facts, but do not
certify any free-form proposed CandidateDraftV03 text.
"""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

from cfm_id_llm.candidate_queries import (
    BusinessQueryReviewV011, CandidateReasonerV011, CoreCoverageV011,
    MockCoveragePortV011,
)
from cfm_id_llm.providers import MockProvider
from cfm_id_llm.quality import MultiQueryQualityReportV010
from cfm_id_llm.schemas import BusinessCase
from evaluation.math_oracles import run_oracles

FROZEN = Path(__file__).resolve().parent / 'candidate_queries'


def fixture(name: str) -> dict | list:
    return json.loads((FROZEN / name).read_text(encoding='utf-8'))


def run_probe(change_coverage=None, change_candidate=None, *, review_query_ids=None):
    case=BusinessCase.model_validate(fixture('business_case.json'))
    quality=MultiQueryQualityReportV010.model_validate(fixture('a0_quality_report.json'))
    review=fixture('human_business_review_MOCK.json')
    if review_query_ids is not None:
        review['confirmed_query_ids']=review_query_ids
        # The Core mock record is now stale unless explicitly rebound; this is
        # intentional: an altered business review is not eligible automatically.
    review=BusinessQueryReviewV011.model_validate(review)
    core=fixture('mock_core_coverage.json')
    if change_coverage is not None: change_coverage(core)
    candidate=fixture('mock_candidate_q2.json')
    if change_candidate is not None: change_candidate(candidate)
    # Use ORIGINAL query IDs for mock lookups to expose any altered identifiers.
    port=MockCoveragePortV011({'q1':CoreCoverageV011.model_validate(core[0]),
                               'q2':CoreCoverageV011.model_validate(core[1])})
    agent=MockProvider(candidate)
    response=CandidateReasonerV011(agent,port).run(case=case,quality=quality,
                business_review=review,allow_mock_preview=True)
    return response,agent.calls


def _core(status, reason=None, fallback='BLOCKED'):
    def edit(items):
        items[1]['status']=status
        items[1]['fallback']=fallback
        if reason is not None: items[1]['reason_code']=reason
    return edit


def _change(key,val):
    return lambda cand:cand.update({key:val})


def _change_proposal(key,val):
    return lambda cand:cand['proposal'].update({key:val})


def _undetermined(c):
    p=c['proposal'];p.update(claimed_identification='UNDETERMINED',scope='AS_REVIEWED',
                 candidate_expression=None,additional_requirements=[])


def _notpoint(c):
    p=c['proposal'];p.update(claimed_identification='NOT_POINT',candidate_expression=None,
              nonidentification_witness={
              'world_a':'World A has the same factual observed records but different missing potentials',
              'world_b':'World B has identical observed distribution but different missing potentials',
              'why_observables_match':'All observed assignments have identical response probabilities',
              'why_targets_differ':'An unobserved assignment outcome differs and changes the target'})


def run_offline_probes():
    probes=[
        ('candidate_conditional',None,None,'UNVERIFIED_CANDIDATE'),
        ('already_point',_core('POINT'),None,'BLOCKED'),
        ('core_needs_input',_core('NEEDS_INPUT'),None,'BLOCKED'),
        ('missing_adapter',_core('NO_ADAPTER'),None,'BLOCKED'),
        ('core_incompatible',_core('INCOMPATIBLE'),None,'BLOCKED'),
        ('failed_replay',_core('CORE_VERIFICATION_FAILED'),None,'BLOCKED'),
        ('software_unsupported_not_coverage',_core('UNSUPPORTED','A5_PERMISSION_OPEN','ELIGIBLE_NOT_EXECUTED'),None,'BLOCKED'),
        ('unsupported_but_fallback_denied',_core('UNSUPPORTED','NO_REGISTERED_THEOREM'),None,'BLOCKED'),
        ('model_changes_target',None,_change('target_sha256','1'*64),'REJECTED_UNSAFE_OUTPUT'),
        ('model_changes_semantics',None,_change('semantics_sha256','2'*64),'REJECTED_UNSAFE_OUTPUT'),
        ('model_changes_science',None,_change('science_scope_sha256','3'*64),'REJECTED_UNSAFE_OUTPUT'),
        ('model_wrong_query',None,_change('query_id','q1'),'REJECTED_UNSAFE_OUTPUT'),
        ('model_uses_unlicensed_A5',None,_change_proposal('admitted_assumptions_used',['mean_signature_sufficiency']),'REJECTED_UNSAFE_OUTPUT'),
        ('model_claims_unapproved_A4',None,_change_proposal('a4_used',{'source':'REVIEWED_OPERATOR','level':'FULL_JOINT_LAW','operator':'P(Y,T,W)'}),'REJECTED_UNSAFE_OUTPUT'),
        ('model_forces_certificate',None,_change('mathematical_certificate',{'fake':True}),'REJECTED_UNSAFE_OUTPUT'),
        ('model_forces_estimation',None,_change('estimation_handoff_allowed',True),'REJECTED_UNSAFE_OUTPUT'),
        ('model_missing_formula',None,_change_proposal('candidate_expression',None),'REJECTED_UNSAFE_OUTPUT'),
        ('model_undetermined',None,_undetermined,'UNDETERMINED_UNVERIFIED'),
        ('model_notpoint_sketch_only',None,_notpoint,'UNVERIFIED_CANDIDATE'),
    ]
    rows=[]
    for name,c,m,expected in probes:
        result,calls=run_probe(c,m)
        q1,q2=result.results
        rows.append(dict(probe=name,expected=expected,observed=q2.status,
                         passed=q2.status==expected and q1.status=='BLOCKED',
                         candidate_model_calls=calls, reason_code=q2.reason_code))
    oracles=run_oracles()
    return {
        'benchmark':'CFM-ID-Identification-Candidate-v0.11-software-probes',
        'evaluation_kind':'OFFLINE_MOCK_SOFTWARE_GATE_CHECKS_NOT_MODEL_ACCURACY',
        'model':'NONE_MOCK_ONLY',
        'actual_math_core_called':False,
        'mathematical_candidate_formula_verification':'NOT_PERFORMED',
        'online_api_calls':0,
        'probes_total':len(rows), 'probes_passed':sum(x['passed'] for x in rows),
        'mathematical_oracle_sanity_checks':len(oracles),
        'mathematical_oracle_sanity_passed':sum(x['passed'] for x in oracles.values()),
        'reference_oracles_are_not_candidate_proof':True,
        'probes':rows,
    }


def expert_worksheet(batch_report: dict) -> dict:
    """Never fill in scientific quality labels from the mocked answer."""
    return {
        'kind':'EXPERT_MATHEMATICAL_REVIEW_TEMPLATE_UNSCORED',
        'review_schema':'cfm-id-candidate-expert-review-v0.11',
        'source':'Independent reviewer checks a candidate against EXACT typed A4/A5 and actual Core',
        'mathematical_certification':'NOT_PERFORMED',
        'allowed_values':[True,False,None],
        'entries':[{
            'query_id':r['query_id'],
            'report_fingerprint':r['coverage_sha256'],
            'candidate_status':r['status'],
            'candidate_claim':(r['candidate']['proposal']['claimed_identification'] if r['candidate'] else None),
            'ratings':{
                'preserves_exact_formal_estimand':None,
                'uses_only_scientifically_admitted_a4_a5':None,
                'additional_conditions_are_explicit':None,
                'formula_is_mathematically_valid_under_stated_conditions':None,
                'nonidentification_worlds_are_observationally_equivalent':None,
                'nonidentification_worlds_have_different_targets':None,
                'research_value_of_candidate':None,
                'critical_misleading_claim':None,
            },
            'reviewer':'', 'notes':'',
        } for r in batch_report['results'] if r['candidate'] is not None],
    }


def score_expert_worksheet(template: dict) -> dict:
    if template.get('kind')!='EXPERT_MATHEMATICAL_REVIEW_TEMPLATE_UNSCORED':
        raise ValueError('Unknown expert worksheet')
    keys=('preserves_exact_formal_estimand','uses_only_scientifically_admitted_a4_a5',
          'additional_conditions_are_explicit','formula_is_mathematically_valid_under_stated_conditions',
          'nonidentification_worlds_are_observationally_equivalent',
          'nonidentification_worlds_have_different_targets','research_value_of_candidate',
          'critical_misleading_claim')
    rows=template['entries']
    scores={}
    for name in keys:
        accepted=[]
        for item in rows:
            if name not in item.get('ratings',{}):raise ValueError('Missing rating field')
            val=item['ratings'][name]
            if val is not None and type(val) is not bool:
                raise ValueError('Only human boolean or null ratings accepted')
            if type(val) is bool:accepted.append(val)
        scores[name]={'reviewed':len(accepted),
                      'positive_rate':round(sum(accepted)/len(accepted),4) if accepted else None}
    return {'kind':'EXPERT_REVIEW_SCORES','entries':len(rows),'independent_review_needed':True,
            'not_a_mathematical_certificate':True,'scores':scores}


def main(argv:list[str]|None=None)->int:
    p=argparse.ArgumentParser(description='CFM-ID v0.11 candidate offline gate probes and expert worksheet')
    p.add_argument('--output')
    p.add_argument('--worksheet')
    p.add_argument('--score-expert-worksheet')
    args=p.parse_args(argv)
    if args.score_expert_worksheet:
        results=score_expert_worksheet(json.loads(Path(args.score_expert_worksheet).read_text(encoding='utf-8')))
    else:
        results=run_offline_probes()
        if args.worksheet:
            report,_=run_probe()
            Path(args.worksheet).write_text(json.dumps(expert_worksheet(report.model_dump(mode='json')),
                                                  ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    serialized=json.dumps(results,ensure_ascii=False,indent=2)+'\n'
    if args.output:Path(args.output).write_text(serialized,encoding='utf-8')
    else:print(serialized,end='')
    if 'probes_total' in results and results['probes_total']!=results['probes_passed']:
        return 1
    return 0


if __name__=='__main__':
    raise SystemExit(main())
