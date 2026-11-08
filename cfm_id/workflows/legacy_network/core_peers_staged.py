"""Frozen network compatibility implementation extracted from evaluation.

Explicit inputs and independent reviews remain required. No default benchmark
selection, fixture approval, or candidate-model continuation is provided here.
See README.md before extending this historical protocol.
"""
from cfm_id.workflows.legacy_network.core_peers_staged_base import compose_reading
from cfm_id.workflows.legacy_network.core_peers_staged_base import target_request as previous_request


def target_request(bundle,envelope):
    system,user=previous_request(bundle,envelope)
    system+='''
以下区分也适用于原始business_question.md本身：同一段业务文字可能混有历史事实和当前问题，不能把所有文字都当成当前目标的约定。
反例：“上季度我们独立抽签测试了工具”只描述历史，不能支持remaining.rule=原抽签条件平均。
正例：“这次比较时，其他人仍沿原抽签，只在符合上述情形的安排里按原概率取平均”才明确当前目标的安排。
当前目标没有作出这项约定，就填remaining={"rule":"未确定","source":null,"quote":null}；不要引用历史抽签替代它。
同样，只问“核心伙伴用工具是否带动别人”，没有说明几名伙伴或两种比较情形时，不能从历史分组自动补出过半与至多一半；未知neighbors保留不明确。
即使有已绑定研究候选，当前问题的评价平均方式、同伴条件、参考情形、其余分配规则也可能未知；分别保留，等待业务方澄清。
'''
    return system,user
