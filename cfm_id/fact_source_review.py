"""Source-first review over network fact records, before method inspection.

No candidate changes or automatic entailment. A rejected role/citation returns
to reading; accepting an extra restriction never removes it from native checks.
"""
from copy import deepcopy
import json
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field
from .business_dispatch import sha
from cfm_id_llm.fact_source_contract import DIMENSIONS, EVIDENCE_RULE, role_for

VERSION = 'fact-source-review-1'
FAMILIES = ('NETWORK_FIXED_POLICY_FACTS', 'NETWORK_POLICY_CONTRAST_FACTS',
            'NETWORK_RANDOMIZED_EFFECT_FACTS', 'NETWORK_OBSERVATIONAL_POLICY_FACTS',
            'NETWORK_RANDOMIZED_ARM_FACTS','NETWORK_FINITE_POLICY_FACTS','NETWORK_OBSERVATIONAL_EFFECT_FACTS')


class Decision(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, frozen=True)
    field_role: Literal['ACCEPTED','REJECTED','PENDING']
    value_state: Literal['ACCEPTED','REJECTED','PENDING']
    source_coverage: Literal['ACCEPTED','REJECTED','PENDING']
    reason: str
    source_ids: list[str]


class SourceReview(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, frozen=True)
    version: Literal['fact-source-review-1'] = VERSION
    binding_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    authority: Literal['SYNTHETIC_TEST','EXTERNAL_RESEARCH_REVIEW']
    reviewer: str = Field(min_length=3,max_length=200)
    evidence: str = Field(min_length=12,max_length=3000)
    decisions: dict[str,Decision]


def _pointer(value, path):
    for part in path.split('/')[1:]:
        part = part.replace('~1','/').replace('~0','~')
        value = value[int(part)] if type(value) is list else value[part]
    return value


def prepare(entry, candidate):
    """Select the explicit entry contract; historical entries remain strict v1."""
    if entry.get('material_inventory') is not None:
        from .reading_impact_review import prepare as prepare_impact
        return prepare_impact(entry,candidate)
    return _prepare_fields(entry,candidate)


def _prepare_fields(entry, candidate):
    """A local worksheet, no model call and no native method selection."""
    from .fact_reading_revision import _references, _paths
    from cfm_id_llm.fact_wire_models import model_for
    from cfm_id_llm.source_reference_wire import expand, definition_evidence
    if entry.get('state') != 'READY_TO_READ' or entry.get('reader_id') not in FAMILIES:
        raise ValueError('SOURCE_REVIEW_REQUIRES_CONNECTED_NETWORK_READER')
    _paths(candidate)
    model = model_for(entry)
    if model is None:
        raise ValueError('SOURCE_REVIEW_REQUIRES_REGISTERED_WIRE_MODEL')
    model.model_validate(deepcopy(candidate))  # Validation only; do not use defaults as new facts.
    refs = _references(entry)
    if candidate.get('reference_context') != refs['context']:
        raise ValueError('STALE_SOURCE_REVIEW_REFERENCE_CONTEXT')
    expand(candidate, refs)  # Reject foreign/duplicate source IDs, including unused definitions.
    body = json.JSONDecoder().raw_decode(entry['request']['user'])[0]
    definitions = body.get('evidence_dependency_contract',{}).get('definitions',{})
    rows = {'': dict(role='对照全部原文检查本问目标与所有已知信息、未知及真正限制是否完整保留；字段缺省不证明原文没有内容。',
        candidate=deepcopy(candidate), citation_groups={}, explicit_definitions={},
        scope='WHOLE_READING_COMPLETENESS_NOT_A_SHARED_CITATION')}

    def walk(value, path=''):
        if type(value) is dict:
            groups = {k:deepcopy(v) for k,v in value.items() if k.endswith('source_ids')}
            if groups:
                dependencies = definition_evidence(candidate,definitions,value.get('definition_refs',[]),
                    record_path=path,aliases=refs['aliases'])
                rows[path] = dict(role=role_for(path),candidate=deepcopy(value),citation_groups=groups,
                    explicit_definitions=dependencies,scope='RECORD_LOCAL_CITATIONS_ONLY')
            for k,v in value.items():
                walk(v,path+'/'+k.replace('~','~0').replace('/','~1'))
        elif type(value) is list:
            for i,v in enumerate(value):walk(v,path+'/'+str(i))
    walk(candidate)
    if entry.get('reviewed_intent') is not None:
        from cfm_id_llm.reviewed_intent_handoff import add_review_expectations
        add_review_expectations(rows,entry['reviewed_intent'])
    # New contracts expose their schema-owned combination rules for reviewers.
    # No metadata is added to old worksheets, preserving historical bindings.
    schema=body.get('output_schema',{})
    mean_ref=schema.get('properties',{}).get('mean_sufficiency',{}).get('$ref','')
    if mean_ref.startswith('#/$defs/') and '/mean_sufficiency' in rows:
        rules=schema.get('$defs',{}).get(mean_ref.rsplit('/',1)[-1],{}).get('x-cfm-field-contract')
        if rules:rows['/mean_sufficiency']['combination_rules']=deepcopy(rules)
    from cfm_id_llm.network_mean_order_reading import PROFILES
    if entry.get('network_fact_contract') in PROFILES:
        from cfm_id_llm.mean_order_field_contract import field_constraints
        for path, row in rows.items():
            if path.startswith('/mean_order_model'):
                row['public_field_constraints'] = field_constraints([path], request=entry['request'])
    from cfm_id_llm import mean_order_ownership as ownership
    if entry.get('network_fact_contract') == ownership.PROFILE:
        checks = ownership.overlap_checks(candidate)
        for path, row in rows.items():
            constraints = ownership.field_constraints([path], request=entry['request'])
            if constraints:
                row.setdefault('public_field_constraints', []).extend(constraints)
            if path in checks:
                row['ownership_check'] = checks[path]
    from cfm_id_llm.shared_fact_definitions import add_review_definitions
    evidence_rule = add_review_definitions(rows,candidate,entry,body) or EVIDENCE_RULE
    source_catalog = deepcopy(refs['aliases'])
    identity = dict(version=VERSION,entry=entry,candidate=candidate,fields=rows,
        source_catalog=source_catalog,evidence_rule=evidence_rule)
    return dict(version=VERSION,binding_sha256=sha(identity),expected_authority=entry['query_review']['authority'],
        query_id=entry['query_id'],request_sha256=entry['request_sha256'],reader_id=entry['reader_id'],
        fields=rows,source_catalog=source_catalog,original_materials=deepcopy(entry['bundle']),evidence_rule=evidence_rule,
        decisions={k:dict(**{a:'PENDING' for a in DIMENSIONS},reason='',source_ids=[]) for k in rows},
        is_approval=False,scientific_approval=False,backend_called=False,
        scope='Source roles, completeness and actual citation coverage only; no candidate repair or mathematical conclusion.')


def validate_decision_evidence(decisions,source_catalog):
    """Shared record validity only; never create or change review decisions."""
    for decision in decisions.values():
        if len(set(decision.source_ids)) != len(decision.source_ids) or any(k not in source_catalog for k in decision.source_ids):
            raise ValueError('CURRENT_REVIEW_SOURCES_REQUIRED')
        if any(getattr(decision,a) != 'PENDING' for a in DIMENSIONS) and (
                len(decision.reason.strip()) < 12 or not decision.source_ids):
            raise ValueError('SOURCE_REVIEW_REASON_AND_EVIDENCE_REQUIRED')


def inspect_review(entry, candidate, record):
    raw=record.model_dump(mode='json') if hasattr(record,'model_dump') else record
    from . import reading_impact_review as impact
    if isinstance(raw,dict) and raw.get('version')==impact.VERSION:
        return impact.inspect_review(entry,candidate,raw)
    w = _prepare_fields(entry,candidate)
    out = dict(state='REVIEW_REQUIRED',reason_code='FACT_SOURCE_REVIEW_REQUIRED',
        source_review_worksheet=w,source_review_receipt=None,source_review_record=None)
    if record is None:
        return out
    r = SourceReview.model_validate(record.model_dump(mode='json') if isinstance(record,SourceReview) else record)
    if (r.binding_sha256 != w['binding_sha256'] or r.authority != w['expected_authority'] or
            set(r.decisions) != set(w['fields']) or not r.reviewer.strip() or not r.evidence.strip()):
        raise ValueError('INVALID_OR_STALE_FACT_SOURCE_REVIEW')
    validate_decision_evidence(r.decisions,w['source_catalog'])
    from .source_review_diagnostics import describe
    out['source_review_diagnostics'] = describe(w, r)
    record = r.model_dump(mode='json')
    receipt = dict(version=VERSION,review=record,review_sha256=sha(record),
        candidate_sha256=sha(candidate),request_sha256=entry['request_sha256'],
        candidate_modified=False,citations_repaired=False,scientific_approval=False,mathematical_verification='NOT_PERFORMED')
    out.update(source_review_receipt=receipt,source_review_record=record)
    decisions = {getattr(d,a) for d in r.decisions.values() for a in DIMENSIONS}
    if 'REJECTED' in decisions:
        return dict(out,state='READING_RECHECK_REQUIRED',reason_code='FACT_SOURCE_REVIEW_REJECTED',
            rejected_fields=[p for p,d in r.decisions.items() if any(getattr(d,a)=='REJECTED' for a in DIMENSIONS)])
    if 'PENDING' in decisions:
        return dict(out,reason_code='FACT_SOURCE_REVIEW_PENDING')
    return dict(out,state='SOURCE_REVIEWED',reason_code=None)
