"""Complete synthetic D1-D6/E1-E5 businesses and explicit offline readings.

These references are never imported by runtime code and are NOT LLM results.
The protocol, targets and answers are constructed before any execution.
"""
from copy import deepcopy
import json
from pathlib import Path
from cfm_id import business_intake as intake, business_dispatch as dispatch
from cfm_id_llm.schemas import BusinessCase, SourceDocument
from cfm_id_llm import network_policy_reading as policy, network_effect_reading as effects
from cfm_id_llm.network_contrast_reading import VERSION as CONTRAST_VERSION
from examples.business_dispatch_reference import approve
from examples.network_effect_dispatch_reference import approval_records


NODES = ['甲店','乙店','丙店','丁店','戊店','己店']
EDGES = [[NODES[i],NODES[j]] for i,j in ((0,2),(2,4),(4,0),(1,3),(3,5),(5,1))]
GROUPS = [NODES[i:i+2] for i in (0,2,4)]
DESIGNS = {
 'D1': dict(kind='INDEPENDENT_BERNOULLI',probabilities=dict(zip(NODES,['1/3','1/2','2/3','1/4','3/4','2/5'])),fixed_count=None),
 'D2': dict(kind='UNIFORM_FIXED_QUOTA',probabilities=None,fixed_count=3),
 'D3': dict(kind='TWO_GROUP_FIXED_QUOTA',probabilities=None,fixed_count=None,groups=[NODES[:2],NODES[2:]],treated_quotas=[1,2]),
 'D4': dict(kind='CLUSTER_BERNOULLI',probabilities=None,fixed_count=None,clusters=GROUPS,cluster_probabilities=['1/3','1/2','2/3']),
 'D5': dict(kind='MULTI_GROUP_FIXED_QUOTA',probabilities=None,fixed_count=None,groups=GROUPS,treated_quotas=[1,1,1]),
 'D6': dict(kind='TWO_STAGE_QUOTA_MIXTURE',probabilities=None,fixed_count=None,groups=GROUPS,
            quota_profiles=[[1,1,1],[0,2,1]],profile_probabilities=['1/3','2/3']),
}
DESIGN_TEXT = {
 'D1':'原试点六家门店分别独立抽签，甲、乙、丙、丁、戊、己店的启用概率依次为三分之一、二分之一、三分之二、四分之一、四分之三、五分之二。',
 'D2':'原试点从六家门店均匀抽取恰好三家启用，所有三店名单等概率。',
 'D3':'原试点分两组：甲店与乙店为第一组，其余四店为第二组。两组分别均匀抽取一店、两店启用，两组抽取独立。',
 'D4':'原试点的固定簇为甲乙、丙丁、戊己。三簇整体启用的概率依次为三分之一、二分之一、三分之二；否则整簇不启用，不同簇独立抽签。',
 'D5':'原试点的固定组为甲乙、丙丁、戊己，每组均匀抽取一店启用，各组抽取独立。',
 'D6':'原试点的处理前固定组为甲乙、丙丁、戊己。先抽取两种名额方案之一：以三分之一概率给三组分配一、一、一的名额，以三分之二概率分配零、二、一的名额。给定方案后，各组独立、均匀抽取规定数量门店启用。',
}
EXPOSURES = {
 'E1':('STRICT_MAJORITY_TIES_LOW',1,'严格超过一半合作店启用记1，其余记0；平票和无合作店也记0。','合作店严格过半启用','合作店至多一半启用'),
 'E2':('THREE_LEVEL_TREATED_NEIGHBOR_FRACTION',2,'启用合作店比例小于三分之一记0，至少三分之一但小于三分之二记1，至少三分之二记2；无合作店时不定义该比例。','至少三分之二合作店启用','不到三分之一合作店启用'),
 'E3':('PRETREATMENT_CORE_COLLABORATOR_MAJORITY',1,'仅按指定核心合作店计算启用比例，严格过半记1，其余记0。核心名单在试点前固定，每店的名单如下：','核心合作店严格过半启用','核心合作店至多一半启用'),
 'E4':('EXACT_TREATED_NEIGHBOR_COUNT',2,'同伴状态直接记录启用合作店的人数，不合并不同人数。','恰好两家合作店启用','没有合作店启用'),
 'E5':('ANY_TREATED_NEIGHBOR',1,'至少一名合作店启用记1，没有合作店启用记0。','至少一家合作店启用','没有合作店启用'),
}


def material(design='D2', exposure='E4', family='effect', *, reverse=False, population=None):
    nodes=list(NODES); population=list(population or nodes)
    cores={n:[next(v if u==n else u for u,v in EDGES if n in (u,v))] for n in nodes}
    kind,high,definition,high_text,low_text=EXPOSURES[exposure]
    first=[1,1,0,0,1,1] if design=='D4' else [1,0,1,0,1,0]
    second=[1-v for v in first]
    if reverse:first,second=second,first
    def policy_text(values):return '、'.join(n for n,v in zip(nodes,values) if v)+'启用，其余门店不启用'
    own=(0,1) if reverse else (1,0)
    if family=='effect':
        question=f'在{high_text}时，本店'+('未启用与启用' if reverse else '启用与未启用')+'相比，平均顾客等待时间相差多少？计算前者减后者。'
        target_kind='DIRECT_EFFECT'
    elif family=='spillover':
        question=f'本店不启用时，{high_text}与{low_text}相比，平均顾客等待时间相差多少？计算前者减后者。'
        target_kind='SPILLOVER_EFFECT'
    elif family=='policy':
        question=f'若规定{policy_text(first)}，评价名单内门店的等权平均顾客等待时间能否唯一确定？'
        target_kind='FIXED_POLICY_VALUE'
    elif family=='contrast':
        question=f'若从“{policy_text(second)}”改成“{policy_text(first)}”，同一评价名单内门店的等权平均顾客等待时间增加多少？计算后一方案减前一方案。'
        target_kind='TOTAL_EFFECT'
    else:raise ValueError('UNKNOWN_EXAMPLE_FAMILY')
    docs=dict(
      study='连锁企业试点AI排班助手，研究单位为门店。研究对象仅为'+ '、'.join(nodes)+'。启用记1，未启用记0。结果为考核周顾客平均等待分钟数。',
      network='门店之间会交流排班经验，完整无向合作边为'+'；'.join(u+'与'+v for u,v in EDGES)+'。除此之外无其他边，网络在处理前固定。',
      assignment=DESIGN_TEXT[design], exposure=definition+('；'.join(n+'的核心店为'+','.join(v) for n,v in cores.items()) if exposure=='E3' else ''),
      population='评价名单在抽签前固定为'+'、'.join(population)+'，对这些门店取等权平均。',
      context='所有问题固定在同一考核周、同一经营背景，使用相同结果定义、分钟单位和评价口径。',
      remaining='局部比较不固定其余门店名单，而在满足本店和同伴条件的安排中，按原试点的条件分配概率平均。',
      science='本合成研究拟采用：完整处理分配与所有门店所有完整安排下的潜在结果独立；观察结果等于实际完整安排的潜在结果；所需条件一阶矩存在且有限。',
      information='每家门店的结果与完整处理向量的总体联合分布均作为符号总体信息提供，不是有限样本估计值。',
      sufficiency='政策问题另行拟采用：全部门店在所有完整二元安排下的潜在结果均值只依赖本店处理和上述同伴状态。')
    if design=='D6':docs['first_stage']='拟采用：最终完整处理名单相同时，第一阶段抽到的名额方案本身不再直接影响任何门店的结果。'
    case=BusinessCase(case_id=f'synthetic_{design}_{exposure}_{family}',business_question=question,
        sources=[SourceDocument(source_id=k,text=v) for k,v in docs.items()])
    return case,dict(nodes=nodes,edges=deepcopy(EDGES),population=population,cores=cores,kind=kind,high=high,
        first=first,second=second,own=own,design=design,exposure=exposure,family=family,target_kind=target_kind,docs=docs)


def a0_reference(case,data):
    from cfm_id_llm.evidence_refs import build_catalog
    refs=build_catalog(case)
    def claim(text,doc):return dict(state='STATED',value=text,refs=[r['ref'] for r in refs if r['source_id']==doc])
    docs=data['docs'];goal=claim(case.business_question,'business_question')
    semantics=dict(target_population=claim(docs['population'],'population'),aggregation=claim(docs['population'],'population'),
        intervention=goal,comparator='NOT_APPLICABLE' if data['family']=='policy' else goal,
        time_horizon=claim(docs['context'],'context'))
    if data['family'] in ('effect','spillover'):
        semantics.update(neighbor_exposure=goal,standardization_distribution=claim(docs['remaining'],'remaining'),policy_assignment='NOT_APPLICABLE')
    else:semantics['policy_assignment']=goal
    families=dict(D1='INDEPENDENT_BERNOULLI',D2='COMPLETE_RANDOMIZATION',D3='STRATIFIED_FIXED_QUOTAS',
        D4='CLUSTER_RANDOMIZATION',D5='STRATIFIED_FIXED_QUOTAS',D6='OTHER')
    common=dict(analysis_unit=claim('门店','study'),treatment=claim('启用AI排班助手','study'),
        outcome=claim('考核周顾客平均等待分钟数','study'),assignment_family=families[data['design']],
        assignment_law=claim(docs['assignment'],'assignment'),unit_network=claim(docs['network'],'network'),
        exposure_mapping=claim(docs['exposure'],'exposure'),network_pretreatment_status=claim(docs['network'],'network'),
        available_information=claim(docs['information'],'information'),covariates=[])
    return dict(common=common,queries=[dict(kind=data['target_kind'],goal=goal,semantics=semantics)])


def fact_reference(entry,data):
    family=data['family']; local=family in ('effect','spillover'); reader=effects if local else policy
    refs=reader.reference_catalog(entry['bundle'],binding=entry['fact_binding_sha256'])
    def ids(doc):return [k for k,v in refs['aliases'].items() if v['doc_id']==doc]
    def declaration(doc):return dict(value=True,source_ids=ids(doc))
    nodes=data['nodes']
    c=dict(version=effects.VERSION if local else CONTRAST_VERSION if family=='contrast' else policy.VERSION,
        reference_context=refs['context'],study=dict(nodes=nodes,edges=data['edges'],graph_kind='SIMPLE_UNDIRECTED',
          edge_list_complete=True,treatment='启用AI排班助手',outcome='考核周顾客平均等待分钟数',outcome_kind='CONTINUOUS',
          context=data['docs']['context'],source_ids=ids('study')+ids('network')+ids('context')),
        assignment=dict(deepcopy(DESIGNS[data['design']]),source_ids=ids('assignment')+ids('study')),
        exposure=dict(kind=data['kind'],core_collaborators=data['cores'] if data['exposure']=='E3' else None,source_ids=ids('exposure')),
        first_stage_exclusion=dict(status='PROPOSED',source_ids=ids('first_stage')) if data['design']=='D6' else None,
        information=[dict(operator='NODE_FULL_LAW',availability='SYMBOLIC_POPULATION_OPERATOR',outcome_nodes=nodes,source_ids=ids('information')+ids('study'))],
        additional_restrictions=[],unresolved=[])
    if local:
        a,b=data['own'] if family=='effect' else (0,0)
        first,second=(data['high'],data['high']) if family=='effect' else (data['high'],0)
        c['target']=dict(kind=data['target_kind'],operation='FIRST_MINUS_SECOND',
            first=dict(own=a,exposure=first,source_ids=ids('__question__')+ids('exposure')+ids('study')),
            second=dict(own=b,exposure=second,source_ids=ids('__question__')+ids('exposure')+ids('study')),
            population=data['population'],aggregation='EQUAL_MEAN',population_fixed_before_assignment=declaration('population'),
            remaining_assignment='ORIGINAL_DESIGN_CONDITIONAL',remaining_source_ids=ids('remaining'),
            shared_outcome_and_context=declaration('context'),source_ids=ids('__question__')+ids('population'))
        c['design_facts']=dict(assignment_rule_available=declaration('assignment'),network_fixed_before_treatment=declaration('network'))
        c['scientific_statements']={k:dict(status='PROPOSED',source_ids=ids('science')) for k in
            ('assignment_outcome_independence','consistency','finite_conditional_means')}
        c['information'][0]['arm_cells']=[]
    else:
        def endpoint(values):return dict(assignment=dict(zip(nodes,values)),population=data['population'],aggregation='EQUAL_MEAN',source_ids=ids('__question__')+ids('population'))
        c['target']=(dict(kind='FIXED_POLICY_MEAN',**endpoint(data['first'])) if family=='policy' else
            dict(kind='FIXED_POLICY_MEAN_DIFFERENCE',operation='FIRST_MINUS_SECOND',first=endpoint(data['first']),second=endpoint(data['second']),
                shared_outcome_and_context=declaration('context'),source_ids=ids('__question__')+ids('population')))
        c['assumptions']={k:declaration('assignment' if k=='known_assignment_law' else 'network' if k=='fixed_pretreatment_network' else 'science')
            for k in ('known_assignment_law','full_vector_randomization','consistency','fixed_pretreatment_network','finite_conditional_first_moments')}
        c['mean_sufficiency']=dict(value=True,scope='ALL_BINARY_ASSIGNMENTS',covered_nodes=nodes,source_ids=ids('sufficiency'))
        c['information'][0].update(assignment_cells=[],signature_cells=[])
        profile=entry.get('network_fact_contract')
        if profile:
            from cfm_id_llm.network_fact_protocols import network_fact_protocol
            protocol=network_fact_protocol(profile); old=c.pop('assumptions')
            if family=='policy':c['version']=protocol.wire_version
            c['design_facts']=dict(assignment_rule_available=old['known_assignment_law'],network_fixed_before_treatment=old['fixed_pretreatment_network'])
            def statement(doc):
                return (dict(status='PROPOSED',quotations=[dict(source_id=i,quote=refs['aliases'][i]['text']) for i in ids(doc)])
                    if protocol.wire_version=='network-source-statements-1' else dict(status='PROPOSED',source_ids=ids(doc)))
            c['scientific_statements']={k:statement('science') for k in ('assignment_outcome_independence','consistency','finite_conditional_means')}
            c['mean_sufficiency']=dict(statement('sufficiency'),scope='ALL_BINARY_ASSIGNMENTS',covered_nodes=nodes)
        # Hand-authored fixtures must satisfy the selected wire contract. Never
        # apply these additions to a model response or infer population scope.
        if profile in ('network-policy-definition-refs-1','network-policy-record-definitions-1',
                       'network-policy-scopes-1','network-policy-scopes-2'):
            c['assignment']['definition_refs']=['study'] if data['design']!='D2' else []
            for endpoint in ([c['target']] if family=='policy' else [c['target']['first'],c['target']['second']]):
                endpoint['definition_refs']=['study']
            for info in c['information']:info['definition_refs']=['study']
        if profile in ('network-policy-record-definitions-1','network-policy-scopes-1','network-policy-scopes-2'):
            c['mean_sufficiency']['definition_refs']=['study']
        if profile in ('network-policy-scopes-1','network-policy-scopes-2'):
            for info in c['information']:
                info.update(scope_status='DECLARED',scope_source_ids=list(info['source_ids']))
        if profile == 'network-shared-definitions-1':
            from cfm_id_llm.shared_fact_definitions import LAW_NAMES
            c['study']['network_source_ids']=ids('network')
            reverse={value:key for key,value in LAW_NAMES.items()}
            for info in c['information']:info['operator']=reverse.get(info['operator'],info['operator'])
    return c


def setup(design='D2',exposure='E4',family='effect',*,profile=None,**kwargs):
    case,data=material(design,exposure,family,**kwargs)
    s=intake.start(case,reading_format='compact',fact_format='short_refs',network_fact_contract=profile,
        assignment_semantics='joint-assignment-law-1')
    s=intake.receive_candidate(s,a0_reference(case,data),request_sha256=s.request_sha256)
    q=approve(dispatch.prepare_reader(s,'q1')['query_worksheet'])
    e=dispatch.prepare_reader(s,'q1',query_review=q)
    if e['state']!='READY_TO_READ':raise ValueError(e)
    options=dict(query_review=q,candidate=fact_reference(e,data),request_sha256=e['request_sha256'])
    return s,e,options,dispatch.inspect_methods(s,'q1',**options)


def run(output):
    folder=Path(output);folder.mkdir(parents=True,exist_ok=False);rows=[]
    for design in DESIGNS:
        for exposure in EXPOSURES:
            for family in ('effect','spillover','policy','contrast'):
                s,e,o,p=setup(design,exposure,family)
                result=dispatch.execute(s,'q1',**o,**approval_records(p)) if p['state']=='REVIEW_REQUIRED' else p
                rows.append(dict(design=design,exposure=exposure,family=family,state=result['state'],
                    reason_code=result.get('reason_code'),independent_replay=result.get('independent_replay',False)))
    summary=dict(rows=rows,passed=all(r['state']=='POINT' and r['independent_replay'] for r in rows),
        model_api_calls=0,synthetic_reference_only=True,llm_accuracy_measured=False)
    (folder/'SUMMARY.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    return summary


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True);parser.add_argument('--allow-synthetic-reviews',action='store_true')
    args=parser.parse_args()
    if not args.allow_synthetic_reviews:parser.error('Explicit synthetic review selection required')
    result=run(args.output);print(json.dumps(dict(passed=result['passed'],cases=len(result['rows']),model_api_calls=0)))
    raise SystemExit(0 if result['passed'] else 1)
