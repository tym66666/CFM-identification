"""Experimental opt-in prompt: preserve skill-1's schema and validators.

This profile is not the default and never grants review or scientific approval.
"""
from .target_first_skill import *  # reuse the exact established response contract
from . import target_first_skill as _baseline

CONTRACT = 'target-first-skill-guarded-1'
ADDITION = ('补充检查：变量因果图仅指变量之间明确的因果箭头；随机化、潜在结果独立、'
    '一致性、合作网络结构或均值充分性都不是变量因果图。原文没有变量图时该字段填UNKNOWN。'
    '每个字段的引用必须支持该字段的完整值：如果值列出具体网点名单或0/1编码，'
    '引用明确列出名单或编码的来源；不要依赖其他字段的引用。'
    '对所有材料逐项核对，业务问题与附件对目标政策相反且未协调时，不要擅自断言某一方案已确定；'
    '遵循既有合同表达不确定或冲突，不补造事实，不批准假设。')


def system_prompt(**kwargs):
    return _baseline.system_prompt(**kwargs)+'\n\n'+ADDITION
