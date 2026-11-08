"""Explicit, table-scoped evidence links for the existing R3 signature reader.

Only evidence representation changes. Raw references are retained for review;
the mathematical adapter receives the same facts and direct claim sources.
"""
from copy import deepcopy
from hashlib import sha256
import json
from typing import Literal
from pydantic import Field, model_validator, field_validator
from pydantic_core import PydanticCustomError
from . import network_observational_signature_reading as previous
from . import network_observational_policy_reading as base
from .source_reference_wire import catalog, expand, definition_evidence

PROFILE = 'mean-signature-definitions'
VERSION = 'network-observational-definitions-1'
RULE = ('source_ids引用本记录的直接主张；definition_refs只复用已引用的定义。'
    'study解释对象身份和本人处理编码，table_coordinates解释本条information的表头对象顺序和0/1编码。'
    '政策选择、评价范围、概率值、信息覆盖及科学采用状态仍须直接引用；不能由定义推出。'
    '未声明依赖不继承，定义与主张分别审核，不替模型选择来源。')
COORDINATES_RULE = ('逐表记录原表头的对象顺序node_order和本人处理编码：treated_value=1、untreated_value=0。'
    'source_ids引用表头和编码原文；不知道的定义留空列表或null。'
    '本表存在完整安排记录时，这些定义必须齐全；其他表的表头不能替代。')
DEFINITIONS = {
    'study':dict(path='/study/source_ids', supports=['object identity','own-treatment coding']),
    'table_coordinates':dict(path='/information/*/coordinates/source_ids',
        supports=['this table object order','this table own-treatment coding']),
}


def require_links(record, name, required):
    if len(record.definition_refs)!=len(set(record.definition_refs)):
        raise PydanticCustomError('unique_definition_refs','Definition references must be unique')
    if required and name not in record.definition_refs:
        raise PydanticCustomError('explicit_definition_required','Declare the definition dependency: {name}',{'name':name})
    if record.definition_refs and not record.source_ids:
        raise PydanticCustomError('direct_claim_source_required','A definition cannot replace the direct claim source')
    return record


class Target(base.Target):
    definition_refs: list[Literal['study']] = Field(description=RULE)

    @model_validator(mode='after')
    def dependencies(self):return require_links(self,'study',bool(self.assignment or self.population))


class AssignmentMass(base.AssignmentMass):
    definition_refs: list[Literal['table_coordinates']] = Field(description=RULE)

    @model_validator(mode='after')
    def dependencies(self):return require_links(self,'table_coordinates',bool(self.assignment))


class Coordinates(base.Cited):
    node_order: list[str]
    treated_value: Literal[1] | None
    untreated_value: Literal[0] | None

    @field_validator('treated_value','untreated_value',mode='before')
    @classmethod
    def integer_coding(cls,value):
        if value is not None and type(value) is not int:
            raise PydanticCustomError('integer_coding_required','Coding must be an integer or null')
        return value


class Information(base.Information):
    definition_refs: list[Literal['study']] = Field(description=RULE)
    coordinates: Coordinates = Field(description=COORDINATES_RULE)
    assignment_masses: list[AssignmentMass] = Field(max_length=4096)

    @model_validator(mode='after')
    def dependencies(self):
        require_links(self,'study',bool(self.outcome_nodes))
        c=self.coordinates
        if len(c.node_order)!=len(set(c.node_order)):
            raise PydanticCustomError('unique_table_nodes','Table node order must be unique')
        if any(row.assignment for row in self.assignment_masses):
            if not c.node_order or c.treated_value!=1 or c.untreated_value!=0 or not c.source_ids:
                raise PydanticCustomError('table_coordinates_required','Populated table requires its own cited order and coding')
            if any(row.assignment and set(row.assignment)!=set(c.node_order) for row in self.assignment_masses):
                raise PydanticCustomError('table_coordinate_mismatch','Row objects must match this table coordinate definition')
        return self


class Sufficiency(previous.ConditionalMeanSufficiency):
    definition_refs: list[Literal['study']] = Field(description=RULE)

    @model_validator(mode='after')
    def dependencies(self):return require_links(self,'study',bool(self.covered_nodes))


class Reading(previous.ObservationalSignatureReading):
    version: Literal['network-observational-definitions-1']
    target: Target
    information: list[Information]
    mean_sufficiency: Sufficiency = Field(description=previous.SUFFICIENCY_DESCRIPTION)

    @model_validator(mode='after')
    def definition_scope(self):
        records=[self.target,self.mean_sufficiency,*self.information]
        if any('study' in r.definition_refs for r in records) and not self.study.source_ids:
            raise PydanticCustomError('cited_definition_required','Referenced study definition needs sources')
        if any(set(row.coordinates.node_order)-set(self.study.nodes) for row in self.information):
            raise PydanticCustomError('table_coordinate_mismatch','Table objects must belong to this study')
        return self


def reference_catalog(bundle, *, binding):
    return catalog(bundle,base.documents(bundle),binding=binding,version=VERSION)


def make_request(bundle, *, binding):
    refs=reference_catalog(bundle,binding=binding)
    request=base.request_for_model(bundle,refs,Reading)
    old=previous.make_request(bundle,binding=binding)
    body=json.loads(request['user']);schema=body['output_schema']
    for name,node in schema['$defs'].items():
        props=node.get('properties',{})
        if 'definition_refs' not in props:continue
        props['definition_refs']['uniqueItems']=True
        node.setdefault('allOf',[]).append(dict(
            **{'if':dict(properties={'definition_refs':dict(minItems=1)},required=['definition_refs']),
               'then':dict(properties={'source_ids':dict(minItems=1)})}))
        keys={'Target':['assignment','population'],'AssignmentMass':['assignment'],
              'Information':['outcome_nodes'],'Sufficiency':['covered_nodes']}[name]
        conditions=[dict(properties={key:dict(**({'minProperties':1,'type':'object'} if key=='assignment' else {'minItems':1,'type':'array'}))},required=[key]) for key in keys]
        node['allOf'].append({'if':{'anyOf':conditions},'then':{'properties':{'definition_refs':{'minItems':1}}}})
    schema['$defs']['Coordinates']['properties']['node_order']['uniqueItems']=True
    schema['$defs']['Information']['allOf'].append({
        'if':{'properties':{'assignment_masses':{'contains':{'properties':{
            'assignment':{'type':'object','minProperties':1}},'required':['assignment']}}},'required':['assignment_masses']},
        'then':{'properties':{'coordinates':{'properties':{
            'node_order':{'minItems':1},'source_ids':{'minItems':1},
            'treated_value':{'const':1},'untreated_value':{'const':0}}}}}})
    body['source_review_contract']=json.loads(old['user'])['source_review_contract']
    body['source_review_contract']['definition_refs_supported']=True
    body['evidence_dependency_contract']=dict(version=VERSION,definitions=deepcopy(DEFINITIONS),
        instruction=RULE,coordinate_instruction=COORDINATES_RULE,
        automatic_source_selection=False,entailment_verified=False)
    return dict(system=old['system'],user=json.dumps(body,ensure_ascii=False))


def parse(bundle, raw, *, binding):
    refs=reference_catalog(bundle,binding=binding)
    value=Reading.model_validate(deepcopy(raw)).model_dump(mode='json')
    if value['reference_context']!=refs['context']:raise ValueError('STALE_SOURCE_REFERENCE_CONTEXT')
    expand(value,refs)  # Includes unused coordinate definitions.
    rows=[('/target',value['target']),('/mean_sufficiency',value['mean_sufficiency'])]
    rows += [(f'/information/{i}',r) for i,r in enumerate(value['information'])]
    rows += [(f'/information/{i}/assignment_masses/{j}',r) for i,info in enumerate(value['information']) for j,r in enumerate(info['assignment_masses'])]
    resolutions=[]
    for path,r in rows:
        uses=r['definition_refs']
        evidence=definition_evidence(value,DEFINITIONS,uses,record_path=path,aliases=refs['aliases'])
        resolutions.append(dict(field_path=path,direct_source_ids=deepcopy(r['source_ids']),
            definition_refs=deepcopy(uses),definitions=evidence))
    for _,r in rows:r.pop('definition_refs')
    coordinates=[deepcopy(info.pop('coordinates')) for info in value['information']]
    value['version']=previous.VERSION
    decoded=base.parse_for_model(value,refs,previous.ObservationalSignatureReading)
    decoded['evidence_dependencies']=dict(version=VERSION,resolutions=resolutions,table_coordinates=coordinates,
        raw_candidate_sha256=sha256(json.dumps(raw,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode('utf8')).hexdigest(),
        automatic_source_selection=False,source_entailment_verified=False,raw_candidate_modified=False,
        scientific_approval=False,native_source_ids_role='DIRECT_CLAIMS_ONLY_DEFINITIONS_RETAINED_IN_RECEIPT')
    return decoded


def field_constraints(paths, *, request):
    body=json.JSONDecoder().raw_decode(request['user'])[0]
    if body.get('evidence_dependency_contract',{}).get('version')!=VERSION:
        raise ValueError('OBSERVATIONAL_DEFINITION_REQUEST_REQUIRED')
    rows=previous.field_constraints(paths,request=request)
    for path in paths:
        rows.append(dict(field_path=path,description=body['evidence_dependency_contract']['instruction']))
        if not path or path.startswith('/information'):
            rows.append(dict(field_path=path,description=body['evidence_dependency_contract']['coordinate_instruction']))
    return rows


def validation_diagnostic(error):
    descriptions={
        'explicit_definition_required':RULE,'unique_definition_refs':RULE,
        'direct_claim_source_required':RULE,'cited_definition_required':RULE,
        'table_coordinates_required':COORDINATES_RULE,'integer_coding_required':COORDINATES_RULE,
        'unique_table_nodes':COORDINATES_RULE,'table_coordinate_mismatch':COORDINATES_RULE,
    }
    return dict(description=descriptions[error['type']]) if error['type'] in descriptions else {}
