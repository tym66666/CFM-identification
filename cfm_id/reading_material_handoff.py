"""Original-source inventory between audited A0 and fact reading.

No prose classifier, answer completion, citation repair or scientific approval.
An A0 label is a locator to review, never proof of a source's information type.
"""
from copy import deepcopy
import json
from .business_intake import _sha

VERSION='information-inventory-1'
FIELDS=('sample_data_description','available_information')
FAMILIES=('NETWORK_FIXED_POLICY_FACTS','NETWORK_POLICY_CONTRAST_FACTS',
          'NETWORK_RANDOMIZED_ARM_FACTS','NETWORK_FINITE_POLICY_FACTS','NETWORK_OBSERVATIONAL_EFFECT_FACTS')


def build(session,query_id,query_review):
    from cfm_id_llm.compact_reference_contract import catalog
    if not query_review.get('field_review'):
        raise ValueError('MATERIAL_HANDOFF_REQUIRES_INDEPENDENT_A0_FIELD_REVIEW')
    sources={r['ref']:r for r in catalog(session.case,session.a0_reference_contract)}
    common=session.candidate.get('common',{});items={}
    # Document sharing with another A0 field prevents a later pure-note exception.
    other_docs=set()
    def walk(value,path=''):
        if isinstance(value,dict):
            if path!='/common/sample_data_description':
                other_docs.update(sources[r]['source_id'] for r in value.get('refs',[]))
            for k,v in value.items():walk(v,path+'/'+k)
        elif isinstance(value,list):
            for i,v in enumerate(value):walk(v,path+'/'+str(i))
    walk(session.candidate)
    for name in FIELDS:
        claim=common.get(name)
        if not isinstance(claim,dict) or claim.get('state') not in ('STATED','INTERPRETED','MISSING'):continue
        locations=[dict(doc_id=sources[r]['source_id'],quote=sources[r]['quote']) for r in claim.get('refs',[])]
        if not locations:raise ValueError('MATERIAL_HANDOFF_SOURCE_REQUIRED')
        docs=sorted({r['doc_id'] for r in locations})
        items[name]=dict(a0_field='common.'+name,a0_claim=deepcopy(claim),original_locations=locations,
            document_ids=docs,shared_with_other_a0_fields=bool(set(docs)&other_docs),
            source_classification='NOT_INFERRED',scientific_approval=False)
    return dict(version=VERSION,query_id=query_id,intake_sha256=_sha(session.model_dump(mode='json')),
        query_review_sha256=_sha(query_review),items=items)


def references(entry):
    from cfm_id_llm.fact_reading_contracts import contract_for_entry
    contract=contract_for_entry(entry)
    return contract.reference_catalog(entry['bundle'],binding=entry['fact_binding_sha256'])


def located_items(inventory,refs):
    """Map exact original quotes to current fact slices; no A0 prose as evidence."""
    result={}
    for key,item in inventory['items'].items():
        ids=[]
        for loc in item['original_locations']:
            found=[alias for alias,row in refs['aliases'].items() if row['doc_id']==loc['doc_id']
                and (row['text'] in loc['quote'] or loc['quote'] in row['text'])]
            if not found:raise ValueError('HANDOFF_ORIGINAL_SOURCE_NOT_LOCATABLE')
            ids.extend(alias for alias in found if alias not in ids)
        result[key]=dict(item,source_ids=ids)
    return result


def attach(request,inventory,refs):
    items=located_items(inventory,refs)
    public=dict(kind='ORIGINAL_SOURCE_ACCOUNTING_NOT_EVIDENCE',
        instruction='逐项对照source_catalog中的原文，保留信息或明确疑点；此前A0标签只是待核定位，不决定总体/样本性质，不补范围或科学条件。返回仍按原输出Schema。',
        items=[dict(item_id=k,a0_field=v['a0_field'],a0_state=v['a0_claim']['state'],source_ids=v['source_ids']) for k,v in items.items()])
    return dict(request,user=request['user']+'\n\n原材料交接清单（不是新事实或许可）：\n'+json.dumps(public,ensure_ascii=False))


def source_documents(value,refs):
    docs=set()
    def walk(v):
        if isinstance(v,dict):
            for k,x in v.items():
                if k.endswith('source_ids'):docs.update(refs['aliases'][s]['doc_id'] for s in x)
                else:walk(x)
        elif isinstance(v,list):
            for x in v:walk(x)
    walk(value);return docs


def omissions(entry,candidate):
    """Diagnostic only: matching locators is not semantic or source approval."""
    inventory=entry.get('material_inventory')
    if inventory is None:return []
    refs=references(entry);items=located_items(inventory,refs);rows=[]
    for key,item in items.items():
        paths=[f'/information/{i}' for i,row in enumerate(candidate.get('information',[]))
               if set(row.get('source_ids',[]))&set(item['source_ids'])]
        rows.append(dict(item_id=key,a0_field=item['a0_field'],source_ids=item['source_ids'],
            fact_paths=paths,status='CITATION_LINKED_REQUIRES_REVIEW' if paths else 'NO_INFORMATION_RECORD_LINK',
            source_entailment_verified=False))
    return rows
