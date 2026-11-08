"""Synthetic five-route fixtures and frozen browser questions, not model answers.

Reference readings are ONLY for deterministic regression. Web experiments send
question + proposal as plain text and must not reuse these readings/reviews.
"""
from copy import deepcopy
from itertools import product
from cfm_id_llm import network_extended_reading as rd
from cfm_id import network_extended_dispatch as adapter
from .business_dispatch_reference import approve

NODES=['甲站','乙站','丙站']
KINDS={'arm':'NETWORK_DESIGN_STANDARDIZED_ARM_MEAN','mixture':'STOCHASTIC_POLICY_VALUE',
       'observed':'DIRECT_EFFECT','stratum':'DIRECT_EFFECT','nodewise':'SPILLOVER_EFFECT'}
FAMILIES={'arm':rd.ARM,'mixture':rd.MIX,'observed':rd.OBS,'stratum':rd.OBS,'nodewise':rd.OBS}
QUESTIONS={
 'arm':'我们管理甲、乙、丙三个社区配送站，站点之间会互相调配骑手。想了解本周甲站使用排班助手、相邻站点都不使用时，甲站每单的平均配送分钟数是多少。只评价甲站，不与其他情况相减；其余安排按原试点抽签规则在上述条件下的概率平均。',
 'mixture':'我们管理甲、乙、丙三个社区配送站，站点之间会互相调配骑手。本周准备在两个完整方案中抽签：四分之一概率只让甲站使用排班助手，四分之三概率只让乙站使用，其他站均不使用。这就是全部候选方案。希望知道这个抽签政策下三个站每单平均配送分钟数的等权平均是多少。',
 'observed':'我们管理甲、乙、丙三个社区配送站，站点之间会互相调配骑手。过去由各站自行决定是否使用排班助手。想在工具使用前已登记的普通需求背景下，评价本周甲站在相邻站都不用时，自己使用相对于自己不用，每单平均配送分钟数相差多少。先算使用减不使用，只评价甲站；其余站的使用安排按这个背景下实际采用规律在对应状态内的概率平均，不跨背景平均。',
 'stratum':'我们管理甲、乙、丙三个社区配送站，站点之间会互相调配骑手。过去由各站自行决定是否使用排班助手。想在普通需求背景下，比较本周甲站在相邻站都不用时，自己使用减去自己不用，每单平均配送分钟数的变化。只评价甲站。先在业务淡季和旺季分别比较，再按这两个季节在研究总体中的占比平均，不按工具使用概率加权。季节在使用工具前已经确定。',
 'nodewise':'我们管理甲、乙、丙三个社区配送站，站点之间会互相调配骑手。过去由各站自行决定是否使用排班助手。想在普通需求背景下，比较本周甲站自己不用时，至少一个相邻站使用减去相邻站都不用，每单平均配送分钟数相差多少。只评价甲站。比较时调整甲站是否配有专职调度员，以及全部相邻站中有专职调度员的站数，再按这两项特征的总体分布平均；这些人员配置在使用工具前已确定。',
}
COMMON='''这是用于演示的合成研究方案，并非企业真实数据。研究单位的完整顺序为甲站、乙站、丙站。甲站与乙站合作，乙站与丙站合作，没有其他合作边、没有自环，是使用工具前固定的无向网络。本周各站是否使用排班助手记为1或0；1是使用，0是不使用。结果是本周每单平均配送分钟数，连续数值。评价对象在使用工具前已固定。
本研究采用以下条件：实际观察结果等于该次完整使用名单下的潜在结果；上述合作网络在本周保持固定；所涉及的条件平均结果存在且有限。两端比较使用同一结果定义、本周时期和背景。只要至少一个合作邻站使用，就将同伴状态记为1，否则为0。这只是状态定义，本身不表示两种完整安排的结果相同。'''

def business(name,negative=False):
    q=QUESTIONS[name];text=COMMON
    if name in ('arm','mixture'):
        text+='\n原试点是每个站独立抽签，以1/2概率使用；全部分配规则已知。研究采用完整抽签名单与所有站在全部可能完整名单下的潜在结果独立这一条件。没有第一阶段名额方案。'
        text+='\n理论识别可用同一研究下每个站的结果与完整使用向量的符号总体联合分布，覆盖全部三个站，不是样本估计；本次不提供总体均值的数值。'
    else:
        text+='\n历史使用方式是各站自行选择，不是随机试验。研究固定在工具使用前登记的普通需求背景，背景不包含季节或调度人员配置；所给信息、科学条件和本次目标均对应这个固定背景。'
        if name=='observed':
            text+='\n本研究采用：在该固定背景下，全部站点在所有完整使用安排下的潜在结果，与实际完整使用向量条件独立。'
            text+='\n给定同一符号总体信息：实际使用向量的总体分布按三个站分解，每个站的使用概率为1/2，并且包括甲站在本人0或1、同伴状态0或1这四个状态下的结果条件总体均值。此处是观察分布的描述，不把它当作随机试验。分配律完整，四个均值的覆盖明确；不提供均值数值，不是样本估计。'
        else:
            text+='\n本研究另行采用：对甲站，在所有完整使用安排下，只要甲站本人的使用状态和上述同伴状态相同，其个体潜在结果就相同。这是额外科学条件，不是由同伴状态定义得出的。'
            if name=='stratum':
                text+='\n共同处理前季节B有淡季、旺季两层，研究总体各占1/2。给定任一季节和普通需求背景后，三个站实际使用的联合分布按站分解，各站概率均为1/2。另给定甲站在每个季节、本人0或1且同伴0或1下的全部八个结果条件总体均值算子，数值未给，不是样本估计。两季是全部层级，所给总体分布与均值范围完整。研究采用：在每个季节和该背景内，甲站在每一种本人/同伴状态下的潜在结果均值，不随实际本人使用状态和实际同伴状态改变。'
            else:
                text+='\n处理前每站是否配有专职调度员记为X，1有、0无。总体只有两个完整配置：甲乙丙全部为0，概率1/2；甲乙丙全部为1，概率1/2。给定任一完整X配置及普通需求背景后，实际使用的联合分布按站分解，各站使用概率均为1/2。甲站的调整变量是自身X与全部合作邻站中X=1的站数，故总体中出现(0,0)和(1,1)两种组合。明确给定甲站在每个组合、本人0或1、同伴0或1下的全部八个结果条件总体均值算子，不给数值，不是样本估计。配置分布及均值覆盖完整。研究采用：给定甲站自身X、全部合作邻站中X=1的站数及普通需求背景后，甲站每一种本人/同伴状态下的潜在结果均值，不随实际本人使用状态与同伴状态改变；不是仅给定全网X向量的另一项假设。'
    if negative:
        if name=='mixture':
            text=text.replace('理论识别可用同一研究下每个站的结果与完整使用向量的符号总体联合分布，覆盖全部三个站，不是样本估计；本次不提供总体均值的数值。','目前只有三个站本周各一条使用和配送记录，没有总体分布或总体条件均值资料。')
        elif name=='arm':
            text=text.replace('研究采用完整抽签名单与所有站在全部可能完整名单下的潜在结果独立这一条件。','是否采用完整抽签名单与全部潜在结果独立这一条件，负责人尚未决定。')
        elif name=='observed':
            text=text.replace('本研究采用：在该固定背景下，全部站点在所有完整使用安排下的潜在结果，与实际完整使用向量条件独立。','本研究明确不采用完整使用向量与全部潜在结果在该背景下条件独立的假设。')
        else:
            text=text.replace('本研究另行采用：对甲站，在所有完整使用安排下，只要甲站本人的使用状态和上述同伴状态相同，其个体潜在结果就相同。','对于甲站本人和同伴状态相同时个体潜在结果相同这一条件，负责人尚未决定是否采用。')
    return dict(id=name+('_negative' if negative else ''),question=q,document=text,expected='NEEDS_INPUT' if negative and name!='observed' else 'ADAPTER_NOT_CONNECTED' if negative else 'POINT')

def fixture(name):
    family=FAMILIES[name];case=business(name)
    bundle=dict(case_id=case['id'],question=case['question'],documents={'proposal':case['document']})
    entry=dict(reader_id=family,reference_format='short_refs',bundle=bundle,fact_binding_sha256='a'*64,request_sha256='b'*64,
        query_id='q1',remaining_query_ids=[],query_review=dict(authority='SYNTHETIC_TEST'),selected_query={'target':{'kind':KINDS[name]}})
    refs=rd.reference_catalog(bundle,binding=entry['fact_binding_sha256'],family=family);ids=list(refs['aliases'])
    cited=lambda **kw:dict(source_ids=ids,**kw)
    dec=lambda v=True:cited(value=v)
    raw=dict(version=rd.MODELS[family].model_fields['version'].annotation.__args__[0],reference_context=refs['context'],
        study=cited(nodes=NODES,edges=[NODES[:2],NODES[1:]],graph_kind='SIMPLE_UNDIRECTED',edge_list_complete=True,
            treatment='本周使用排班助手：1使用，0不用',outcome='本周每单平均配送分钟数',outcome_kind='CONTINUOUS',context='本周'),
        additional_restrictions=[],unresolved=[])
    exposure=cited(kind='ANY_TREATED_NEIGHBOR',core_collaborators=None)
    probs={n:'1/2' for n in NODES}
    if family!=rd.OBS:
        raw.update(assignment=cited(kind='INDEPENDENT_BERNOULLI',probabilities=probs,fixed_count=None),first_stage_exclusion=None,
            assumptions={k:dec() for k in adapter.BASE_CONDITIONS})
        if name=='arm':raw.update(exposure=exposure,target=cited(population=NODES[:1],first=cited(own=1,exposure=0),averaging='ORIGINAL_DESIGN_CONDITIONAL',population_fixed_before_assignment=dec()),
            information=[cited(operator='NODE_FULL_LAW',availability='SYMBOLIC_POPULATION_OPERATOR',outcome_nodes=NODES,arm_cells=[])])
        else:raw.update(target=cited(population=NODES,aggregation='EQUAL_MEAN',policy_distribution_complete=dec(),components=[cited(assignment=dict(zip(NODES,z)),weight=p) for z,p in [([1,0,0],'1/4'),([0,1,0],'3/4')]]),
            information=[cited(operator='NODE_FULL_LAW',availability='SYMBOLIC_POPULATION_OPERATOR',outcome_nodes=NODES,assignment_cells=[])])
    else:
        method={'observed':adapter.P,'stratum':adapter.B,'nodewise':adapter.X}[name]
        assumptions={k:dec() for k in adapter.BASIC}
        for k in ('full_vector_conditional_exchangeability','potential_outcome_exposure_sufficiency','exposure_level_conditional_exchangeability','local_covariate_exposure_mean_exchangeability'):
            assumptions[k]=dec(True if k in adapter.SCIENCE[method] else None)
            if k!='full_vector_conditional_exchangeability':assumptions[k].update(covered_nodes=NODES[:1] if k in adapter.SCIENCE[method] else [],scope='ALL_BINARY_ASSIGNMENTS' if k in adapter.SCIENCE[method] else 'UNKNOWN')
        raw.update(regime=cited(kind='OBSERVATIONAL'),conditioning=cited(kind='FIXED_PRETREATMENT_CONTEXT',definition='使用工具前已登记的普通需求背景'),exposure=exposure,assumptions=assumptions,
            target=cited(kind=KINDS[name],operation='FIRST_MINUS_SECOND',first=cited(own=0 if name=='nodewise' else 1,exposure=1 if name=='nodewise' else 0),second=cited(own=0,exposure=0),population=NODES[:1],aggregation='SINGLE',population_fixed_before_treatment=dec(),shared_outcome_and_context=dec(),averaging=next(k for k,v in adapter.AVG.items() if v==method)))
        s=cited(operator={'observed':'FACTORIZED_ARM_LAW','stratum':'STRATIFIED_ARM_LAW','nodewise':'NODEWISE_ARM_LAW'}[name],availability='SYMBOLIC_POPULATION_OPERATOR',outcome_nodes=NODES[:1],complete_law_and_mean_scope=dec(),same_study_and_context=dec(),assignment_masses=[],probabilities=None,mixture_components=[],adjustment_variable=None,strata=[],profiles=[],covered_cells=[])
        cell=lambda a,e,b=None,x=None,k=None:dict(node=NODES[0],own=a,exposure=e,stratum=b,own_feature=x,neighbor_feature_count=k)
        if name=='observed':s.update(probabilities=probs,covered_cells=[cell(a,e) for a,e in product((0,1),repeat=2)])
        if name=='stratum':s.update(adjustment_variable='处理前季节B',strata=[cited(label=b,mass='1/2',probabilities=probs) for b in ('淡季','旺季')],covered_cells=[cell(a,e,b=b) for b in ('淡季','旺季') for a,e in product((0,1),repeat=2)])
        if name=='nodewise':s.update(adjustment_variable='处理前是否有专职调度员X',profiles=[cited(label=str(x),mass='1/2',features={n:x for n in NODES},probabilities=probs,mixture_components=[]) for x in (0,1)],covered_cells=[cell(a,e,x=x,k=x) for x in (0,1) for a,e in product((0,1),repeat=2)])
        fields={'observed':('probabilities','covered_cells'),'stratum':('adjustment_variable','strata','covered_cells'),'nodewise':('adjustment_variable','profiles','covered_cells')}
        common=('source_ids','operator','availability','outcome_nodes','complete_law_and_mean_scope','same_study_and_context')
        raw['information']=[{k:v for k,v in s.items() if k in (*common,*fields[name])}]
    return entry,raw

def execute(plan):
    records={r['method']:dict(reading_review=approve(r['reading_worksheet']),science_review=approve(r['science_worksheet'])) for r in plan['methods']}
    return adapter._execute_plan(plan,plan_review=approve(plan['plan_worksheet']),native_reviews=records,research_protocol_selected=True)

def setup(name):
    """Legacy canonical A0 compatibility fixture through the common dispatcher."""
    from cfm_id import business_intake as intake,business_dispatch as dispatch
    from cfm_id_llm.schemas import BusinessCase,SourceDocument,SemanticClaim,TargetDraft,DraftProblemSpec,UnitsVariablesDraft,StructureDraft,InformationDesignDraft
    from cfm_id_llm.quality import MultiQueryDraftV010,BusinessInquiryV010,QuerySemanticsV010
    case=business(name);e,raw=fixture(name)
    bc=BusinessCase(case_id=case['id'],business_question=case['question'],sources=[SourceDocument(source_id='proposal',text=case['document'])])
    def claim(value,source):return SemanticClaim(value=value,basis='EXPLICIT_TEXT',evidence=[dict(source_id=source,quote=value)])
    goal=claim(case['question'],'business_question');proposal=claim(case['document'],'proposal')
    sem=dict(target_population=goal,intervention=goal,aggregation=goal,time_horizon=goal,neighbor_exposure=goal,standardization_distribution=goal)
    if name in ('observed','stratum','nodewise'):sem['comparator']=goal
    if name=='mixture':sem['policy_assignment']=goal
    q=BusinessInquiryV010(query_id='q1',business_goal=goal,target=TargetDraft(kind=KINDS[name],description=goal),semantics=QuerySemanticsV010(**sem))
    shared=DraftProblemSpec(target=q.target,units_variables=UnitsVariablesDraft(analysis_unit=claim('配送站','business_question'),treatment=claim('排班助手','business_question'),outcome=claim('本周每单平均配送分钟数','proposal')),
        structure=StructureDraft(unit_network=proposal),information_design=InformationDesignDraft(assignment_family='OBSERVATIONAL' if name in ('observed','stratum','nodewise') else 'INDEPENDENT_BERNOULLI',assignment_law=proposal))
    a0=MultiQueryDraftV010(shared_draft=shared,primary_query_id='q1',queries=[q]).model_dump(mode='json')
    s=intake.start(bc,reading_format='canonical',fact_format='short_refs');s=intake.receive_candidate(s,a0,request_sha256=s.request_sha256)
    initial=dispatch.prepare_reader(s,'q1')
    if 'query_worksheet' not in initial:raise ValueError(initial)
    review=approve(initial['query_worksheet']);entry=dispatch.prepare_reader(s,'q1',query_review=review)
    if entry['state']!='READY_TO_READ':raise ValueError(entry)
    refs=rd.reference_catalog(entry['bundle'],binding=entry['fact_binding_sha256'],family=FAMILIES[name]);ids=list(refs['aliases'])
    def remap(v):
        if isinstance(v,dict):return {k:ids if k=='source_ids' and x else remap(x) for k,x in v.items()}
        if isinstance(v,list):return [remap(x) for x in v]
        return v
    raw=remap(raw);raw['reference_context']=refs['context']
    options=dict(query_review=review,candidate=raw,request_sha256=entry['request_sha256'])
    return s,options,dispatch.inspect_methods(s,'q1',**options)
