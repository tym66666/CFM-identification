"""Frozen network compatibility implementation extracted from evaluation.

Explicit inputs and independent reviews remain required. No default benchmark
selection, fixture approval, or candidate-model continuation is provided here.
See README.md before extending this historical protocol.
"""
from copy import deepcopy
import json
import re
import cfm_id.workflows.legacy_network.materials_optional_tables as base
import cfm_id.workflows.legacy_network.materials_undecided_allocation as prior
from cfm_id.workflows.legacy_network.materials_base import bundle_value
from cfm_id.workflows.legacy_network.materials_target_provenance import target_sources
from cfm_id.serialization import canonical_hash


VERSION='business-materials-v0.24.5'


def clause_choices(text):
    """Contiguous whole clauses only; a model cannot remove words inside one.

    Keep original spelling/punctuation between clauses. Boundary punctuation is
    optional because references conventionally cite the sentence without it.
    """
    parts=[m.span() for m in re.finditer(r'[^；;。！？!?\n]+',text) if m.group().strip()]
    values=[]
    for start in range(len(parts)):
        for end in range(start,len(parts)):
            value=text[parts[start][0]:parts[end][1]].strip()
            if value and value not in values: values.append(value)
    if text.strip() and text.strip() not in values: values.append(text.strip())
    return values


def make_request(value):
    system,user=prior.make_request(value)
    message=json.loads(user)
    choices={ref:clause_choices(text) for ref,text in target_sources(bundle_value(value)).items()}
    message['remaining_evidence_clause_choices']=choices
    schema=message['output_schema']['$defs']['Question']
    schema['properties']['remaining_evidence_span']={
        'anyOf':[{'type':'string','enum':list(dict.fromkeys(v for vs in choices.values() for v in vs))},{'type':'null'}],
        'description':'remaining_source非空时，选择该来源下完整支持其余安排规则与条件平均的语句；原句有无关预算等内容时不要一并引用。来源为null时本字段也为null。'}
    schema['required'].append('remaining_evidence_span')
    system+='''
remaining_source保留来源编号，remaining_evidence_span引用该行中支持此字段的完整语句。
从remaining_evidence_clause_choices[remaining_source]选取，必须包含完整的安排规则和条件平均意思，必要时选连续多句。
不要只截取“按原抽签”等几个词，不得删掉同一句中的否定、未定、提议或冲突限定。
预算、采购等其他事项未定不代表人员安排未定；选择真正支持人员安排的那段完整陈述。
如果只是几种未选定的提议、只提到安排而没有肯定说明规则，两字段都填null。该引用仍是待审核证据，不是识别证明。
'''
    return system,json.dumps(message,ensure_ascii=False)


def normalize(value,raw):
    copied=deepcopy(raw)
    if not isinstance(copied,dict) or not isinstance(copied.get('questions'),dict):
        raise ValueError('TOP_LEVEL_INVALID')
    catalog=target_sources(bundle_value(value))
    citations={};vetoes=[]
    for sid,q in copied['questions'].items():
        if not isinstance(q,dict) or 'remaining_evidence_span' not in q:
            raise ValueError('REMAINING_EVIDENCE_SPAN_REQUIRED')
        span=q.pop('remaining_evidence_span')
        source=q.get('remaining_source')
        if source is None:
            if span is not None: raise ValueError('SPAN_WITHOUT_REMAINING_SOURCE')
            citations[sid]=None
            continue
        if not isinstance(source,str) or source not in catalog:
            raise ValueError('TARGET_STATEMENT_SOURCE_REQUIRED')
        if not isinstance(span,str) or span not in clause_choices(catalog[source]):
            raise ValueError('REMAINING_EVIDENCE_COMPLETE_SOURCE_CLAUSE_REQUIRED')
        citations[sid]=dict(source=source,span=span)
        if prior._UNCERTAIN.search(span) or prior._DENIED.search(span):
            q['remaining_source']=None
            vetoes.append(dict(question_id=sid,field='remaining_source',source=source,
                reason_code='REMAINING_EVIDENCE_SPAN_UNSET_OR_DENIED',withheld=True))
    return copied,citations,vetoes


def project(value,raw):
    normalized,_,_=normalize(value,raw)
    return base.project(value,normalized)


def evaluate_draft(value,raw,packet,*,synthetic_protocol_selected=False):
    try:
        normalized,citations,vetoes=normalize(value,raw)
    except (ValueError,KeyError,TypeError) as exc:
        return dict(version=VERSION,status='REJECTED',reason_code=str(exc) if isinstance(exc,ValueError) else 'READING_SCHEMA_INVALID',
            results=[],production_admission=False,candidate_generator_called=False,estimation_called=False,policy_called=False,
            nonidentification_proven=False,semantic_correctness_verified=False,model_draft_sha256=canonical_hash(raw))
    result=base.evaluate_draft(value,normalized,packet,synthetic_protocol_selected=synthetic_protocol_selected)
    result.update(version=VERSION,remaining_evidence_citations=citations,remaining_evidence_vetoes=vetoes,
        remaining_evidence_gate='whole_source_clause_membership_and_contradiction_veto_not_semantic_proof',
        model_draft_sha256=canonical_hash(raw))
    return result
