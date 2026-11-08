"""Opt-in local field explanations; identical inline wire and review semantics."""
from . import compact_inline_evidence_contract as inline

CONTRACT = 'inline-target-roles-1'
EXTRA_STATE_RULES = inline.EXTRA_STATE_RULES
project = inline.project
apply_gate = inline.apply_gate
review_items = inline.review_items

# These are universal field questions, not business-specific answers. They
# affect requests only: parsing never classifies natural language or fills gaps.
ROLE_NOTES = {
    ('ComparisonOrder', 'operation'): (
        '只回答用户要求哪一端减哪一端，与两端内容是否齐全分别判断。'
        '主方案相对基准的增加量=主方案减基准；主方案相对基准的减少量=基准减主方案。'
        '即使基准名单/规则尚未选定，只要增加或减少的方向明确，仍保留这个运算；'
        '只把未定内容留在comparator，不能因此用UNSPECIFIED。'
        'UNSPECIFIED表示所求方向本身未定，不表示效应数值、正负或识别结果未知。'
        '两端都明确但仅要差额且方向未给时才保留方向未定。'
        '单方案水平或分别报告水平用NOT_APPLICABLE。按完整问题含义判断，不按单个增减词判断。'),
    ('CompactSemantics', 'comparator'): (
        '只回答拿主方案与什么具体安排/状态比较，不负责决定减法方向。'
        '要比较且原文明示基准未选定时为MISSING并引用该声明；没有给出且未明示缺失则UNKNOWN。'
        '不能因为基准未知就删除已明确的增加/减少方向，也不能把尚未决定改成全不使用。'),
    ('CompactCommon', 'exposure_mapping'): (
        '回答如何把合作对象的处理情况归并：计数、比例、至少一个等规则，以及无合作对象的约定。'
        '这是定义，不回答本次目标要固定哪一档或按哪种安排平均，也不自动声明只看汇总值就够。'),
    ('CompactSemantics', 'neighbor_exposure'): (
        '只回答本次问题对同伴处理明确要求固定什么、比较什么，或按什么规则平均。'
        '原文只是定义计数/分档，未指定本次采用哪个状态时，不能抄定义来填这个字段。'
        '原文只给完整政策名单时，在policy_assignment保留名单；本字段未另给口径则UNKNOWN，'
        '不要为了填字段自行沿网络计算，再标为STATED。UNKNOWN不意味着无干扰。'
        '若问题确实明确指定同伴都不用、至少一位使用、比较两种同伴状态或按某分配规则平均，'
        '必须在这里忠实保留并引用问题，不能一律UNKNOWN。'
        '原文明示尚未决定同伴条件时用MISSING及该声明，不能用映射定义替代缺项。'),
    ('CompactSemantics', 'policy_assignment'): (
        '完整名单或共同分配规则放在这里，保留全部对象的已定和未定安排。'
        '不要把它当成目标同伴状态的重复字段；逐个比较本人状态、同时给出同伴条件不等于'
        '给全体对象同时实施一份完整政策，不能自行补全名单。'),
}


def describe(schema):
    guidance = inline.describe(schema)
    for (model, name), text in ROLE_NOTES.items():
        prop = schema['$defs'][model]['properties'][name]
        prop['description'] = (prop.get('description', '') + ' 本字段的判断范围：' + text).strip()
    return guidance + (
        '\n先分别核对目标运算、主方案内容、基准内容，不把任一项未知扩散到其他已知项。'
        '同伴汇总定义与本题的同伴条件分别核对；细则见对应Schema字段。'
        '这些说明不是新业务事实，不代替来源或科学审核。')
