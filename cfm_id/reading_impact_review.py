"""Separate source completeness from a narrowly audited identification impact.

Only omission of an isolated, pure estimation-record description can be
nonblocking. Incorrect supplied facts, mixed sources, population information,
scientific conditions and finite-model/sharp-bound inputs retain strict gates.
This module never changes a candidate or creates a scientific approval.
"""
from copy import deepcopy
import re
from typing import Literal
from pydantic import BaseModel,ConfigDict,Field
from . import fact_source_review as source,reading_material_handoff as handoff
from .business_intake import _sha

VERSION='fact-source-impact-review-1'


class MaterialDecision(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True,frozen=True)
    disposition: Literal['PENDING','REPRESENTED','OMITTED_ESTIMATION_NOTE','SOURCE_STATES_MISSING','REJECTED']
    fact_paths: list[str]=Field(default_factory=list)
    source_ids: list[str]=Field(default_factory=list)
    reason: str=''
    pure_record_description: bool=False
    no_values_definitions_or_scientific_content: bool=False


class Review(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True,frozen=True)
    version: Literal['fact-source-impact-review-1']=VERSION
    binding_sha256: str=Field(pattern=r'^[0-9a-f]{64}$')
    authority: Literal['EXTERNAL_RESEARCH_REVIEW','SYNTHETIC_TEST']
    reviewer: str=Field(min_length=3)
    evidence: str=Field(min_length=12)
    decisions: dict[str,source.Decision]
    material_decisions: dict[str,MaterialDecision]


def prepare(entry,candidate):
    if entry.get('reader_id') not in handoff.FAMILIES or 'material_inventory' not in entry:
        raise ValueError('IMPACT_REVIEW_REQUIRES_BOUND_INFORMATION_HANDOFF')
    w=source._prepare_fields(entry,candidate)
    refs=handoff.references(entry);items=handoff.located_items(entry['material_inventory'],refs)
    # Same strict field/source review. No blanket "noncritical field" checkbox.
    w['fields']['']['role']+=(' 仅可另行列明完全遗漏的纯估计记录说明；它须通过独立内容审核和程序依赖检查。'
        '除此之外原完整性标准不变；已经填写但错误的值、范围、引用或科学状态不可豁免。')
    w.update(version=VERSION,material_items=items,material_coverage=handoff.omissions(entry,candidate),
        material_decisions={k:dict(disposition='PENDING',fact_paths=[],source_ids=[],reason='',
            pure_record_description=False,no_values_definitions_or_scientific_content=False) for k in items},
        compatibility='New explicit review; old rejected source reviews cannot be reused or auto-converted.')
    w['binding_sha256']=_sha(dict(version=VERSION,entry=entry,candidate=candidate,worksheet=w))
    return w


def _note_dependency(entry,raw,item,decision):
    """Structural nonuse, conditional on independent classification of full text."""
    if (item['a0_field']!='common.sample_data_description' or item['a0_claim']['state'] not in ('STATED','INTERPRETED')
        or item['shared_with_other_a0_fields'] or not decision.pure_record_description
        or not decision.no_values_definitions_or_scientific_content or decision.fact_paths):
        return None
    refs=handoff.references(entry);docs=set(item['document_ids'])
    if docs & handoff.source_documents(raw,refs):return None
    if raw.get('bounded_model') is not None:return None  # No claim about PARTIAL/sharpness.
    population=[i for i,row in enumerate(raw.get('information',[]))
        if row.get('operator') in ('FULL_JOINT_LAW','NODE_FULL_LAW')
        and row.get('availability')=='SYMBOLIC_POPULATION_OPERATOR'
        and row.get('outcome_nodes') and row.get('source_ids')
        and not (docs & handoff.source_documents(row,refs))]
    if not population:return None
    return dict(kind='ISOLATED_ESTIMATION_NOTE_NOT_USED',document_ids=sorted(docs),
        no_candidate_field_uses_documents=True,independent_population_paths=[f'/information/{i}' for i in population],
        content_classification='INDEPENDENT_REVIEW_NOT_PROGRAM_PROOF',candidate_modified=False,
        scientific_approval=False,scope='Existing fixed-policy POINT paths only; never a PARTIAL completeness waiver.')


def _evidence(decision,item,catalog):
    if (len(decision.source_ids)!=len(set(decision.source_ids)) or
        any(s not in catalog for s in decision.source_ids)):
        raise ValueError('CURRENT_MATERIAL_REVIEW_SOURCES_REQUIRED')
    if decision.disposition!='PENDING' and (len(decision.reason.strip())<12 or
        not set(item['source_ids'])<=set(decision.source_ids)):
        raise ValueError('MATERIAL_REVIEW_REASON_AND_ORIGINAL_SOURCES_REQUIRED')


def inspect_review(entry,candidate,record):
    w=prepare(entry,candidate);r=Review.model_validate(record)
    if (r.binding_sha256!=w['binding_sha256'] or r.authority!=w['expected_authority']
        or set(r.decisions)!=set(w['fields']) or set(r.material_decisions)!=set(w['material_items'])
        or not r.reviewer.strip() or not r.evidence.strip()):
        raise ValueError('INVALID_OR_STALE_IMPACT_REVIEW')
    # Reuse exact evidence validity checks; no conversion of old decisions.
    source.validate_decision_evidence(r.decisions,w['source_catalog'])
    issues=[];pending=[];omitted=[];receipts={}
    for path,d in r.decisions.items():
        axes=[a for a in source.DIMENSIONS if getattr(d,a)=='REJECTED']
        if axes:issues.append(dict(field_path=path,category='IDENTIFICATION_RELEVANT_OR_UNRESOLVED',
            code='FIELD_REVIEW_REJECTED',dimensions=axes,blocks_identification=True))
        if any(getattr(d,a)=='PENDING' for a in source.DIMENSIONS):pending.append(path)
    for key,d in r.material_decisions.items():
        item=w['material_items'][key];_evidence(d,item,w['source_catalog'])
        if d.disposition=='PENDING':pending.append('materials/'+key);continue
        code=None
        if d.disposition=='REJECTED':code='MATERIAL_READING_REJECTED'
        elif d.disposition=='REPRESENTED':
            selected=[]
            if not d.fact_paths or len(d.fact_paths)!=len(set(d.fact_paths)):code='MATERIAL_INFORMATION_PATH_REQUIRED'
            for path in d.fact_paths:
                if not re.fullmatch(r'/information/(0|[1-9][0-9]*)',path):code='MATERIAL_INFORMATION_PATH_REQUIRED';break
                index=int(path.rsplit('/',1)[1])
                if index>=len(candidate.get('information',[])):code='MATERIAL_INFORMATION_PATH_REQUIRED';break
                selected.append(candidate['information'][index])
            linked={sid for row in selected for sid in row.get('source_ids',[])}
            if not set(item['source_ids'])<=linked:code='MATERIAL_SOURCE_NOT_ACCOUNTED_FOR'
            if item['a0_field']=='common.sample_data_description' and any(
                x.get('operator')!='FINITE_SAMPLE' or x.get('availability')!='FINITE_SAMPLE' for x in selected):
                code='SAMPLE_DESCRIPTION_CANNOT_BE_POPULATION_INFORMATION'
            if item['a0_claim']['state']=='MISSING':code='A0_MISSING_STATE_REQUIRES_RECHECK'
        elif d.disposition=='SOURCE_STATES_MISSING':
            if item['a0_claim']['state']!='MISSING' or d.fact_paths:code='EXPLICIT_SOURCE_MISSING_STATE_REQUIRED'
            if any(set(row.get('source_ids',[]))&set(item['source_ids']) and row.get('availability') not in ('UNKNOWN','FINITE_SAMPLE')
                   for row in candidate.get('information',[])):code='MISSING_STATE_CONFLICTS_WITH_FACT_INFORMATION'
        else:
            dependency=_note_dependency(entry,candidate,item,d)
            if dependency is None:code='NONBLOCKING_NOTE_DEPENDENCY_NOT_ESTABLISHED'
            else:omitted.append(key);receipts[key]=dependency
        if code:issues.append(dict(field_path='materials/'+key,category='IDENTIFICATION_RELEVANT_OR_UNRESOLVED',code=code,blocks_identification=True))
    axes={a:('REJECTED' if any(getattr(d,a)=='REJECTED' for d in r.decisions.values()) else
        'PENDING' if any(getattr(d,a)=='PENDING' for d in r.decisions.values()) else 'REVIEWED') for a in source.DIMENSIONS}
    assessment=dict(version='reading-identification-assessment-1',format='VALIDATED',field_review=axes,
        material_completeness='INCOMPLETE' if omitted or issues else 'PENDING' if pending else 'COMPLETE',
        identification_inputs='REJECTED' if issues else 'PENDING' if pending else 'SOURCE_REVIEWED',
        issues=issues+[dict(field_path='materials/'+key,category='MATERIAL_COMPLETENESS_ONLY',
            code='OMITTED_ESTIMATION_RECORD_NOTE',blocks_identification=False) for key in omitted],
        pending_fields=pending,nonblocking_dependencies=receipts,
        scientific_approval=False,original_candidate_unchanged=True)
    state='READING_RECHECK_REQUIRED' if issues else 'REVIEW_REQUIRED' if pending else 'SOURCE_REVIEWED'
    # Preserve the independently supplied new review itself.
    value=r.model_dump(mode='json');receipt=dict(version=VERSION,review=value,review_sha256=_sha(value),
        candidate_sha256=_sha(candidate),request_sha256=entry['request_sha256'],candidate_modified=False,
        citations_repaired=False,scientific_approval=False,mathematical_verification='NOT_PERFORMED')
    return dict(state=state,reason_code='READING_IMPACT_REJECTED' if issues else 'READING_IMPACT_PENDING' if pending else None,
        source_review_worksheet=w,source_review_record=value,source_review_receipt=receipt,reading_assessment=assessment)


def pending_assessment():
    return dict(version='reading-identification-assessment-1',format='VALIDATED',
        field_review={a:'PENDING' for a in source.DIMENSIONS},
        material_completeness='PENDING',identification_inputs='PENDING',issues=[],pending_fields=['source_and_material_review'],
        nonblocking_dependencies={},scientific_approval=False,original_candidate_unchanged=True)


def invalid_assessment():
    value=pending_assessment()
    value.update(format='REJECTED_OR_STALE',material_completeness='NOT_ASSESSED',
        field_review={a:'NOT_ASSESSED' for a in source.DIMENSIONS},identification_inputs='REJECTED',pending_fields=[],
        issues=[dict(category='FORMAT_OR_SOURCE_BINDING',code='INVALID_MATERIAL_ACCOUNTING_INPUT',blocks_identification=True)])
    return value


def report_result(result,assessment):
    result=deepcopy(result);assessment=deepcopy(assessment)
    if assessment['nonblocking_dependencies'] and result.get('independent_replay') and result.get('state')!='POINT':
        result.update(state='CHECK_BLOCKED',reason_code='NONBLOCKING_NOTE_OUTSIDE_POINT_SCOPE',
            independent_replay=False,mathematical_claim=None,certificate=None,answers=[])
    verified=bool(result.get('independent_replay') and result.get('mathematical_claim'))
    result.update(reading_assessment=assessment,identification_assessment=dict(
        state=result['state'],backend_called=bool(result.get('backend_called')),independent_replay=bool(result.get('independent_replay')),
        verified=verified,reading_completeness_is_identification_success=False))
    return result
