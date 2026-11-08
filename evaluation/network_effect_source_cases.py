"""Frozen prose fixtures for source-coverage experiments, never runtime defaults.

The A0 and fact references are human-authored component-test references. Their
use must be disclosed; API experiments must never send them to the model.
"""
from copy import deepcopy
from cfm_id import business_intake as intake, business_dispatch as dispatch
from cfm_id_llm.schemas import BusinessCase,SourceDocument
from cfm_id_llm import network_effect_reading as reading
from examples.network_effect_dispatch_reference import a0_reference
from examples.business_dispatch_reference import approve

CASES=('retail_split','retail_memo','retail_single','logistics_subset','missing_science','extra_bound')


def material(name):
    if name not in CASES:raise ValueError('UNKNOWN_FROZEN_SOURCE_CASE')
    logistics=name in ('logistics_subset','missing_science')
    if logistics:
        nodes=['长安站','河西站','湖东站','南山站','文昌站'];members=nodes[:2]
        edges=list(zip(nodes,nodes[1:]+nodes[:1]));rates=['1/4','1/3','1/2','3/5','2/3']
        unit='配送站';action='启用揽件排程工具';outcome='本周每单上门取件的平均等待分钟数'
        intro='配送公司希望了解揽件排程工具及合作站的使用情况如何影响客户等待。各站会相互支援人员，不能只看本站的工具使用情况。'
        goal='在本站使用工具的情况下，合作站使用工具的比例至多一半，相比严格超过一半，平均等待时间多多少？按前一种情况减后一种情况。'
        kind='SPILLOVER_EFFECT';arms=((1,0),(1,1))
    else:
        nodes=['南城店','北苑店','江滨店','西桥店'];members=nodes[1:2] if name=='retail_single' else nodes
        edges=[(nodes[0],n) for n in nodes[1:]];rates=['1/4','1/3','1/2','2/3']
        unit='门店';action='启用补货提醒工具';outcome='本周每次补货的平均等待分钟数'
        intro='连锁零售企业希望了解补货提醒工具是否缩短门店等待补货的时间。门店之间会调拨库存，因此合作门店使用工具也可能影响本站。'
        goal=('如果合作门店中使用工具的数量没有超过半数，北苑店开通工具与保持不开通相比，平均等待补货的时间相差多少？开通的情况减去不开通的情况。'
              if name=='retail_single' else '合作门店中至多一半使用工具时，本店启用工具与本店不启用相比，平均等待补货的时间相差多少？前者减后者。')
        kind='DIRECT_EFFECT';arms=((1,0),(0,0))
    single=len(members)==1
    population=('评价名单在抽签前确定，只评价'+members[0]+'，只报告该对象的均值，不对其他对象做平均。' if single else
        '评价名单在抽签前固定为'+('全部'+str(len(nodes))+'个'+unit if members==nodes else '、'.join(members))+'，名单中的每个对象各算一份，取等权平均。')
    remaining=('每端分别把符合该端自身使用状态和合作对象状态的完整名单列入，按原试点的抽签概率取平均；不固定其余对象的使用名单，也不改用另一套抽签概率。'
        if name=='retail_single' else '比较两端各自按原试点抽签概率，对满足该端自身状态及合作对象状态的完整安排取平均，不另外固定其他对象使用与否。')
    independence='本合成研究负责人明确拟采用：整份启用名单与每个对象在每种完整名单下的潜在结果独立；'
    consistency='' if name=='missing_science' else '实际观测结果就是实际完整名单下对应的潜在结果；'
    docs=dict(study=intro+'完整对象名单是'+'、'.join(nodes)+'。每个'+unit+'是一个研究对象。'+action+'记为1，未启用记为0；结果是'+outcome+'。',
        network='完整无向合作边只有'+'、'.join(a+'与'+b for a,b in edges)+'，其余对象对没有边，也没有自环或重边。合作关系在原试点抽签前已经确定，整个评价期内不变。',
        assignment='原试点对各对象分别独立抽签，已知完整抽签规则为：'+'；'.join(n+'启用概率为'+p for n,p in zip(nodes,rates))+'。',
        exposure='严格超过一半合作对象启用工具，记为同伴状态1；至多一半记为0，平票和没有合作对象也记为0。这只是分组记录的定义。',
        population=population,remaining=remaining,
        science=independence+consistency+'涉及的条件一阶矩存在且有限。',
        information='本理论研究可以使用全部'+str(len(nodes))+'个对象的逐对象总体条件均值，覆盖本人是否启用与同伴0或1组成的全部四个状态。只有可用总体均值的符号声明，没有数值；不是有限样本平均或估计。',
        context='本次两端比较均针对本周，使用同一研究背景和同一种结果定义，结果及其总体均值统一以分钟计。')
    if name=='extra_bound':docs['extra']='研究负责人还明确采用额外条件：每个对象在每一种完整启用名单下的平均等待时间至少为5分钟。该均值下界与前述条件同时成立。'
    order=list(docs)
    if name=='retail_memo':order=['context','information','network','science','population','remaining','assignment','study','exposure']
    question=intro+'\n'+population+'\n'+goal+'\n'+remaining
    sources=([SourceDocument(source_id='business_memo',text='\n\n'.join(docs[k] for k in order))]
             if name=='retail_memo' else [SourceDocument(source_id=k,text=docs[k]) for k in order])
    case=BusinessCase(case_id='SOURCE-COVERAGE-'+name,business_question=question,sources=sources)
    data=dict(nodes=nodes,members=members,edges=edges,probabilities=dict(zip(nodes,rates)),unit=unit,
        treatment=action,outcome=outcome,docs=docs,questions={'q1':goal,'q2':goal},kind=kind,arms=arms,
        aggregation='SINGLE' if single else 'EQUAL_MEAN',name=name)
    return case,data


def reference_a0(case,data):
    raw=a0_reference(case,data);chosen=raw['queries'][0 if data['kind']=='DIRECT_EFFECT' else 1]
    chosen['query_id']='q1';raw['queries']=[chosen];raw['shared_draft']['target']=deepcopy(chosen['target'])
    if data['name']=='retail_memo':
        def remap(value):
            if isinstance(value,dict):
                return {k:('business_memo' if k=='source_id' and v!='business_question' else remap(v)) for k,v in value.items()}
            if isinstance(value,list):return [remap(v) for v in value]
            return value
        raw=remap(raw)
    return raw


def reference_facts(entry,data):
    refs=reading.reference_catalog(entry['bundle'],binding=entry['fact_binding_sha256'])
    def ids(*docs):
        # Original paragraph text may appear in a reordered multi-paragraph memo.
        found=[]
        for doc in docs:
            for key,row in refs['aliases'].items():
                if row['doc_id']==doc or (row['doc_id']=='business_memo' and row['text'].strip()==data['docs'][doc]):found.append(key)
        return list(dict.fromkeys(found))
    goal=[k for k,v in refs['aliases'].items() if data['questions']['q1'] in v['text']]
    def declaration(value,doc):return dict(value=value,source_ids=ids(doc))
    first,second=data['arms']
    return dict(version=reading.VERSION,reference_context=refs['context'],
        study=dict(source_ids=ids('study','network','context'),nodes=data['nodes'],edges=[list(e) for e in data['edges']],
            graph_kind='SIMPLE_UNDIRECTED',edge_list_complete=True,treatment=data['treatment'],outcome=data['outcome'],
            outcome_kind='CONTINUOUS',context=data['docs']['context']),
        assignment=dict(source_ids=ids('assignment'),kind='INDEPENDENT_BERNOULLI',probabilities=data['probabilities'],fixed_count=None),
        target=dict(source_ids=goal+ids('population'),kind=data['kind'],operation='FIRST_MINUS_SECOND',
            first=dict(source_ids=goal,own=first[0],exposure=first[1]),second=dict(source_ids=goal,own=second[0],exposure=second[1]),
            population=data['members'],aggregation=data['aggregation'],population_fixed_before_assignment=declaration(True,'population'),
            remaining_assignment='ORIGINAL_DESIGN_CONDITIONAL',remaining_source_ids=ids('remaining'),shared_outcome_and_context=declaration(True,'context')),
        exposure=dict(kind='STRICT_MAJORITY_TIES_LOW',source_ids=ids('exposure')),
        design_facts=dict(assignment_rule_available=declaration(True,'assignment'),network_fixed_before_treatment=declaration(True,'network')),
        scientific_statements={k:dict(status='NOT_STATED' if data['name']=='missing_science' and k=='consistency' else 'PROPOSED',
            source_ids=[] if data['name']=='missing_science' and k=='consistency' else ids('science'))
            for k in ('assignment_outcome_independence','consistency','finite_conditional_means')},
        information=[dict(operator='NODE_ARM_MEANS',availability='SYMBOLIC_POPULATION_OPERATOR',outcome_nodes=data['nodes'],
            arm_cells=[dict(node=n,own=a,exposure=e) for n in data['nodes'] for a in (0,1) for e in (0,1)],source_ids=ids('information'))],
        additional_restrictions=[dict(text=data['docs']['extra'],source_ids=ids('extra'))] if data['name']=='extra_bound' else [],unresolved=[])


def setup(name):
    case,data=material(name);s=intake.start(case,reading_format='canonical',fact_format='short_refs')
    s=intake.receive_candidate(s,reference_a0(case,data),request_sha256=s.request_sha256)
    q=approve(dispatch.prepare_reader(s,'q1')['query_worksheet']);e=dispatch.prepare_reader(s,'q1',query_review=q)
    if e['state']!='READY_TO_READ':raise ValueError('REFERENCE_A0_NOT_READY')
    return s,e,data,reference_facts(e,data)
