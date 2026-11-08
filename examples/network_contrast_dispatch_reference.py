"""Explicit synthetic comparisons through the user-neutral business intake.

These hand-authored readings/reviews are test fixtures, not LLM measurements or
approvals of a real business. All original source texts remain in the case.
"""
from copy import deepcopy
from itertools import combinations
from pathlib import Path
from cfm_id import business_intake as intake, business_dispatch as dispatch, business_case
from cfm_id_llm.schemas import BusinessCase, SourceDocument
from cfm_id_llm.evidence_refs import build_catalog
from cfm_id_llm.network_policy_reading import reference_catalog
from cfm_id_llm.network_fact_protocols import network_fact_protocol
from cfm_id_llm.network_contrast_reading import VERSION
from .business_dispatch_reference import approve


def material(kind='point', *, bounds=('0','1'), reverse=False):
    nodes = ['甲店','乙店','丙店','丁店']
    if kind == 'point':
        first, second = [1,1,0,0], [0,0,1,1]
        edges = list(zip(nodes, nodes[1:])); population = list(nodes); quota = 2; cells = []
        first_text, second_text = '甲乙两店启用、丙丁两店不启用', '丙丁两店启用、甲乙两店不启用'
    elif kind == 'partial':
        first, second = [1]*4, [0]*4
        edges = list(combinations(nodes, 2)); population = list(nodes); quota = 2
        cells = [dict(node=n, own=a, exposure=e, value='1/2') for n in nodes for a,e in ((1,0),(0,1))]
        first_text, second_text = '四家店全部启用', '四家店全部不启用'
    elif kind == 'cancellation':
        first, second = [1,1,1,0], [1,1,0,0]
        edges = [(nodes[0],nodes[1])]; population = [nodes[0],nodes[2]]; quota = 1
        cells = [dict(node=nodes[2],own=a,exposure=0,value=v) for a,v in ((0,'1/5'),(1,'3/5'))]
        first_text, second_text = '甲乙丙三店启用、丁店不启用', '甲乙两店启用、丙丁两店不启用'
    else:
        raise ValueError('UNKNOWN_SYNTHETIC_COMPARISON')
    if reverse:
        first,second = second,first; first_text,second_text = second_text,first_text
    question = (f'我们四家门店考虑换一种AI排班工具的推广安排。如果从“{second_text}”改成“{first_text}”，'
                f'在同一个考核周，{ "、".join(population)}的平均准时开门率会增加多少？'
                '两种方案都评价刚才列出的同一批门店，每家等权。')
    docs = dict(
        study='研究对象只有甲店、乙店、丙店、丁店，门店是研究单位。启用AI排班工具记1，不启用记0。结果为同一考核周是否每天准时开门，是记1、否记0。两端政策比较同一结果定义、单位、期间和研究背景。',
        network='门店之间存在合作和信息交流，结果可能受相邻店安排影响。网络为处理前固定的简单无向网络，完整合作边为'+ '、'.join(a+'—'+b for a,b in edges)+'，没有其他边；没有列出合作边的店是孤立点。',
        assignment=f'原试点在四家门店中每轮恰好抽取{quota}家启用AI，所有大小为{quota}的完整名单等概率。',
        science='本研究明确采用：上述完整分配律已知；完整处理向量与全部门店在所有完整二元安排下的潜在结果独立；一致性，即观察结果等于实际完整安排下的潜在结果；处理前固定网络；所需条件一阶矩有限。',
        exposure='同伴暴露按合作邻居定义：严格超过一半的邻居启用为1，否则为0；平票为0，孤立店为0。',
        sufficiency=('本研究明确不采用潜在结果均值只依赖自身处理和同伴暴露的限制。' if kind=='point' else
            '本研究明确采用：对全部四家门店及所有完整二元安排，每店潜在结果均值仅依赖自身处理和上述同伴暴露。'),
        information=('已知每家门店的结果与完整处理向量的联合总体分布，作为符号总体信息，不是有限样本。' if kind=='point' else
            '以下是精确总体条件均值，不是样本估计：\n'+'\n'.join(
                f"{v['node']}，自身处理={v['own']}、同伴暴露={v['exposure']}时，所述准时开门指标的总体条件均值为{v['value']}。" for v in cells)))
    if kind!='point':
        docs['bounds'] = ('以下界限限制潜在结果的条件均值，适用于全部四家门店、所有完整二元安排和同一研究背景；'
            '结果定义是该考核周是否每天准时开门，单位为0/1指标，期间为同一考核周。\n' +
            '\n'.join(f'{n}的均值下界为{bounds[0]}，上界为{bounds[1]}。' for n in nodes))
        docs['complete_model'] = ('本研究声明：可用总体信息恰为以上列出的精确总体均值，没有完整联合分布或其他总体信息；'
            '除明确列出的基础科学条件、全安排均值暴露充分性及逐店界限外，没有跨对象或跨安排的额外耦合限制。')
    case = BusinessCase(case_id='cooperative_stores_comparison', business_question=question,
        sources=[SourceDocument(source_id=k,text=v) for k,v in docs.items()])
    return case, dict(kind=kind,nodes=nodes,edges=[list(e) for e in edges],first=first,second=second,
                      population=population,quota=quota,cells=cells,bounds=bounds)


def a0_reference(case):
    catalog = build_catalog(case)
    def claim(text, source='business_question'):
        return dict(state='STATED',value=text,refs=[r['ref'] for r in catalog if r['source_id']==source])
    question = claim(case.business_question)
    return dict(common=dict(analysis_unit=claim('门店','study'),treatment=claim('启用AI排班工具','study'),
        outcome=claim('同一考核周是否每天准时开门','study'),unit_network=claim(case.source_map()['network'],'network')),
        queries=[dict(kind='TOTAL_EFFECT',goal=question,semantics=dict(target_population=deepcopy(question),
            intervention=deepcopy(question),comparator=deepcopy(question),policy_assignment=deepcopy(question),
            aggregation=deepcopy(question),time_horizon=claim('同一考核周','study')))])


def fact_reference(entry, data):
    refs = reference_catalog(entry['bundle'],binding=entry['fact_binding_sha256'])
    def ids(doc):return [k for k,r in refs['aliases'].items() if r['doc_id']==doc]
    def declaration(value,doc):return dict(value=value,source_ids=ids(doc))
    nodes=data['nodes']; finite=data['kind']!='point'
    raw = dict(version=VERSION,reference_context=refs['context'],
        study=dict(nodes=nodes,edges=data['edges'],graph_kind='SIMPLE_UNDIRECTED',edge_list_complete=True,
            treatment='启用AI排班工具',outcome='考核周是否每天准时开门',outcome_kind='BINARY',context='同一考核周的四家门店',source_ids=ids('study')+ids('network')),
        assignment=dict(kind='UNIFORM_FIXED_QUOTA',fixed_count=data['quota'],probabilities=None,source_ids=ids('assignment')),
        target=dict(kind='FIXED_POLICY_MEAN_DIFFERENCE',operation='FIRST_MINUS_SECOND',source_ids=ids('__question__'),
            shared_outcome_and_context=declaration(True,'study'),
            **{s:dict(assignment=dict(zip(nodes,data[s])),population=data['population'],aggregation='EQUAL_MEAN',source_ids=ids('__question__')) for s in ('first','second')}),
        assumptions={k:declaration(True,'science') for k in ('known_assignment_law','full_vector_randomization','consistency','fixed_pretreatment_network','finite_conditional_first_moments')},
        exposure=dict(kind='STRICT_MAJORITY_TIES_LOW',source_ids=ids('exposure')),
        mean_sufficiency=dict(value=finite,scope='ALL_BINARY_ASSIGNMENTS' if finite else 'UNKNOWN',covered_nodes=nodes if finite else [],source_ids=ids('sufficiency')),
        information=[dict(operator='NODE_SIGNATURE_MEANS' if finite else 'NODE_FULL_LAW',
            availability='EXACT_POPULATION_VALUE' if finite else 'SYMBOLIC_POPULATION_OPERATOR',
            outcome_nodes=list(dict.fromkeys(v['node'] for v in data['cells'])) if finite else nodes,
            signature_cells=data['cells'],assignment_cells=[],source_ids=ids('information'))],
        additional_restrictions=[],unresolved=[],bounded_model=None)
    if finite:
        raw['bounded_model']=dict(bounds_kind='CONDITIONAL_MEAN',bounds_scope='ALL_BINARY_ASSIGNMENTS_CONDITIONAL_ON_STUDY_CONTEXT',
            bounds=[dict(node=n,lower=data['bounds'][0],upper=data['bounds'][1],source_ids=ids('bounds')) for n in nodes],
            outcome_definition='考核周是否每天准时开门',outcome_unit='0/1指标',outcome_period='同一考核周',source_ids=ids('bounds'),
            listed_means_are_complete_information=declaration(True,'complete_model'),
            no_additional_coupling_constraints=declaration(True,'complete_model'))
    protocol=network_fact_protocol(entry.get('network_fact_contract'))
    if protocol.wire_version!='network-policy-reading-1':
        old=raw.pop('assumptions')
        raw['design_facts']=dict(assignment_rule_available=old['known_assignment_law'],network_fixed_before_treatment=old['fixed_pretreatment_network'])
        def statement(value,doc):
            status='ADOPTED' if value else 'NOT_ADOPTED'
            if protocol.wire_version=='network-source-statements-1':
                return dict(status=status,quotations=[dict(source_id=s,quote=refs['aliases'][s]['text']) for s in ids(doc)])
            return dict(status=status,source_ids=ids(doc))
        raw['scientific_statements']={k:statement(True,'science') for k in ('assignment_outcome_independence','consistency','finite_conditional_means')}
        raw['mean_sufficiency']=dict(statement(finite,'sufficiency'),scope='ALL_BINARY_ASSIGNMENTS' if finite else 'UNKNOWN',covered_nodes=nodes if finite else [])
    if entry.get('network_fact_contract') in ('network-policy-definition-refs-1', 'network-policy-record-definitions-1', 'network-policy-scopes-1', 'network-policy-scopes-2'):
        # Hand-authored fixture only: never apply this to a returned LLM answer.
        raw['assignment']['definition_refs']=['study'] if raw['assignment']['probabilities'] else []
        for side in ('first','second'):raw['target'][side]['definition_refs']=['study']
        for info in raw['information']:info['definition_refs']=['study']
        if entry.get('network_fact_contract') in ('network-policy-record-definitions-1','network-policy-scopes-1','network-policy-scopes-2'):
            raw['mean_sufficiency']['definition_refs']=['study'] if raw['mean_sufficiency']['covered_nodes'] else []
    if entry.get('network_fact_contract') in ('network-policy-scopes-1','network-policy-scopes-2'):
        for info in raw['information']:
            info.update(scope_status='DECLARED' if info['outcome_nodes'] else 'UNSPECIFIED',
                        scope_source_ids=list(info['source_ids']) if info['outcome_nodes'] else [])
    return raw


def setup(kind='point', *, profile=None, **kwargs):
    case,data=material(kind,**kwargs)
    s=intake.start(case,network_fact_contract=profile)
    s=intake.receive_candidate(s,a0_reference(case),request_sha256=s.request_sha256)
    q=approve(dispatch.prepare_reader(s,'q1')['query_worksheet'])
    entry=dispatch.prepare_reader(s,'q1',query_review=q)
    options=dict(query_review=q,candidate=fact_reference(entry,data),request_sha256=entry['request_sha256'])
    return s,entry,options


def approval_records(plan):
    return dict(plan_review=approve(plan['plan_worksheet']),native_reviews={r['method']:dict(
        reading_review=approve(r['reading_worksheet']),science_review=approve(r['science_worksheet'])) for r in plan['methods']},
        research_protocol_selected=True)


def run(output):
    out=Path(output);out.mkdir(parents=True,exist_ok=False);rows=[]
    for kind in ('point','partial','cancellation'):
        s,e,o=setup(kind,bounds=('1/4','3/4') if kind=='partial' else ('0','1'))
        p=dispatch.inspect_methods(s,'q1',**o)
        a=approval_records(p)
        row=dict(o,**{k:v for k,v in a.items() if k!='research_protocol_selected'})
        result=business_case.execute_case(s,{'q1':row},case_review=approve(business_case.prepare_case(s)['case_worksheet']),research_protocol_selected=True)
        intake.write_json(out/(kind+'_case.json'),s.case.model_dump(mode='json'))
        intake.write_json(out/(kind+'_result.json'),result)
        actual=result['results'][0]['result']
        rows.append(dict(case=kind,state=actual['state'],claim=actual['mathematical_claim'],independent_replay=actual['independent_replay']))
    intake.write_json(out/'SUMMARY.json',dict(api_calls=0,synthetic_reviews_only=True,rows=rows))
    return rows


if __name__=='__main__':
    import argparse,json
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--allow-synthetic-reviews',action='store_true')
    args=p.parse_args()
    if not args.allow_synthetic_reviews:p.error('Explicit synthetic fixture review selection required')
    print(json.dumps(run(args.output),ensure_ascii=False))
