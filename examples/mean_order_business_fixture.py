"""Hypothetical business and independent reference data; never sent as gold.

Only bundle is public. Reviews are explicit test assertions. A real candidate
must match frozen semantic references; these helpers never fix its fields.
"""
from copy import deepcopy
from fractions import Fraction as F
from itertools import combinations
from cfm_id_bridge.scientific_binding import sha
from cfm_id import mean_order_business as entry,mean_order_reading as reader
from cfm_id.mean_order_contract import MeanOrderProblem, input_digest
from cfm_id.question_bound_assignment import question_catalog
from cfm_id.source_locations import build_catalog
from examples.bounded_contrast_fixture import make_case as base_case,reviews as base_reviews
from examples.partial_contrast_reference import set_common_information
from examples.mean_order_fixture import make_problem


def make_case(*,mode='BOTH',wording=0,nodes=None,edges=None,quota=2,first=None,second=None,population=None):
    nodes=list('ABCD') if nodes is None else list(nodes)
    edges=list(combinations(nodes,2)) if edges is None else edges
    first=[1]*len(nodes) if first is None else first; second=[0]*len(nodes) if second is None else second
    population=nodes if population is None else population
    p=base_case(nodes,edges,quota,first,second,population,serial=824)
    vals={(v.node,v.own,v.exposure):str(F(3*v.own+2*v.exposure,5)) for v in p['information']['first'].values}
    set_common_information(p,values=vals,bounds_kind='CONDITIONAL_MEAN')
    modes={n:mode for n in nodes} if type(mode) is str else mode
    lines=['以下是供研究者独立审核的科学条件，不是试点已经证明的结论。',
           '这里的结果指同一天是否按时完成任务；讨论潜在结果的条件均值时，保持该研究背景不变。']
    references=[]
    for axis in ('OWN','PEERS'):
        for included in (True,False):
            selected=[n for n in nodes if (modes[n] in (axis,'BOTH'))==included]
            if not selected:continue
            who='、'.join(selected)
            if not included:
                text=f'针对{who}，本轮明确不作'+('本人使用不降低自身结果均值' if axis=='OWN' else '合作邻居使用不降低该组结果均值')+'这项假设。'
            elif axis=='OWN':
                text=[f'针对{who}，提出以下均值假设：保持其他小组的使用安排不变，只把该组自己从不用改为使用，其按时完成概率不会下降。这个条件适用于所有完整使用安排，包括原试点没有出现的安排。',
                    f'对{who}，我们愿意单独审核这样一条条件：给定同一研究背景，不管其他人怎么安排，自己用辅助系统的平均潜在结果不低于自己不用。这里也包括原试点没有支持到的完整名单。',
                    f'对{who}，无论其余小组如何使用，给该组自己启用系统不会降低它的条件平均完成率。这是拟采用的科学假设，涵盖全部二元安排，包括全员用、全员不用。'][wording%3]
            else:
                text=[f'针对{who}，提出以下均值假设：保持该组自身和其余小组的安排不变，只把任意一个合作邻居从不用改为使用，该组的条件平均完成率不会下降。它适用于所有完整安排，包括原试点未出现的安排。',
                    f'对{who}，我们另提一条待审核条件：在给定研究背景下，固定本人以及其他人的用法，增加一个使用系统的合作邻居不会拉低该组的平均潜在结果；对所有可能名单都如此，不限于试点抽过的名单。',
                    f'对{who}，拟假定邻居增加使用对该组的条件均值没有负向影响：只切换一个邻居，其余使用状态不变，本人的平均完成率不降低。这个假定覆盖全部完整安排，含历史零支持安排。'][wording%3]
            lines.append(text)
            references.append(dict(nodes=selected,axis=axis,relation='NONDECREASING' if included else 'NOT_ASSUMED',
                level='CONDITIONAL_MEAN' if included else None,scope='ALL_BINARY_ASSIGNMENTS' if included else None,
                basis='ASSUMPTION_STATEMENT',text=text))
    p['bundle']['documents']['conditions.txt']='\n'.join(lines)
    p['raw']['reading']['intents']['q1']['question_id']=question_catalog(p['bundle'])['q1']['question_id']
    catalog=build_catalog(p['bundle']['documents']);claims=[]
    for row in references:
        claim={k:v for k,v in row.items() if k!='text'}
        claim['source_ids']=[sid for sid,v in catalog.items() if v['doc_id']=='conditions.txt' and v['text'].strip()==row['text']]
        claims.append(claim)
    candidate=dict(comparison=deepcopy(p['raw']),order_reading=dict(version=reader.VERSION,claims=claims,reported_conflict=False,other_restriction_source_ids=[]))
    st=p['inquiries']['first'].study;info=p['information']['first']
    problem=make_problem(nodes=nodes,edges=edges,quota=quota,mode=modes,first=first,second=second,
        weights=p['coordinates']['unit_weights'],values=[v.model_dump() for v in info.values],bounds=[v.model_dump() for v in info.bounds])
    model=problem.model_dump()
    model.update(context=st.context_reference,a4_source=info.source_id,a4_provenance=info.a4_provenance,
        bounds_kind=info.bounds_kind,bounds_provenance=info.bounds_provenance,outcome_definition=info.outcome_definition,
        outcome_unit=info.outcome_unit,outcome_period=info.outcome_period)
    problem=MeanOrderProblem.model_validate(model)
    science=dict(study_sha256=sha(st),treatment_variable=st.treatment_variable,outcome_variable=st.outcome_variable,
                 model=problem.model_dump(exclude=entry.DERIVED))
    return dict(base=p,bundle=p['bundle'],candidate=candidate,science=science,expected_problem=problem,
                expected_modes=modes,expected_candidate=deepcopy(candidate))


def semantic_rows(candidate):
    # Independent evaluation view: no theorem call or solving. Claim grouping
    # and list order may vary, but all semantics and evidence are retained.
    result={}
    for c in candidate['order_reading']['claims']:
        if not c['nodes']:raise ValueError('MISSING_SCOPE')
        for n in c['nodes']:
            key=(n,c['axis'])
            if key in result:raise ValueError('DUPLICATE_AXIS')
            result[key]=(c['relation'],c['level'],c['scope'],c['basis'],set(c['source_ids']))
    return result


def matches_reference(case,actual):
    from cfm_id.fixed_comparison import project
    try:
        _,_,_,targets=project(case['bundle'],actual['comparison'])
        if targets!={'q1':case['base']['coordinates']}:return False
        expected=semantic_rows(case['expected_candidate']); got=semantic_rows(actual)
        if set(expected)!=set(got):return False
        for pair,want in expected.items():
            if got[pair][:4]!=want[:4] or not want[4]<=got[pair][4]:return False
        reader.project(case['bundle'],actual['order_reading'])
        return actual['order_reading']['reported_conflict'] is False and not actual['order_reading']['other_restriction_source_ids']
    except (ValueError,TypeError,KeyError):return False


def endpoint_reviews(case,actual):
    p=deepcopy(case['base']);p['bundle']=case['bundle'];p['raw']=actual['comparison']
    return base_reviews(p)


def business_review(case,actual,chain):
    if not matches_reference(case,actual):raise ValueError('ACTUAL_READING_DIFFERS_FROM_FROZEN_REFERENCE')
    sheet=entry.worksheet(case['bundle'],actual,query_id='q1',science=case['science'],packet=chain['packet'],context=chain['context'])
    if sheet['problem_sha256']!=input_digest(case['expected_problem']):raise ValueError('COMPILED_MODEL_DIFFERS_FROM_INDEPENDENT_REFERENCE')
    return entry.ReviewedMeanOrderBusiness(**sheet,reviewer='Independent synthetic protocol reviewer',
        evidence='Original business comparison and every order axis checked against predeclared hypothetical science',
        reviewed_target_direction_population=True,reviewed_complete_a4_and_no_unmodeled_constraints=True,
        reviewed_base_assumptions_and_all_arrangement_scope=True,reviewed_bounds_and_each_order_axis=True,
        synthetic_fixture=True,confirmed_node_modes=case['expected_modes'],
        axis_decisions={entry.axis_key(n,a):'CONFIRMED' for n in case['expected_modes'] for a in ('OWN','PEERS')},
        reviewed_order_source_meaning_and_outcome=True,reviewed_original_comparison_and_endpoint_chain=True)


def run(case,actual=None):
    actual=deepcopy(case['candidate'] if actual is None else actual)
    preview=entry.prepare(case['bundle'],actual,query_id='q1',science=case['science'])
    if preview['state']!='REVIEW_REQUIRED':return preview
    if not matches_reference(case,actual):
        return dict(preview,state='REVIEW_REQUIRED',reason_code='INDEPENDENT_SEMANTIC_REVIEW_WITHHELD')
    chain=endpoint_reviews(case,actual);review=business_review(case,actual,chain)
    return entry.submit(case['bundle'],actual,query_id='q1',science=case['science'],review=review,**chain)
