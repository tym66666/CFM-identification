"""Source-bound choices about optional assumptions, not scientific permission.

This is a reading/adapter contract. It neither proves a theorem nor infers a
stance from prose. Unrecognized assumptions remain in the residual records.
"""
from typing import Literal
from pydantic import Field, model_validator
from .network_policy_reading import Cited

CONDITIONS = ('MEAN_EXPOSURE_SUFFICIENCY','OUTCOME_EXPOSURE_SUFFICIENCY')
RULE = (
    'assumption_choices只记录原文明确谈及的可选假设及采用态度。MEAN_EXPOSURE_SUFFICIENCY'
    '表示固定本人处理和同伴分组后，完整安排的其他差别不再改变总体均值；'
    'OUTCOME_EXPOSURE_SUFFICIENCY表示同一对象在这些完整安排下的潜在结果逐个相同，'
    '不只是平均值相同。按原文选择，不互相替代，也不自动增补另一项采用态度。'
    'NOT_ADOPTED表示本次不依赖该假设，不表示假设被证明为假；UNDECIDED表示采用与否尚未决定；'
    'ASSERTED_FALSE表示原文断言该性质不成立。ADOPTED、PROPOSED、CONFLICTING分别表示采用、拟采用和声明冲突。'
    'scope=CURRENT_STUDY只用于这项选择适用于当前研究，范围不同用OTHER，范围不清用UNKNOWN。'
    '未谈及则列表为空，不凭沉默补态度。每项必须引用说明假设、态度及范围的原文。'
    '已有scientific_statements中的必要条件仍只在那里填写，不重复。'
    '本列表已经表达的采用态度不再复制到additional_restrictions或unresolved；'
    '同段里另有均值相等、上界、单调性等真正约束仍须完整保留在additional_restrictions。'
    '所有状态只是原文读取，不批准科学条件，也不选择定理。')


class AssumptionChoice(Cited):
    condition: Literal['MEAN_EXPOSURE_SUFFICIENCY','OUTCOME_EXPOSURE_SUFFICIENCY']
    status: Literal['ADOPTED', 'PROPOSED', 'NOT_ADOPTED', 'UNDECIDED', 'ASSERTED_FALSE', 'CONFLICTING']
    scope: Literal['CURRENT_STUDY', 'OTHER', 'UNKNOWN'] = Field(description=RULE)

    @model_validator(mode='after')
    def cited(self):
        if not self.source_ids or len(set(self.source_ids)) != len(self.source_ids):
            raise ValueError('ASSUMPTION_CHOICE_REQUIRES_UNIQUE_SOURCES')
        return self


def field_constraints(paths):
    return [dict(field_path='/assumption_choices', description=RULE)] if any(
        p == '' or p.startswith(('/assumption_choices', '/additional_restrictions', '/unresolved'))
        for p in paths) else []


def applicability(choices, *, required_conditions):
    """Compare typed declarations with an adapter's explicit requirements.

    Irrelevant non-adoption/indecision is retained but grants no license. Positive
    or false assertions are real model declarations; this small adapter does not
    compile those extra conditions. No free-text matching or candidate repair.
    """
    missing, blocked, retained = [], [], []
    seen = set()
    for choice in choices:
        identity = (choice.condition, choice.scope)
        if identity in seen or choice.status == 'CONFLICTING':
            blocked.append('CONFLICTING_ASSUMPTION_CHOICES')
        elif choice.scope != 'CURRENT_STUDY':
            missing.append('请说明这项假设选择是否适用于本次研究。')
        elif choice.condition in required_conditions:
            if choice.status == 'UNDECIDED':
                missing.append('当前方法需要的假设尚未决定是否采用：' + choice.condition)
            elif choice.status in ('NOT_ADOPTED', 'ASSERTED_FALSE'):
                blocked.append('REQUIRED_ASSUMPTION_NOT_ADOPTED:' + choice.condition)
            else:
                # Scientific permission must still come from a native review.
                retained.append(dict(condition=choice.condition, status=choice.status, required=True))
        elif choice.status in ('NOT_ADOPTED', 'UNDECIDED'):
            retained.append(dict(condition=choice.condition, status=choice.status, required=False))
        else:
            blocked.append('ADDITIONAL_ASSUMPTION_MODEL_NOT_CONNECTED:' + choice.condition)
        seen.add(identity)
    return dict(missing=missing, blocked=blocked, retained=retained)
