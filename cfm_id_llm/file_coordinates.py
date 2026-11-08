"""Compact coordinates from validated finite graphs; no scientific inference."""
from copy import deepcopy
import json

class CoordinateError(ValueError):
    pass


def prepare_for_graph(entry,nodes,edges):
    if len(nodes)<32 or entry.get('reader_id')!='NETWORK_RANDOMIZED_EFFECT_FACTS':
        return entry,None
    user = entry['request']['user'].lstrip()
    try:
        body, end = json.JSONDecoder().raw_decode(user)
        definitions = body['output_schema']['$defs']
        study = definitions['Study']['properties']
        info = definitions['EffectInformation']['properties']
    except (KeyError, ValueError, TypeError):
        return entry, None
    observed = {tuple(sorted(e)) for e in edges}
    tables = {}
    for sid, source in body['source_catalog'].items():
        text = source['text']
        start = text.find('[[')
        if start<0 or text.count('[[')!=1:
            continue
        try:
            rows, _ = json.JSONDecoder().raw_decode(text[start:])
        except ValueError:
            continue
        if (isinstance(rows,list) and len(rows)==len(observed)>0
                and all(isinstance(e,list) and len(e)==2 and all(isinstance(n,str) for n in e) for e in rows)
                and {tuple(sorted(e)) for e in rows}==observed):
            tables[sid]=rows
    if tables:
        study['edges']={'anyOf':[study['edges'],{'type':'object','additionalProperties':False,
            'required':['from_source'],'properties':{'from_source':{'type':'string','enum':list(tables)}}}]}
    pair={'type':'array','items':{'type':'integer'},'minItems':2,'maxItems':2}
    info['arm_cells']={'anyOf':[info['arm_cells'],{'type':'null'},{'type':'object','additionalProperties':False,
        'required':['each_listed_outcome_node','pairs'],'properties':{
            'each_listed_outcome_node':{'const':True},'pairs':{'type':'array','minItems':1,'uniqueItems':True,'items':pair}}}]}
    definitions['EffectInformation'].setdefault('allOf',[]).append({
        'if':{'properties':{'arm_cells':{'type':'null'}},'required':['arm_cells']},
        'then':{'properties':{'operator':{'const':'FINITE_SAMPLE'},'availability':{'const':'FINITE_SAMPLE'},
                              'source_ids':{'minItems':1}}}})
    body['coordinate_notation']={
        'edges':'原文中的完整边表可用 {"from_source":"来源编号"} 原样引用；study.source_ids须同时引用该原文。可引用来源：'+','.join(tables),
        'arm_cells':'若有来源明确声明每个 outcome_nodes 成员都覆盖同一组 (本人处理,同伴暴露) 状态，可用 {"each_listed_outcome_node":true,"pairs":[...]}。只列原文给出的状态；不同对象覆盖不同时逐格列出。明确为有限样本且有引用时，格子不适用，填 [] 或 null；总体均值记录不可用 null 表示完整覆盖。'}
    wire=deepcopy(entry)
    wire['request']['user']=json.dumps(body,ensure_ascii=False)+user[end:]
    return wire,tables


def expand(answer, tables):
    if tables is None or not isinstance(answer,dict):
        return answer
    candidate=deepcopy(answer)
    study=candidate.get('study')
    # The uploaded-file reference belongs to network_file_binding. Leave its
    # exact wire shape intact for that validator; do not misread it as the
    # older source-table reference. Without a binding the native array schema
    # still rejects it. Mixed or unknown reference shapes remain errors here.
    if (isinstance(study,dict) and isinstance(study.get('edges'),dict)
            and set(study['edges']) != {'from_network'}):
        ref=study['edges'];sid=ref.get('from_source')
        if (set(ref)!={'from_source'} or not isinstance(sid,str) or sid not in tables
                or sid not in (study.get('source_ids') or [])):
            raise CoordinateError('STUDY_EDGES_REQUIRES_CITED_SOURCE_TABLE')
        study['edges']=deepcopy(tables[sid])
    for info in candidate.get('information') or []:
        if (isinstance(info,dict) and 'arm_cells' in info and info['arm_cells'] is None
                and info.get('operator')=='FINITE_SAMPLE' and info.get('availability')=='FINITE_SAMPLE'
                and info.get('source_ids')):
            info['arm_cells']=[]
        if not isinstance(info,dict) or not isinstance(info.get('arm_cells'),dict):
            continue
        group=info['arm_cells'];pairs=group.get('pairs');nodes=info.get('outcome_nodes')
        if (info.get('operator')!='NODE_ARM_MEANS' or info.get('availability') not in
                ('EXACT_POPULATION_VALUE','SYMBOLIC_POPULATION_OPERATOR') or not info.get('source_ids')
                or set(group)!={'each_listed_outcome_node','pairs'} or group['each_listed_outcome_node'] is not True
                or not isinstance(nodes,list) or not nodes or not all(isinstance(n,str) for n in nodes)
                or len(set(nodes))!=len(nodes) or not isinstance(pairs,list) or not pairs
                or not all(isinstance(p,list) and len(p)==2 and all(type(n) is int for n in p) for p in pairs)
                or len(set(map(tuple,pairs)))!=len(pairs)):
            raise CoordinateError('ARM_CELLS_REQUIRES_EXPLICIT_CITED_RECTANGLE')
        if len(nodes)*len(pairs)>100_000:
            raise CoordinateError('ARM_CELL_EXPANSION_LIMIT')
        info['arm_cells']=[dict(node=n,own=own,exposure=exposure) for n in nodes for own,exposure in pairs]
    return candidate
