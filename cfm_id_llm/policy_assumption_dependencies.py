"""One declared rule table for absent/explicit assumption evidence.

Schema, model parsing, source review, diagnostics and rechecks share these
rules. Prior wires are unchanged. No candidate repair or scientific approval.
"""
from copy import deepcopy
from dataclasses import dataclass
from typing import Literal
from pydantic import ConfigDict, model_validator
from . import policy_scope_reading as previous, policy_record_definitions as records

CONTRACT = 'network-policy-scopes-2'


@dataclass(frozen=True)
class Rule:
    code: str
    trigger_field: str
    trigger: str
    requirements: tuple
    description: str

    def schema(self):
        condition = ({'const':'NOT_STATED'} if self.trigger=='NOT_STATED' else
                     {'not':{'const':'NOT_STATED'}} if self.trigger=='EXPLICIT' else {'minItems':1})
        return {'if':{'properties':{self.trigger_field:condition},'required':[self.trigger_field]},
                'then':{'properties':deepcopy(dict(self.requirements))}}

    def violated(self, value):
        actual=value[self.trigger_field]
        active=(actual=='NOT_STATED' if self.trigger=='NOT_STATED' else
                actual!='NOT_STATED' if self.trigger=='EXPLICIT' else bool(actual))
        if not active:return False
        for field, constraint in self.requirements:
            v=value[field]
            if ('const' in constraint and v!=constraint['const'] or
                'maxItems' in constraint and len(v)>constraint['maxItems'] or
                'minItems' in constraint and len(v)<constraint['minItems'] or
                'contains' in constraint and constraint['contains']['const'] not in v):return True
        return False


RULES = (
    Rule('ABSENT_ASSUMPTION_HAS_NO_DEPENDENCIES','status','NOT_STATED',
         (('source_ids',{'maxItems':0}),('definition_refs',{'maxItems':0}),
          ('covered_nodes',{'maxItems':0}),('scope',{'const':'UNKNOWN'})),
         'NOT_STATED：没有这项科学声明；来源、定义依赖、覆盖名单为空，scope为UNKNOWN。'),
    Rule('EXPLICIT_STATEMENT_REQUIRES_SOURCE_SELECTION','status','EXPLICIT',
         (('source_ids',{'minItems':1}),),
         '采用、拟采用、拒绝、未定、冲突均是明确声明，须引用本声明原文；引用不等于科学批准。'),
    Rule('EXPLICIT_DEFINITION_DEPENDENCIES_REQUIRED','covered_nodes','NONEMPTY',
         (('definition_refs',{'contains':{'const':'study'}}),),
         '覆盖名单非空时显式引用study解释对象；覆盖范围及科学状态仍需自己的直接来源。'),
    Rule('DIRECT_CLAIM_SOURCE_REQUIRED','definition_refs','NONEMPTY',
         (('source_ids',{'minItems':1}),),
         '定义依赖不替代直接主张来源；不得为通过校验补造来源或改变科学状态。'),
)


def rule_sheet():
    return [dict(error_code=r.code,description=r.description,combination=r.schema()) for r in RULES]


def schema_rules(schema):
    schema.setdefault('allOf',[]).extend(r.schema() for r in RULES)
    schema['x-cfm-field-contract']=rule_sheet()


class DefinedMeanSufficiency(records.DefinedMeanSufficiency):
    model_config=ConfigDict(json_schema_extra=schema_rules)

    @model_validator(mode='after')
    def definition_state_pairing(self):
        value=self.model_dump(mode='json')
        for rule in RULES:
            if rule.violated(value):raise ValueError(rule.code)
        return self


class Reading(previous.Reading):
    version: Literal['network-policy-scopes-2']
    mean_sufficiency: DefinedMeanSufficiency


def make_request(bundle, *, binding, assignment_semantics=None):
    request=previous.make_request(bundle,binding=binding,assignment_semantics=assignment_semantics)
    return previous._request(request,Reading,contract=CONTRACT)


def make_contrast_request(bundle, *, binding, assignment_semantics=None):
    from . import network_contrast_reading as contrast
    request=previous.make_contrast_request(bundle,binding=binding,assignment_semantics=assignment_semantics)
    return previous._request(request,contrast.reading_model(CONTRACT),contract=CONTRACT)


def _receipt(decoded,raw):
    # Same declared coordinates and assumptions, only a distinct wire identity.
    return previous._receipt(decoded,raw,decoded['evidence_dependencies']['information_scopes'])


def parse(bundle,raw,*,binding):
    value=Reading.model_validate(deepcopy(raw)).model_dump(mode='json')
    value['version']=previous.CONTRACT
    decoded=_receipt(previous.parse(bundle,value,binding=binding),raw)
    decoded['evidence_dependencies']['version']=CONTRACT
    return decoded


def parse_contrast(bundle,raw,*,binding):
    from . import network_contrast_reading as contrast
    contrast.reading_model(CONTRACT).model_validate(deepcopy(raw))
    decoded=_receipt(previous.parse_contrast(bundle,raw,binding=binding),raw)
    decoded['evidence_dependencies']['version']=CONTRACT
    for side in contrast.SIDES:
        endpoint=decoded['endpoint_candidates'][side]
        endpoint['version']=CONTRACT
        decoded['endpoint_readings'][side]=parse(bundle,endpoint,binding=binding)
    return decoded


def field_constraints(paths,*,request):
    rows=previous.field_constraints(paths,request=request,contract=CONTRACT)
    if any(not p or '/mean_sufficiency'.startswith(p) or p.startswith('/mean_sufficiency/') for p in paths):
        rows += [dict(field_path='/mean_sufficiency',**r) for r in rule_sheet()]
    return rows


def validation_diagnostic(error):
    cause=error.get('ctx',{}).get('error')
    code=cause.args[0] if type(cause) is ValueError and len(cause.args)==1 else None
    rule=next((r for r in RULES if r.code==code),None)
    return dict(error_code=rule.code,description=rule.description,combination=rule.schema()) if rule else previous.validation_diagnostic(error)
