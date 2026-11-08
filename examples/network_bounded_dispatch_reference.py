"""Source-grounded synthetic mean-box cases; no online outputs or auto approvals."""
from pathlib import Path
from copy import deepcopy
from .network_dispatch_reference import case as point_case,intake_mock,candidate,approval_records
from .business_dispatch_reference import approve
from cfm_id import business_dispatch as dispatch,business_intake as intake,business_case
from cfm_id_llm.network_policy_reading import reference_catalog


def case(*,n=7,quota=3,center_bounds=('0','1'),bounds_kind='CONDITIONAL_MEAN',missing_scope=False,extra=False,topology='star'):
    original,nodes,_=point_case(n=n,quota=quota)
    data=original.model_dump(mode='json')
    cells=[dict(node=nodes[0],own=0,exposure=0,value='1/2')]+[
        dict(node=node,own=1,exposure=1,value='1/2') for node in nodes[1:]]
    # The five-node, quota-four comparison also has a supported central target.
    if n==5 and quota==4:
        cells[0]['exposure']=1
        cells.append(dict(node=nodes[0],own=1,exposure=1,value='1/2'))
    if topology=='chain':
        if (n,quota)!=(4,2):raise ValueError('Chain fixture uses four nodes and quota two')
        cells=[dict(node=node,own=1 if i in (0,3) else 0,exposure=1,value='1/2') for i,node in enumerate(nodes)]
        for source in data['sources']:
            if source['source_id']=='network':
                source['text']='合作网络为固定的处理前简单无向网络，完整边为'+'、'.join(
                    a+'—'+b for a,b in zip(nodes,nodes[1:]))+'，没有其他边。'
    elif topology!='star':raise ValueError('Unknown fixture topology')
    for source in data['sources']:
        if source['source_id']=='information':
            source['text']='以下是本题声明可用的精确总体条件均值，不是有限样本估计：\n'+'\n'.join(
                f"{v['node']}，自身处理={v['own']}、同伴暴露={v['exposure']}时，本周按时完成指标的总体条件均值={v['value']}。" for v in cells)
    kind='潜在结果均值' if bounds_kind=='CONDITIONAL_MEAN' else '潜在结果本身几乎必然'
    docs=dict(bounds=f'界限与上文研究背景相同，对每个对象、每一种完整二元安排均成立，限制{kind}。'
        +'结果定义为本周任务按时完成记1、未完成记0；单位为0/1指标，期间为本周。\n'
        +f'{nodes[0]}的下界为{center_bounds[0]}，上界为{center_bounds[1]}。\n'
        +'\n'.join(node+'的下界为0，上界为1。' for node in nodes[1:]),
        complete_model=('研究暂未确认是否还有其他总体信息或耦合条件。' if missing_scope else
            '本研究明确约定：总体信息只有以上逐项列出的精确总体均值，不包含完整联合分布、其他总体信息或额外聚合均值；'
            '除前述随机化、一致性、固定网络、有限矩、全安排均值暴露充分性以及上述界限外，没有跨对象、跨情境的额外耦合限制。'))
    if extra:
        # This is a different, coupled model, not the independent mean box.
        # Do not contradict the extra condition with a no-coupling assertion.
        docs['complete_model']=('研究暂未确认是否还有其他总体信息或耦合条件。' if missing_scope else
            '本研究明确约定：总体信息只有以上逐项列出的精确总体均值，不包含完整联合分布、其他总体信息或额外聚合均值；'
            '模型限制包括前述随机化、一致性、固定网络、有限矩、全安排均值暴露充分性、上述界限，以及另列的自身处理单调性；没有其他限制。')
        docs['extra']='对每个网点和所有完整二元安排，固定其他网点的处理安排，将该网点自身处理从0改为1时，该网点潜在结果均值不得下降。'
    # Match the source model already used by the standard business fixture.
    source_type=type(original.sources[0])
    from cfm_id_llm.schemas import BusinessCase
    data['sources'] += [source_type(source_id=k,text=v).model_dump(mode='json') for k,v in docs.items()]
    return BusinessCase.model_validate(data),cells


def reference(entry, *,n=7,quota=3,center_bounds=('0','1'),bounds_kind='CONDITIONAL_MEAN',missing_scope=False,extra=False,topology='star'):
    _,cells=case(n=n,quota=quota,center_bounds=center_bounds,bounds_kind=bounds_kind,missing_scope=missing_scope,extra=extra,topology=topology)
    raw=candidate(entry,n=n,quota=quota)
    if topology=='chain':raw['study']['edges']=[list(e) for e in zip(raw['study']['nodes'],raw['study']['nodes'][1:])]
    refs=reference_catalog(entry['bundle'],binding=entry['fact_binding_sha256'])
    ids=lambda doc:[k for k,r in refs['aliases'].items() if r['doc_id']==doc]
    raw['information']=[dict(operator='NODE_SIGNATURE_MEANS',availability='EXACT_POPULATION_VALUE',
        outcome_nodes=list(raw['study']['nodes']),assignment_cells=[],signature_cells=cells,source_ids=ids('information'))]
    raw['bounded_model']=dict(source_ids=ids('bounds'),bounds_kind=bounds_kind,
        bounds_scope='ALL_BINARY_ASSIGNMENTS_CONDITIONAL_ON_STUDY_CONTEXT',
        outcome_definition='本周任务按时完成记1、未完成记0',outcome_unit='0/1指标',outcome_period='本周',
        bounds=[dict(node=node,lower=center_bounds[0] if i==0 else '0',upper=center_bounds[1] if i==0 else '1',
            source_ids=ids('bounds')) for i,node in enumerate(raw['study']['nodes'])],
        listed_means_are_complete_information=dict(value=None if missing_scope else True,source_ids=ids('complete_model')),
        no_additional_coupling_constraints=dict(value=False if extra else None if missing_scope else True,
            source_ids=ids('extra') if extra else ids('complete_model')))
    if extra:raw['additional_restrictions']=[dict(text='额外单调性限制',source_ids=ids('extra'))]
    return raw


def setup(**kwargs):
    business,_=case(**kwargs);s=intake_mock(business)
    review=approve(dispatch.prepare_reader(s,'q1')['query_worksheet'])
    entry=dispatch.prepare_reader(s,'q1',query_review=review)
    raw=reference(entry,**kwargs)
    options=dict(query_review=review,candidate=raw,request_sha256=entry['request_sha256'])
    return s,entry,options,dispatch.inspect_methods(s,'q1',**options)


def run(output):
    out=Path(output);out.mkdir(parents=True,exist_ok=False);rows=[]
    for label,kwargs in [('point',dict(center_bounds=('1/2','1/2'))),
        ('narrow',dict(center_bounds=('1/4','3/4'))),('wide',{}),
        ('missing_model_scope',dict(missing_scope=True)),('extra_constraint',dict(extra=True)),
        ('binary_outcome_incompatible',dict(center_bounds=('1/4','3/4'),bounds_kind='ALMOST_SURE_OUTCOME'))]:
        s,e,options,plan=setup(**kwargs)
        reviews=approval_records(plan) if plan['state']=='REVIEW_REQUIRED' else {}
        r=dispatch.execute(s,'q1',**options,**reviews)
        intake.write_json(out/(label+'_result.json'),r)
        rows.append(dict(case=label,state=r['state'],reason=r['reason_code'],
            interval=(r['mathematical_claim'] or {}).get('interval'),independent_replay=r['independent_replay']))
    report=dict(api_calls=0,synthetic_reviews_only=True,rows=rows)
    intake.write_json(out/'SUMMARY.json',report);return report


if __name__=='__main__':
    import argparse,json
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--allow-synthetic-reviews',action='store_true')
    a=p.parse_args()
    if not a.allow_synthetic_reviews:p.error('Explicit synthetic review selection required')
    print(json.dumps(run(a.output),ensure_ascii=False))
