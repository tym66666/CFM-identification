"""Human-readable, source-constrained display projection for the v3.0 supervisor UI.

This is PRESENTATION ONLY. No identification route, theorem, support probability,
A4/A5 scientific license or certificate is generated or modified here.

NBIB is a separate business-understanding benchmark (not formal Core POINT evidence).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

CONDITION_NAMES = (
    ('target', '研究问题与比较对象', '本次要回答谁、什么处理、什么状态下的结果'),
    ('setting', '实验安排或使用机制', '如何发放试用资格，或员工怎样选择使用'),
    ('network', '合作网络与同伴状态', '谁与谁有关联，以及“同伴使用”如何定义'),
    ('information', '所需总体研究信息', '能否合法得到目标对应的总体条件均值，不是只有样本记录'),
    ('assumptions', '必要的因果前提', '随机化或无混杂等必要前提已由研究者在本例中接受'),
    ('support', '目标状态能够出现', '原试验或观测分配机制对目标状态有严格正支持'),
)
STATE_LABEL = {
    'confirmed': '✓ 已提供/已确认',
    'missing': '？ 还需补充',
    'failed': '× 不满足',
    'unchecked': '— 暂未检查',
}

# Plain-language explanations are an editorial rendering of the EXACT formal
# synthetic fixture; they are not new business measurements or scientific facts.
SETTING_STORIES = {
    'S1': ('在线推荐功能试用',
           '一个六人关联用户网络中，平台独立随机给每位用户开放新推荐功能；已事先记录关联关系。',
           '指定用户获得功能后，在不同同伴使用状态下，平均业务指标该怎样计算？'),
    'S2': ('销售团队 AI 试用名额',
           '一个六人协作团队只有三个试用名额，采用统一随机抽签；其中一名核心员工与其余五人合作。',
           '核心员工自己试用 AI、且指定数量的同事也试用时，平均业务表现能否确定？'),
    'S3': ('门店团队整体随机试用',
           '六名成员分成三个事先确定的团队，每队两人；以团队为单位抽签，入选后全队使用新工具。',
           '指定员工自己使用工具、同伴使用情况特定时，平均业务指标能否确定？'),
    'S4': ('三个部门的固定试用名额',
           '六名员工分属三个部门，每个部门两人且各随机挑选一名试用；部门之间仍有合作关系。',
           '指定员工自己获得试用资格时，合作同事的使用人数不同会怎样影响识别？'),
    'S5': ('先选部门名额，再抽员工',
           '六名员工分成三个部门。首先随机确定各部门试用名额方案，再在部门内部抽取试用员工。',
           '指定员工使用新工具、同伴使用情况特定时，试验能否支持该平均结果？'),
    'S6': ('员工自主选择 AI 工具',
           '六名员工自主选择是否使用 AI。研究者假定已经掌握某个处理前二元特征及其同伴汇总，用于调整。',
           '在接受相应科学前提后，员工本人使用 AI 时，同伴是否使用 AI 会不会造成额外影响？'),
    'GOLDEN': ('三人团队最小验证',
               '三名员工按链状合作，试验每次随机挑选两人使用工具。每次只改一个条件，看看识别结论如何变化。',
               '指定第一名员工使用工具、直接相邻同伴使用达到严格多数时的平均结果能否确定？'),
}

SCENARIO_QUESTIONS = {
    'S1': {
       'point':'指定用户自己获得新推荐功能，且至少一名关联用户也获得时，能否确定该类状态下的平均业务结果？',
       'a4_missing':'仍问“自己和至少一名关联用户获得功能”的平均结果；如果没有正式认可的总体结果信息，还能判断吗？',
       'point_e4':'指定用户获得推荐功能，且**恰好一位**关联用户也获得时，能否确定对应的平均业务结果？',
    },
    'S2': {
       'point':'如果核心员工获得 AI 试用资格，且恰有两位合作同事试用，能否确定这一状态下的平均业务结果？',
       'zero_support':'只抽三人试用，却要求核心员工自己试用且另外三名同事同时试用：原试验能出现这种情况吗？',
       'a4_missing':'仍问“核心员工自己和两位同事试用”的平均业务结果；如果研究信息未获认可，还能给出结论吗？',
    },
    'S3': {
       'point':'整个团队一起抽签。指定员工使用新工具且至少一名关联同事也使用时，能确定平均业务结果吗？',
       'zero_support':'以团队为单位同时开通工具：指定员工自己使用，但所有关联同事都没使用，这种状态可能出现吗？',
       'a4_missing':'仍问“本人和关联同事都可能使用”的平均结果；缺少认可的总体信息时能给出结论吗？',
    },
    'S4': {
       'point':'三个部门各抽一人试用。指定员工使用工具，且恰好一名合作同事试用时，平均业务结果能确定吗？',
       'zero_support':'三个部门各只抽一人。指定员工已经试用，还要求**两名**关联同事也试用，原设计支持吗？',
       'a4_missing':'仍问“自己与一位同事试用”的平均结果；若研究信息未获认可，还能确定吗？',
    },
    'S5': {
       'point':'先随机分配部门名额，再抽员工。如果指定员工自己使用、至少一位同伴使用，能确定其平均结果吗？',
       'a5_missing':'同一个问题，但如果“名额方案公告本身不会改变员工结果”尚未获得科学确认，还能判断吗？',
       'zero_support':'这套部门名额方案下，若要求指定员工自己使用，且**恰好两位**关联同事也使用，有可能发生吗？',
    },
    'S6': {
       'point':'员工自主使用 AI。如果员工本人已经使用 AI，当同伴从无人使用变为至少一人使用时，他的平均表现会怎样变化？',
       'a5_missing':'仍问“自己使用 AI 的员工受到同伴影响多少”，但还没确认相关无混杂前提时，能给出因果结论吗？',
       'a4_sample_only':'仍问同伴使用 AI 的因果影响；如果只有有限员工日志、缺少需要的总体信息，能直接认证吗？',
    },
    'GOLDEN': {
       'base':'三名员工每次抽两人试用。指定员工本人试用且邻居中严格多数也试用时，平均结果能确定吗？',
       'missing_a4':'保留相同试验与问题，但撤去目标状态的总体结果信息，会发生什么？',
       'a4_not_admitted':'有一份总体结果信息，但尚未获准在本研究中使用，能直接给出结论吗？',
       'a5_unresolved':'保留相同资料，但随机化与一致性等必要因果前提尚未确认，还能认证吗？',
       'a5_rejected':'如果明确不接受原先需要的因果前提，还能使用原识别公式吗？',
       'zero_quota':'把随机试用人数改为零，原来要求“本人试用”的目标还能出现吗？',
       'add_network_edge':'额外加一条合作边后，原先的“邻居严格多数使用”目标还会出现吗？',
       'different_exposure':'保持试验不变，改成用“邻居使用比例分档”定义同伴状态，目标会怎样改变？',
       'query_not_confirmed':'如果负责人尚未正式确认要回答这个问题，是否可以直接颁发识别结论？',
    }
}

DESIGN_NAMES = {
    'D1':'每人独立随机抽签',
    'D2':'固定人数随机抽签',
    'D3':'两个部门各有名额',
    'D4':'整个团队一起抽签',
    'D5':'多个部门分别固定名额',
    'D6':'先抽部门名额，再抽员工',
    'OBS':'员工自主选择使用',
}
EXPOSURE_NAMES = {
    'E1':'超过半数的直接同伴使用',
    'E2':'直接同伴使用比例分为三档',
    'E3':'核心合作同事中超过半数使用',
    'E4':'直接同伴中恰好几人使用',
    'E5':'至少一位直接同伴使用',
    'strict_majority':'超过半数的直接同伴使用',
    'three_level_treated_neighbor_fraction':'直接同伴使用比例分为三档',
    'any_treated_neighbor':'至少一位直接同伴使用',
    'exact_treated_neighbor_count':'直接同伴中恰好几人使用',
}

BLOCKER_CONDITION = {
    'a4_missing': ('information','missing'),
    'a4_not_admitted': ('information','missing'),
    'a4_sample_only': ('information','missing'),
    'missing_a4': ('information','missing'),
    'a5_missing': ('assumptions','missing'),
    'a5_unresolved': ('assumptions','missing'),
    'a5_rejected': ('assumptions','failed'),
    'zero_support': ('support','failed'),
    'zero_quota': ('support','failed'),
    'add_network_edge': ('support','failed'),
    'query_not_confirmed': ('target','missing'),
}

BLOCKER_COPY = {
    'a4_missing':'缺少被正式接受的总体信息，原有数据字段或有限记录不足以代替。',
    'missing_a4':'已撤去目标状态的总体均值来源。',
    'a4_not_admitted':'信息虽存在，但未获准作为本次识别依据。',
    'a4_sample_only':'样本日志不能直接当作已知的总体条件均值。',
    'a5_missing':'相关因果前提还没有经研究者明确接受。',
    'a5_unresolved':'研究者尚未确认必要的随机化与一致性等前提。',
    'a5_rejected':'已有必要前提被明确否认，原定理不能继续使用。',
    'zero_support':'原分配机制不可能产生目标所要求的处理与同伴状态。',
    'zero_quota':'试用名额为零，目标却要求本人试用。',
    'add_network_edge':'增加合作边后，同伴多数的定义发生变化，原配额无法实现目标状态。',
    'query_not_confirmed':'负责人尚未批准该数学问题，不应直接颁发识别证书。',
}


def explain_formal_case(case: dict[str, Any]) -> dict[str, Any]:
    """Display only. All formal status and support values come from the Core report."""
    sid = case['scenario_id']
    variant = case['variant']
    status = case['identification']['status']
    title, context, default_question = SETTING_STORIES[sid]
    question = SCENARIO_QUESTIONS[sid].get(variant, default_question).replace('**','')
    if variant != 'point' and variant != 'base' and variant != 'point_e4' and variant != 'different_exposure':
        headline = '对照：' + title
    else:
        headline = title
    states = {key:'confirmed' for key, *_ in CONDITION_NAMES}
    blocked = BLOCKER_CONDITION.get(variant)
    if blocked:
        key, state = blocked
        states[key] = state
        if key != 'support':
            # A blocked theorem does not certify the remaining exact support.
            states['support'] = 'unchecked'
    if status == 'POINT':
        if case['proof']['replay_verified'] is not True:
            raise AssertionError('A POINT display requires the original replay evidence')
        if any(v != 'confirmed' for v in states.values()):
            raise AssertionError('A non-confirmed condition cannot be displayed as POINT')
    elif status == 'NEEDS_INPUT':
        if blocked is None or blocked[1] == 'failed':
            raise AssertionError(f'Unmapped or contradictory NEEDS_INPUT: {case["case_id"]}')
    elif status == 'UNSUPPORTED':
        if blocked is None or blocked[1] != 'failed' and variant != 'query_not_confirmed':
            raise AssertionError(f'Unmapped or contradictory UNSUPPORTED: {case["case_id"]}')
    else:
        raise AssertionError('Unexpected formal status')
    hints = {
        'target': '目标和比较方式已写入本次合成规格',
        'setting': ('观测采用行为的条件分配模型已给出' if sid == 'S6' else '原随机抽签机制已定义'),
        'network': '使用已知固定网络，并明确同伴状态的定义',
        'information': '合成研究使用了获准的总体结果算子，不是由样本自动推出',
        'assumptions': ('已接受本例所需的暴露充分性与局部无混杂前提' if sid == 'S6'
                        else '已接受本例所需的随机化与结果一致性前提'),
        'support': ('已精确核算支持概率 '+str(case['identification']['support'])
                    if status == 'POINT' and isinstance(case['identification']['support'], str)
                    else '每个相关调整层的支持已核验' if status == 'POINT'
                    else '请按当前试验分配规则逐项核对'),
    }
    if sid == 'S5' and states['assumptions'] == 'confirmed':
        hints['assumptions'] = '另已接受“第一阶段名额公告没有额外直接作用”的前提'
    if variant == 'a5_missing' and sid == 'S5':
        hints['assumptions'] = '名额方案公告没有额外直接作用尚未获准'
    if variant == 'a5_missing' and sid == 'S6':
        hints['assumptions'] = '局部无混杂前提尚未被研究者接受'
    if states['information'] == 'missing':
        hints['information'] = BLOCKER_COPY.get(variant, '需要补充正式认可的总体信息')
    if states['assumptions'] in ('missing', 'failed') and variant != 'a5_missing':
        hints['assumptions'] = BLOCKER_COPY.get(variant, '必要因果前提未接受')
    if states['target'] == 'missing':
        hints['target'] = '这项数学问题尚未得到业务负责人确认'
    if states['support'] == 'failed':
        hints['support'] = '目标状态在原处理分配机制下严格零支持'
    if states['support'] == 'unchecked':
        hints['support'] = '前置条件未通过，未形成完整认证结论'
    conditions = [
        {'id':key, 'label':label, 'definition':definition,
         'state':states[key], 'display_status':STATE_LABEL[states[key]],
         'case_specific_explanation': hints[key]}
        for key,label,definition in CONDITION_NAMES
    ]
    no_problem = status == 'POINT'
    cause = (
      '本次合成研究已声明所需条件，正式数学程序通过核验；可以给出总体识别公式，但不是实际销售额或政策收益估计。'
      if no_problem else BLOCKER_COPY.get(variant, '尚缺正式定理所需的研究条件。')
    )
    return {
        'headline': headline,
        'business_context': context,
        'question': question,
        'design_label': DESIGN_NAMES.get(case['inputs']['design'], '指定试验安排'),
        'exposure_label': EXPOSURE_NAMES.get(case['inputs']['exposure'], '已指定的同伴状态'),
        'conditions': conditions,
        'replay_status': '已完成独立数学复核' if case['proof']['replay_verified'] else '尚未颁发数学识别证书',
        'conclusion': cause,
        'next_step_plain': (
            '数学识别公式已经确定；若要估计现实金额，需另行使用有限样本方法。'
            if no_problem else '补充或修订缺失条件，再提交正式数学识别；不能据此断言因果目标普遍不可识别。'
        ),
        'synthetic_provenance': '模拟网络与预先声明的研究条件；并非真实企业已审核结论',
    }


def load_original_nbib_benchmark() -> list[dict[str, Any]]:
    """21 original multi-query business stories: LANGUAGE BENCHMARK ONLY.

    In the supplied NBIB references, none has admitted population A4 and none
    was executed as a formal Core identification query; do not promote results.
    """
    p = ROOT / 'assets/benchmark_assets' / 'benchmarks' / 'network_business_identification'
    cases = json.loads((p / 'gateway_target_only_cases.json').read_text(encoding='utf-8'))
    rows = []
    for case in cases:
        cid = case['case_id']
        gold = json.loads((p / 'gold' / 'references' / f'{cid}.json').read_text(encoding='utf-8'))
        if (gold['A4_population_operator_from_business_files'] != 'NOT_PROVIDED'
                or gold['identification_library_status'] != 'NOT_RUN_ON_THIS_GENERATED_CASE'):
            raise AssertionError(f'NBIB {cid} is not safe to show as an unverified example')
        qs = [v['quote'] for v in case['expected']]
        rows.append({
            'id': cid,
            'title': gold['scenario_title'],
            'industry': gold['industry'],
            'questions': qs,
            'original_description': case['business_question'],
            'study_type': gold.get('assignment_family', '未定'),
            'mathematical_status': 'NOT_FORMALLY_CHECKED',
            'display_status': '业务语义题 · 尚未认证',
            'needs': '需先独立确认业务目标、因果前提和所需总体信息，再运行正式定理。有限样本记录不能直接视为总体信息。',
            'display_conditions': [
                {'state':'missing','label':'业务问题的数学含义','explanation':'题库给出候选问法，尚待负责人确认具体目标'},
                {'state':'confirmed','label':'业务研究背景','explanation':'资料描述了业务场景和处理安排，但不等于科学审核'},
                {'state':'missing','label':'所需总体研究信息','explanation':'原业务题库明确标记没有提供正式总体信息'},
                {'state':'missing','label':'必要因果前提','explanation':'尚未获得本次目标所需的独立科学确认'},
                {'state':'unchecked','label':'支持与正式证书','explanation':'尚未对该业务目标执行正式数学程序与独立复核'},
            ],
        })
    if len(rows) != 21 or len({r['id'] for r in rows}) != 21:
        raise AssertionError('Expected exactly 21 original NBIB business cases')
    return rows


def enhance_payload(core_cases: list[dict[str, Any]]) -> dict[str, Any]:
    return {
      'display_contract': 'cfm-id-v3-supervisor-readability-v1',
      'cases': {c['case_id']:explain_formal_case(c) for c in core_cases},
      'nbib_business_questions': load_original_nbib_benchmark(),
      'condition_legend': [
          {'symbol':'✓','status':'已提供/已确认','meaning':'对应的合成数学输入或正式程序已经核对，不代表真实世界假设已被证明'},
          {'symbol':'？','status':'还需补充','meaning':'当前查询缺少正式准入信息或科学确认'},
          {'symbol':'×','status':'不满足','meaning':'已知当前输入违背所用路线的必要条件'},
          {'symbol':'—','status':'暂未检查','meaning':'因前置条件不足，尚未得到可验证结论'},
      ],
    }
