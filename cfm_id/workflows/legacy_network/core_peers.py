"""Frozen network compatibility implementation extracted from evaluation.

Explicit inputs and independent reviews remain required. No default benchmark
selection, fixture approval, or candidate-model continuation is provided here.
See README.md before extending this historical protocol.
"""
from cfm_id.workflows.legacy_network.core_peers_base import make_request as previous_request


def make_request(bundle):
    system, user = previous_request(bundle)
    system += '''
选最优也要保留原文明确的评价人群。“让全公司满意度最高”明确评价全公司员工，population填全体、ids=[]并引用来源。
尚未决定给谁授权，是待选择的处理名单未知，不是评价人群未知。不能因为本入口不执行优化就清空其他已知字段。
如果全公司怎样汇总没有明确说清，aggregation仍可填不明确；这与已知全体评价范围是两回事。
'''
    return system, user
