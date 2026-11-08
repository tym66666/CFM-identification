"""One explicitly budgeted reading repair using public validation issues only.

The caller controls whether to spend a second model call. This is not a network
retry. It never receives a benchmark reference, expected state or science packet.
"""
import json
from . import business_condition_evidence_base as evidence


def make_request(bundle,base_request,rejected_candidate):
    _,receipt=evidence.project_evidence(bundle,rejected_candidate)
    if receipt['passed']:raise ValueError('NO_EVIDENCE_ERROR_TO_REPAIR')
    system,user=base_request;message=json.loads(user)
    message['rejected_reading_candidate']=rejected_candidate
    message['public_contract_validation_issues']=receipt['issues']
    system+='''
上一份阅读候选没有通过公开证据合同检查。请根据原始材料重新阅读并返回同一schema的完整JSON。
校验错误只是程序指出的引用/字段问题，不含标准答案，不是科学审核结果。
核对被指出的条件是否真由当前问题原句表达；若未表达，保留未知，不能用历史分析分组补齐。
同时复核其他字段，保留原文已明确的信息，不为了通过检查把所有字段清空。不要补A4/A5或因果结论。
'''
    return system,json.dumps(message,ensure_ascii=False)
