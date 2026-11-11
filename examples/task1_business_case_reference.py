"""Task-1 complete business case: unequal fixed quota and rerandomized balance.

A realistic 6-store chain demo where the new assignment designs run through the
full business dispatch (intake -> reading -> dispatch -> make_arm -> verified
POINT certificate). Effect and spillover families are wired end to end; policy
value / contrast remain a separate policy-value backend (see the task-1
limitations note), so this reference covers the arm-mean POINT route.

This is an explicit synthetic fixture: no LLM calls and no real scientific
approval. Run with --allow-synthetic-reviews.
"""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

from cfm_id import business_intake as intake, business_dispatch as dispatch
from cfm_id_llm.schemas import (BusinessCase, SourceDocument, SemanticClaim,
                                TargetDraft, DraftProblemSpec, UnitsVariablesDraft, StructureDraft)
from cfm_id_llm.quality import MultiQueryDraftV010, BusinessInquiryV010, QuerySemanticsV010
from cfm_id_llm import network_effect_reading as reading
from examples.business_dispatch_reference import approve

NODES = ['甲店', '乙店', '丙店', '丁店', '戊店', '己店']
EDGES = [[NODES[i], NODES[j]] for i, j in ((0, 2), (2, 4), (4, 0), (1, 3), (3, 5), (5, 1))]

# Task-1 assignment designs (business field record), one per scenario.
DESIGNS = {
    'D7_unequal': dict(kind='UNEQUAL_PROBABILITY_FIXED_QUOTA', probabilities=None, fixed_count=3,
                       unit_weights={'甲店': '2', '乙店': '1', '丙店': '1', '丁店': '1', '戊店': '1', '己店': '1'}),
    'D8_rerandomized': dict(kind='RERANDOMIZED_BALANCED', probabilities=None, fixed_count=3,
                            unit_weights=dict.fromkeys(NODES, '1'),
                            balance_covariates={'x': {'甲店': '0', '乙店': '0', '丙店': '0',
                                                       '丁店': '1', '戊店': '1', '己店': '1'}},
                            balance_tolerance='1/2'),
}

DESIGN_TEXT = {
    'D7_unequal': '原试点从六家门店恰好抽取三家启用，但各门店入选权重不等：甲店权重为二，其余门店权重为一；每个三店名单的概率按其成员权重乘积归一，重要门店因此有更高入选机会。',
    'D8_rerandomized': '原试点先从六家门店均匀抽取三家，再检查处理前特征是否平衡：若启用三家与未启用三家的处理前特征均值差超过二分之一，则重新抽取，直到满足平衡为止。',
}


def material(design='D7_unequal'):
    unit = '门店'
    treatment = '启用排班助手'
    outcome = '本周顾客平均等待分钟数'
    background = '一家连锁企业想了解排班助手是否减少顾客等待。六家门店会互相调配员工，合作关系在试点前已经固定。'
    edges_text = '；'.join(a + '与' + b for a, b in EDGES)
    questions = {
        'q1': f'合作对象过半启用时，自己{ treatment }与自己未启用相比，{ outcome }相差多少？前者减后者。',
        'q2': f'自己不启用时，合作对象过半启用与至多一半启用相比，{ outcome }相差多少？前者减后者。',
    }
    docs = dict(
        study=background + '完整名单为' + '、'.join(NODES) + '。处理记1为' + treatment + '，记0为未启用；结果是' + outcome + '。',
        network='完整无向合作边为' + edges_text + '；除此之外没有合作边。网络在处理前固定。',
        assignment=DESIGN_TEXT[design],
        exposure='严格超过一半合作对象启用记为同伴高状态1；至多一半（包括平票）记为低状态0；没有合作对象也记为0。',
        population='评价名单在抽签前固定为全部六个' + unit + '，对这些' + unit + '取等权平均。',
        remaining='两种比较都不固定其他对象的完整名单；在满足各端自身与同伴条件的安排中，按原试点抽签概率平均，不另外改变抽签规则。',
        context='所有比较使用同一周、同一背景和同一结果口径，结果单位均为分钟。',
        science='本合成研究拟采用：完整处理向量与所有对象在所有完整安排下的潜在结果独立；观察结果等于实际完整安排下的潜在结果；相关条件一阶矩存在且有限。',
        information='本理论研究可使用每个对象按自身是否启用与同伴高低分成的四个组的总体条件平均结果；它们是符号总体信息，不是样本估计；不提供具体数值。',
    )
    question = background + '\n' + docs['population'] + '\n' + '\n'.join(questions.values()) + '\n' + docs['remaining']
    case = BusinessCase(case_id='synthetic_task1_' + design, business_question=question,
                        sources=[SourceDocument(source_id=k, text=v) for k, v in docs.items()])
    return case, dict(nodes=NODES, edges=EDGES, questions=questions, unit=unit,
                      treatment=treatment, outcome=outcome, design=design, docs=docs)


def a0_reference(case, data):
    def claim(text, source):
        return SemanticClaim(value=text, basis='EXPLICIT_TEXT', evidence=[dict(source_id=source, quote=text)])

    d = data['docs']
    queries = []
    for qid, kind in [('q1', 'DIRECT_EFFECT'), ('q2', 'SPILLOVER_EFFECT')]:
        goal = claim(data['questions'][qid], 'business_question')
        queries.append(BusinessInquiryV010(query_id=qid, business_goal=goal, target=TargetDraft(kind=kind, description=goal),
            semantics=QuerySemanticsV010(target_population=claim(d['population'], 'population'),
                aggregation=claim(d['population'], 'population'), intervention=goal, comparator=goal,
                neighbor_exposure=claim(d['exposure'], 'exposure'), standardization_distribution=claim(d['remaining'], 'remaining'))))
    shared = DraftProblemSpec(target=queries[0].target, units_variables=UnitsVariablesDraft(
        analysis_unit=claim(data['unit'], 'study'), treatment=claim(data['treatment'], 'study'),
        outcome=claim(data['outcome'], 'study')), structure=StructureDraft(unit_network=claim(d['network'], 'network')))
    return MultiQueryDraftV010(shared_draft=shared, primary_query_id='q1', queries=queries).model_dump(mode='json')


def fact_reference(entry, data):
    refs = reading.reference_catalog(entry['bundle'], binding=entry['fact_binding_sha256'])

    def ids(doc):
        return [k for k, v in refs['aliases'].items() if v['doc_id'] == doc]

    def declaration(value, doc):
        return dict(value=value, source_ids=ids(doc))

    own_first, own_second, second_exposure = (1, 0, 1) if entry['query_id'] == 'q1' else (0, 0, 0)
    return dict(version=reading.VERSION, reference_context=refs['context'],
        study=dict(nodes=data['nodes'], edges=[list(e) for e in data['edges']], graph_kind='SIMPLE_UNDIRECTED',
            edge_list_complete=True, treatment=data['treatment'], outcome=data['outcome'], outcome_kind='CONTINUOUS',
            context=data['docs']['context'], source_ids=ids('study') + ids('network') + ids('context')),
        assignment=dict(deepcopy(DESIGNS[data['design']]), source_ids=ids('assignment') + ids('study')),
        target=dict(kind='DIRECT_EFFECT' if entry['query_id'] == 'q1' else 'SPILLOVER_EFFECT', operation='FIRST_MINUS_SECOND',
            first=dict(own=own_first, exposure=1, source_ids=ids('__question__')),
            second=dict(own=own_second, exposure=second_exposure, source_ids=ids('__question__')),
            population=data['nodes'], aggregation='EQUAL_MEAN',
            population_fixed_before_assignment=declaration(True, 'population'),
            remaining_assignment='ORIGINAL_DESIGN_CONDITIONAL', remaining_source_ids=ids('remaining'),
            shared_outcome_and_context=declaration(True, 'context'), source_ids=ids('__question__') + ids('population')),
        exposure=dict(kind='STRICT_MAJORITY_TIES_LOW', source_ids=ids('exposure')),
        design_facts=dict(assignment_rule_available=declaration(True, 'assignment'),
                          network_fixed_before_treatment=declaration(True, 'network')),
        scientific_statements={k: dict(status='PROPOSED', source_ids=ids('science')) for k in
                               ('assignment_outcome_independence', 'consistency', 'finite_conditional_means')},
        information=[dict(operator='NODE_ARM_MEANS', availability='SYMBOLIC_POPULATION_OPERATOR',
            outcome_nodes=data['nodes'],
            arm_cells=[dict(node=n, own=a, exposure=e) for n in data['nodes'] for a in (0, 1) for e in (0, 1)],
            source_ids=ids('information'))],
        additional_restrictions=[], unresolved=[])


def setup(design='D7_unequal', qid='q1'):
    case, data = material(design)
    s = intake.start(case, reading_format='canonical', fact_format='short_refs')
    s = intake.receive_candidate(s, a0_reference(case, data), request_sha256=s.request_sha256)
    q = approve(dispatch.prepare_reader(s, qid)['query_worksheet'])
    e = dispatch.prepare_reader(s, qid, query_review=q)
    if e['state'] != 'READY_TO_READ':
        raise ValueError(('Fixture A0 not ready', e))
    o = dict(query_review=q, candidate=fact_reference(e, data), request_sha256=e['request_sha256'])
    return s, e, o, dispatch.inspect_methods(s, qid, **o)


def approval_records(plan):
    return dict(plan_review=approve(plan['plan_worksheet']),
        native_reviews={r['method']: dict(reading_review=approve(r['reading_worksheet']),
                                          science_review=approve(r['science_worksheet']))
                        for r in plan['methods']},
        research_protocol_selected=True)


def run(output):
    folder = Path(output)
    folder.mkdir(parents=True, exist_ok=False)
    rows = []
    for design in ('D7_unequal', 'D8_rerandomized'):
        case, data = material(design)
        s = intake.start(case, reading_format='canonical', fact_format='short_refs')
        s = intake.receive_candidate(s, a0_reference(case, data), request_sha256=s.request_sha256)
        for qid in ('q1', 'q2'):
            q = approve(dispatch.prepare_reader(s, qid)['query_worksheet'])
            e = dispatch.prepare_reader(s, qid, query_review=q)
            o = dict(query_review=q, candidate=fact_reference(e, data), request_sha256=e['request_sha256'])
            p = dispatch.inspect_methods(s, qid, **o)
            result = dispatch.execute(s, qid, **o, **approval_records(p)) if p['state'] == 'REVIEW_REQUIRED' else p
            rows.append(dict(design=design, query=qid, state=result['state'],
                             reason_code=result.get('reason_code'),
                             independent_replay=result.get('independent_replay', False)))
        intake.write_json(folder / (design + '_business.json'), case.model_dump(mode='json'))
    summary = dict(rows=rows, passed=all(r['state'] == 'POINT' and r['independent_replay'] for r in rows),
                   model_api_calls=0, synthetic_reference_only=True, llm_accuracy_measured=False)
    intake.write_json(folder / 'SUMMARY.json', summary)
    return summary


if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', required=True)
    p.add_argument('--allow-synthetic-reviews', action='store_true')
    args = p.parse_args()
    if not args.allow_synthetic_reviews:
        p.error('Explicit synthetic reference selection required')
    print(json.dumps(run(args.output), ensure_ascii=False))
