"""Rebuild reviewed bounded inputs and replay the saved PARTIAL certificate."""
import argparse
import json
from pathlib import Path
from cfm_id import project,network_policy_dispatch as network,network_bounded_dispatch as bounded,bounded_policy_verify
from cfm_id.business_dispatch import checked_review
from evaluation.task6.scripts.n01_fullchain import session,a0_review,entry_from_review


def main():
    p=argparse.ArgumentParser();p.add_argument('--workdir',required=True);a=p.parse_args();d=Path(a.workdir)
    def read(name):return json.loads((d/(name+'.json')).read_text(encoding='utf8'))
    prior=read('plan');approvals=read('scientific_reviews_EDIT');saved=read('execution_result')
    fresh=project.inspect_methods(session(d),'q1',query_review=a0_review(d),candidate=read('fact_candidate'),
        request_sha256=entry_from_review(d)['request_sha256'],source_review=read('source_review_EDIT'))
    if fresh.get('state')!='REVIEW_REQUIRED' or fresh.get('plan_sha256')!=prior.get('plan_sha256'):
        raise ValueError('Reviewed source or plan changed')
    plan_review=checked_review(approvals['plan_review'],fresh['plan_worksheet'])
    if plan_review.authority!='SYNTHETIC_TEST' or approvals['research_protocol_selected'] is not True:
        raise ValueError('Explicit synthetic trial authority required')
    rows=fresh['methods']
    if len(rows)!=1 or rows[0]['method']!=bounded.METHOD:raise ValueError('Expected bounded model')
    records=network.native_reviews_from_json(fresh,approvals['native_reviews'])[bounded.METHOD]
    for name,sheet in (('reading_review','reading_worksheet'),('science_review','science_worksheet')):
        records[name]=checked_review(records[name],rows[0][sheet])
        if records[name].authority!=plan_review.authority:raise ValueError('Review authority mismatch')
    inquiry,information=bounded.compile_reviewed(fresh,rows[0],records,plan_review.authority)
    cert=saved['certificate']
    if saved.get('state')!='PARTIAL' or bounded_policy_verify.replay(cert,inquiry=inquiry,information=information) is not True:
        raise ValueError('Saved partial certificate failed replay')
    if [cert['lower'],cert['upper']]!=['3/7','4/7'] or cert['sharp'] is not True:
        raise ValueError('Certificate differs from separately derived sharp reference')
    out={'state':'PARTIAL','replay_result':True,'interval':[cert['lower'],cert['upper']],
       'certificate_sha256':cert['certificate_sha256'],'authority':'SYNTHETIC_TEST','reviewer':'Codex AI',
       'scope':'Fictional research model; proposed assumption explicitly selected for this test'}
    with (d/'certificate_replay_check.json').open('x',encoding='utf8') as f:json.dump(out,f,ensure_ascii=False,indent=2)
    print(json.dumps(out,ensure_ascii=False))


if __name__=='__main__':main()
