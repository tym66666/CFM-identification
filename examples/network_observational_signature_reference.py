"""Synthetic R3 business cases with hand-authored readings and explicit reviews.

No API calls or LLM accuracy claims. Run with --allow-synthetic-reviews.
"""
from pathlib import Path
from cfm_id import business_intake as intake, business_dispatch as dispatch, business_case
from cfm_id import method_diagnostics
from cfm_id_llm.schemas import BusinessCase, SourceDocument
from cfm_id_llm import network_observational_signature_reading as reader
from .network_observational_policy_reference import material as base_material, a0_reference, fact_reference as base_facts
from .network_dispatch_reference import approval_records
from .business_dispatch_reference import approve


def material(*, grouping='STRICT_MAJORITY_TIES_LOW', sufficiency=True, full_support=False,
             zero_signature=False, subset=False, exchangeability=True, sample_only=False):
    base,data=base_material(exchangeability=exchangeability,sample_only=sample_only)
    nodes=['青禾店','柳岸店','南园店','白桥店','云台店']
    population=nodes[1:] if subset else nodes[:]
    edges=[[nodes[0],n] for n in nodes[1:]]
    cores={n:([nodes[1],nodes[2]] if n==nodes[0] else [nodes[0]]) for n in nodes}
    descriptions={
        'STRICT_MAJORITY_TIES_LOW':'合作门店中使用工具的门店严格超过一半记为1，否则记为0。没有合作门店时记0。',
        'THREE_LEVEL_TREATED_NEIGHBOR_FRACTION':'合作门店使用比例小于三分之一记0，至少三分之一但小于三分之二记1，至少三分之二记2。孤立门店无此定义。',
        'PRETREATMENT_CORE_COLLABORATOR_MAJORITY':'仅考虑事先选定的核心合作门店，其中使用者严格超过一半记1，否则记0。核心名单：'+str(cores),
        'EXACT_TREATED_NEIGHBOR_COUNT':'同伴状态就是合作门店中使用工具的门店数量。',
        'ANY_TREATED_NEIGHBOR':'只要有至少一家合作门店使用工具就记1，否则记0。'}
    masses=[([0 if j==i else 1 for j in range(5)],'1/5') for i in range(5)]
    if full_support:masses=[([1]*5,'1')]
    if zero_signature:masses=[([0]*5,'1')]
    docs=base.source_map()
    # The original synthetic scientific declarations apply to the new explicit study.
    docs={k:v for k,v in docs.items() if k not in ('business_question','__question__')}
    docs['study']='完整研究名单为'+ '、'.join(nodes)+'。研究单位是门店；使用排班辅助工具记1，不使用记0；结果是下周是否按时完成全部客户预约，是记1、否记0。研究背景为下周门店预约安排。'
    data['conditioning']='采用工具前已登记的同一商圈和预约需求背景'
    docs['conditioning']='本研究固定在'+data['conditioning']+'，全部条件在采用工具前确定；本题不跨背景层平均。'
    docs['network']='门店会通过互相调派员工影响彼此。处理前固定的全部无向合作边为'+ '、'.join('与'.join(e) for e in edges)+'，没有其他边。'
    docs['table']='对象顺序为'+ '、'.join(nodes)+'。\n'+'\n'.join('完整使用向量'+str(z)+'，'+('样本频数比例' if sample_only else '条件总体概率')+'为'+p+'。' for z,p in masses)
    docs['exposure']=descriptions[grouping]
    docs['sufficiency']=('本合成研究拟采用以下额外条件：在上述固定处理前背景下，对'+ '、'.join(population)+
        '，每一家在所有完整二元使用安排下的潜在结果条件均值，只依赖该店是否使用工具和上述同伴状态。'
        if sufficiency is True else '是否采用上述固定背景下、所有完整安排上的条件均值充分性尚未决定。'
        if sufficiency is None else '本研究明确不采用上述条件均值充分性。')
    question='五家门店会互相调派员工，过去是否使用排班辅助工具由各店负责人自行决定。我们想知道，在上述相同的需求背景下，如果下周五店都使用工具，'+('除青禾店以外四店' if subset else '全部五店')+'按时完成全部客户预约的平均比例能否唯一确定？评价名单为'+ '、'.join(population)+'，各店等权。'
    case=BusinessCase(case_id='observational_signature_shops',business_question=question,
        sources=[SourceDocument(source_id=k,text=v) for k,v in docs.items()])
    data.update(nodes=nodes,edges=edges,population=population,assignment=[1]*5,unit='门店',
        outcome='下周是否按时完成全部客户预约',context='下周门店预约安排',masses=masses,
        grouping=grouping,cores=cores if grouping=='PRETREATMENT_CORE_COLLABORATOR_MAJORITY' else None,
        sufficiency=sufficiency)
    return case,data


def fact_reference(entry,data):
    raw=base_facts(entry,data)
    from cfm_id_llm import network_observational_definitions as defined
    active=defined if entry.get('observational_fact_profile')==defined.PROFILE else reader
    refs=active.reference_catalog(entry['bundle'],binding=entry['fact_binding_sha256'])
    def ids(doc):return [k for k,r in refs['aliases'].items() if r['doc_id']==doc]
    raw.update(version=active.VERSION,reference_context=refs['context'],
        exposure=dict(kind=data['grouping'],core_collaborators=data['cores'],source_ids=ids('exposure')),
        mean_sufficiency=dict(value=data['sufficiency'],scope='ALL_BINARY_ASSIGNMENTS' if data['sufficiency'] is True else 'UNKNOWN',
            covered_nodes=data['population'] if data['sufficiency'] is True else [],source_ids=ids('sufficiency')))
    if active is defined:
        raw['target']['definition_refs']=['study']
        raw['mean_sufficiency']['definition_refs']=['study'] if raw['mean_sufficiency']['covered_nodes'] else []
        table=ids('table')
        for info in raw['information']:
            info['definition_refs']=['study'] if info['outcome_nodes'] else []
            info['coordinates']=dict(node_order=data['nodes'],treated_value=1,untreated_value=0,
                source_ids=list(dict.fromkeys([*ids('study'),table[0]])))
            for i,row in enumerate(info['assignment_masses']):
                row['definition_refs']=['table_coordinates'];row['source_ids']=[table[i+1]]
    return raw


def setup(*, profile=reader.PROFILE, **kwargs):
    case,data=material(**kwargs)
    s=intake.start_configured(case,dict(observational_fact_profile=profile))
    s=intake.receive_candidate(s,a0_reference(case,data),request_sha256=s.request_sha256)
    review=approve(dispatch.prepare_reader(s,'q1')['query_worksheet'])
    entry=dispatch.prepare_reader(s,'q1',query_review=review)
    return s,entry,dict(query_review=review,candidate=fact_reference(entry,data),request_sha256=entry['request_sha256'])


def run(output):
    out=Path(output);out.mkdir(parents=True,exist_ok=False);rows=[]
    for name,kwargs,expected in (
        ('signature_point',{},'POINT'),('full_point_without_sufficiency',dict(full_support=True,sufficiency=False),'POINT'),
        ('undecided_sufficiency',dict(sufficiency=None),'NEEDS_INPUT'),('refused_sufficiency',dict(sufficiency=False),'ADAPTER_NOT_CONNECTED'),
        ('missing_exchangeability',dict(exchangeability=None),'NEEDS_INPUT'),('sample_only',dict(sample_only=True),'NEEDS_INPUT'),
        ('zero_signature_support',dict(zero_signature=True),'UNSUPPORTED')):
        s,e,o=setup(**kwargs);plan=dispatch.inspect_methods(s,'q1',**o)
        reviews=approval_records(plan) if plan.get('methods') else dict(research_protocol_selected=True)
        result=dispatch.execute(s,'q1',**o,**reviews)
        assert result['state']==expected,(name,result)
        diagnostic=method_diagnostics.describe(plan,result=result if plan.get('plan_sha256') else None,
            **{k:v for k,v in reviews.items() if k!='research_protocol_selected'})
        whole=None
        if expected=='POINT':
            whole=business_case.execute_case(s,{'q1':dict(o,**{k:v for k,v in reviews.items() if k!='research_protocol_selected'})},
                case_review=approve(business_case.prepare_case(s)['case_worksheet']),research_protocol_selected=True)
            assert whole['results'][0]['result']['independent_replay']
        intake.save(s,out/(name+'_intake.json'))
        intake.write_json(out/(name+'_result.json'),dict(plan=plan,result=result,diagnostic=diagnostic,whole_case=whole))
        rows.append(dict(case=name,state=result['state'],method=result.get('primary_method'),reason_code=result.get('reason_code'),
                         independent_replay=result['independent_replay'],backend_called=result['backend_called']))
    intake.write_json(out/'SUMMARY.json',dict(api_calls=0,hand_authored_readings=True,synthetic_reviews_only=True,rows=rows))
    return rows


if __name__=='__main__':
    import argparse,json
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True);parser.add_argument('--allow-synthetic-reviews',action='store_true')
    args=parser.parse_args()
    if not args.allow_synthetic_reviews:parser.error('Explicit synthetic fixture review selection required')
    print(json.dumps(run(args.output),ensure_ascii=False))
