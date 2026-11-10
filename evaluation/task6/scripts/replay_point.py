"""Rebuild a reviewed R1b input and replay its actual saved certificate."""
import argparse
import json
from pathlib import Path
from cfm_id import project, network_policy_dispatch as network
from cfm_id.business_dispatch import checked_review
from evaluation.task6.scripts.n01_fullchain import session, a0_review, entry_from_review
from pfn_pipeline import identification_policy_r1b as r1b


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workdir',required=True);a=p.parse_args()
    d=Path(a.workdir)
    def read(name):return json.loads((d/(name+'.json')).read_text(encoding='utf8'))
    previous=read('plan'); approvals=read('scientific_reviews_EDIT'); saved=read('execution_result')
    fresh=project.inspect_methods(session(d),'q1',query_review=a0_review(d),candidate=read('fact_candidate'),
        request_sha256=entry_from_review(d)['request_sha256'],source_review=read('source_review_EDIT'))
    if fresh.get('plan_sha256')!=previous.get('plan_sha256') or fresh.get('state')!='REVIEW_REQUIRED':
        raise ValueError('Fact/source review or plan no longer matches')
    plan_review=checked_review(approvals['plan_review'],fresh['plan_worksheet'])
    if plan_review.authority!='SYNTHETIC_TEST' or approvals['research_protocol_selected'] is not True:
        raise ValueError('Expected explicit synthetic trial authority')
    rows=fresh['methods']
    if len(rows)!=1 or rows[0]['method']!=network.R1B:raise ValueError('Expected R1b point plan')
    records=network.native_reviews_from_json(fresh,approvals['native_reviews'])[network.R1B]
    for name,sheet in (('reading_review','reading_worksheet'),('science_review','science_worksheet')):
        records[name]=checked_review(records[name],rows[0][sheet])
        if records[name].authority!=plan_review.authority:raise ValueError('Review authority mismatch')
    st,target,sources,assumptions,signature,sufficiency=network._compile(fresh,rows[0],records,plan_review.authority)
    rebuilt=r1b.identify_verified_fixed_policy(st,target,sources,assumptions=assumptions)
    replay=r1b.replay_verified_fixed_policy(rebuilt)
    if replay is not True or rebuilt.summary()!=saved['certificate'] or saved.get('state')!='POINT':
        raise ValueError('Saved certificate differs from independently replayed reviewed input')
    output={'state':'POINT','saved_certificate_matches_rebuilt':True,'replay_result':True,
        'authority':'SYNTHETIC_TEST','reviewer':'Codex AI','scope':'Fictional trial; no human or production approval',
        'certificate_sha256':saved['certificate']['certificate_sha256'],'assignment_probability':rebuilt.assignment_probability}
    target_path=d/'certificate_replay_check.json'
    with target_path.open('x',encoding='utf8') as f:json.dump(output,f,ensure_ascii=False,indent=2)
    print(json.dumps(output,ensure_ascii=False))


if __name__=='__main__':main()
