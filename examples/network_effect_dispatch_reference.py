"""Explicit synthetic local-effect fixture; no model calls or runtime defaults."""
import json
from pathlib import Path
from cfm_id import business_intake as intake, business_dispatch as dispatch, business_case
from cfm_id_llm.schemas import BusinessCase, SourceDocument, SemanticClaim, TargetDraft, DraftProblemSpec, UnitsVariablesDraft, StructureDraft
from cfm_id_llm.quality import MultiQueryDraftV010, BusinessInquiryV010, QuerySemanticsV010
from cfm_id_llm import network_effect_reading as reading
from examples.business_dispatch_reference import approve


def material(*,population='all',scenario='shops',sample_only=False,missing_remaining=False,post_assignment=False):
    if scenario=='shops':
        nodes=['甲店','乙店','丙店','丁店'];unit='门店';treatment='启用排班助手';outcome='本周顾客平均等待分钟数'
        background='一家连锁企业希望了解排班助手是否减少顾客等待。四家门店会相互调配员工，合作关系在试点前已经固定。'
    else:
        nodes=['北站','西站','东站','南站'];unit='配送站';treatment='启用路线提示工具';outcome='本周每单平均延误分钟数'
        background='配送公司希望了解路线提示工具是否减少延误。四个配送站会相互支援，支援关系在试点前已经固定。'
    members=nodes if population=='all' else nodes[:2] if population=='subset' else nodes[1:2]
    scope=('评价名单在抽签前固定为'+('全部四个'+unit if population=='all' else '、'.join(members))+'，'
        +('只评价这个对象的均值。' if population=='single' else '对名单中的对象取等权平均。'))
    if post_assignment:scope='评价本轮实际抽中启用的对象，名单在抽签后确定，对这些对象取等权平均。'
    remaining=('其余对象的安排尚未决定采用什么规则，暂不指定。' if missing_remaining else
        '两种比较都不固定其他对象的完整名单；在满足各端自身与同伴条件的安排中，按原试点抽签概率平均，不另外改变抽签规则。')
    questions={
        'q1':f'合作对象过半启用时，自己{treatment}与自己未启用相比，{outcome}相差多少？前者减后者。',
        'q2':f'自己不启用时，合作对象过半启用与至多一半启用相比，{outcome}相差多少？前者减后者。'}
    edges=list(zip(nodes,nodes[1:]))
    probabilities=dict(zip(nodes,['2/5','1/2','3/5','2/3']))
    docs=dict(study=background+'完整名单为'+'、'.join(nodes)+'。处理记1为'+treatment+'，记0为未启用；结果是'+outcome+'。',
        network='完整无向合作边为'+'；'.join(a+'与'+b for a,b in edges)+'；除此之外没有合作边。网络在处理前固定。',
        assignment='原试点各对象独立抽签决定启用，已知完整规则为：'+'；'.join(n+'的概率为'+p for n,p in probabilities.items())+'。',
        exposure='严格超过一半合作对象启用记为同伴高状态1；至多一半（包括平票）记为低状态0；没有合作对象也记为0。',
        population=scope,remaining=remaining,
        context='所有比较使用同一周、同一背景和同一结果口径，结果单位均为分钟。',
        science='本合成研究拟采用：完整处理向量与所有对象在所有完整安排下的潜在结果独立；观察结果等于实际完整安排下的潜在结果；相关条件一阶矩存在且有限。',
        information=('目前只有试点样本及样本平均结果，尚未声明可用的总体观测信息。' if sample_only else
            '本理论研究可使用每个对象按自身是否启用与同伴高低分成的四个组的总体条件平均结果；范围为全部四个对象的全部四个组。它们是符号总体信息，不是样本估计；不提供具体数值。'))
    question=background+'\n'+scope+'\n'+'\n'.join(questions.values())+'\n'+remaining
    case=BusinessCase(case_id='synthetic_local_effect_'+scenario+'_'+population,business_question=question,
        sources=[SourceDocument(source_id=k,text=v) for k,v in docs.items()])
    return case,dict(nodes=nodes,edges=edges,probabilities=probabilities,members=members,questions=questions,
        unit=unit,treatment=treatment,outcome=outcome,population=population,sample_only=sample_only,
        missing_remaining=missing_remaining,post_assignment=post_assignment,docs=docs)


def a0_reference(case,data):
    def claim(text,source):return SemanticClaim(value=text,basis='EXPLICIT_TEXT',evidence=[dict(source_id=source,quote=text)])
    d=data['docs'];queries=[]
    for qid,kind in [('q1','DIRECT_EFFECT'),('q2','SPILLOVER_EFFECT')]:
        goal=claim(data['questions'][qid],'business_question')
        queries.append(BusinessInquiryV010(query_id=qid,business_goal=goal,target=TargetDraft(kind=kind,description=goal),
            semantics=QuerySemanticsV010(target_population=claim(d['population'],'population'),
                aggregation=claim(d['population'],'population'),intervention=goal,comparator=goal,
                neighbor_exposure=claim(d['exposure'],'exposure'),standardization_distribution=claim(d['remaining'],'remaining'))))
    shared=DraftProblemSpec(target=queries[0].target,units_variables=UnitsVariablesDraft(
        analysis_unit=claim(data['unit'],'study'),treatment=claim(data['treatment'],'study'),outcome=claim(data['outcome'],'study')),
        structure=StructureDraft(unit_network=claim(d['network'],'network')))
    return MultiQueryDraftV010(shared_draft=shared,primary_query_id='q1',queries=queries).model_dump(mode='json')


def fact_reference(entry,data):
    refs=reading.reference_catalog(entry['bundle'],binding=entry['fact_binding_sha256'])
    def ids(doc):return [k for k,v in refs['aliases'].items() if v['doc_id']==doc]
    def declaration(value,doc):return dict(value=value,source_ids=ids(doc))
    own_first,own_second,second_exposure=(1,0,1) if entry['query_id']=='q1' else (0,0,0)
    return dict(version=reading.VERSION,reference_context=refs['context'],
        study=dict(nodes=data['nodes'],edges=[list(e) for e in data['edges']],graph_kind='SIMPLE_UNDIRECTED',
            edge_list_complete=True,treatment=data['treatment'],outcome=data['outcome'],outcome_kind='CONTINUOUS',
            context=data['docs']['context'],source_ids=ids('study')+ids('network')+ids('context')),
        assignment=dict(kind='INDEPENDENT_BERNOULLI',probabilities=data['probabilities'],fixed_count=None,source_ids=ids('assignment')),
        target=dict(kind='DIRECT_EFFECT' if entry['query_id']=='q1' else 'SPILLOVER_EFFECT',operation='FIRST_MINUS_SECOND',
            first=dict(own=own_first,exposure=1,source_ids=ids('__question__')),
            second=dict(own=own_second,exposure=second_exposure,source_ids=ids('__question__')),
            population=data['members'],aggregation='SINGLE' if data['population']=='single' else 'EQUAL_MEAN',
            population_fixed_before_assignment=declaration(not data['post_assignment'],'population'),
            remaining_assignment='UNKNOWN' if data['missing_remaining'] else 'ORIGINAL_DESIGN_CONDITIONAL',
            remaining_source_ids=[] if data['missing_remaining'] else ids('remaining'),
            shared_outcome_and_context=declaration(True,'context'),source_ids=ids('__question__')+ids('population')),
        exposure=dict(kind='STRICT_MAJORITY_TIES_LOW',source_ids=ids('exposure')),
        design_facts=dict(assignment_rule_available=declaration(True,'assignment'),network_fixed_before_treatment=declaration(True,'network')),
        scientific_statements={k:dict(status='PROPOSED',source_ids=ids('science')) for k in
            ('assignment_outcome_independence','consistency','finite_conditional_means')},
        information=[dict(operator='FINITE_SAMPLE' if data['sample_only'] else 'NODE_ARM_MEANS',
            availability='FINITE_SAMPLE' if data['sample_only'] else 'SYMBOLIC_POPULATION_OPERATOR',
            outcome_nodes=data['nodes'],arm_cells=[] if data['sample_only'] else
                [dict(node=n,own=a,exposure=e) for n in data['nodes'] for a in (0,1) for e in (0,1)],source_ids=ids('information'))],
        additional_restrictions=[],unresolved=[])


def setup(qid='q1', **kwargs):
    case,data=material(**kwargs)
    s=intake.start(case,reading_format='canonical',fact_format='short_refs')
    s=intake.receive_candidate(s,a0_reference(case,data),request_sha256=s.request_sha256)
    q=approve(dispatch.prepare_reader(s,qid)['query_worksheet'])
    e=dispatch.prepare_reader(s,qid,query_review=q)
    if e['state']!='READY_TO_READ':raise ValueError(('Fixture A0 not ready',e))
    o=dict(query_review=q,candidate=fact_reference(e,data),request_sha256=e['request_sha256'])
    return s,e,o,dispatch.inspect_methods(s,qid,**o)


def approval_records(plan):
    return dict(plan_review=approve(plan['plan_worksheet']),native_reviews={r['method']:dict(
        reading_review=approve(r['reading_worksheet']),science_review=approve(r['science_worksheet'])) for r in plan['methods']},
        research_protocol_selected=True)


def run(output):
    folder=Path(output);folder.mkdir(parents=True,exist_ok=False);rows=[]
    for scenario in ('shops','delivery'):
        case,data=material(scenario=scenario)
        s=intake.start(case,reading_format='canonical',fact_format='short_refs')
        s=intake.receive_candidate(s,a0_reference(case,data),request_sha256=s.request_sha256)
        submissions={}
        for qid in ('q1','q2'):
            q=approve(dispatch.prepare_reader(s,qid)['query_worksheet']);e=dispatch.prepare_reader(s,qid,query_review=q)
            o=dict(query_review=q,candidate=fact_reference(e,data),request_sha256=e['request_sha256'])
            p=dispatch.inspect_methods(s,qid,**o);a=approval_records(p)
            submissions[qid]=dict(o,**{k:v for k,v in a.items() if k!='research_protocol_selected'})
        result=business_case.execute_case(s,submissions,case_review=approve(business_case.prepare_case(s)['case_worksheet']),
            research_protocol_selected=True)
        intake.write_json(folder/(scenario+'_business.json'),case.model_dump(mode='json'))
        intake.write_json(folder/(scenario+'_result.json'),result)
        rows.append(dict(case=scenario,state=result['state'],queries=[dict(query_id=r['query_id'],state=r['result']['state'],
            replay=r['result']['independent_replay']) for r in result['results']]))
    summary=dict(rows=rows,model_api_calls=0,synthetic_reference_only=True,llm_accuracy_measured=False)
    intake.write_json(folder/'SUMMARY.json',summary);return summary


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--allow-synthetic-reviews',action='store_true')
    a=p.parse_args()
    if not a.allow_synthetic_reviews:p.error('Explicit synthetic review selection required')
    print(json.dumps(run(a.output),ensure_ascii=False))
