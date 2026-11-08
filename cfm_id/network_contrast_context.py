"""Review-only bridge to existing fixed-context contrast mathematics.

No inference from unconditional randomization, text matching, added model
fields or new mathematical assumptions. The native context remains exactly
the independently read study.context, bound into both endpoint certificates.
"""
from copy import deepcopy
from cfm_id_llm import query_conditioning_contract as conditioning


SCIENCE_REQUIREMENTS = {
    'fixed_background_is_pretreatment_common_population':
        '本问限定的是处理前确定的同一背景和研究总体，不是按处理后的结果筛选，也不是跨背景按分布平均。',
    'assignment_law_and_randomization_given_fixed_background':
        '声明的完整分配律及完整向量随机化在该固定背景下成立；不能从无条件随机化自动推出。',
    'a4_information_given_fixed_background':
        '全部可用总体算子、均值和信息完整性声明对应同一固定背景；有限记录或跨背景均值不能替代。',
    'scientific_constraints_given_fixed_background':
        '全部采用的科学条件在该背景下成立；包括一致性、一阶矩，以及实际采用的均值充分性、界限和均值顺序及其全安排作用域。',
}


def prepare(entry, contract, decoded):
    """Expose independently sourced claims; never decide their truth here."""
    context = entry.get('reviewed_target_context')
    if context is None or conditioning.state(context['conditioning_context']) not in ('STATED', 'INTERPRETED'):
        return None
    if contract.target_context is None:
        raise ValueError('CONTRAST_FIXED_BACKGROUND_HANDOFF_REQUIRED')
    studies = {side: decoded['endpoint_readings'][side]['facts']['study'] for side in ('first', 'second')}
    if studies['first'] != studies['second']:
        raise ValueError('COMMON_CONTRAST_BACKGROUND_REQUIRED')
    study = studies['first']
    item = contract.target_context.review_item(context,
        dict(definition=study['context'], source_ids=deepcopy(study['source_ids'])))
    item['scientific_requirements'] = dict(SCIENCE_REQUIREMENTS)
    item['native_context_field'] = 'study.context'
    return item


def bind_single_policy(entry, contract, study, plan):
    """Same fixed-context review for one policy; historical plans stay intact."""
    from .business_dispatch import sha, worksheet
    context=entry.get('reviewed_target_context')
    if (entry.get('reader_id')!='NETWORK_FIXED_POLICY_FACTS' or not context
            or conditioning.state(context['conditioning_context']) not in ('STATED','INTERPRETED')
            or plan.get('state')!='REVIEW_REQUIRED' or 'plan_worksheet' not in plan):
        return plan
    if contract.target_context is None:raise ValueError('POLICY_FIXED_BACKGROUND_HANDOFF_REQUIRED')
    item=contract.target_context.review_item(context,
        dict(definition=study.context,source_ids=deepcopy(study.source_ids)))
    item.update(scientific_requirements=dict(SCIENCE_REQUIREMENTS),native_context_field='study.context')
    result=deepcopy(plan);result['target_conditioning_review']=item
    for row in result['methods']:
        binding=sha(dict(previous=row['reading_worksheet']['binding_sha256'],target_context=item))
        row['reading_worksheet']=worksheet(binding,(*row['reading_worksheet']['decisions'],item['decision']))
        row['science_worksheet']=worksheet(binding,(*row['science_worksheet']['decisions'],*SCIENCE_REQUIREMENTS))
    binding=sha(dict(previous=plan['plan_sha256'],target_context=item,methods=result['methods']))
    result.update(plan_sha256=binding,plan_worksheet=worksheet(binding,plan['plan_worksheet']['decisions']))
    return result
