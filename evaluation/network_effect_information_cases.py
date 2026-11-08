"""Complete new business packets, frozen before online information tests.

Two scenarios, four information variants each; variants are not independent
businesses. Reference A0/facts are component fixtures, never runtime defaults.
"""
from cfm_id import business_intake as intake, business_dispatch as dispatch
from cfm_id_llm.schemas import BusinessCase, SourceDocument
from cfm_id_llm.network_effect_reading import reference_catalog
from examples.business_dispatch_reference import approve
from evaluation.network_effect_citation_cases import reference_a0
from evaluation.network_effect_source_cases import reference_facts

CASES = tuple(f'{family}_{variant}' for family in ('bakery', 'laundry')
              for variant in ('population', 'sample', 'mixed', 'missing'))
EXPECTED = {name: 'POINT' if name.endswith(('population', 'mixed')) else 'NEEDS_INPUT' for name in CASES}


def material(name):
    if name not in CASES:
        raise ValueError('UNKNOWN_INFORMATION_CASE')
    family, variant = name.split('_')
    if family == 'bakery':
        nodes = ['文华店', '春江店', '柳岸店', '松涛店', '金桂店']
        members = nodes[1:3]
        edges = list(zip(nodes, nodes[1:] + nodes[:1]))
        rates = ['1/4', '1/3', '1/2', '2/3', '3/4']
        unit, action, outcome = '烘焙门店', '启用备料提醒', '本月每笔缺料补送的平均完成分钟数'
        intro = '烘焙连锁希望减少门店缺料后的等待。门店会向有合作关系的店调借原料，因此邻店使用备料提醒也可能影响本店的补送。'
        goal = '合作门店中使用备料提醒的比例不超过一半时，本店使用提醒与不使用相比，补送平均需要的时间相差多少？计算使用时的均值减去不使用时的均值。'
        kind, arms = 'DIRECT_EFFECT', ((1, 0), (0, 0))
    else:
        nodes = ['望湖店', '梧桐店', '明珠店', '锦溪店']
        members = nodes
        edges = list(zip(nodes, nodes[1:]))
        rates = ['1/3', '2/5', '3/5', '2/3']
        unit, action, outcome = '洗衣门店', '启用订单协作看板', '本月每笔跨店洗护订单的平均完成小时数'
        intro = '洗衣连锁的门店会把部分订单交给合作店处理。公司想了解订单协作看板是否影响周边门店，即使某家店自己没有使用看板，也可能因合作店使用而受影响。'
        goal = '本店不使用看板时，合作店中使用看板的数量超过半数，与至多一半使用相比，订单平均完成时间相差多少？计算超过半数时的均值减去至多一半时的均值。'
        kind, arms = 'SPILLOVER_EFFECT', ((0, 1), (0, 0))
    population = ('评价名单在试点抽签之前已经固定为' + '、'.join(members)
                  + '。先分别计算名单中每家店的差值，再对这些店取等权平均，不按订单量加权。')
    remaining = ('比较的每一端，在符合该端本店使用情况和合作店使用比例的所有完整安排中，按原试点抽签概率平均。'
                 '其余门店不固定为某个使用名单，也不改用新的分配概率。')
    sample = ('业务部门提交的是完整名单中每家店本月的有限订单样本，以及按本店是否使用、合作状态0或1分组的样本平均时间。'
              '即使表格列全了四组，这份记录也只是样本资料，不是精确总体均值或总体分布。')
    full = ('本次理论研究另有一份总体信息声明：完整名单中每家店，在本人使用或不使用与合作状态0或1组成的全部四种情况下，'
            '总体条件平均结果都可作为已知信息使用。不提供这些均值的具体数值，也不把样本均值当作总体均值；声明对应同一原试点。')
    first = ('可用的总体信息仅覆盖评价名单中的门店、比较第一端的情况：' +
             ('合作店至多一半使用，本店使用提醒。' if family == 'bakery' else '本店不使用，合作店超过半数使用看板。') +
             '这些总体条件均值可用，但未给数值。其他对象或状态的总体均值没有提供，尤其没有比较第二端的总体均值。')
    docs = dict(
        study=intro + '完整研究名单为' + '、'.join(nodes) + '。每家' + unit + '是一个研究对象。'
              + action + '记为1，不使用记为0。结果指标为' + outcome + '。',
        network='完整双向合作关系为' + '；'.join(a + '与' + b for a, b in edges) +
                '。其他门店对之间没有合作关系，没有自环或重复关系。关系在抽签前固定，本月保持不变。',
        assignment='原试点对每家店独立抽签，完整规则为' + '；'.join(n + '使用的概率是' + p for n, p in zip(nodes, rates)) + '。',
        exposure='合作店中严格超过一半使用工具时，合作状态记1；至多一半记0。恰好一半或没有合作店，也记0。这是合作情况的记录口径。',
        population=population, remaining=remaining,
        science='研究负责人为本次合成研究明确拟采用以下条件：整份使用名单与所有门店在各完整安排下的潜在结果独立；'
                '实际观察结果等于实际完整安排下对应的潜在结果；涉及的条件一阶矩存在且有限。',
        context='比较两端都针对本月，使用相同业务背景和结果定义。所有提供的信息都对应同一试点、期间和结果口径。',
        information=sample + '除此之外，没有声明任何总体信息可用。' if variant == 'sample' else first if variant == 'missing' else full)
    if variant in ('mixed', 'missing'):
        docs['sample_records'] = sample
    order = ['study', 'population', 'context', 'network', 'exposure', 'assignment', 'information', 'science', 'remaining']
    if 'sample_records' in docs:
        order.insert(2, 'sample_records')
    question = intro + '\n' + population + '\n' + goal + '\n' + remaining
    case = BusinessCase(case_id='INFORMATION-COMBINATION-' + name, business_question=question,
                        sources=[SourceDocument(source_id=k, text=docs[k]) for k in order])
    data = dict(name=name, nodes=nodes, members=members, edges=edges, probabilities=dict(zip(nodes, rates)),
                unit=unit, treatment=action, outcome=outcome, docs=docs, questions={'q1': goal, 'q2': goal},
                kind=kind, arms=arms, aggregation='EQUAL_MEAN', memo=False, variant=variant)
    return case, data


def setup(name):
    case, data = material(name)
    state = intake.start(case, reading_format='canonical', fact_format='short_refs')
    state = intake.receive_candidate(state, reference_a0(case, data), request_sha256=state.request_sha256)
    query_review = approve(dispatch.prepare_reader(state, 'q1')['query_worksheet'])
    entry = dispatch.prepare_reader(state, 'q1', query_review=query_review)
    if entry['state'] != 'READY_TO_READ':
        raise ValueError('REFERENCE_A0_NOT_READY')
    raw = reference_facts(entry, data)
    info = raw['information'][0]
    if data['variant'] == 'sample':
        info.update(operator='FINITE_SAMPLE', availability='FINITE_SAMPLE', arm_cells=[])
    if data['variant'] == 'missing':
        info['outcome_nodes'] = data['members']
        a, e = data['arms'][0]
        info['arm_cells'] = [dict(node=n, own=a, exposure=e) for n in data['members']]
    if data['variant'] in ('mixed', 'missing'):
        refs = reference_catalog(entry['bundle'], binding=entry['fact_binding_sha256'])
        raw['information'].append(dict(operator='FINITE_SAMPLE', availability='FINITE_SAMPLE',
            outcome_nodes=data['nodes'], arm_cells=[],
            source_ids=[k for k, v in refs['aliases'].items() if v['doc_id'] == 'sample_records']))
    return state, entry, data, raw
