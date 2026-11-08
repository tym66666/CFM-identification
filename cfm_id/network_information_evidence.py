"""Independent provenance review for one exact table with supporting documents.

This classifies evidence roles, not A4 truth or scientific assumptions. It never
edits the candidate, combines information entries, or invokes mathematics.
"""
from typing import Literal
from pydantic import Field
from .fact_reading_revision import StrictRecord
from .business_dispatch import sha, DispatchError
from .source_locations import build_catalog
from cfm_id_llm.network_policy_reading import documents, NetworkPolicyReading
from cfm_id_llm.network_fact_protocols import network_fact_protocol

VERSION='network-information-evidence-review-1'
CONTRAST_VERSION='network-contrast-information-evidence-review-1'

class InformationEvidenceReview(StrictRecord):
    version: Literal['network-information-evidence-review-1','network-contrast-information-evidence-review-1']=VERSION
    binding_sha256: str=Field(pattern=r'^[0-9a-f]{64}$')
    authority: Literal['SYNTHETIC_TEST','EXTERNAL_RESEARCH_REVIEW']
    reviewer: str=Field(min_length=3,max_length=200)
    evidence: str=Field(min_length=12,max_length=3000)
    disposition: Literal['ACCEPTED','REJECTED','PENDING']
    table_source_ids: list[str]=Field(min_length=1,max_length=64)
    supporting_source_ids: list[str]=Field(max_length=64)

def _worksheet(entry,raw,c):
    contrast=entry.get('reader_id')=='NETWORK_POLICY_CONTRAST_FACTS'
    from .network_bounded_dispatch import model_information_indices
    indices=model_information_indices(c)
    information=[c.information[i] for i in indices]
    if not contrast and (entry.get('reader_id')!='NETWORK_FIXED_POLICY_FACTS' or len(information)!=1):
        raise ValueError('SINGLE_NETWORK_INFORMATION_ENTRY_REQUIRED')
    if not information or any(info.operator!='NODE_SIGNATURE_MEANS' or
            info.availability!='EXACT_POPULATION_VALUE' for info in information):
        raise ValueError('EXACT_SIGNATURE_TABLE_REQUIRED')
    catalog=build_catalog(documents(entry['bundle']))
    ids=list(dict.fromkeys(sid for info in information for sid in info.source_ids))
    if len({catalog[s]['doc_id'] for s in ids})<2:
        raise ValueError('MULTIDOCUMENT_EVIDENCE_REQUIRED')
    version=CONTRAST_VERSION if contrast else VERSION
    binding=sha(dict(version=version,request_sha256=entry['request_sha256'],
        fact_binding_sha256=entry['fact_binding_sha256'],bundle=entry['bundle'],
        query_review=entry['query_review'],candidate=raw))
    result=dict(version=version,binding_sha256=binding,expected_authority=entry['query_review']['authority'],
        source_catalog={s:catalog[s] for s in ids},
        instruction='独立确认全部精确格子来自同一个原始信息表；其他引用仅用于解释对象、编码、暴露或期间，不包含另一份总体信息、额外方程或约束。无法确认就保持PENDING或拒绝，不能删除引用来通过。此审核不批准科学条件。',
        scientific_approval=False,is_approval=False)
    if contrast:
        result.update(information_entries=[info.model_dump(mode='json') for info in information],
            entry_source_ids={str(i):list(c.information[i].source_ids) for i in indices},
            scope='One original exact table, possibly partitioned into disjoint records; both ordered targets and the unchanged full candidate are bound. Every record must cite the table. No new information, equality or coupling may be classified as a definition.')
    else:result['information']=information[0].model_dump(mode='json')
    if len(indices)!=len(c.information):
        result['original_entry_indices']=indices
    return result

def prepare(entry,raw):
    if entry.get('reader_id')=='NETWORK_POLICY_CONTRAST_FACTS':
        from cfm_id_llm.fact_reading_contracts import contract_for_entry
        decoded=contract_for_entry(entry).parse(entry['bundle'],raw,binding=entry['fact_binding_sha256'])['endpoint_readings']['first']
    else:decoded=network_fact_protocol(entry.get('network_fact_contract')).parse(entry['bundle'],raw,binding=entry['fact_binding_sha256'])
    c=NetworkPolicyReading.model_validate(decoded['facts'])
    return _worksheet(entry,raw,c)

def check(entry,raw,c,record):
    w=_worksheet(entry,raw,c)
    r=InformationEvidenceReview.model_validate(record)
    if r.version!=w['version'] or r.binding_sha256!=w['binding_sha256'] or r.authority!=w['expected_authority'] or not r.reviewer.strip() or not r.evidence.strip():
        raise ValueError('STALE_OR_WRONG_AUTHORITY_INFORMATION_EVIDENCE_REVIEW')
    ids=r.table_source_ids+r.supporting_source_ids
    if len(ids)!=len(set(ids)) or set(ids)!=set(w['source_catalog']):
        raise ValueError('EXACT_DISJOINT_SOURCE_ROLE_COVERAGE_REQUIRED')
    table_docs={w['source_catalog'][s]['doc_id'] for s in r.table_source_ids}
    if len(table_docs)!=1:
        raise ValueError('ONE_ORIGINAL_TABLE_DOCUMENT_REQUIRED')
    if w['version']==CONTRAST_VERSION and any(not set(ids)&set(r.table_source_ids)
            for ids in w['entry_source_ids'].values()):
        raise ValueError('EACH_INFORMATION_ENTRY_MUST_CITE_ORIGINAL_TABLE')
    if r.disposition=='REJECTED':raise DispatchError('CHECK_BLOCKED','INFORMATION_EVIDENCE_REVIEW_REJECTED')
    if r.disposition!='ACCEPTED':raise DispatchError('REVIEW_REQUIRED','INFORMATION_EVIDENCE_REVIEW_PENDING')
    receipt=dict(version=w['version'],review=r.model_dump(mode='json'),review_sha256=sha(r.model_dump(mode='json')),
        table_documents=sorted(table_docs),supporting_documents=sorted({w['source_catalog'][s]['doc_id'] for s in r.supporting_source_ids}),
        candidate_modified=False,information_entries_merged=False,scientific_approval=False)
    if w['version']==CONTRAST_VERSION:
        receipt['information_entry_count']=len(w['information_entries'])
    return receipt
