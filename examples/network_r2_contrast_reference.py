"""Complete synthetic businesses and reviewed fixtures; no model accuracy claim.

Run only with --allow-synthetic-reviews. Fixtures never enter runtime imports.
"""
from copy import deepcopy
from pathlib import Path
from cfm_id import business_intake as intake,business_dispatch as dispatch,business_case
from cfm_id_llm.schemas import BusinessCase,SourceDocument
from cfm_id_llm.evidence_refs import build_catalog
from cfm_id_llm.network_policy_reading import reference_catalog
from .network_contrast_dispatch_reference import fact_reference as base_facts,approval_records
from .business_dispatch_reference import approve


def material(scene='clinics', *, information='signature', sufficiency=True, reverse=False, quota=None):
    if scene=='clinics':
        nodes=['青桥门诊','柳岸门诊','松林门诊','河湾门诊','南园门诊','东亭门诊']
        edges=[[nodes[i],nodes[(i+1)%6]] for i in range(6)];population=nodes[:]
        unit='门诊';treatment='使用排班辅助工具';outcome='本周是否每天准时开诊';outcome_kind='BINARY'
        intro='六家社区门诊准备调整排班辅助工具的推广安排。相邻门诊会临时调派医护人员，使用工具的影响可能传到合作门诊。'
        question='如果把这六家门诊全部启用工具，与全部不启用相比，本周每天准时开诊的门诊比例会增加多少？评价全部六家门诊，每家等权。'
        quota=3 if quota is None else quota
    elif scene=='warehouses':
        nodes=['青禾仓','白桥仓','云台仓','竹园仓','河东仓']
        edges=[nodes[i:i+2] for i in range(4)];population=[nodes[0],nodes[-1]]
        unit='仓库';treatment='使用配载辅助工具';outcome='本周每单平均完成配载所需的分钟数';outcome_kind='CONTINUOUS'
        intro='五个仓库通过固定合作线路共享车辆并转运货物，合作仓库的工具使用也可能影响本仓的作业时间。'
        question='如果五个仓库全部启用配载工具，相比全部不启用，青禾仓和河东仓本周每单平均配载时间会变化多少分钟？按全部启用减全部不启用计算，只评价这两仓，两仓等权。'
        quota=2 if quota is None else quota
    else:raise ValueError('UNKNOWN_SYNTHETIC_SCENE')
    first,second=[1]*len(nodes),[0]*len(nodes)
    if reverse:
        first,second=second,first
        question=('如果五个仓库全部不启用配载工具，相比全部启用，青禾仓和河东仓本周每单平均配载时间会变化多少分钟？按全部不启用减全部启用计算，只评价这两仓，两仓等权。') if scene=='warehouses' else (
            '如果六家门诊全部不启用工具，与全部启用相比，本周每天准时开诊的门诊比例会变化多少？按全部不启用减全部启用计算，评价全部六家门诊，每家等权。')
    cells=[dict(node=n,own=a,exposure=a) for n in population for a in (0,1)]
    docs=dict(
        study=intro+'本研究单位为'+unit+'，完整名单为'+'、'.join(nodes)+'。'+treatment+'记为1，不使用记为0。结果是'+outcome+'。两份安排比较同一周、同一定义与单位的结果和业务背景。'+('准时开诊记1，否则记0。' if outcome_kind=='BINARY' else ''),
        network='合作关系在抽签前固定，本周不变。完整无向合作边是'+'、'.join('与'.join(e) for e in edges)+'；无其他边，无自环或重复边。',
        assignment=f'原试点每轮在完整名单中恰好抽取{quota}个对象使用工具，所有同人数完整名单等概率。',
        science='本合成研究拟采用：已知完整分配律；完整工具安排与全部对象在所有完整安排下的潜在结果独立；实际结果等于实际完整安排下的潜在结果；处理前网络固定；所需一阶矩存在且有限。',
        exposure='合作邻居中严格超过一半使用工具记同伴状态1，否则记0；平票和没有合作邻居都记0。',
        sufficiency=('本合成研究拟采用：全部评价对象在所有完整二元安排下的潜在结果均值，仅由本人是否使用工具以及上述同伴状态决定。' if sufficiency is True else
            '是否采用潜在结果均值只由本人使用情况和同伴状态决定的条件，尚未决定。' if sufficiency is None else
            '本研究明确不采用潜在结果均值只由本人使用情况和同伴状态决定的限制。'),
        information=('已声明可用以下符号总体信息：对'+'、'.join(population)+'中的每个对象，分别知道本人使用且同伴状态1、本人不使用且同伴状态0时的总体条件结果均值；这里不给均值数值，不是样本估计。' if information=='signature' else
            '已声明可使用所有评价对象的结果与完整使用安排的联合总体分布；属于符号总体信息，不是有限记录。'),
    )
    case=BusinessCase(case_id='r2_contrast_'+scene,business_question=question,sources=[SourceDocument(source_id=k,text=v) for k,v in docs.items()])
    return case,dict(kind='point',nodes=nodes,edges=edges,population=population,quota=quota,first=first,second=second,cells=cells,
        information=information,sufficiency=sufficiency,unit=unit,treatment=treatment,outcome=outcome,outcome_kind=outcome_kind)


def a0_reference(case,data):
    catalog=build_catalog(case)
    def claim(value,source='business_question'):
        return dict(state='STATED',value=value,refs=[r['ref'] for r in catalog if r['source_id']==source])
    goal=claim(case.business_question)
    return dict(common=dict(analysis_unit=claim(data['unit'],'study'),treatment=claim(data['treatment'],'study'),
        outcome=claim(data['outcome'],'study'),unit_network=claim(case.source_map()['network'],'network')),
        queries=[dict(kind='TOTAL_EFFECT',goal=goal,semantics=dict(target_population=deepcopy(goal),
            intervention=deepcopy(goal),comparator=deepcopy(goal),policy_assignment=deepcopy(goal),aggregation=deepcopy(goal),time_horizon=claim('本周','study')))])


def fact_reference(entry,data):
    raw=base_facts(entry,data);refs=reference_catalog(entry['bundle'],binding=entry['fact_binding_sha256'])
    ids=lambda doc:[k for k,r in refs['aliases'].items() if r['doc_id']==doc]
    raw['study'].update(treatment=data['treatment'],outcome=data['outcome'],outcome_kind=data['outcome_kind'],context='本周同一业务背景')
    sf=raw['mean_sufficiency'];adopt=data['sufficiency']
    if 'value' in sf:sf['value']=adopt
    else:sf['status']='PROPOSED' if adopt is True else 'UNDECIDED' if adopt is None else 'NOT_ADOPTED'
    sf.update(scope='ALL_BINARY_ASSIGNMENTS' if adopt is True else 'UNKNOWN',covered_nodes=data['population'] if adopt is True else [])
    if entry.get('network_fact_contract') in ('network-policy-record-definitions-1','network-policy-scopes-1','network-policy-scopes-2'):
        # Hand-authored reference follows the changed scope; never applied to LLM output.
        sf['definition_refs']=['study'] if sf['covered_nodes'] else []
    info=raw['information'][0];info.update(outcome_nodes=data['population'],signature_cells=[])
    if data['information']=='signature':info.update(operator='NODE_SIGNATURE_MEANS',signature_cells=data['cells'])
    raw['target']['shared_outcome_and_context']['source_ids']=ids('study')
    return raw


def setup(scene='clinics', *, profile=None, **kwargs):
    case,data=material(scene,**kwargs)
    s=intake.start(case,network_fact_contract=profile)
    s=intake.receive_candidate(s,a0_reference(case,data),request_sha256=s.request_sha256)
    q=approve(dispatch.prepare_reader(s,'q1')['query_worksheet']);entry=dispatch.prepare_reader(s,'q1',query_review=q)
    return s,entry,dict(query_review=q,candidate=fact_reference(entry,data),request_sha256=entry['request_sha256'])


def run(output):
    out=Path(output);out.mkdir(parents=True,exist_ok=False);rows=[]
    for name,scene,options,expected in (
        ('clinics','clinics',{},'POINT'),('warehouses','warehouses',{},'POINT'),
        ('both_methods','clinics',dict(information='full'),'POINT'),
        ('missing_sufficiency','clinics',dict(sufficiency=None),'NEEDS_INPUT'),
        ('refused_sufficiency','clinics',dict(sufficiency=False,information='full'),'UNSUPPORTED'),
        ('one_endpoint_zero_support','clinics',dict(quota=1),'UNSUPPORTED')):
        s,e,o=setup(scene,**options);plan=dispatch.inspect_methods(s,'q1',**o)
        approvals=approval_records(plan) if plan.get('methods') else dict(research_protocol_selected=True)
        result=dispatch.execute(s,'q1',**o,**approvals);assert result['state']==expected,result
        whole=None
        if expected=='POINT':
            whole=business_case.execute_case(s,{'q1':dict(o,**{k:v for k,v in approvals.items() if k!='research_protocol_selected'})},
                case_review=approve(business_case.prepare_case(s)['case_worksheet']),research_protocol_selected=True)
            assert whole['results'][0]['result']['independent_replay']
        intake.write_json(out/(name+'_case.json'),s.case.model_dump(mode='json'))
        intake.write_json(out/(name+'_result.json'),dict(plan=plan,result=result,whole_case=whole))
        rows.append(dict(case=name,state=result['state'],independent_replay=result['independent_replay'],backend_called=result['backend_called']))
    intake.write_json(out/'SUMMARY.json',dict(api_calls=0,hand_authored_readings=True,synthetic_reviews_only=True,rows=rows))
    return rows


if __name__=='__main__':
    import argparse,json
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--allow-synthetic-reviews',action='store_true');a=p.parse_args()
    if not a.allow_synthetic_reviews:p.error('Explicit synthetic fixture review selection required')
    print(json.dumps(run(a.output),ensure_ascii=False))
