"""Opt-in sample/population field contract; existing wire and parser semantics.

Original samples remain in cited documents. They are not dropped from the case
or reclassified as exact population values. No estimator or math dependency.
"""
import json
from .information_field_rules import RULES

CONTRACT = 'network-source-selections-information-1'

SAMPLE_GUIDANCE = '''有限样本记录、样本均值、估计值或置信区间，只能表示为operator=FINITE_SAMPLE、availability=FINITE_SAMPLE；保留原文明示的outcome_nodes，assignment_cells和signature_cells都为空列表。样本的数值、格子和其他原文细节由source_ids指向的完整原材料保留，不能把它们复制进总体格子字段，也不能因此删去该信息条目或原材料。引用须覆盖实际保留的样本内容及其样本性质。现有格子字段专门表示总体信息，不是所有数值的通用容器。不能为了满足字段规则把样本标签改为总体标签；有冲突就保留原意和疑点，不猜总体值。'''


def make_request(bundle, *, binding, assignment_semantics=None):
    from .network_reading_contract import make_request as previous
    request = previous(bundle, binding=binding, assignment_semantics=assignment_semantics)
    lines = request['system'].splitlines()
    prefix = '同一原文材料的一份均值表尽量保留在一个information条目中'
    matches = [i for i, text in enumerate(lines) if text.startswith(prefix)]
    if len(matches) != 1:
        raise ValueError('READING_BASE_INSTRUCTION_CHANGED')
    lines[matches[0]] = ('同一原文材料的一份总体签名均值表尽量保留在一个information条目中，'
                         '仅该总体表的格子写入signature_cells；不同材料来源不合并。'
                         '样本表不使用总体格子字段。没有要求数值估计并不使政策目标不明确；'
                         '“能否唯一确定”仍是对该目标的识别问题。')
    lines.append(SAMPLE_GUIDANCE)
    body = json.loads(request['user'])
    info = body['output_schema']['$defs']['Information']
    info['allOf'] = [r.schema() for r in RULES]
    info['description'] = SAMPLE_GUIDANCE
    info['properties']['signature_cells']['description'] = (
        '仅NODE_SIGNATURE_MEANS总体格子；非空value仅供EXACT_POPULATION_VALUE。'
        '符号总体格子可保留value=null。样本数据不填此字段，仍用来源引用完整保留。')
    return dict(system='\n'.join(lines), user=json.dumps(body, ensure_ascii=False))
