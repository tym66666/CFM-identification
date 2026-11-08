"""Synthetic, source-bound mean-order ladder through the common business entry.

Hand-authored readings and independent synthetic reviews, not an LLM accuracy
experiment. The three versions keep target, network, A4 and bounds fixed.
"""
from copy import deepcopy
from . import network_contrast_dispatch_reference as base
from .business_dispatch_reference import approve
from cfm_id import business_intake as intake, business_dispatch as dispatch
from cfm_id_llm.schemas import BusinessCase, SourceDocument
from cfm_id_llm.network_policy_reading import reference_catalog
from cfm_id_llm.network_mean_order_reading import PROFILE


def setup(mode='BOTH', *, negative=None, reverse=False, cancellation=False, supported=False):
    case, data = base.material('partial', reverse=reverse)
    docs = case.source_map()
    docs.pop('business_question')
    data['cells'] = [dict(node=n, own=a, exposure=e, value=v) for n in data['nodes']
                     for a,e,v in ((1,0,'3/5'),(0,1,'2/5'))]
    docs['information'] = '以下为精确总体条件均值，不是样本估计：\n' + '\n'.join(
        f"{v['node']}，自身处理={v['own']}、同伴暴露={v['exposure']}时，所述准时开门指标的总体条件均值为{v['value']}。"
        for v in data['cells'])
    axes = dict(OWN=mode in ('OWN','BOTH'), PEERS=mode in ('PEERS','BOTH'))
    docs['orders'] = ('以下科学声明针对全部四家门店、同一考核周和背景，覆盖所有完整二元安排，'
        '包括原试点未出现的安排；约束的是是否每天准时开门这个0/1数值结果的条件均值，不是每次结果。\n' +
        ('本研究拟采用：其余门店安排不变，只让本店由不用改为使用工具，本店的结果均值不会降低。' if axes['OWN'] else
         '本研究明确不假定：其余门店安排不变，只增加本店使用，会使本店结果均值不降低。') + '\n' +
        ('本研究拟采用：本店及其余门店安排不变，只将任一合作邻居由不用改为使用，本店的结果均值不会降低。' if axes['PEERS'] else
         '本研究明确不假定：本店及其余安排不变，只增加合作邻居使用，会使本店结果均值不降低。'))
    docs['complete_model'] = ('本研究声明：可用总体信息恰为所列的精确总体均值，没有其他总体信息。'
        '除基础科学条件、全部安排的均值暴露充分性、逐店界限以及上述明确采用的均值顺序外，没有其他限制。' +
        ('本次有均值顺序耦合限制。' if any(axes.values()) else '本次明确不作任何均值顺序假设，没有额外耦合限制。'))
    if negative=='missing_peer':
        docs['orders']=docs['orders'].rsplit('\n',1)[0] + '\n对于增加邻居使用的作用，目前尚未决定采用什么科学条件。'
    question=case.business_question
    if supported:
        data.update(first=[1,1,0,0],second=[0,0,1,1],population=['甲店'])
        question='在同一考核周，把“丙丁使用、甲乙不用”改成“甲乙使用、丙丁不用”，甲店的准时开门率会增加多少？只评价甲店，用新方案减原方案。'
    if cancellation:
        data['first']=deepcopy(data['second'])
        question='在同一考核周，比较四家店全部不用工具与同一个全部不用方案，四家等权平均的准时开门率差值是多少？'
    case=BusinessCase(case_id='mean_order_'+mode.lower(), business_question=question,
        sources=[SourceDocument(source_id=k,text=v) for k,v in docs.items()])
    session=intake.start(case, network_fact_contract=PROFILE)
    session=intake.receive_candidate(session,base.a0_reference(case),request_sha256=session.request_sha256)
    review=approve(dispatch.prepare_reader(session,'q1')['query_worksheet'])
    entry=dispatch.prepare_reader(session,'q1',query_review=review)
    raw=base.fact_reference(entry,data)
    refs=reference_catalog(entry['bundle'],binding=entry['fact_binding_sha256'])
    ids=lambda doc:[k for k,v in refs['aliases'].items() if v['doc_id']==doc]
    claims=[dict(nodes=data['nodes'],axis=axis,
        relation='NONDECREASING' if adopted else 'NOT_ASSUMED',
        level='CONDITIONAL_MEAN' if adopted else None,
        scope='ALL_BINARY_ASSIGNMENTS' if adopted else None,
        basis='ASSUMPTION_STATEMENT',source_ids=ids('orders')) for axis,adopted in axes.items()
        if not (negative=='missing_peer' and axis=='PEERS')]
    raw['mean_order_model']=dict(order_reading=dict(version='mean-order-reading-1',claims=claims,
        reported_conflict=False,other_restriction_source_ids=[]),
        no_additional_constraints_beyond_declared_orders=dict(value=True,source_ids=ids('complete_model')))
    raw['bounded_model']['no_additional_coupling_constraints']['value']=not any(axes.values())
    return session,entry,dict(query_review=review,candidate=raw,request_sha256=entry['request_sha256'])


def run(output):
    from pathlib import Path
    out=Path(output);out.mkdir(parents=True,exist_ok=False)
    rows=[]
    for name, options in [('both',dict(mode='BOTH')),('own',dict(mode='OWN')),('none',dict(mode='NONE')),
                          ('missing_peer',dict(negative='missing_peer')),('point',dict(supported=True))]:
        s,e,o=setup(**options)
        plan=dispatch.inspect_methods(s,'q1',**o)
        approvals=base.approval_records(plan) if 'plan_worksheet' in plan else {}
        result=dispatch.execute(s,'q1',**o,**approvals)
        intake.write_json(out/(name+'.json'),dict(material=s.case.model_dump(mode='json'),candidate=o['candidate'],
            plan=plan,result=result))
        rows.append(dict(case=name,state=result['state'],claim=result['mathematical_claim'],
                         reason=result['reason_code'],independent_replay=result['independent_replay']))
    intake.write_json(out/'SUMMARY.json',dict(api_calls=0,synthetic_readings_and_reviews=True,rows=rows))
    return rows


if __name__=='__main__':
    import argparse,json
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',required=True)
    parser.add_argument('--allow-synthetic-reviews',action='store_true')
    args=parser.parse_args()
    if not args.allow_synthetic_reviews:parser.error('Explicit synthetic review selection required')
    print(json.dumps(run(args.output),ensure_ascii=False))
