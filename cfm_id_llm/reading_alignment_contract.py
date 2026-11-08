"""Opt-in comparison and statement-scope guidance, never semantic repair."""
import json
from . import network_source_dependencies as dependencies

A0_CONTRACT = 'inline-unified-contract-11'
NETWORK_CONTRACT = 'network-source-selections-alignment-1'
DIRECTION = ('按本次实际填入的intervention和comparator解释operation，不把intervention自动理解为使用/1、'
    'comparator自动理解为不使用/0。把operation中的两端名称替换成本次已填的业务状态，再与原问的减法核对。'
    '明确“X减Y”的原文决定方向；不能被附近的增加、减少、改善等词覆盖。'
    '没有明确算式时再按用户请求的增量或减少量理解，确实未定则保留UNSPECIFIED。'
    '这只是核对，不另造基准、不交换两端、不因结果预期好坏把差值变成正数。')
A0_GUIDANCE = DIRECTION + (' 每个字段先用其自己的内容核对来源：若表达新增了名字、编码、时期或两端条件，'
    '该字段引用须同时覆盖这些定义和本问选择；仅重复已有字段内容不会自动继承它的引用。'
    '只输出原Schema要求的候选，不添加计算过程、自评或审核结论。')
SCIENCE = ('逐项读取本科学条件自己的采用态度，先找该条件对应的主张，再判断修饰它的采用/拟采用/未决定/拒绝。'
    '同段不同条件可有不同状态，不能把段首或段尾的态度复制给全段。'
    '“接受/已采用”对应ADOPTED，明确计划采用为PROPOSED，尚未决定为UNDECIDED，拒绝采用为NOT_ADOPTED；'
    '同一条件确有冲突才用CONFLICTING，材料没提才用NOT_STATED。'
    '一段若同时支持多个条件可分别引用，但同一引用不意味着状态相同。所有状态仍只是原文声明，不能授予科学许可。')
FACT_GUIDANCE = SCIENCE + (' 比较目标的first/second按实际业务状态和FIRST_MINUS_SECOND核对原问，不按处理编码大小排序。'
    '逐字段把自己写出的具体名字、状态编码与其来源对照：比较问题说明选了哪端，名册/定义说明展开成什么。'
    '所需依据在不同材料中时引用须共同覆盖；资料确实没有说明则保留未知，不补引用或删除真实限制。')


def _status_rules(schema):
    rows=[];defs=schema.get('$defs',{})
    def walk(node,path,ancestors=()):
        if '$ref' in node:
            ref=node['$ref']
            if not ref.startswith('#/$defs/') or ref in ancestors:raise ValueError('LOCAL_ACYCLIC_SCHEMA_REQUIRED')
            return walk(defs[ref[8:]],path,(*ancestors,ref))
        for key,value in node.get('properties',{}).items():
            if key=='status' and 'ADOPTED' in value.get('enum',[]):
                rows.append(dict(field_path=path+'/status',description=value['description']))
            else:walk(value,path+'/'+key,ancestors)
        if 'items' in node:walk(node['items'],path+'/*',ancestors)
        for value in node.get('anyOf',[]):walk(value,path,ancestors)
    walk(schema,'')
    return rows


def apply(request):
    request=dependencies.apply(request)
    body=json.loads(request['user']);schema=body['output_schema']
    for node in [schema,*schema.get('$defs',{}).values()]:
        status=node.get('properties',{}).get('status',{})
        if 'ADOPTED' in status.get('enum',[]) and SCIENCE not in status.get('description',''):
            status['description']=(status.get('description','')+' '+SCIENCE).strip()
    body['reading_alignment_contract']=dict(version=NETWORK_CONTRACT,
        field_constraints=_status_rules(schema),automatic_repair=False,scientific_approval=False)
    system=request['system']
    if FACT_GUIDANCE not in system:system+='\n'+FACT_GUIDANCE
    return dict(system=system,user=json.dumps(body,ensure_ascii=False))


def field_constraints(paths,*,request):
    body=json.JSONDecoder().raw_decode(request['user'])[0]
    if body.get('reading_alignment_contract',{}).get('version')!=NETWORK_CONTRACT:
        raise ValueError('ALIGNMENT_REQUEST_REQUIRED')
    rows=dependencies.field_constraints(paths,request=request)
    def normal(path):return '/'.join('*' if p.isdigit() else p for p in path.split('/'))
    return rows+[r for r in _status_rules(body['output_schema']) if any(q=='' or normal(q)==r['field_path'] or
        normal(q).startswith(r['field_path']+'/') or r['field_path'].startswith(normal(q)+'/') for q in paths)]


def make_request(bundle,*,binding,assignment_semantics=None):
    return apply(dependencies.make_request(bundle,binding=binding,assignment_semantics=assignment_semantics))
