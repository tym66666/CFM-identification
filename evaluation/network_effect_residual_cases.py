"""Fresh full-prose role tests; reference fixtures never enter model requests.

Five packets are variants of two businesses, not five independent scenarios.
An extra bound is deliberately in the same paragraph as available information.
"""
from cfm_id import business_intake as intake, business_dispatch as dispatch
from cfm_id_llm.schemas import BusinessCase, SourceDocument
from cfm_id_llm.network_effect_reading import reference_catalog
from examples.business_dispatch_reference import approve
from evaluation.network_effect_citation_cases import reference_a0
from evaluation.network_effect_source_cases import reference_facts

CASES = ('retail_mixed', 'retail_gap', 'retail_extra', 'service_mixed', 'service_sample')
EXPECTED = {'retail_mixed': 'POINT', 'retail_gap': 'NEEDS_INPUT', 'retail_extra': 'ADAPTER_NOT_CONNECTED',
            'service_mixed': 'POINT', 'service_sample': 'NEEDS_INPUT'}


def material(name):
    if name not in CASES:
        raise ValueError('UNKNOWN_RESIDUAL_CASE')
    family, variant = name.split('_')
    if family == 'retail':
        nodes = ['百合店', '紫藤店', '枫叶店', '山茶店']
        members = [nodes[0], nodes[2]]
        edges = list(zip(nodes, nodes[1:] + nodes[:1]))
        rates = ['1/4', '1/3', '2/3', '3/4']
        unit, action, outcome = '便利店', '启用缺货共享清单', '本月每笔跨店调货的平均等待分钟数'
        intro = '便利店缺货时会向合作门店调货。公司准备评估缺货共享清单：即使本店不用清单，合作门店使用后也可能更快找到可以调拨的货品。'
        goal = '本店不使用清单时，合作门店中超过半数使用清单，与至多一半使用相比，调货的平均等待时间相差多少？计算超过半数时的均值减去至多一半时的均值。'
        kind, arms = 'SPILLOVER_EFFECT', ((0, 1), (0, 0))
    else:
        nodes = ['朝阳组', '白鹭组', '海星组', '银杏组', '青松组']
        members = nodes
        edges = [(nodes[0], n) for n in nodes[1:]]
        rates = ['1/5', '1/3', '1/2', '2/3', '4/5']
        unit, action, outcome = '客服小组', '使用工单分派助手', '本月每笔转派工单的平均解决小时数'
        intro = '电商售后部门的小组会在业务繁忙时向合作组转派工单。分派助手可能影响本组，也可能通过转派影响合作组。负责人希望了解在合作组较少使用助手时，本组使用助手的作用。'
        goal = '合作组中使用助手的比例至多一半时，本组使用助手与不使用相比，转派工单的平均解决时间差多少？用使用时的均值减去不使用时的均值。'
        kind, arms = 'DIRECT_EFFECT', ((1, 0), (0, 0))
    population = ('评价名单在抽签前确定为' + '、'.join(members)
                  + '。先计算每个对象自己的差值，再对名单中对象等权平均，不按业务量加权。')
    remaining = ('比较每一端时，把符合该端自身使用状态和合作对象状态的全部完整安排纳入，按原试点抽签概率平均。'
                 '其余对象不固定成某个使用名单，也不使用另一套抽签规则。')
    sample = ('业务部门另外提交完整研究名单中每个对象本月的有限业务样本，并按自身是否使用、合作状态0或1列出四组样本平均时间。'
              '这张表是样本统计，不能当作精确总体均值或总体分布。')
    full = ('本次理论研究声明：完整研究名单中每个对象，在自身使用或不使用、合作状态0或1组成的四种情况下，'
            '总体条件平均结果均可作为已知信息使用。这里只声明这些总体均值可用，不给具体数值；它们不是业务样本表里的样本均值。')
    gap = ('可用的总体信息只覆盖百合店和枫叶店在本店不使用清单、合作店超过半数使用时的总体条件平均结果。'
           '这些总体均值没有给出数值。其他对象或状态的总体均值未提供，尤其没有本店不使用且合作店至多一半使用的总体均值。')
    extra = ('研究负责人还明确采用：每个便利店在每种完整使用名单下的平均调货等待时间不超过18分钟。'
             '这一上界与前述总体信息同时成立。')
    info = sample + '除此之外，本次没有提供任何总体均值或总体分布。' if variant == 'sample' else gap if variant == 'gap' else full
    if variant == 'extra':
        info += extra
    docs = dict(
        study=intro + '完整研究名单为' + '、'.join(nodes) + '。每个' + unit + '作为一个对象。'
              + action + '记1，不使用记0。结果指标为' + outcome + '。',
        network='双向合作关系的完整清单是' + '；'.join(a + '与' + b for a, b in edges) +
                '。其他对象对没有合作关系，没有自环或重复边。这份关系表在试点抽签前已固定，本月保持不变。',
        assignment='原试点中各对象独立抽签，完整规则如下：' + '；'.join(n + '使用的概率为' + p for n, p in zip(nodes, rates)) + '。',
        exposure='合作对象中严格超过一半使用工具时，合作状态为1；至多一半使用为0。平票及没有合作对象也记0。这只是记录合作情况的分组口径。',
        population=population, remaining=remaining,
        science='研究负责人为本次合成推演明确拟采用：完整使用名单与全部对象在各完整安排下的潜在结果独立；实际观察结果就是实际完整安排下的潜在结果；涉及的条件一阶矩存在且有限。',
        context='两端都以本月为评价期，采用同一业务背景和结果定义。所提供的信息也对应同一原试点、同一期间和同一结果口径。',
        information=info)
    if variant != 'sample':
        docs['sample_records'] = sample
    order = ['information', 'study', 'context', 'population', 'assignment', 'network', 'exposure', 'science', 'remaining']
    if 'sample_records' in docs:
        order.insert(4, 'sample_records')
    case = BusinessCase(case_id='RESIDUAL-ROLES-' + name,
        business_question=intro + '\n' + population + '\n' + goal + '\n' + remaining,
        sources=[SourceDocument(source_id=k, text=docs[k]) for k in order])
    data = dict(name=name, nodes=nodes, members=members, edges=edges, probabilities=dict(zip(nodes, rates)),
        unit=unit, treatment=action, outcome=outcome, docs=docs, questions={'q1': goal, 'q2': goal},
        kind=kind, arms=arms, aggregation='EQUAL_MEAN', memo=False, variant=variant, extra_text=extra if variant == 'extra' else None)
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
    refs = reference_catalog(entry['bundle'], binding=entry['fact_binding_sha256'])
    ids = lambda doc: [k for k, v in refs['aliases'].items() if v['doc_id'] == doc]
    info = raw['information'][0]
    if data['variant'] == 'sample':
        info.update(operator='FINITE_SAMPLE', availability='FINITE_SAMPLE', arm_cells=[])
    else:
        raw['information'].append(dict(operator='FINITE_SAMPLE', availability='FINITE_SAMPLE',
            outcome_nodes=data['nodes'], arm_cells=[], source_ids=ids('sample_records')))
    if data['variant'] == 'gap':
        info['outcome_nodes'] = data['members']
        a, e = data['arms'][0]
        info['arm_cells'] = [dict(node=n, own=a, exposure=e) for n in data['members']]
        raw['unresolved'] = [dict(text='未提供比较第二端的总体均值。', source_ids=ids('information'))]
    if data['variant'] == 'extra':
        raw['additional_restrictions'] = [dict(text=data['extra_text'], source_ids=ids('information'))]
    return state, entry, data, raw
