"""Explicit evidence dependencies and count-valued local mean outcomes.

Dependencies are supplied on the wire, not guessed from business text. Their
resolution is auditable and establishes no entailment or scientific approval.
"""
from copy import deepcopy
from typing import Literal
import json
from pydantic import Field
from . import network_effect_reading as legacy, role_effect_reading as roles
from .source_reference_wire import expand
from .network_policy_reading import COUNT_RULE

VERSION='network-owned-effect-reading-1'
DEFINITIONS=('study','exposure')
DEPENDENCY_RULE='source_ids只引用本记录主张的直接原文；definition_refs显式引用本次其他定义记录。study提供名册和本人编码，exposure提供同伴编码。两类来源共同接受审核，不自动补依赖或认定引用支持语义。'

class Study(legacy.Study):
 outcome_kind: Literal['BINARY','COUNT','CONTINUOUS','OTHER','UNKNOWN']=Field(description=COUNT_RULE)

class LocalArm(legacy.LocalArm):
 definition_refs: list[Literal['study','exposure']]=Field(description=DEPENDENCY_RULE)

class Assignment(legacy.Assignment):
 definition_refs: list[Literal['study']]=Field(description=DEPENDENCY_RULE)

class Information(legacy.EffectInformation):
 definition_refs: list[Literal['study']]=Field(description=DEPENDENCY_RULE)

class Target(roles.RoleTarget):
 reference: LocalArm
 evaluated: LocalArm
 definition_refs: list[Literal['study']]=Field(description=DEPENDENCY_RULE)

class Reading(roles.RoleReading):
 version: Literal['network-owned-effect-reading-1']
 study: Study
 assignment: Assignment
 target: Target
 information: list[Information]

class CanonicalReading(legacy.NetworkEffectReading):
 study: Study

def transform_request(request):
 request=roles.transform_request(request);body=json.loads(request['user']);old=body['output_schema']
 schema=Reading.model_json_schema()
 # Carry the public descriptions/coverage contracts into the explicit new wire.
 names={'Study':'Study','Assignment':'Assignment','Target':'EffectTarget','Information':'EffectInformation','LocalArm':'LocalArm'}
 for name,node in schema['$defs'].items():
  prior=old['$defs'].get(names.get(name,name),{})
  for k,p in node.get('properties',{}).items():
   if k not in ('definition_refs','outcome_kind') and k in prior.get('properties',{}) and 'description' in prior['properties'][k]:
    p['description']=prior['properties'][k]['description']
 for node in [schema,*schema['$defs'].values()]:
  for name,p in node.get('properties',{}).items():
   if name.endswith('source_ids'):p.update(items={'$ref':'#/$defs/SourceId'},uniqueItems=True)
 schema['$defs']['SourceId']=deepcopy(old['$defs']['SourceId'])
 schema['properties']['reference_context']['const']=old['properties']['reference_context']['const']
 body['output_schema']=schema;body['fact_contract']=VERSION
 body.pop('source_dependency_contract',None);body.pop('role_coordinate_contract',None)
 body['evidence_dependency_contract']=dict(version=VERSION,definitions={
  'study':dict(path='/study/source_ids',supports=['object identity','own-treatment coding']),
  'exposure':dict(path='/exposure/source_ids',supports=['exposure coding'])},
  required=dict(assignment=['study when probabilities, groups or clusters contain named objects'],target=['study when population nonempty'],
   local_arm=['study when own known','exposure when exposure known'],information=['study when outcome_nodes nonempty']),
  instruction=DEPENDENCY_RULE,automatic_source_selection=False,entailment_verified=False)
 # Replace only citation ownership wording. Scientific and information rules stay.
 system=request['system']
 from .network_source_dependencies import INSTRUCTION
 system=system.replace('\n'+INSTRUCTION,'')
 from .source_coverage_contract import INSTRUCTION as flat_citations
 system=system.replace('\n'+flat_citations,'')
 system=system.replace('reference和evaluated各自引用选择该角色状态的业务原文及own/exposure编码定义。',
  'reference和evaluated各自的source_ids引用选择该角色状态的业务原文；编码来源通过显式definition_refs解析。')
 system+='\n'+DEPENDENCY_RULE+'\n'+COUNT_RULE+'\n'
 system+='新合同中source_ids负责直接事实，definition_refs负责编码与名册依赖；父定义引用不能隐式继承，必须在本记录列出依赖。'+\
  '有概率名单、分组或簇名单的assignment、有评价名单的target及有对象名单的information须列study；own已知的两端列study，exposure已知的两端列exposure。'+\
  '本端source_ids引用业务所选状态；定义引用不能替代这项选择。有限记录未明确覆盖哪些对象时outcome_nodes留空，不能因study有完整名册便声称记录覆盖全体。'
 # Override superseded local citation descriptions, keeping new rule explicit.
 for name in ('LocalArm','Assignment','Target','Information'):
  schema['$defs'][name]['properties']['source_ids']['description']=DEPENDENCY_RULE
 body['source_coverage_contract']=dict(version=VERSION,groups={
  **{k:v for k,v in legacy.CITATION_GROUPS.items() if k not in ('EffectTarget','EffectInformation','LocalArm','Assignment')},
  'Target':{'source_ids':['kind','population scope','aggregation'],'definition_refs':['object identity'], 'remaining_source_ids':['remaining_assignment']},
  'Information':{'source_ids':['operator','availability','scope'],'definition_refs':['object identity']},
  'Assignment':{'source_ids':['kind',*legacy.components.ASSIGNMENT_FIELDS],'definition_refs':['object identity']},
  'LocalArm':{'source_ids':['selected own state','selected exposure state'],'definition_refs':['own/exposure coding']}},independent_review_required=True)
 return dict(system=system,user=json.dumps(body,ensure_ascii=False))

def parse(bundle,raw,*,binding,reviewed_query):
 wire=Reading.model_validate(deepcopy(raw));candidate=wire.model_dump(mode='json')
 refs=legacy.reference_catalog(bundle,binding=binding)
 if wire.reference_context!=refs['context']:raise ValueError('STALE_EFFECT_REFERENCE_CONTEXT')
 # Reject foreign IDs even on definitions not subsequently used.
 expand(deepcopy(candidate),refs)
 resolutions=[]
 rows=[('/assignment',candidate['assignment'],{'study'} if any(getattr(wire.assignment, k) for k in ('probabilities','groups','clusters')) else set()),
  ('/target',candidate['target'],{'study'} if wire.target.population else set())]
 rows += [(f'/target/{name}',candidate['target'][name],
  ({'study'} if getattr(wire.target,name).own is not None else set()) | ({'exposure'} if getattr(wire.target,name).exposure is not None else set())) for name in ('reference','evaluated')]
 rows += [(f'/information/{i}',c,{'study'} if c['outcome_nodes'] else set()) for i,c in enumerate(candidate['information'])]
 for path,record,required in rows:
  uses=record.pop('definition_refs')
  if len(set(uses))!=len(uses) or not required<=set(uses):raise ValueError('EXPLICIT_DEFINITION_DEPENDENCIES_REQUIRED')
  direct=list(record['source_ids']);resolved=list(direct)
  for name in uses:
   origin=candidate[name]['source_ids']
   if not origin:raise ValueError('CITED_DEFINITION_REQUIRED')
   resolved.extend(origin)
  # Direct claim evidence cannot be replaced by a declaration of its definitions.
  if required and not direct:raise ValueError('DIRECT_CLAIM_SOURCE_REQUIRED')
  record['source_ids']=list(dict.fromkeys(resolved))
  resolutions.append(dict(field_path=path,direct_source_ids=direct,definition_refs=uses,resolved_source_ids=record['source_ids']))
 business_kind=candidate['study']['outcome_kind']
 candidate['version']=roles.VERSION
 if business_kind=='COUNT':candidate['study']['outcome_kind']='CONTINUOUS'
 decoded=roles.parse(bundle,candidate,binding=binding,reviewed_query=reviewed_query)
 decoded['facts']['study']['outcome_kind']=business_kind
 CanonicalReading.model_validate(decoded['facts'])
 decoded['evidence_dependencies']=dict(version=VERSION,resolutions=resolutions,source_entailment_verified=False,raw_candidate_modified=False)
 decoded['outcome_domain_embedding']=dict(business_kind=business_kind,native_kind='continuous' if business_kind=='COUNT' else business_kind.lower(),
  scope='LOCAL_POINT_MEAN_ONLY',count_restriction_retained_in_business=True,distributional_continuity_assumed=False,
  sharp_bound_or_nonidentification_transfer=False)
 return decoded

def field_constraints(paths):
 from .reading_alignment_contract import SCIENCE
 return roles.field_constraints(paths)+[dict(field_path=p,description=DEPENDENCY_RULE+' '+COUNT_RULE+' '+SCIENCE) for p in paths]
