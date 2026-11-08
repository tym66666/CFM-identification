"""Explicit information scope for policy means and joint contrasts.

No scope inference, source repair or math. Shares native parsing and review with
the existing definition contract; optional unknown sample scope stays unknown.
"""
from copy import deepcopy
import hashlib
import json
from typing import Literal
from pydantic import Field, model_validator
from . import policy_record_definitions as previous, policy_evidence_dependencies as definitions

CONTRACT = 'network-policy-scopes-1'
SCOPE_RULE = ('scope_status=DECLARED表示本条信息的对象范围有原文声明，outcome_nodes保留该范围，'
    'scope_source_ids单独引用范围原句；定义引用只解释名字，不证明记录覆盖。'
    '未说明范围用UNSPECIFIED，outcome_nodes、assignment_cells、signature_cells及scope_source_ids均为空。'
    '名册、评价名单和记录条数不能代替覆盖声明；明确给出的总体或样本范围不得隐藏为未知。')
STATE_RULE = ('status=NOT_STATED时source_ids必须为空；其他科学状态必须有本条件的原文来源。'
    '没有第一阶段排除条件声明可用null；不得因设计类别自动批准科学条件。')
RULE_CODES = {
    'FIRST_STAGE_EXCLUSION_SOURCE_STATE_REQUIRED': STATE_RULE,
    'ABSENT_STATEMENT_HAS_NO_SOURCE_SELECTION': STATE_RULE,
    'EXPLICIT_STATEMENT_REQUIRES_SOURCE_SELECTION': STATE_RULE,
    'ABSENT_SUFFICIENCY_CANNOT_INVENT_SCOPE': '未声明均值充分性时scope=UNKNOWN且covered_nodes为空；不补科学条件。',
    'UNSPECIFIED_INFORMATION_SCOPE_MUST_STAY_EMPTY': SCOPE_RULE,
    'DECLARED_INFORMATION_SCOPE_REQUIRES_NODES_AND_DIRECT_EVIDENCE': SCOPE_RULE,
    'INFORMATION_TYPE_REQUIRES_DIRECT_EVIDENCE': '信息类型与可用性必须有本条直接来源；范围及名册引用不能替代。',
    'UNIQUE_SCOPE_SOURCES_REQUIRED': 'scope_source_ids必须是当前来源目录中的不重复编号。',
}


class Information(definitions.PolicyInformation):
    scope_status: Literal['UNSPECIFIED', 'DECLARED'] = Field(description=SCOPE_RULE)
    scope_source_ids: list[str] = Field(description=SCOPE_RULE)

    @model_validator(mode='after')
    def scope_pairing(self):
        if (self.operator != 'UNKNOWN' or self.availability != 'UNKNOWN') and not self.source_ids:
            raise ValueError('INFORMATION_TYPE_REQUIRES_DIRECT_EVIDENCE')
        if self.scope_status == 'UNSPECIFIED':
            if self.outcome_nodes or self.assignment_cells or self.signature_cells or self.scope_source_ids:
                raise ValueError('UNSPECIFIED_INFORMATION_SCOPE_MUST_STAY_EMPTY')
        elif not self.outcome_nodes or not self.scope_source_ids:
            raise ValueError('DECLARED_INFORMATION_SCOPE_REQUIRES_NODES_AND_DIRECT_EVIDENCE')
        if len(set(self.scope_source_ids)) != len(self.scope_source_ids):
            raise ValueError('UNIQUE_SCOPE_SOURCES_REQUIRED')
        return self


class Reading(previous.Reading):
    version: Literal['network-policy-scopes-1']
    information: list[Information]


def _request(request, model, *, contract=CONTRACT):
    # Use the same ownership factory, retaining the issued field descriptions.
    result = definitions._request(request, model, contract=contract,
        extra_required={'mean_sufficiency': 'study when covered_nodes is nonempty; scope and adoption need direct evidence'},
        schema_aliases={'DefinedMeanSufficiency': 'SelectedMeanSufficiency', 'Information': 'PolicyInformation'})
    body = json.loads(result['user']); schema = body['output_schema']
    info = schema['$defs']['Information']
    info['allOf'] = [{
        'if': {'properties': {'scope_status': {'const': 'UNSPECIFIED'}}, 'required': ['scope_status']},
        'then': {'properties': {k: {'maxItems': 0} for k in ('outcome_nodes','assignment_cells','signature_cells','scope_source_ids')}},
        'else': {'properties': {k: {'minItems': 1} for k in ('outcome_nodes','scope_source_ids')}}},
        {'if': {'anyOf': [
            {'properties': {'operator': {'not': {'const': 'UNKNOWN'}}}, 'required': ['operator']},
            {'properties': {'availability': {'not': {'const': 'UNKNOWN'}}}, 'required': ['availability']}]},
         'then': {'properties': {'source_ids': {'minItems': 1}}}}]
    for name in ('scope_status','scope_source_ids','outcome_nodes'):
        info['properties'][name]['description'] = SCOPE_RULE
    for node in schema['$defs'].values():
        props = node.get('properties', {})
        if 'status' in props and 'source_ids' in props:
            node.setdefault('allOf', []).append({
                'if': {'properties': {'status': {'const': 'NOT_STATED'}}, 'required': ['status']},
                'then': {'properties': {'source_ids': {'maxItems': 0}}},
                'else': {'properties': {'source_ids': {'minItems': 1}}}})
            props['source_ids']['description'] = props['source_ids'].get('description','') + ' ' + STATE_RULE
    body['information_scope_contract'] = dict(instruction=SCOPE_RULE, automatic_scope_inference=False,
        source_ownership=dict(source_ids='information type and availability', scope_source_ids='declared object scope', definition_refs='identity only'))
    return dict(system=result['system'], user=json.dumps(body,ensure_ascii=False))


def make_request(bundle, *, binding, assignment_semantics=None):
    return _request(previous.make_request(bundle,binding=binding,assignment_semantics=assignment_semantics), Reading)


def make_contrast_request(bundle, *, binding, assignment_semantics=None):
    from . import network_contrast_reading as contrast
    return _request(previous.make_contrast_request(bundle,binding=binding,assignment_semantics=assignment_semantics),
                    contrast.reading_model(CONTRACT))


def _project(raw, model):
    value = model.model_validate(deepcopy(raw)).model_dump(mode='json'); scopes = []
    for index, row in enumerate(value['information']):
        scopes.append(dict(field_path=f'/information/{index}', scope_status=row.pop('scope_status'),
            scope_source_ids=row.pop('scope_source_ids'), outcome_nodes=deepcopy(row['outcome_nodes']),
            source_entailment_verified=False))
    return value, scopes


def _receipt(decoded, raw, scopes):
    # Keep all declared scope sources in the original bound source worksheet.
    # Do not turn them into additional population-information tables.
    decoded['evidence_dependencies'].update(version=CONTRACT, information_scopes=scopes,
        automatic_scope_inference=False)
    if 'statement_reading_receipt' in decoded:
        decoded['statement_reading_receipt']['original_candidate_sha256'] = hashlib.sha256(
            json.dumps(raw,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
    return decoded


def parse(bundle, raw, *, binding):
    from .source_reference_wire import expand
    from .network_policy_reading import reference_catalog
    value, scopes = _project(raw, Reading)
    expand(deepcopy(raw), reference_catalog(bundle,binding=binding))
    value['version'] = previous.CONTRACT
    return _receipt(previous.parse(bundle,value,binding=binding),raw,scopes)


def parse_contrast(bundle, raw, *, binding):
    from . import network_contrast_reading as contrast
    from .source_reference_wire import expand
    value, scopes = _project(raw, contrast.reading_model(CONTRACT))
    expand(deepcopy(raw), contrast.reference_catalog(bundle,binding=binding))
    decoded = _receipt(previous.parse_contrast(bundle,value,binding=binding),raw,scopes)
    for side in contrast.SIDES:
        endpoint = deepcopy(raw); endpoint['version'] = CONTRACT
        kind = {'FIXED_POLICY_MEAN_DIFFERENCE':'FIXED_POLICY_MEAN','OTHER':'OTHER','UNKNOWN':'UNKNOWN'}[raw['target']['kind']]
        endpoint['target'] = dict(deepcopy(raw['target'][side]),kind=kind)
        decoded['endpoint_candidates'][side] = endpoint
        decoded['endpoint_readings'][side] = parse(bundle,endpoint,binding=binding)
    return decoded


def field_constraints(paths, *, request, contract=CONTRACT):
    rows = definitions.field_constraints(paths,request=request,contract=contract)
    for path in paths:
        if not path or path.startswith('/information'):
            rows.append(dict(field_path=path,description=SCOPE_RULE))
        if not path or path.startswith(('/first_stage_exclusion','/scientific_statements','/mean_sufficiency')):
            rows.append(dict(field_path=path,description=STATE_RULE))
    return rows


def validation_diagnostic(error):
    """Only closed, model-owned codes; never expose arbitrary validator text."""
    cause = error.get('ctx',{}).get('error')
    args = cause.args if type(cause) is ValueError else ()
    if len(args)==1 and type(args[0]) is str and args[0] in RULE_CODES:
        return dict(error_code=args[0],description=RULE_CODES[args[0]])
    return {}
