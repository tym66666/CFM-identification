"""Public source-review responsibilities; no prompts or prose classification."""

DIMENSIONS = ('field_role', 'value_state', 'source_coverage')
EVIDENCE_RULE = ('本记录的直接引用必须支持它实际声明的内容。对象顺序、编码或指代定义若分散在别处，'
    '须有本记录的引用或当前协议显式声明的definition_refs；不得借父记录、其他字段或审核人补列的来源修复候选。'
    '直接主张与定义依赖分别展示；定义不能代替政策选择、概率或信息覆盖声明。编号有效不证明语义正确。')
ROLES = {
    'instrument': '资格Z及其二元编码；不得与实际参加D混淆。',
    'treatment': '实际参加D及其二元编码；不是资格Z。',
    'outcome': '二元结果Y、编码、观测期间；不是结果效应符号的假设。',
    'study': '研究对象、关系网络、变量定义和结果期间背景；不把普通场景自动当作目标条件。',
    'assignment': '历史分配机制及其参数；不等于目标政策，也不产生科学许可。',
    'regime': '历史采用方式的类别；观察性或随机化标签本身不批准交换性。',
    'first_stage_exclusion': 'D6第一阶段配额方案没有额外结果作用的科学声明及采用状态；设计标签不能授予该条件。',
    'exposure': '原文明示的同伴暴露定义；定义不产生均值暴露充分性。',
    'conditioning': '本问的条件及所指背景；不与跨层平均、评价名单或普通资料说明混淆。',
    'target': '本问政策、比较两端、评价名单、聚合和方向；不能从名册或编码表猜目标。',
    'assumptions': '原文明确采用、拟采用、否定或未定的科学声明；读取审核不批准其真实性。',
    'information': '逐来源保留信息类型、可用状态和实际范围；有限记录不能变为总体算子，资料说明不能充当额外数学限制。',
    'bounded_model': '明确给定的界限及有限模型声明；科学界限与样本区间、总体信息不同。',
    'mean_order_model': '逐对象本人和同伴的均值顺序、适用范围、采用意向及完整模型声明；未说明不等于不假定，每次结果不自动弱化为均值条件。',
    'additional_restrictions': '尚未由专门字段完整表达的真实限制、额外总体信息或指定方法。普通资料说明、已完整表达的条件重复、缺项或识别助手职责不应冒充新限制；错放需重读，不在程序中删除或降格。',
    'unresolved': '真实缺项、未决定、冲突或读取疑点；区分材料缺失与读错。对应字段仍须保留未知，不能当作科学否定或新增约束。',
}


def role_for(path):
    parts = path.split('/')[1:]
    root = parts[0] if parts else ''
    if root == 'information' and 'data_description' in parts:
        from .network_policy_reading import DATA_DESCRIPTION_RULE
        return DATA_DESCRIPTION_RULE
    if 'assignment_masses' in parts:
        return '本行的完整使用向量和概率；引用同时覆盖行值与用来解释坐标的对象顺序、编码。表头不是概率值的来源。'
    return ROLES.get(root, '按当前读取Schema核对本字段的原文含义、状态、范围及引用；不补造事实或科学许可。')


def public_contract(record_paths):
    """Export the existing review rules; never infer sources or alter a reading.

    Readers opt in explicitly. Existing review worksheets and legacy requests
    keep their bindings. Definition links require a separately declared wire
    contract; publishing this rule alone does not enable such links.
    """
    return dict(version='fact-source-review-rules-1', evidence_rule=EVIDENCE_RULE,
        field_roles={path:role_for(path) for path in record_paths},
        scientific_approval=False, automatic_repair=False)
