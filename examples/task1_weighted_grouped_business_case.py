"""Task-1 weighted/grouped exposure through the full business dispatch.

Complements ``task1_business_case_reference.py`` (which covers the new
assignment designs D7/D8 with the classic E1 exposure). This reference drives
the new *exposure* families -- weighted neighbour exposure and grouped
neighbour counts -- through the same intake -> reading -> dispatch -> make_arm
-> verified POINT certificate, so W/G is not only reachable from the native API
but from the reviewed business record as well.

Two scenarios, each asked as a DIRECT (same exposure, own 1 vs 0) and a
SPILLOVER (own 0, two exposure levels) question:

  W_weighted_D7  unequal fixed-quota design + weighted sum exposure
                 ``sum_j w_ij T_j`` with unit weights (coordinates "0"/"1");
  G_grouped_D8   rerandomized balanced design + grouped exposure over two
                 fixed triangles (coordinate "[treated in 东组, 西组]").

This is an explicit synthetic fixture: no LLM calls and no real scientific
approval. Run with --allow-synthetic-reviews.
"""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

from cfm_id import business_intake as intake, business_dispatch as dispatch
from cfm_id_llm.schemas import BusinessCase, SourceDocument
from cfm_id_llm import network_effect_reading as reading
import examples.task1_business_case_reference as base

NODES = base.NODES
EDGES = base.EDGES
EAST = ['甲店', '丙店', '戊店']
WEST = ['乙店', '丁店', '己店']

SCENARIOS = {
    'W_weighted_D7': dict(
        design='D7_unequal',
        exposure=dict(kind='WEIGHTED_EXPOSURE', weights={n: '1' for n in NODES}, mode='sum'),
        population=NODES,
        direct_exposure='1', spill_reference='0', spill_comparison='1',
        exposure_text='同伴暴露按处理前固定的门店权重求和，每个门店权重为一；'
                      '本查询比较加权启用数为一与零两类同伴状态。',
        population_text='评价名单在抽签前固定为全部六个门店，对这些门店取等权平均。',
    ),
    'G_grouped_D8': dict(
        design='D8_rerandomized',
        exposure=dict(kind='GROUPED_EXPOSURE', groups={'东组': EAST, '西组': WEST}),
        population=EAST,
        direct_exposure='[1, 0]', spill_reference='[0, 0]', spill_comparison='[1, 0]',
        exposure_text='同伴暴露是处理前固定的东、西两组中启用合作对象人数组成的成组坐标；'
                      '评价门店只与本组（东组）门店相邻，故第二坐标恒为零。'
                      '本查询比较“[东组一人启用, 西组零人启用]”与“[东组零人, 西组零人]”。',
        population_text='评价名单在抽签前固定为东组的三个门店，对这三个门店取等权平均。',
    ),
}


def material(scenario):
    cfg = SCENARIOS[scenario]
    treatment = '启用排班助手'
    outcome = '本周顾客平均等待分钟数'
    background = '一家连锁企业想了解排班助手是否减少顾客等待。六家门店会互相调配员工，合作关系在试点前已经固定。'
    edges_text = '；'.join(a + '与' + b for a, b in EDGES)
    questions = {
        'q1': f'合作对象处于同一同伴状态时，自己{ treatment }与自己未启用相比，{ outcome }相差多少？前者减后者。',
        'q2': f'自己不启用时，两种同伴状态相比，{ outcome }相差多少？前者减后者。',
    }
    docs = dict(
        study=background + '完整名单为' + '、'.join(NODES) + '。处理记1为' + treatment + '，记0为未启用；结果是' + outcome + '。',
        network='完整无向合作边为' + edges_text + '；除此之外没有合作边。网络在处理前固定。',
        assignment=base.DESIGN_TEXT[cfg['design']],
        exposure=cfg['exposure_text'],
        population=cfg['population_text'],
        remaining='两种比较都不固定其他对象的完整名单；在满足各端自身与同伴条件的安排中，按原试点抽签概率平均，不另外改变抽签规则。',
        context='所有比较使用同一周、同一背景和同一结果口径，结果单位均为分钟。',
        science='本合成研究拟采用：完整处理向量与所有对象在所有完整安排下的潜在结果独立；观察结果等于实际完整安排下的潜在结果；相关条件一阶矩存在且有限。',
        information='本理论研究可使用每个对象按自身是否启用与同伴暴露分组分成的总体条件平均结果；它们是符号总体信息，不是样本估计；不提供具体数值。',
    )
    question = background + '\n' + docs['population'] + '\n' + '\n'.join(questions.values()) + '\n' + docs['remaining']
    case = BusinessCase(case_id='synthetic_task1_' + scenario, business_question=question,
                        sources=[SourceDocument(source_id=k, text=v) for k, v in docs.items()])
    return case, dict(nodes=NODES, edges=EDGES, questions=questions, unit='门店',
                      treatment=treatment, outcome=outcome, scenario=scenario, docs=docs)


def fact_reference(entry, data):
    refs = reading.reference_catalog(entry['bundle'], binding=entry['fact_binding_sha256'])
    cfg = SCENARIOS[data['scenario']]

    def ids(doc):
        return [k for k, v in refs['aliases'].items() if v['doc_id'] == doc]

    def declaration(value, doc):
        return dict(value=value, source_ids=ids(doc))

    q1 = entry['query_id'] == 'q1'
    first = dict(own=1 if q1 else 0,
                 exposure=cfg['direct_exposure'] if q1 else cfg['spill_comparison'],
                 source_ids=ids('__question__'))
    second = dict(own=0,
                  exposure=cfg['direct_exposure'] if q1 else cfg['spill_reference'],
                  source_ids=ids('__question__'))
    population = cfg['population']
    required = [(n, first['own'], first['exposure']) for n in population] + \
               [(n, second['own'], second['exposure']) for n in population]
    cells = [dict(node=n, own=a, exposure=e) for (n, a, e) in required]
    return dict(version=reading.VERSION, reference_context=refs['context'],
        study=dict(nodes=data['nodes'], edges=[list(e) for e in data['edges']], graph_kind='SIMPLE_UNDIRECTED',
            edge_list_complete=True, treatment=data['treatment'], outcome=data['outcome'], outcome_kind='CONTINUOUS',
            context=data['docs']['context'], source_ids=ids('study') + ids('network') + ids('context')),
        assignment=dict(deepcopy(base.DESIGNS[cfg['design']]), source_ids=ids('assignment') + ids('study')),
        target=dict(kind='DIRECT_EFFECT' if q1 else 'SPILLOVER_EFFECT', operation='FIRST_MINUS_SECOND',
            first=first, second=second, population=population, aggregation='EQUAL_MEAN',
            population_fixed_before_assignment=declaration(True, 'population'),
            remaining_assignment='ORIGINAL_DESIGN_CONDITIONAL', remaining_source_ids=ids('remaining'),
            shared_outcome_and_context=declaration(True, 'context'), source_ids=ids('__question__') + ids('population')),
        exposure={**deepcopy(cfg['exposure']), 'source_ids': ids('exposure')},
        design_facts=dict(assignment_rule_available=declaration(True, 'assignment'),
                          network_fixed_before_treatment=declaration(True, 'network')),
        scientific_statements={k: dict(status='PROPOSED', source_ids=ids('science')) for k in
                               ('assignment_outcome_independence', 'consistency', 'finite_conditional_means')},
        information=[dict(operator='NODE_ARM_MEANS', availability='SYMBOLIC_POPULATION_OPERATOR',
            outcome_nodes=data['nodes'], arm_cells=cells, source_ids=ids('information'))],
        additional_restrictions=[], unresolved=[])


def run(output):
    folder = Path(output)
    folder.mkdir(parents=True, exist_ok=False)
    rows = []
    for scenario in SCENARIOS:
        case, data = material(scenario)
        s = intake.start(case, reading_format='canonical', fact_format='short_refs')
        s = intake.receive_candidate(s, base.a0_reference(case, data), request_sha256=s.request_sha256)
        for qid in ('q1', 'q2'):
            q = base.approve(dispatch.prepare_reader(s, qid)['query_worksheet'])
            e = dispatch.prepare_reader(s, qid, query_review=q)
            if e['state'] != 'READY_TO_READ':
                rows.append(dict(scenario=scenario, query=qid, state=e['state'],
                                 reason_code=e.get('reason_code'), independent_replay=False))
                continue
            o = dict(query_review=q, candidate=fact_reference(e, data), request_sha256=e['request_sha256'])
            p = dispatch.inspect_methods(s, qid, **o)
            result = dispatch.execute(s, qid, **o, **base.approval_records(p)) if p['state'] == 'REVIEW_REQUIRED' else p
            rows.append(dict(scenario=scenario, query=qid, state=result['state'],
                             reason_code=result.get('reason_code'),
                             independent_replay=result.get('independent_replay', False),
                             certificate=result.get('certificate')))
        intake.write_json(folder / (scenario + '_business.json'), case.model_dump(mode='json'))
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
