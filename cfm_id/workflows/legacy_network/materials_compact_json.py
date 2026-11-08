"""Frozen network compatibility implementation extracted from evaluation.

Explicit inputs and independent reviews remain required. No default benchmark
selection, fixture approval, or candidate-model continuation is provided here.
See README.md before extending this historical protocol.
"""
import cfm_id.workflows.legacy_network.materials_target_precedence as previous


VERSION = 'business-materials-v0.24.1'


SYSTEM = previous.SYSTEM + '\n序列化要求：输出一行紧凑JSON，不缩进、不添加用于排版的空格或换行，不用Markdown代码围栏。所有必需字段仍必须保留，不能为缩短输出省略字段或条件。\n'


def make_request(value):
    _, user = previous.make_request(value)
    return SYSTEM, user


def project(value, raw):
    return previous.project(value, raw)


def evaluate_draft(value, raw, packet, *, synthetic_protocol_selected=False):
    result = previous.evaluate_draft(value, raw, packet, synthetic_protocol_selected=synthetic_protocol_selected)
    result['version'] = VERSION
    return result
