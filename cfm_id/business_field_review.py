"""Field-level independent review feeding the existing query-review boundary.

The reviewer supplies semantic decisions. Code checks coverage, provenance of
the review and current scope, never natural-language truth or scientific merit.
"""
from copy import deepcopy
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

from . import business_intake as intake
from cfm_id_llm import business_field_contract as contract
from cfm_id_llm.compact_reference_contract import catalog
from cfm_id_llm.compact_response_contract import evidence_contract, review_definition

VERSION = 'business-field-review-1'
DIMENSIONS = ('field_role', 'value_state', 'source_coverage')
Authority = Literal['EXTERNAL_RESEARCH_REVIEW', 'SYNTHETIC_TEST']
Disposition = Literal['ACCEPTED', 'PENDING', 'REJECTED']


class Decision(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, frozen=True)
    field_role: Disposition
    value_state: Disposition
    source_coverage: Disposition
    reason: str = ''
    source_ids: list[str] = Field(default_factory=list)


class FieldReview(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, frozen=True)
    version: Literal['business-field-review-1'] = VERSION
    binding_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    authority: Authority
    reviewer: str = Field(min_length=3)
    evidence: str = Field(min_length=12)
    decisions: dict[str, Decision]


def _worksheet(value, query_id, authority):
    if authority not in ('EXTERNAL_RESEARCH_REVIEW', 'SYNTHETIC_TEST'):
        raise intake.IntakeError('INVALID_FIELD_REVIEW_AUTHORITY')
    s = intake._checked(value); reading = intake.inspect(s)
    if s.reading_format != 'compact' or 'report' not in reading:
        raise intake.IntakeError('CURRENT_VALID_COMPACT_READING_REQUIRED')
    queries = reading['report']['draft']['queries']
    positions = [i for i,q in enumerate(queries) if q['query_id'] == query_id]
    if len(positions) != 1:
        raise intake.IntakeError('EXACT_CURRENT_QUERY_REQUIRED')
    raw = s.candidate; query = raw['queries'][positions[0]]
    sources = {r['ref']:dict(r) for r in catalog(s.case, s.a0_reference_contract)}
    items = {}

    def add(rule, path, value, present, *, evidence_from=None, enum_default=None):
        candidate = deepcopy(value)
        state = (value.get('state','UNKNOWN') if type(value) is dict else
                 value if type(value) is str else 'UNKNOWN')
        if rule.shape == 'enum': state = 'ENUM'; candidate = value if present else enum_default
        if rule.shape == 'claims' and type(value) is not dict:
            state = 'COLLECTION'; candidate = [] if not present else candidate
        refs = value.get('refs',[]) if type(value) is dict else []
        if evidence_from is not None:
            refs = evidence_from.get('refs',[]) if type(evidence_from) is dict else []
        items[path] = dict(definition=review_definition(rule,s.a0_response_contract), raw_present=present, candidate=candidate,
            state=state, actual_citations=[deepcopy(sources[r]) for r in refs],
            evidence_mode='DECLARED_ENUM_BASIS' if rule.shape=='enum' else 'THIS_FIELD_ONLY')

    common = raw.get('common', {})
    evidence = evidence_contract(s.a0_response_contract)
    deferred = getattr(evidence, 'DEFERRED_COMMON', ())
    for rule in contract.COMMON:
        if rule.name in deferred:
            continue  # Owned and independently reviewed by the fact stage.
        path = 'common.'+rule.name; value = common.get(rule.name)
        if rule.shape == 'claims' and value:
            for i,c in enumerate(value): add(rule, f'{path}[{i}]', c, True)
        else:
            add(rule, path, value, rule.name in common,
                evidence_from=common.get('assignment_law',{}) if rule.name=='assignment_family' else None,
                enum_default='UNRESOLVED')
    for rule in contract.QUERY:
        add(rule, f'queries.{query_id}.{rule.name}', query.get(rule.name), rule.name in query,
            evidence_from=query.get('goal',{}) if rule.shape=='enum' else None)
    semantics = query.get('semantics', {})
    evidence = evidence_contract(s.a0_response_contract)
    omitted = evidence.omitted_semantics(query) if evidence is not None and hasattr(evidence, 'omitted_semantics') else ()
    for rule in contract.SEMANTICS:
        if rule.name in omitted:
            continue
        add(rule, f'queries.{query_id}.semantics.{rule.name}', semantics.get(rule.name), rule.name in semantics)
        if evidence is not None and hasattr(evidence, 'review_semantics'):
            items[f'queries.{query_id}.semantics.{rule.name}']['definition']=evidence.review_semantics(query,rule)
    state_rules = dict(contract.STATE_RULES)
    if evidence is not None:
        state_rules.update(getattr(evidence, 'EXTRA_STATE_RULES', {}))
        for rule, path, value, state in evidence.review_items(raw, query_id):
            add(rule, path, value, True)
            items[path]['state'] = state
    identity = dict(version=VERSION, intake_sha256=intake._sha(s.model_dump(mode='json')), query_id=query_id,
        contract_version=contract.VERSION, definitions={section:[review_definition(rule,s.a0_response_contract)
            for rule in contract.fields(section)] for section in ('common','query','semantics')}, state_rules=state_rules,
        evidence_rule=contract.EVIDENCE_RULE, fields=items, source_catalog=sources,
        original_materials=s.case.model_dump(mode='json'), authority=authority)
    return dict(version=VERSION, binding_sha256=intake._sha(identity), expected_authority=authority,
        intake_sha256=identity['intake_sha256'], query_id=query_id, contract_version=contract.VERSION,
        state_rules=deepcopy(state_rules), evidence_rule=contract.EVIDENCE_RULE,
        fields=items, source_catalog=sources, reading_state=reading['state'], is_approval=False,
        original_materials=identity['original_materials'],
        review_scope='Selected business query plus shared facts; no scientific approval or theorem check.',
        decisions={p:dict(**{d:'PENDING' for d in DIMENSIONS},reason='',source_ids=[]) for p in items})


def prepare(value, query_id, *, authority='EXTERNAL_RESEARCH_REVIEW'):
    return dict(state='REVIEW_REQUIRED', field_worksheet=_worksheet(value,query_id,authority),
                request=None, api_calls=0, core_called=False, scientific_approval=False)


def validate_record(record, sheet):
    raw = record.model_dump(mode='json') if isinstance(record,FieldReview) else record
    r = FieldReview.model_validate(raw)
    if (r.binding_sha256 != sheet['binding_sha256'] or r.authority != sheet['expected_authority']
            or set(r.decisions) != set(sheet['fields']) or len(r.reviewer.strip())<3 or len(r.evidence.strip())<12):
        raise intake.IntakeError('INVALID_OR_STALE_FIELD_REVIEW')
    for decision in r.decisions.values():
        nonpending = any(getattr(decision,k)!='PENDING' for k in DIMENSIONS)
        if (len(set(decision.source_ids)) != len(decision.source_ids)
                or any(k not in sheet['source_catalog'] for k in decision.source_ids)
                or (nonpending and (len(decision.reason.strip())<12 or not decision.source_ids))):
            raise intake.IntakeError('FIELD_REVIEW_REASONS_AND_CURRENT_SOURCES_REQUIRED')
    return r


def project_decisions(record):
    def combine(values):
        return 'REJECTED' if 'REJECTED' in values else 'PENDING' if 'PENDING' in values else 'ACCEPTED'
    return dict(
        business_target_and_population=combine([getattr(d,k) for p,d in record.decisions.items()
            if p.startswith('queries.') for k in ('field_role','value_state')]),
        research_structure=combine([getattr(d,k) for p,d in record.decisions.items()
            if p.startswith('common.') for k in ('field_role','value_state')]),
        source_entailment=combine([d.source_coverage for d in record.decisions.values()]))


def validate_attached(review, sheet):
    """Called by dispatch: nested decisions cannot be hidden by top-level ACCEPTED."""
    if sheet is None:
        raise intake.IntakeError('FIELD_REVIEW_WRONG_SCOPE')
    r = validate_record(review.field_review, sheet)
    if (any(getattr(r,k)!=getattr(review,k) for k in ('reviewer','evidence','authority'))
            or project_decisions(r)!=review.decisions):
        raise intake.IntakeError('FIELD_REVIEW_PROJECTION_MISMATCH')
    return r


def submit(value, query_id, record, *, authority='EXTERNAL_RESEARCH_REVIEW'):
    from . import business_dispatch as dispatch
    sheet = _worksheet(value,query_id,authority); r = validate_record(record,sheet)
    review = dispatch.DispatchReview(binding_sha256=intake._sha(dict(
        intake_sha256=sheet['intake_sha256'],query_id=query_id)), reviewer=r.reviewer,evidence=r.evidence,
        authority=r.authority,decisions=project_decisions(r),field_review=r.model_dump(mode='json'))
    entry = dispatch.prepare_reader(value,query_id,query_review=review)
    return dict(state=entry['state'],reason_code=entry.get('reason_code'),
        query_review=review.model_dump(mode='json') if entry.get('query_worksheet') is not None else None,
        field_review=r.model_dump(mode='json'), projected_decisions=review.decisions,
        request=None,api_calls=0,core_called=False,scientific_approval=False,mathematical_claim=None)


def main(argv=None):
    import argparse,json
    from pathlib import Path
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('command',choices=['worksheet','submit']);p.add_argument('--intake',required=True)
    p.add_argument('--query',required=True);p.add_argument('--record');p.add_argument('--output',required=True)
    p.add_argument('--authority',choices=['EXTERNAL_RESEARCH_REVIEW','SYNTHETIC_TEST'],default='EXTERNAL_RESEARCH_REVIEW')
    a=p.parse_args(argv)
    try:
        if Path(a.output).exists():raise ValueError('OUTPUT_EXISTS')
        s=intake.restore(a.intake)
        result=(prepare(s,a.query,authority=a.authority) if a.command=='worksheet' else
                submit(s,a.query,intake.read_json(a.record),authority=a.authority))
        intake.write_json(a.output,result)
    except (ValueError,TypeError,KeyError,AttributeError,OSError):
        print(json.dumps(dict(state='CHECK_BLOCKED',reason_code='FIELD_REVIEW_INPUT_OR_OUTPUT_REJECTED',api_calls=0)))
        return 2
    print(json.dumps(dict(state=result['state'],api_calls=0)));return 0


if __name__=='__main__':
    raise SystemExit(main())
