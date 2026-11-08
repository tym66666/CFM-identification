"""Common file references for existing network readers; native facts stay unchanged."""
from copy import deepcopy
import json
from .network_files import NetworkFileError


def prepare(entry, network):
    if network is None or not entry.get('reader_id', '').startswith('NETWORK_'):
        return entry, None
    wire = deepcopy(entry)
    request = wire['request']; key = 'user' if 'user' in request else 'user_prompt'
    text = request[key].lstrip()
    body, end = json.JSONDecoder().raw_decode(text)
    schema = body['output_schema']
    study = schema['properties']['study']
    if '$ref' in study: study = schema['$defs'][study['$ref'].rsplit('/', 1)[-1]]
    if not {'nodes', 'edges'} <= study.get('properties', {}).keys():
        raise NetworkFileError('NETWORK_READER_STUDY_CONTRACT_MISSING')
    source_ids = [sid for sid, row in body['source_catalog'].items()
                  if row['text'] == network.source()['text']]
    if not source_ids: raise NetworkFileError('NETWORK_FILE_SOURCE_NOT_IN_REQUEST')
    for field in ('nodes', 'edges'):
        previous = study['properties'][field]
        study['properties'][field] = dict(anyOf=[previous, dict(type='object', additionalProperties=False,
            required=['from_network'], properties={'from_network': {'const': network.token}})],
            description='可直接引用本次已导入文件对象，避免重新填写；仍须在study对应来源字段引用网络文件说明。')
    body['network_file_binding'] = dict(reference=network.token, source_ids=source_ids,
        node_count=len(network.nodes), edge_count=len(network.edges),
        instruction='study.nodes和study.edges可填{"from_network":"reference的值"}；程序仅按原文件展开这两个数组。'
                    '不改变graph_kind、edge_list_complete、目标、评价范围或科学态度。'
                    '名单来源放study.source_ids；有network_source_ids字段时，关系来源放该字段，否则放study.source_ids。'
                    '文件完整性只按用户声明读取；不完整/未知不能变成完整。其他原文与文件矛盾仍须报告。',
        scientific_approval=False)
    request[key] = json.dumps(body, ensure_ascii=False) + text[end:]
    return wire, dict(network=network, source_ids=source_ids)


def expand(answer, binding):
    if binding is None: return answer
    if not isinstance(answer, dict) or not isinstance(answer.get('study'), dict): return answer
    result = deepcopy(answer); study = result['study']; net = binding['network']
    for key, expected in (('nodes', list(net.nodes)), ('edges', [list(e) for e in net.edges])):
        value = study.get(key)
        source_key = 'network_source_ids' if key == 'edges' and 'network_source_ids' in study else 'source_ids'
        refs = study.get(source_key)
        if not isinstance(refs, list) or not set(binding['source_ids']).intersection(refs):
            raise NetworkFileError(f'NETWORK_FILE_CITATION_REQUIRED: /study/{source_key}')
        if isinstance(value, dict):
            if value != {'from_network': net.token}:
                raise NetworkFileError(f'NETWORK_REFERENCE_STALE_OR_WRONG: /study/{key}')
            study[key] = expected
        elif key == 'nodes':
            if value != expected: raise NetworkFileError('NETWORK_FILE_NODE_ORDER_MISMATCH: /study/nodes')
        else:
            if (not isinstance(value, list) or len(value) != len(expected)
                    or any(not isinstance(e, list) or len(e) != 2 or not all(isinstance(n, str) for n in e) for e in value)
                    or {frozenset(e) for e in value} != {frozenset(e) for e in expected}):
                raise NetworkFileError('NETWORK_FILE_EDGES_MISMATCH: /study/edges')
    if study.get('graph_kind') != 'SIMPLE_UNDIRECTED':
        raise NetworkFileError('NETWORK_FILE_GRAPH_KIND_MISMATCH: /study/graph_kind')
    complete = {'COMPLETE': True, 'INCOMPLETE': False, 'UNKNOWN': None}[net.completeness]
    if study.get('edge_list_complete') is not complete:
        raise NetworkFileError('NETWORK_FILE_COMPLETENESS_MISMATCH: /study/edge_list_complete')
    return result


def audit_evidence(network, candidate, sources):
    """Recheck file equality for the auditor; not a model's assertion of equality."""
    refs=[sid for sid,row in sources.items() if row['text']==network.source()['text']]
    expand(candidate,dict(network=network,source_ids=refs))
    return dict(reference=network.token,source_ids=refs,
        exact_file_coordinates_checked=['/study/nodes','/study/edges'],
        declaration_states_checked=['/study/graph_kind','/study/edge_list_complete'],
        node_count=len(network.nodes),edge_count=len(network.edges),scientific_approval=False,
        instruction='这是本地程序重新核对候选与上传文件得到的结果，不是模型自述。nodes/edges逐项来自完整原文件，'
                    '源文件行号保存在network_file_manifest；摘要不列全部边。关系的业务含义、时期、是否与其他材料矛盾，'
                    '以及科学条件仍需对照用户原文核对；结构一致不证明用户的完整性声明真实。')
