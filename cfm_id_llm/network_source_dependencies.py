"""Opt-in source dependencies, shared by initial reading and explicit recheck.

No source selection, entailment decision, answer rewriting or new wire fields.
Rules derive from the actual public schema, including contrast endpoints.
"""
from copy import deepcopy
import json

CONTRACT = 'network-source-selections-dependencies-1'
INSTRUCTION = '''本轮补充指代与编码的来源责任：一组引用既支持声明，也支持把声明中的指代展开为当前字段值所用的定义。例如声明说全部对象，而字段列出具体名字，须同时引用该声明和明确这些对象的名册；名称已在同一段中完整给出时，无需额外引用。不是固定要求某个文件名，而是核对所选原文是否共同包含所写的事实。
将业务状态写成代码时，引用选择该状态的目标原文和支持该代码含义的定义；只有分组定义不能证明用户要比较哪两端。选择某一同伴状态和列出全部已声明状态是不同任务。原文未确定状态、名单或采用态度时保留未知，不依据代码习惯补值。
同一字段需要多份材料时在本字段列出相关来源；其他字段的引用不自动提供这些依赖。source_dependency_contract逐位置给出相同的公开规则，不能作为业务证据。不粘贴整份目录，不输出自评，不删去真实限制或拒绝。'''

NAMES = '字段展开了具体对象名称时，同时覆盖对象范围声明与用于展开的名册；只写“全体/完整名单”的段落不单独支持这些名字。若一段已同时给出范围和名字，仅该段即可。'
ARMS = '本端引用须覆盖用户选定的本人状态和同伴条件，以及所用编码的定义。分组定义不代替本题比较问题，别端或父记录的引用不代替本端。'
TARGET = '本记录的引用覆盖比较目的和方向、具体评价对象及汇总方式；不能用子记录或仅有名册的引用代替比较目的。'


def _rules(props):
    rules=[]
    if any(k in props for k in ('nodes','probabilities','outcome_nodes','population','assignment','groups','clusters','core_collaborators')):
        rules.append(NAMES)
    if 'own' in props and 'exposure' in props:rules.append(ARMS)
    if 'operation' in props or ('population' in props and 'aggregation' in props):rules.append(TARGET)
    return rules


def _annotate(schema):
    schema=deepcopy(schema)
    for node in [schema,*schema.get('$defs',{}).values()]:
        props=node.get('properties',{})
        if 'source_ids' not in props:continue
        for rule in _rules(props):
            description=props['source_ids'].get('description','')
            if rule not in description:props['source_ids']['description']=(description+' '+rule).strip()
    return schema


def _schema_rules(schema):
    rows=[];definitions=schema.get('$defs',{})
    def walk(node,path,ancestors=()):
        if '$ref' in node:
            ref=node['$ref']
            if not ref.startswith('#/$defs/') or ref[8:] not in definitions:raise ValueError('LOCAL_DEPENDENCY_SCHEMA_REQUIRED')
            if ref in ancestors:raise ValueError('ACYCLIC_DEPENDENCY_SCHEMA_REQUIRED')
            return walk(definitions[ref[8:]],path,(*ancestors,ref))
        props=node.get('properties',{})
        for key,value in props.items():
            child=path+'/'+key
            if key.endswith('source_ids') and value.get('description'):
                rows.append(dict(field_path=child,description=value['description']))
            else:walk(value,child,ancestors)
        if 'items' in node:walk(node['items'],path+'/*',ancestors)
        for option in node.get('anyOf',[]):walk(option,path,ancestors)
    walk(schema,'')
    return rows


def apply(request):
    body=json.loads(request['user']);schema=_annotate(body['output_schema'])
    body['output_schema']=schema
    body['source_dependency_contract']=dict(version=CONTRACT,field_constraints=_schema_rules(schema),
        establishes_entailment=False,repairs_model_citations=False)
    system=request['system']
    if INSTRUCTION not in system:system+='\n'+INSTRUCTION
    return dict(system=system,user=json.dumps(body,ensure_ascii=False))


def field_constraints(paths,*,request):
    body=json.JSONDecoder().raw_decode(request['user'])[0]
    if body.get('source_dependency_contract',{}).get('version')!=CONTRACT:
        raise ValueError('SOURCE_DEPENDENCY_REQUEST_REQUIRED')
    # Recompute from the public schema, never from private feedback or gold.
    rows=_schema_rules(body['output_schema'])
    def normalized(path):return '/'.join('*' if v.isdigit() else v for v in path.split('/'))
    return [r for r in rows if any(q=='' or normalized(q)==r['field_path'] or
        normalized(q).startswith(r['field_path']+'/') or r['field_path'].startswith(normalized(q)+'/') for q in paths)]


def make_request(bundle,*,binding,assignment_semantics=None):
    from .network_remainder_contract import make_request as previous
    return apply(previous(bundle,binding=binding,assignment_semantics=assignment_semantics))
