"""Frozen front-door business materials and independent synthetic reference labels."""
from copy import deepcopy
from cfm_id.source_locations import build_catalog
from cfm_id_llm.dag_reading import documents
from cfm_id_llm.dag_frontdoor_reading import parse
from cfm_id.dag_business import (
    FRONTDOOR_ROUTE, FRONTDOOR_READING_DECISIONS, DagFrontdoorReadingReview,
    inspect_candidate, submit_reviewed)
from cfm_id.dag_frontdoor_contract import FrontdoorReview, DECISIONS
from examples.dag_business_reference import semantic_score as common_score


def _case(case_id, variant='specified', domain='training'):
    x,m,y,u,context = {
        'training': ('参加培训','掌握方法','任务达标','学习意愿','本季度新员工'),
        'maintenance': ('接受保养','润滑到位','设备故障','设备磨损','本月仓储设备'),
        'marketing': ('收到优惠','访问页面','完成购买','购买意愿','本周会员用户'),
    }[domain]
    nodes=[u,x,m,y]
    edges=[(u,x),(u,y),(x,m),(m,y)]
    if variant=='direct_path':edges.append((x,y))
    question='我们研究'+context+'。如果把每个对象的“'+x+'”分别设为0和1、其他机制不变，“'+y+'”的总体分布如何从已有总体信息得到？'
    additions={
        'specified':'请检验能否用“'+m+'”作前门变量。',
        'search':'没有指定前门变量，请在有观测的变量中寻找合适的单个前门变量。',
        'control':'业务方指定把“'+m+'”作为控制变量，请检查这个普通协变量调整方案。',
        'undecided':'我们还没有决定是否要用“'+m+'”作前门变量，请先保留这个未定事项。',
        'role_clarification':'请用“'+m+'”作前门变量，而不是要求把它作为控制变量。',
        'both':'请用“'+m+'”作前门变量，同时还要求把“'+m+'”作为协变量控制。',
        'forbidden':'我们明确不允许把“'+m+'”作前门变量。',
        'paraphrase':'希望借助对“'+m+'”的观测来按前门方法识别这个干预分布，请固定用这个变量来检验。',
        'latent_choice':'请检验能否用“'+u+'”作前门变量。',
        'implicit_role':'请分析这个干预分布能否由已有总体信息表示。',
    }
    question+=additions.get(variant,additions['specified'])
    docs={
        'variables':'\n'.join(n+('在本模型中分为高/低两档，分别记为1/0；没有观测记录。' if n==u else
                                '表示是否出现该状态，出现为1、未出现为0；有观测记录。') for n in nodes),
        'relations':'\n'.join(a+'直接影响'+b+'。' for a,b in edges),
        'context':'研究对象和时期：'+context+'。',
        'model':'本次拟采用固定的、无时间反馈的有向无环结构模型。\n'
                '以上列出了本模型全部直接因果关系，没有其他直接因果边。\n'
                '所有共同原因均已在变量清单中显式列出，不另有遗漏的共同原因。\n'
                '各结构方程剩余的随机噪声相互独立。\n'
                '所问干预仅设定处理变量，其他变量的结构机制保持不变。',
        'information':'已知全部有观测记录变量的完整联合总体分布，作为符号总体信息，不是样本频率。\n'
                      '这些观测变量每一种联合0/1取值组合的总体概率都严格大于零。'
    }
    if variant=='unknown_positive':
        docs['information']=docs['information'].splitlines()[0]+'\n尚未确定每种联合取值的总体概率是否都严格大于零。'
    if variant=='sample':
        docs['information']='手头只有全部有观测记录变量的一千条个体样本，没有给出总体联合分布。'
    if variant=='unknown_graph':
        lines=docs['model'].splitlines();lines[1]='所列直接因果关系是否完整尚未核实，尚未决定是否采用完整图假设。'
        docs['model']='\n'.join(lines)
    bundle=dict(case_id=case_id,documents=docs,question=question)
    catalog=build_catalog(documents(bundle))
    def ids(doc,index=None):
        values=[sid for sid,row in catalog.items() if row['doc_id']==doc]
        return values if index is None else [values[index]]
    role_status={'search':'UNSPECIFIED','control':'UNSPECIFIED','undecided':'UNDECIDED',
                 'forbidden':'FORBIDDEN','implicit_role':'UNSPECIFIED'}.get(variant,'SPECIFIED')
    role_variable=None if role_status=='UNSPECIFIED' else u if variant=='latent_choice' else m
    scope_names=['static_acyclic','graph_complete','latent_causes_accounted','independent_errors','perfect_intervention']
    unknown_scope=lambda name:variant=='unknown_graph' and name=='graph_complete'
    unknown_positive=variant in ('unknown_positive','sample')
    reference=dict(
        version='dag-frontdoor-reading-2',
        variables=[dict(name=n,observation='LATENT' if n==u else 'OBSERVED',domain='BINARY',source_ids=ids('variables',i))
                   for i,n in enumerate(nodes)],
        relations=[dict(cause=a,effect=b,kind='DIRECT_CAUSE',source_ids=ids('relations',i)) for i,(a,b) in enumerate(edges)],
        target=dict(kind='INTERVENTIONAL_DISTRIBUTION',treatment=x,outcome=y,context=context,source_ids=ids('__question__')),
        scope={name:dict(value=None if unknown_scope(name) else True,
                        source_ids=[] if unknown_scope(name) else ids('model',i)) for i,name in enumerate(scope_names)},
        information=dict(kind='FINITE_SAMPLE' if variant=='sample' else 'FULL_JOINT_POPULATION_LAW',
                         variables=[x,m,y],source_ids=ids('information',0),
                         positivity=dict(value=None if unknown_positive else True,
                                         source_ids=[] if unknown_positive else ids('information',1))),
        adjustment=[m] if variant in ('control','both') else None,
        adjustment_source_ids=ids('__question__') if variant in ('control','both') else [],
        frontdoor_choice=dict(status=role_status,variable=role_variable,
                              source_ids=[] if role_status=='UNSPECIFIED' else ids('__question__')),
        additional_restrictions=[],unresolved=[])
    expected='POINT';reason=None
    if variant in ('control','both'):
        expected='UNSUPPORTED';reason='FRONTDOOR_WITH_ADJUSTMENT_REQUEST_NOT_ADAPTED'
    elif variant=='forbidden':
        expected='UNSUPPORTED';reason='FRONTDOOR_ROLE_PROHIBITED'
    elif variant in ('undecided','unknown_positive','sample','unknown_graph'):
        expected='NEEDS_INPUT';reason='MISSING_OR_AMBIGUOUS_DAG_DECLARATIONS'
    elif variant=='direct_path':
        expected='UNSUPPORTED';reason='SPECIFIED_VARIABLE_FAILS_FRONTDOOR'
    elif variant=='latent_choice':
        expected='UNSUPPORTED';reason='DISTINCT_OBSERVED_FRONTDOOR_VARIABLE_REQUIRED'
    return dict(bundle=bundle,reference=reference,expected_state=expected,expected_reason=reason,
                expected_frontdoor=m if expected=='POINT' else None,route_id=FRONTDOOR_ROUTE,variant=variant)


def cases():
    return [
        _case('FB01_specified'),
        _case('FB02_search','search','maintenance'),
        _case('FB03_control','control'),
        _case('FB04_undecided','undecided'),
        _case('FB05_direct_path','direct_path'),
        _case('FB06_unknown_positive','unknown_positive','marketing'),
        _case('FB07_role_clarification','role_clarification','marketing'),
        _case('FB08_both','both'),
        _case('FB09_forbidden','forbidden'),
        _case('FB10_sample','sample','maintenance'),
        _case('FB11_unknown_graph','unknown_graph'),
        _case('FB12_paraphrase','paraphrase','maintenance'),
        _case('FB13_latent_choice','latent_choice'),
        _case('FB14_implicit_role','implicit_role'),
    ]


def semantic_score(bundle,wire,reference):
    try:
        actual=parse(bundle,wire).model_dump();gold=parse(bundle,reference).model_dump()
    except ValueError:
        return dict(passed=False,structure=False,fields={},citation_coverage=False)
    a=deepcopy(actual);g=deepcopy(gold)
    ac=a.pop('frontdoor_choice');gc=g.pop('frontdoor_choice')
    a['version']=g['version']='dag-reading-1'
    result=common_score(bundle,a,g)
    result['fields']['frontdoor_choice']=all(ac[k]==gc[k] for k in ('status','variable'))
    result['citation_coverage'] &= set(gc['source_ids'])<=set(ac['source_ids'])
    result['passed']=all(result['fields'].values()) and result['citation_coverage']
    result['unresolved_count']=len(actual['unresolved'])
    return result


def reference_reviews(bundle,wire):
    view=inspect_candidate(bundle,wire,route_id=FRONTDOOR_ROUTE)
    if view['state']!='REVIEW_REQUIRED':raise ValueError('REVIEW_READY_REFERENCE_REQUIRED')
    common=dict(reviewer='Independent synthetic scenario protocol',
                evidence='Frozen hypothetical graph, population information and requested roles checked against independent references.',
                authority='SYNTHETIC_TEST')
    reading={k:v for k,v in view['reading_worksheet'].items() if k!='is_approval'}
    science={k:v for k,v in view['science_worksheet'].items() if k!='is_approval'}
    reading.update(**common,decisions={k:'ACCEPTED' for k in FRONTDOOR_READING_DECISIONS})
    science.update(**common,decisions={k:'ACCEPTED' for k in DECISIONS})
    return DagFrontdoorReadingReview.model_validate(reading),FrontdoorReview.model_validate(science)


def assess(case,wire):
    bundle=case['bundle'];score=semantic_score(bundle,wire,case['reference'])
    view=inspect_candidate(bundle,wire,route_id=FRONTDOOR_ROUTE)
    initial_state=view['state']
    if score['passed'] and initial_state=='REVIEW_REQUIRED':
        reading,science=reference_reviews(bundle,wire)
        view=submit_reviewed(bundle,wire,reading_review=reading,science_review=science,
                             research_protocol_selected=True,route_id=FRONTDOOR_ROUTE)
    elif not score['passed']:
        view['reference_review_withheld']=True
    state=view['state']==case['expected_state']
    proof=(view['independent_replay'] and view['certificate']['frontdoor_variable']==case['expected_frontdoor']
           if case['expected_state']=='POINT' else
           view['certificate'] is None and view['reason_code']==case['expected_reason'])
    return dict(passed=bool(score['passed'] and state and proof),score=score,initial_state=initial_state,
                final_state=view['state'],result=view,expected_state=case['expected_state'],
                synthetic_only=True,real_world_semantic_accuracy=False)


if __name__=='__main__':
    import json
    rows=[dict(case=c['bundle']['case_id'],**assess(c,c['reference'])) for c in cases()]
    print(json.dumps(dict(passed=all(r['passed'] for r in rows),rows=rows),ensure_ascii=False,indent=2))

