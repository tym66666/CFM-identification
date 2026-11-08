"""Clarify reported facts and evidence fields, without approving science.

This request-only adapter does not infer a field value, modify a model answer,
grant a scientific license, or call the Identification Core.
"""
from copy import deepcopy
import json


FACT_INSTRUCTION = '''
研究事实与科学审核分开：study 记录材料说了什么，不判断该说法已获认证。
declared_independent 只记录材料是否明确声明本入口分配单位之间的抽签相互独立：明确独立填 true，明确不独立/相关填 false，没有说明或矛盾尚未澄清填 null。
有明确声明就同时给 independence_source；null 时来源也为 null。材料是合成案例、尚未科学审核或当前目标未确定，都不抹去已有声明。
独立性说的是分配抽签，不是结果独立或没有同伴影响；独立市场实例也不等于单位抽签独立。不能从相同概率或概率表自行推出独立。
填写 true 仍只是附来源的阅读候选；A4/A5 的批准由后续独立审核完成，不能填任何科学许可。
各字段独立摘录：某个设计事实未说明，只将该事实及其来源留空，不能连带删除已明确的目标条件、其余安排或相应来源。
同一条目标安排明确适用于多个问题时，每一问都保留这条安排及来源；不能因为某个研究条件未知或暂时无法识别，就把已知业务目标改成未知。
'''

SOURCE_INSTRUCTION = '''
来源位置与原文分开填写：population_source、remaining_source、independence_source、exposure_source 都填 source_catalog 中的来源编号，而不是编号对应的整段文字。
population_source 和 remaining_source 只能选当前 active_goal_document 的编号；study 的来源可选全部材料中的编号。probability_source 仍按其字段要求填写设计表名。
remaining_source 指向当前目标中说明其余安排的来源；remaining_evidence_span 才填写该来源内完整连续原文。peer_evidence 和 intents.quote 也填写原文，不填来源编号。
编号存在只证明能定位材料，不证明理解正确。缺少所需声明时保留 null，不从历史抽签、其他问题或科学识别要求补入。
'''


def clarify_request(request):
    """Return a copied request; annotate existing fields using public sources."""
    result = deepcopy(request)
    message = json.loads(result['user'])
    schema = message['output_schema']
    catalog = list(message.get('source_catalog', {}))
    prefix = message.get('active_goal_document', '') + ':'
    target = [key for key in catalog if key.startswith(prefix)]
    changed_fact = False
    changed_source = False

    def refs(ids, description):
        shape = {'anyOf': [{'type': 'string', 'enum': ids}, {'type': 'null'}]} if ids else {'type': 'null'}
        return {**shape, 'description': description}

    def walk(node):
        nonlocal changed_fact, changed_source
        if isinstance(node, dict):
            props = node.get('properties', {})
            if 'declared_independent' in props:
                props['declared_independent']['description'] = (
                    '材料对本入口分配单位抽签独立性的声明：明确独立 true，明确相关 false，'
                    '未说明或矛盾未澄清 null。记录声明不等于科学批准，合成或未认证不应抹去明确声明。')
                changed_fact = True
            for key in ('population_source', 'remaining_source'):
                if key in props:
                    props[key] = refs(target, '当前目标材料的来源编号；不是原文。缺少所需声明时为 null。')
                    changed_source = True
            for key in ('independence_source', 'exposure_source'):
                if key in props:
                    props[key] = refs(catalog, '支持这一材料声明的 source_catalog 编号；不是原文或科学批准。未声明时为 null。')
                    changed_source = True
            if 'remaining_evidence_span' in props:
                props['remaining_evidence_span']['description'] = 'remaining_source 对应来源中的完整连续原文；保留否定和未确定等词。'
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(schema)
    if not (changed_fact or changed_source):
        return result
    system = result['system']
    system = system.replace(
        'remaining_source引用当前目标中肯定说明其他人按原抽签在满足条件的安排中平均的语句，并用remaining_evidence_span引用完整连续语句。',
        'remaining_source填写当前目标中说明其余安排的来源编号；remaining_evidence_span引用该来源的完整连续语句。')
    system = system.replace(
        'remaining_source引用当前目标中肯定说明其余分配沿原抽签在满足条件的安排中平均的原句。',
        'remaining_source填写当前目标中说明其余安排的来源编号，而不是原句。')
    result['system'] = system + (FACT_INSTRUCTION if changed_fact and FACT_INSTRUCTION not in system else '') + (SOURCE_INSTRUCTION if changed_source and SOURCE_INSTRUCTION not in system else '')
    result['user'] = json.dumps(message, ensure_ascii=False)
    return result
