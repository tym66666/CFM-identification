"""Exercise the project conflict-stop entry on one source-reviewed pilot case.

The intervention does not claim the model found the conflict, does not alter
the candidate or approve a target, and never runs math.
"""
import argparse
import hashlib
import json
from pathlib import Path
from cfm_id import business_field_review,business_intake,project

ROOT=Path(__file__).resolve().parents[1]
def build(folder):
    folder=Path(folder)
    def read(name):return json.loads((folder/(name+'.json')).read_text(encoding='utf8'))
    snapshot=business_intake._checked(read('intake_snapshot'))
    expected=json.loads((ROOT/'pilot_cases/materials/conflict.json').read_text(encoding='utf8'))
    if snapshot.case.model_dump(mode='json')!=type(snapshot.case).model_validate(expected).model_dump(mode='json'):
        raise ValueError('Fictional case changed')
    initial=read('result')
    if initial.get('internal_binding_is_unmodified_request') is not True or not initial.get('response_received'):
        raise ValueError('Bound real model response required')
    audit=read('known_issue_review')['review']
    field='queries.q1.semantics.first_arrangement'
    if audit['decisions'][field]['value_state']!='REJECTED':raise ValueError('Actual target field was not rejected')
    submitted=business_field_review.submit(snapshot,'q1',audit,authority=audit['authority'])
    if submitted.get('state')!='CHECK_BLOCKED' or submitted.get('reason_code')!='DISPATCH_REVIEW_REJECTED':
        raise ValueError('Current source-bound project rejection required')
    candidate=read('model_candidate')
    original_question=snapshot.case.business_question
    email=next(s.text for s in snapshot.case.sources if s.source_id=='contradictory_business_email')
    if '都使用AI' not in original_question or '均不使用AI' not in email or '尚未协调' not in email:
        raise ValueError('The two reviewed policy assertions no longer match the source')
    conflict_review={'version':'intake-conflict-review-1','query_id':'q1','field':field,'authority':audit['authority'],
      'reviewer':audit['reviewer'],'reason':'业务问题要求全部使用，负责人补充邮件要求全部不使用且尚未协调，两个目标政策相互冲突。',
      'sources':[{'source_id':'s0001','quote':original_question}, {'source_id':'s0025','quote':email}]}
    result=project.review_conflict(snapshot,'q1',field_review=audit,conflict_review=conflict_review)
    return dict(result,stage='REVIEWER_INTERVENTION_NOT_MODEL_FIRST_PASS',
      project_a0_review_state=submitted['state'],project_a0_review_reason=submitted['reason_code'],
      question_origin='project source-reviewed conflict stop; not a model-generated question',
      source_documents=['business_question','contradictory_business_email'],
      model_candidate_sha256=hashlib.sha256(json.dumps(candidate,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode('utf8')).hexdigest(),
      prewritten_business_reply_included_in_model_request=False,
      reviewer=audit['reviewer'],model_candidate_modified=False)


def main():
    p=argparse.ArgumentParser();p.add_argument('--folder',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    result=build(a.folder)
    with Path(a.output).open('x',encoding='utf8') as f:json.dump(result,f,ensure_ascii=False,indent=2)
    print(json.dumps(result,ensure_ascii=False))


if __name__=='__main__':main()
