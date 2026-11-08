"""Describe field-local citation duties; never infer entailment or edit replies.

The caller declares coverage groups for its public reading schema. Every cited
record and direct data field must be accounted for, so schema changes cannot
silently leave the displayed citation duties stale. This is request metadata,
not a verifier of natural-language truth or a source-repair mechanism.
"""
from copy import deepcopy

VERSION = 'field-local-citations-2'
INSTRUCTION = '''引用按字段所属的对象分别负责，不能用回答其他位置的引用代替。
按照Schema的properties顺序输出：本对象的事实字段在前，引用数组在后。写完本对象的事实后，再选择支持这些实际主张的来源，避免先列引用后补事实而漏引。不能由输出顺序推断缺失的事实。
每个source_ids的Schema说明列出它负责的字段。逐项核对其具体事实是否被这一组引用完整支持；来自多份材料时保留相应来源，不能只引用最先介绍对象的材料。同一来源可分别出现在多个确实需要它的对象中。
有自己source_ids的子对象独立负责引用；例如父对象的引用不自动覆盖子对象，子对象的引用也不能代替父对象的引用。专用的remaining_source_ids只支持remaining_assignment。
只列与本组事实有关的来源，不能把整个目录全部粘贴来凑覆盖。引用编号存在不代表支持该事实。未说明的内容仍用规定的未知/缺失状态，不因要求引用而补事实；NOT_STATED的来源仍为空。真实缺项、冲突、额外约束都必须保留。输出前复查覆盖，但不输出自评、额外检查表或识别结论。'''


def annotate(schema, groups):
    """Return annotated copies; preserve all validation constraints and values."""
    result=deepcopy(schema);definitions=result.get('$defs',{})
    def owns_citations(node):
        if '$ref' in node:
            ref=node['$ref']
            if not ref.startswith('#/$defs/') or ref[8:] not in definitions:
                raise ValueError('LOCAL_READING_SCHEMA_REFERENCE_REQUIRED')
            node=definitions[ref[8:]]
        if any(k.endswith('source_ids') for k in node.get('properties',{})):return True
        return any(owns_citations(x) for x in node.get('anyOf',[])) or (
            'items' in node and owns_citations(node['items']))
    cited={name:d for name,d in definitions.items()
           if any(k.endswith('source_ids') for k in d.get('properties',{}))}
    if set(groups)!=set(cited):raise ValueError('EXACT_CITED_RECORD_COVERAGE_REQUIRED')
    for name,record in cited.items():
        props=record['properties'];sources={k for k in props if k.endswith('source_ids')}
        if set(groups[name])!=sources:raise ValueError('EXACT_CITATION_FIELDS_REQUIRED')
        direct={k for k,p in props.items() if k not in sources and not owns_citations(p)}
        assigned=[k for values in groups[name].values() for k in values]
        if set(assigned)!=direct or len(set(assigned))!=len(assigned):
            raise ValueError('EXACT_DIRECT_FIELD_COVERAGE_REQUIRED')
        for key,covered in groups[name].items():
            if not covered:raise ValueError('NONEMPTY_CITATION_SCOPE_REQUIRED')
            explanation='本对象的这些字段共同使用本组引用：'+', '.join(covered)+'。逐项覆盖其具体主张；其他对象的引用不代替这里的引用。只选相关原文，缺失事实不得补造。'
            props[key]['description']=(props[key].get('description','')+' '+explanation).strip()
        # JSON object ordering is presentation only. Do not reorder returned
        # candidates, alter constraints, or fill in any values or references.
        record['properties']={k:props[k] for k in props if k not in sources}
        record['properties'].update({k:props[k] for k in props if k in sources})
    return result,dict(version=VERSION,groups=deepcopy(groups),
        emission_order='facts_then_local_sources',
        establishes_entailment=False,repairs_model_citations=False)
