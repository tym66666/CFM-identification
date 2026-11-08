"""Opt-in A0 wording only; no target inference, defaults or approval rules."""
from typing import Literal

CONTRACT = 'target-summary-1'
READINESS_CONTRACT = 'target-summary-2'
SHAPE_CONTRACT = 'target-summary-3'
Profile = Literal['target-summary-1', 'target-summary-2', 'target-summary-3'] | None

GUIDANCE = '''目标量与评价对象分开记录：target_population回答评价谁；aggregation回答对这些对象的哪个结果量、怎样概括。它不只用于多个对象之间的汇总。
原文明示只评价某一个对象的平均结果或期望时，aggregation保留“该对象的结果均值/期望”并引用原文；不因无需跨对象加权而填UNKNOWN或NOT_APPLICABLE。明确问该对象某事件的发生概率时保留事件及概率口径；若材料明确该结果为该事件的0/1指标，其概率就是该指标的均值。没有明示该对应关系时不得把任意概率替换成某个已有结果的均值。
单个评价对象不等于只给该对象处理。policy_assignment照原文保留全部对象的完整安排；target_population仍只包含所评价的对象，不能把结果平均到所有被处理对象。单对象目标不需另造标准化分布或对照，也不要求用户再说明跨对象等权。
多个评价对象的均值、总和、加权方式分别按原文提取。明确等权或明确给出权重就保留；只列对象名单、只说“整体怎么样”或“有什么影响”不能自动补均值、等权、比较组或事件。单个对象也一样：只有名称而未说结果量，不自动填均值或成功概率，缺项继续UNKNOWN。
概率/期望是所请求的量，不能改写成一次实际结果的预测。变量DAG的干预分布仍按原目标保留，不为填aggregation缩成均值。以上是字段解释，不是案例证据；原文支持的解释用INTERPRETED并引用来源，仍需独立业务审核，不给科学许可或识别公式。'''

DESCRIPTION = ('原文要求的结果量及汇总口径：包括单个对象的结果均值、期望或明确事件概率，'
               '也包括多个对象的均值、总和和明示权重。单对象不需跨对象等权声明；'
               '仅有对象名称而未说结果量仍为UNKNOWN，不推定均值、等权、对照或公式。')

READINESS_GUIDANCE = '''目标字段的“已说明”与“已定值”不是一回事。以下约束semantics中的目标坐标，不改变原始材料：STATED或INTERPRETED的value须给出该字段所问的确定口径，不能只转述它尚未明确、被推迟、存在待选方案或需要别人确认。原文明示“未决定”也是有来源的信息，但不是已经确定的字段值；该字段仍填UNKNOWN，未定原因及已定部分在goal中忠实保留并引用原文。
逐字段判断，不因一个口径未定把全部目标清空。例如评价对象和完整政策已定、汇总口径未定时，前两者继续保留；已知要加权均值却未给权重时，aggregation仍UNKNOWN，goal保留加权均值及权重未定，不能默认等权。列举平均/总和等候选不等于同时请求多个已定目标，不自动拆成已决定的多个queries。
不按否定词判未知。已明确“不取平均，取总和”给出了总和；明确追溯“此前未决定，现已确定”的最终口径可按该原文记录。相反，意向、待审批或暂未选择的方案不能自动变成决定。若材料有未解决冲突，保留冲突，不自行决定优先级。
分开目标与答案：不知道均值数值、尚不能确认是否识别、没有具体百分比，不使一个已明确的目标变成UNKNOWN；也不能因为材料已有某种总体均值，替用户选择要问的量。
若所求结果量仍未定、类别无法准确表达，kind保留UNRESOLVED而非替用户选均值目标；kind为UNRESOLVED/OTHER时，comparator未知就填UNKNOWN，不用NOT_APPLICABLE消除未决性。已明确的单状态政策均值仍可按原合同使用无需比较的NOT_APPLICABLE。这些说明不是额外证据，所有候选仍需独立来源和业务意图审核。'''

READINESS_DESCRIPTION = (DESCRIPTION + ' 已说明“未定”不等于已给出本字段口径：未定、待选、待确认或必要权重缺失时填UNKNOWN，'
                         '在goal保留已定部分和未定原因；不得把这些说明作为STATED/INTERPRETED的值。明确否定平均而指定总和仍是已知总和；目标未知与答案数值未知分开。')

SHAPE_GUIDANCE = '''先保留用户所求的量，再分别记录构成这个量的条件是否齐全。目标种类与条件完备性分开判断；不能因基准未定就把差值改成单个水平，也不能因为提到两种做法就自动创建差值。
对象间存在相互影响时：给定一份安排，只问该安排下明确对象的平均结果，属于FIXED_POLICY_VALUE；明确问两份完整安排的平均结果相差多少，属于TOTAL_EFFECT。这里TOTAL_EFFECT是已有的粗粒度比较类别，精确的两端安排、评价人群和方向留给后续审核；它不是识别方法名或科学结论。只有符合单状态目标时，前文“给定名单是政策价值”才适用。历史安排、未选方案或解释背景不自动构成所问基准。
对有向比较，intervention与policy_assignment记录被评价的新安排/主方案，comparator记录明确要求相减的基准安排；goal和aggregation保留谁减谁及原文汇总口径。“从原安排改为新安排，增加多少”是新减原；“原安排比新安排高多少”是原减新，不按出现顺序排序。只明确相差但未给方向时保留方向未定，不猜正负。全部启用与全部不启用只是完整安排的可能取值，比较不限于这两种。
比较一问不拆成两个无关的水平问题。反过来，明确要分别报告两种安排的水平、未请求相减时，保留两个水平问题；若同时请求水平和差值则分别保留真正请求的量。不能按句子数量、问号或出现方案的数量机械拆题。
明确要比较但尚未指定基准时，比较类别仍可为TOTAL_EFFECT，comparator填UNKNOWN，在goal保留已定目标和缺失原因。只决定主方案、不清楚是要结果水平还是变化量时，kind用UNRESOLVED；不能替用户选目标。某些对象的安排未定时保留其他已定部分及原文限制，不把未知对象设为0，不靠已有设计填满安排。评价对象、期间和权重也逐项读取，不能因希望比较而改成同一人群、同一期间或等权。
本人及同伴状态共同改变、其余安排按各端下原设计条件平均的逐对象总效应属于LOCAL_TOTAL_EFFECT，不是两份完整政策。以上关于TOTAL_EFFECT的说明只覆盖对象网络里的两份完整安排比较。本人处理差异、同伴暴露差异、随机政策、政策选择、变量因果图的干预分布仍按各自原义提取，不为进入已接通的路线改类。自由文本含“比较”“影响”“提高”不单独决定类别；以完整请求为准。缺条件、没有总体信息或科学声明时，保留缺项，不补因果假设，不声称可以识别。'''


def describe_shape(schema, profile: Profile):
    """Only request descriptions change; types, values and parser are untouched."""
    if profile != SHAPE_CONTRACT:
        return
    schema['$defs']['CompactQuery']['properties']['kind']['description'] = (
        '按实际请求的量分类，不按所提方案数或已有资料。对象网络的一份完整安排下均值是FIXED_POLICY_VALUE；'
        '两份完整安排的均值差是TOTAL_EFFECT。明确比较但缺基准仍保留差值类别及UNKNOWN对照；'
        '尚未决定问水平还是差值用UNRESOLVED。类别不是识别证明。')
    for field, text in {
        'comparator': '只有明确请求相减或比较的基准才填；历史背景不是自动对照。差值基准未定用UNKNOWN，不能NOT_APPLICABLE。',
        'policy_assignment': '保留本问题主方案的完整安排；比较中基准另在comparator保留，方向在goal保留。未定部分不默认0，不删除已定部分。',
    }.items():
        schema['$defs']['CompactSemantics']['properties'][field]['description'] = text


def guidance(profile: Profile) -> str:
    if profile is None:
        return ''
    if profile not in (CONTRACT, READINESS_CONTRACT, SHAPE_CONTRACT):
        raise ValueError('UNKNOWN_TARGET_SUMMARY_CONTRACT')
    return ('\n\n' + GUIDANCE + ('\n\n' + READINESS_GUIDANCE if profile != CONTRACT else '')
            + ('\n\n' + SHAPE_GUIDANCE if profile == SHAPE_CONTRACT else ''))


def description(profile: Profile) -> str:
    if profile == CONTRACT:
        return DESCRIPTION
    if profile in (READINESS_CONTRACT, SHAPE_CONTRACT):
        return READINESS_DESCRIPTION
    raise ValueError('UNKNOWN_TARGET_SUMMARY_CONTRACT')
