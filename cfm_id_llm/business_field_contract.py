"""Shared compact field roles, legacy wire descriptions and review boundaries.

No case matching, natural-language classifier, theorem selection or approval.
Legacy descriptions remain byte-identical; richer definitions serve reviewers.
"""
from dataclasses import asdict, dataclass

VERSION = 'business-field-contract-1'


@dataclass(frozen=True)
class Field:
    name: str
    meaning: str
    excludes: str
    section: str = 'common'
    shape: str = 'claim'
    allows_inapplicable: bool = False
    wire_description: str | None = None
    question: str | None = None


COMMON = (
    Field('analysis_unit', '一次结果对应的研究单位及其名称范围。', '评价子集不代替完整研究单位集合。'),
    Field('treatment', '处理行动及原文给出的取值编码。', '目标安排不等于历史分配机制。'),
    Field('outcome', '结果变量、事件定义和取值编码。', '样本统计不等于结果定义或总体均值。'),
    Field('assignment_family', '依历史分配规则提出的设计类别。', '全员未来启用不证明历史随机化；未给机制用UNRESOLVED。', shape='enum'),
    Field('assignment_law', '历史共同分配机制及其概率、名额等规则。', '目标政策、预算和独立结果不证明历史分配。', wire_description='历史处理分配机制；目标直接设定某变量不是历史机制。未提供则UNKNOWN，assignment_family同时为UNRESOLVED。'),
    Field('unit_network', '人、门店等研究对象之间的关系或相互影响。', '变量因果箭头不能替代对象关系；未描述不等于无边。', wire_description='研究对象之间的关系网络；变量因果图不能填这里。没有描述则UNKNOWN。'),
    Field('variable_causal_graph', '明确以变量为节点声明的因果关系；提取陈述，不批准图的科学真实性。', '对象间影响、随机化或均值暴露充分性本身不声明变量DAG；不能自行添因果箭头。', wire_description='原文明示的变量因果箭头/关系；仅有随机化、条件独立或均值暴露充分性不构成变量DAG，未描述则UNKNOWN。'),
    Field('exposure_mapping', '原文定义的同伴处理如何汇总为暴露。', '伙伴集合未必给出完整映射；映射定义不蕴含均值充分性。'),
    Field('network_pretreatment_status', '网络何时确定以及研究期间是否变化的材料陈述。', '陈述处理前固定不等于科学条件已批准。'),
    Field('temporal_structure', '观测、分配及目标的时间结构，分别标明。', '历史观测期不能替代目标时点。'),
    Field('sample_data_description', '原文确实提供的有限样本记录或统计。', '符号总体信息不归这里，有限样本不升级为精确总体。', wire_description='个体样本、样本记录或样本统计；符号总体信息不填这里。'),
    Field('available_information', '原文声称可用的总体分布、总体均值或相应信息。', '没有提供总体信息不是一个可用信息值，应UNKNOWN；否定/缺失原因保留在原文。来源陈述也不等于A4许可。', wire_description='原文声明已知的总体分布/均值等；没有就UNKNOWN。它不是目标平均分布。'),
    Field('covariates', '原文给出的协变量及可观测性等说明。', '不能从变量名称自动批准调整集或无混杂。', shape='claims'),
)

SEMANTICS = (
    Field('target_population', '本子问题要评价哪些对象。', '不能扩成所有接受处理的对象。', section='semantics', question='希望对哪些对象评价这个结果？'),
    Field('intervention', '本子问题要评价的具体行动或干预取值。', '不自动补完整比较，也不是历史抽签规则。', section='semantics', question='希望评价对象在什么具体做法或状态下的结果？'),
    Field('comparator', '明确请求比较的另一个状态。', '单状态目标不另造对照；是否不适用由目标类型约束。', section='semantics', allows_inapplicable=True, question='希望与哪一种具体做法或状态比较？'),
    Field('neighbor_exposure', '目标要求固定或平均的同伴处理口径。', '不忽略干扰，不自行推算目标下暴露并称为原文明示。', section='semantics', question='比较本人状态时同伴状态如何保持或平均；若比较同伴影响，具体比较哪两种状态？'),
    Field('aggregation', '目标结果量及汇总方式、权重；也包括单对象的明确均值/概率。', '尚未决定的权重不是已知值，保留UNKNOWN；不写识别求解公式。', section='semantics', wire_description='目标明确要求的汇总运算和权重，例如全体等权均值；不写识别公式。未指定就UNKNOWN。', question='整体结果按什么方式汇总，各对象是否等权？'),
    Field('time_horizon', '目标评价的时点或时间段。', '不能用历史观测时间补未来时点。', section='semantics', question='希望评价实施后的哪个时点或时间段？'),
    Field('policy_assignment', '完整指定名单或随机政策；选择政策时保留约束。', '评价子集不缩减完整处理安排；编码/名单若写入value也须有引用。', section='semantics', allows_inapplicable=True, question='希望评价哪项分配规则，或在什么约束下选择名单？'),
    Field('standardization_distribution', '目标明确要求对协变量取值、同伴状态或其余完整安排按什么分布平均。', '跨研究对象的等权或加权汇总只放aggregation，不在此重复；未另行指定分布时UNKNOWN。不能从已有总体分布或历史抽签分布反推目标，不改变已指定权重。', section='semantics', wire_description='仅填目标明确要求按某分布平均的口径；已有联合总体信息、指定控制变量均不填这里。未指定就UNKNOWN。'),
)

QUERY = (
    Field('goal', '完整保留该业务子问题，包括已定部分及尚未决定的原因。', '不能把未定原因移作已定坐标或自行分拆成新目标。', section='query'),
    Field('kind', '用户请求的量的候选类别。', '类别不是定理选择，不能按可用资料的量代替所问目标。', section='query', shape='enum'),
)


def fields(section):
    return {'common': COMMON, 'semantics': SEMANTICS, 'query': QUERY}[section]


def assert_coverage(common, semantics, query):
    for section, actual in [('common',common),('semantics',semantics),('query',query)]:
        names = [f.name for f in fields(section)]
        if len(names) != len(set(names)) or set(names) != set(actual):
            raise ValueError('BUSINESS_FIELD_CONTRACT_SCHEMA_DRIFT')


def definitions():
    return {s: [asdict(f) for f in fields(s)] for s in ('common', 'query', 'semantics')}


def descriptions(section):
    return {f.name:f.wire_description for f in fields(section) if f.wire_description is not None}


def describe_field_roles(schema):
    """Opt-in request descriptions from the same definitions used by reviewers.

    Keep existing protocol descriptions, schema types and review definitions
    intact. This supplies meaning to the model; it does not classify text.
    """
    for section, model in (('common', 'CompactCommon'), ('query', 'CompactQuery'),
                           ('semantics', 'CompactSemantics')):
        props = schema['$defs'][model]['properties']
        for field in fields(section):
            role = '字段职责：' + field.meaning + ' 边界：' + field.excludes
            if field.shape == 'enum':
                role += ' 格式为Schema枚举字符串，不是claim对象，不携带state/value/refs。'
            elif field.shape == 'claims':
                role += ' 逐项列出实际变量及其说明；没有相应变量时用空列表，不把整份资料名称当作一个变量。'
            else:
                role += ' 未提供本字段所问的内容时用UNKNOWN；相关背景或缺失说明不能冒充本字段已知值。'
            prior = props[field.name].get('description', '')
            props[field.name]['description'] = (prior + ' ' + role).strip()


def questions():
    return {f.name:f.question for f in SEMANTICS if f.question is not None}


def inapplicable_fields():
    # Target-specific restrictions remain in audit_compact, unchanged.
    return {f.name for f in SEMANTICS if f.allows_inapplicable}


STATE_RULES = {
    'STATED': '有来源的确定字段值；来源说尚未决定/没有提供，不等于已给出该字段值。',
    'INTERPRETED': '来源支持的解释，仍须独立语义审核；不是科学批准。',
    'UNKNOWN': '候选未给出该字段值，不证明原文一定缺失；须区分漏读、未定和未提供。',
    'NOT_APPLICABLE': '只在comparator/policy_assignment且目标允许时使用；不能替未知或缺条件。',
}
EVIDENCE_RULE = '逐字段核对模型实际选中的原文是否支持整个value，包括对象名单、编码、时点及限定。审核者另查到的原文不能自动补入模型引用，也不能借其他字段引用宣布本字段引用完整。'
