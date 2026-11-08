"""One owner for shared local conditions; explicit projection, no text inference."""
from copy import deepcopy
from dataclasses import asdict
from . import requested_change_contract as previous, ordered_comparison_contract as ordered
from . import owned_effect_reading as facts
from .business_field_contract import Field

CONTRACT='local-role-ownership-1'
FACT_VERSION=facts.VERSION
apply_gate=previous.apply_gate
EXTRA_STATE_RULES=previous.EXTRA_STATE_RULES
SHARED=Field('shared_condition','两端共同保持的局部条件。',
 'DIRECT_EFFECT只写共同同伴状态；SPILLOVER_EFFECT只写共同本人状态。LOCAL_TOTAL_EFFECT两坐标均改变，没有共同局部处理状态时写UNKNOWN，端点仍完整给出。明确未定保留MISSING及原因和原文，未提为UNKNOWN，不猜0/1。',section='comparison_request')
GUIDANCE='''局部比较每项信息只填写一次。comparison_request.reference/evaluated只写两端发生变化的状态：DIRECT_EFFECT写本人是否使用；SPILLOVER_EFFECT写合作对象使用条件；LOCAL_TOTAL_EFFECT同时写本人及合作对象状态。shared_condition只写两端共同局部处理条件：直接效应为同伴条件，同伴效应为本人状态；LOCAL_TOTAL_EFFECT没有共同局部处理状态时用UNKNOWN，不补一个固定状态。未知或未定的共同条件保留UNKNOWN/MISSING，不能因为两端变化明确而补齐。不要在semantics再输出neighbor_exposure。
各角色用业务原文表达，不需要把启用、不启用或过半重复写成数值代码；编码定义在common的相应字段保留。角色引用选择该状态的目标原文；若自行写出编码，仍需引用编码定义。quantity的枚举、方向与独立引用规则不变。
aggregation只写如何汇总和权重，不重复common.outcome中的结果名称、单位或semantics.time_horizon中的期间；target_population记录评价谁，standardization_distribution记录其余安排按何规则平均。goal保留本问，不扩写资料定义。所有原文明确的信息必须有其所属字段，减少重复不允许删除真实条件。'''

def omitted_semantics(query):
 return (*previous.omitted_semantics(query),'neighbor_exposure') if query.get('kind') in ordered.LOCAL_KINDS else previous.omitted_semantics(query)

def review_definition(rule):
 if rule.name=='shared_condition':return dict(asdict(SHARED),wire_description=SHARED.meaning+' '+SHARED.excludes)
 if rule.section=='comparison_request' and rule.name in ('reference','evaluated'):
  d=previous.review_definition(rule);d['excludes']='只写本端变化状态；共同条件归shared_condition。引用原文选择该状态的位置，写编码时另需定义。';d['wire_description']=d['meaning']+' '+d['excludes'];return d
 return previous.review_definition(rule)

def review_semantics(query,rule):
 d=previous.review_semantics(query,rule)
 if query.get('kind') in ordered.LOCAL_KINDS and rule.name=='aggregation':
  d.update(meaning='本问如何汇总结果及其权重。',excludes='结果名称和单位由common.outcome拥有，时期由time_horizon拥有，不在此重复。')
  d['wire_description']=d['meaning']+' '+d['excludes']
 return d

def describe(schema):
 previous.describe(schema);defs=schema['$defs'];s=defs['OrderedLocalSemantics']
 s['properties'].pop('neighbor_exposure')
 if 'required' in s:s['required']=[k for k in s['required'] if k!='neighbor_exposure']
 s['properties']['aggregation']['description']='只写汇总方式和权重；不重复结果名称、单位、时期和评价名单。'
 r=defs['LocalChangeRequest'];r['properties']['shared_condition']=deepcopy(r['properties']['reference']);r['required'].append('shared_condition')
 for name in ('reference','evaluated','shared_condition'):
  rule=SHARED if name=='shared_condition' else previous.RULES[name]
  r['properties'][name]['description']=review_definition(rule)['wire_description']
 return ''

def system_prompt(**kwargs):
 system=previous.system_prompt(**kwargs)
 old=next(p for p in previous.GUIDANCE.splitlines() if p.startswith('直接效应两端'))
 return system.replace(old,GUIDANCE)

def _combine(*claims):
 """Join explicit claims only; retain unknown/missing state, never infer values."""
 refs=list(dict.fromkeys(r for c in claims if type(c) is dict for r in c.get('refs',[])))
 missing=[c for c in claims if type(c) is dict and c.get('state')=='MISSING']
 if missing:
  return dict(state='MISSING',reason='；'.join(c['reason'] for c in missing),refs=refs)
 if any(c=='UNKNOWN' or type(c) is dict and c.get('state')=='UNKNOWN' for c in claims):return 'UNKNOWN'
 return dict(state='INTERPRETED' if any(c['state']=='INTERPRETED' for c in claims) else 'STATED',
  value='；'.join(c['value'] for c in claims),refs=refs)

def project(raw,catalog):
 from .compact_formulator import CompactClaim
 from .compact_inline_evidence_contract import MissingClaim
 value=deepcopy(raw);refs={c['ref'] for c in catalog}
 for i,q in enumerate(value.get('queries',[]) if type(value) is dict else []):
  if q.get('kind') not in ordered.LOCAL_KINDS:continue
  r=q.get('comparison_request',{});sem=q.get('semantics',{})
  if 'neighbor_exposure' in sem:previous._reject(i,['semantics','neighbor_exposure'],'CHANGE_LEGACY_FIELD_FORBIDDEN')
  if 'shared_condition' not in r:previous._reject(i,['comparison_request','shared_condition'],'missing')
  common=r.pop('shared_condition')
  try:
   if common!='UNKNOWN':
    if type(common) is not dict or common.get('state')=='NOT_APPLICABLE':raise ValueError()
    c=(MissingClaim if common.get('state')=='MISSING' else CompactClaim).model_validate(common)
    if len(set(c.refs))!=len(c.refs) or any(x not in refs for x in c.refs):raise ValueError()
  except (ValueError,TypeError):previous._reject(i,['comparison_request','shared_condition'],'CHANGE_SHAPE_INVALID')
  # Validate original variable-role claims before composing any canonical field.
  for role in ('reference','evaluated'):
   c=r.get(role)
   try:
    if c!='UNKNOWN':
     if type(c) is not dict or c.get('state')=='NOT_APPLICABLE':raise ValueError()
     parsed=(MissingClaim if c.get('state')=='MISSING' else CompactClaim).model_validate(c)
     if len(set(parsed.refs))!=len(parsed.refs) or any(x not in refs for x in parsed.refs):raise ValueError()
   except (ValueError,TypeError):previous._reject(i,['comparison_request',role],'CHANGE_SHAPE_INVALID')
  sem['neighbor_exposure']=deepcopy(common)
  if q['kind']=='SPILLOVER_EFFECT':
   sem['neighbor_exposure']=_combine(common,r['reference'],r['evaluated'])
   for role in ('reference','evaluated'):r[role]=_combine(common,r[role])
 return previous.project(value,catalog)

def review_items(raw,query_id):
 yield from previous.review_items(raw,query_id)
 q=raw['queries'][int(query_id[1:])-1]
 if q.get('kind') in ordered.LOCAL_KINDS:
  c=q['comparison_request']['shared_condition']
  yield SHARED,f'queries.{query_id}.comparison_request.shared_condition',c,c.get('state','UNKNOWN') if type(c) is dict else c

def fact_focus(raw_query,*,query_id,binding):
 from .role_coordinate_contract import fact_focus as old
 focus=old(raw_query,query_id=query_id,binding=binding)
 focus['reviewed_business_roles']['contract']=CONTRACT
 focus['reviewed_business_roles']['shared_condition']={k:deepcopy(v) for k,v in raw_query['comparison_request']['shared_condition'].items() if k!='refs'} if type(raw_query['comparison_request']['shared_condition']) is dict else raw_query['comparison_request']['shared_condition']
 return focus

def recheck_field_roles(paths,**kwargs):
 rows=previous.recheck_field_roles(paths,**kwargs)
 for row in rows:
  if '/comparison_request' in row['field_path'] or '/semantics' in row['field_path']:row['field_role']=GUIDANCE
 return rows

clarify_fact_request=facts.transform_request
fact_constraints=facts.field_constraints
