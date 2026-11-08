"""Hypothetical network protocol and source-bound mocks; no real approvals."""
from copy import deepcopy
from pathlib import Path
from cfm_id import business_intake as intake,business_dispatch as dispatch,business_case
from cfm_id_llm.schemas import (BusinessCase,SourceDocument,SemanticClaim,TargetDraft,
    UnitsVariablesDraft,StructureDraft,DraftProblemSpec)
from cfm_id_llm.quality import BusinessInquiryV010,MultiQueryDraftV010,QuerySemanticsV010
from cfm_id_llm.network_policy_reading import reference_catalog,VERSION
from .business_dispatch_reference import approve


def case(*,design='D2',n=5,quota=4,sufficiency=True):
    nodes=['中心']+['网点'+str(i) for i in range(1,n)]
    question='如果这'+str(n)+'个网点都使用AI助手，评价全部这些网点、每个网点权重相同，平均按时完成率能否由现有总体信息唯一确定？'
    docs={
        'study':'本周有'+str(n)+'个服务网点，名单为'+'、'.join(nodes)+'。每个网点使用AI记1、不使用记0；结果是本周任务是否按时完成，完成记1、未完成记0。',
        'network':'合作网络为固定的处理前简单无向网络，完整边为'+'、'.join('中心—'+x for x in nodes[1:])+'，没有其他边。',
        'assignment':('原试点每个网点各自独立以1/2概率使用AI，所有网点的抽签相互独立。' if design=='D1'
            else f'原试点每轮均匀随机抽取恰好{quota}个网点使用AI；所有同人数名单等概率。'),
        'science':'研究明确采用：已知上述完整分配律；完整处理向量与所有网点在所有完整安排下的潜在结果独立；一致性，即观察结果等于实际安排下的潜在结果；处理前固定网络；所需条件一阶矩有限。',
        'information':'已知每个网点的结果与完整处理向量的联合总体分布，作为符号总体信息；不是有限样本估计值。',
        'exposure':'同伴暴露定义为合作邻居中严格超过一半使用AI时为1，否则为0；平票为0，孤立节点为0。',
        'sufficiency':('研究另行拟采用：对全部网点、所有完整二元安排，每个网点的潜在结果均值只依赖自身处理与上述同伴暴露。'
            if sufficiency else '研究不采用潜在结果均值只由自身处理和同伴暴露决定的限制。'),
    }
    business=BusinessCase(case_id=f'network_{design}_{n}_{quota}_{sufficiency}',business_question=question,
        sources=[SourceDocument(source_id=k,text=v) for k,v in docs.items()])
    return business,nodes,docs


def intake_mock(business):
    docs={s.source_id:s.text for s in business.sources}
    def claim(text,source):
        return SemanticClaim(value=text,basis='EXPLICIT_TEXT',evidence=[dict(source_id=source,quote=text)])
    goal=claim(business.business_question,'business_question')
    target=TargetDraft(kind='FIXED_POLICY_VALUE',description=goal)
    shared=DraftProblemSpec(target=target,units_variables=UnitsVariablesDraft(
        analysis_unit=claim(docs['study'],'study'),treatment=claim('使用AI','study'),outcome=claim('本周任务是否按时完成','study')),
        structure=StructureDraft(unit_network=claim(docs['network'],'network')))
    query=BusinessInquiryV010(query_id='q1',business_goal=goal,target=target,
        semantics=QuerySemanticsV010(target_population=goal,intervention=goal,policy_assignment=goal,aggregation=goal))
    s=intake.start(business,reading_format='canonical',fact_format='short_refs')
    return intake.receive_candidate(s,MultiQueryDraftV010(shared_draft=shared,primary_query_id='q1',queries=[query]).model_dump(mode='json'),
                                    request_sha256=s.request_sha256)


def candidate(entry, *,design='D2',n=5,quota=4,sufficiency=True):
    refs=reference_catalog(entry['bundle'],binding=entry['fact_binding_sha256'])
    def ids(doc):return [k for k,r in refs['aliases'].items() if r['doc_id']==doc]
    nodes=['中心']+['网点'+str(i) for i in range(1,n)]
    return dict(version=VERSION,reference_context=refs['context'],
        study=dict(nodes=nodes,edges=[['中心',x] for x in nodes[1:]],graph_kind='SIMPLE_UNDIRECTED',edge_list_complete=True,
            treatment='使用AI',outcome='本周任务是否按时完成',outcome_kind='BINARY',context='本周服务网点',source_ids=ids('study')+ids('network')),
        assignment=dict(kind='INDEPENDENT_BERNOULLI' if design=='D1' else 'UNIFORM_FIXED_QUOTA',
            probabilities={x:'1/2' for x in nodes} if design=='D1' else None,
            fixed_count=None if design=='D1' else quota,source_ids=ids('assignment')),
        target=dict(kind='FIXED_POLICY_MEAN',assignment={x:1 for x in nodes},population=list(nodes),
            aggregation='EQUAL_MEAN',source_ids=ids('__question__')),
        assumptions={k:dict(value=True,source_ids=ids('science')) for k in ('known_assignment_law',
            'full_vector_randomization','consistency','fixed_pretreatment_network','finite_conditional_first_moments')},
        exposure=dict(kind='STRICT_MAJORITY_TIES_LOW',source_ids=ids('exposure')),
        mean_sufficiency=dict(value=sufficiency,scope='ALL_BINARY_ASSIGNMENTS' if sufficiency else 'UNKNOWN',
            covered_nodes=list(nodes) if sufficiency else [],source_ids=ids('sufficiency')),
        information=[dict(operator='NODE_FULL_LAW',availability='SYMBOLIC_POPULATION_OPERATOR',outcome_nodes=list(nodes),
            assignment_cells=[],signature_cells=[],source_ids=ids('information'))],additional_restrictions=[],unresolved=[])


def approval_records(plan):
    return dict(plan_review=approve(plan['plan_worksheet']),native_reviews={row['method']:dict(
        reading_review=approve(row['reading_worksheet']),science_review=approve(row['science_worksheet'])) for row in plan['methods']},
        research_protocol_selected=True)


def setup(**kwargs):
    b,_,_=case(**kwargs);s=intake_mock(b)
    review=approve(dispatch.prepare_reader(s,'q1')['query_worksheet'])
    entry=dispatch.prepare_reader(s,'q1',query_review=review)
    raw=candidate(entry,**kwargs)
    options=dict(query_review=review,candidate=raw,request_sha256=entry['request_sha256'])
    return s,entry,options,dispatch.inspect_methods(s,'q1',**options)


def run(output):
    path=Path(output);path.mkdir(parents=True,exist_ok=False);rows=[]
    for label,kwargs in [('r1b',dict(design='D1',sufficiency=False)),('r2',{}),
                         ('both',dict(design='D1')),('support_gap',dict(n=7,quota=3))]:
        s,entry,options,plan=setup(**kwargs)
        result=dispatch.execute(s,'q1',**options,**approval_records(plan))
        intake.save(s,path/(label+'_intake.json'));intake.write_json(path/(label+'_plan.json'),plan)
        intake.write_json(path/(label+'_result.json'),result)
        rows.append(dict(case=label,state=result['state'],methods=[a['method'] for a in result['answers']],
            independent_replay=result['independent_replay'],reason=result['reason_code']))
    summary=dict(api_calls=0,synthetic_only=True,rows=rows)
    intake.write_json(path/'SUMMARY.json',summary);return summary


if __name__=='__main__':
    import argparse,json
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--allow-synthetic-reviews',action='store_true')
    a=p.parse_args()
    if not a.allow_synthetic_reviews:p.error('Explicit synthetic review selection required')
    print(json.dumps(run(a.output),ensure_ascii=False))
