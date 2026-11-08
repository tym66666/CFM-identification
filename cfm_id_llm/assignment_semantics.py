"""Shared reading vocabulary, not a classifier, probability compiler or approval.

None preserves the historical request byte for byte. Persist the profile on
the intake so old answers/reviews cannot silently acquire new instructions.
"""
from typing import Literal

VERSION = 'joint-assignment-law-1'
Profile = Literal['joint-assignment-law-1'] | None

GUIDANCE = '''分配方式的共同语义（只帮助阅读，不授予科学许可）：
先区分历史试点的完整处理名单如何产生、一次实际名单、未来要评价的政策。后两项不能补充历史分配机制。网络中结果可能相互影响，与处理如何抽签是不同问题。
均匀固定名额：在明确的N个对象中，每次恰好m个接受处理，全部大小为m的名单都等可能。每个完整名单的概率是1/C(N,m)，其余名单概率为0；这已经完整描述联合分配律，不要求另外提供逐对象概率，也不要求各对象独立抽签。把全部大小为m的组合列为选项再等概率选一个，含义相同。A0名称COMPLETE_RANDOMIZATION与专门事实名称UNIFORM_FIXED_QUOTA对应这一含义。
逐对象独立抽签：对象之间独立地产生处理，概率可以相同也可以不同；不固定每次处理总数。A0与专门事实都用INDEPENDENT_BERNOULLI。原文明示独立抽签可填写此类别；未给概率时probabilities保留null，不能估计。不能把一次实际恰好m人接受处理当成固定名额设计。
固定人数本身不意味着所有同人数名单等概率。明确的非均匀固定人数、重抽直到满足额外条件等机制，若现有类别无法表达，保留完整机制并用OTHER，不改写为均匀固定名额。只知道人数上限、平均人数或固定人数而未说明选择方式，类别保持未决：A0为UNRESOLVED，专门事实为UNKNOWN，不猜概率。
分组分别独立、均匀抽固定名额：A0用STRATIFIED_FIXED_QUOTAS；专门事实的两个组用TWO_GROUP_FIXED_QUOTA，多个组用MULTI_GROUP_FIXED_QUOTA，保留groups和treated_quotas。即使总人数固定，也不能忽略分组限制而当成全体均匀抽签。整簇一起处理、不同簇独立抽签：A0用CLUSTER_RANDOMIZATION，专门事实用CLUSTER_BERNOULLI，保留clusters和cluster_probabilities；其他簇随机化仍按实际规则，不能一概当成独立簇抽签。
两阶段名额混合：先按已知联合概率抽各组名额向量，再给定方案在各组独立均匀抽人。A0目前用OTHER并完整保留两阶段原文，专门事实可用TWO_STAGE_QUOTA_MIXTURE，保留groups、quota_profiles、profile_probabilities。A0粗类别OTHER不阻止后续细读，不能据此直接判数学库未覆盖。不能只取其中一阶段或以平均名额替代；第一阶段方案没有直接结果影响属于另外的科学声明，不能由设计推定。
明确的自选、按业务决策等非实验安排，A0为OBSERVATIONAL；没有描述历史机制不等于观察性设计，保持UNRESOLVED。OTHER表示明确知道当前枚举无法表达的机制，不是未知信息的替代。专门事实入口的OTHER也不表示已经证明不可识别。
上述字典不是案例事实、证据来源或假设批准。不要从类别自动填随机化独立性、均值暴露充分性、总体信息或任何科学许可；事实、未知与额外限制仍须逐项引用原文。'''


def guidance(profile: Profile) -> str:
    if profile is None:
        return ''
    if profile != VERSION:
        raise ValueError('UNKNOWN_ASSIGNMENT_SEMANTICS_PROFILE')
    return '\n\n' + GUIDANCE


def describe(schema, *, specialist=False):
    """Describe existing fields only; never change the candidate wire schema."""
    if specialist:
        props = schema['$defs']['Assignment']['properties']
        props['kind']['description'] = '按共同分配语义读历史机制。全体固定大小名单等概率足以填UNIFORM_FIXED_QUOTA；不要求逐对象概率。'
        props['fixed_count']['description'] = '明确的全体均匀固定名额m；人数上限、样本实现、分组名额不能替代。'
        props['probabilities']['description'] = '仅逐对象独立抽签的已知概率。联合均匀固定名额用fixed_count，probabilities为null。'
        descriptions = {
            'groups':'处理前完整不交组，列出组内对象；与逐组名额或名额向量的位置一致。',
            'treated_quotas':'D3/D5逐组固定名额；不可只填写总人数。',
            'clusters':'D4处理前完整不交簇；同簇对象一起处理。',
            'cluster_probabilities':'与clusters逐簇对应的独立抽签概率；不是逐对象独立概率。',
            'quota_profiles':'D6第一阶段所有可能的完整逐组名额向量；不是平均名额。',
            'profile_probabilities':'与quota_profiles逐项对应、严格为正且精确求和为1的联合方案概率。',
        }
        for name,text in descriptions.items():
            props[name]['description']=text+' 未给出时为null，不自动补全。'
    else:
        props = schema['$defs']['CompactCommon']['properties']
        props['assignment_family']['description'] = '按共同分配语义分类历史机制。全体固定大小名单等概率是COMPLETE_RANDOMIZATION；固定人数但选择方式未知为UNRESOLVED；明确非均匀机制为OTHER。'
