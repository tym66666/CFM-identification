"""Frozen prose cases distinguish provided A4 scope from requested target scope."""
from cfm_id import business_intake as intake,business_dispatch as dispatch
from cfm_id_llm.schemas import BusinessCase,SourceDocument
from examples.business_dispatch_reference import approve
from evaluation.network_effect_citation_cases import reference_a0
from evaluation.network_effect_source_cases import reference_facts as base_facts
from cfm_id_llm.network_effect_reading import reference_catalog

CASES=('cleaning_full','cleaning_target_only','cleaning_missing_arm','cleaning_pending_full',
       'linen_full','linen_extra_full','linen_sample')
EXPECTED={'cleaning_full':'POINT','cleaning_target_only':'POINT','cleaning_missing_arm':'NEEDS_INPUT',
          'cleaning_pending_full':'NEEDS_INPUT','linen_full':'POINT','linen_extra_full':'ADAPTER_NOT_CONNECTED','linen_sample':'NEEDS_INPUT'}


def material(name):
    if name not in CASES:raise ValueError('UNKNOWN_A4_SCOPE_CASE')
    cleaning=name.startswith('cleaning_')
    if cleaning:
        nodes=['东庭站','西庭站','湖畔站','林荫站','新桥站'];members=nodes[:3]
        edges=list(zip(nodes,nodes[1:]+nodes[:1]));rates=['1/4','1/3','1/2','2/3','3/4']
        unit='保洁站';action='使用工单提醒工具';outcome='本月每张保洁工单的平均到场分钟数'
        intro='园区物业希望缩短保洁人员收到工单后到达现场的时间。保洁站会沿既有合作关系相互借调人员，所以合作站使用提醒工具也可能影响本站。'
        goal='在合作站使用工具的比例至多一半时，本站使用提醒工具和不使用相比，平均到场时间差多少？用使用时的均值减去不使用时的均值。'
        kind='DIRECT_EFFECT';arms=((1,0),(0,0))
    else:
        nodes=['晨海点','青山点','银湾点','云岭点'];members=[nodes[1]]
        edges=[(nodes[0],n) for n in nodes[1:]];rates=['1/3','2/5','3/5','2/3']
        unit='布草服务点';action='开启周转提醒';outcome='本月每笔布草补送的平均完成小时数'
        intro='酒店集团想了解布草周转提醒是否影响补送效率。各服务点会通过已有合作关系相互调拨布草，因此合作点开启提醒也可能改变本点的补送时间。'
        goal='青山点自己不开启提醒时，合作点中严格超过一半开启提醒与至多一半开启相比，平均补送时间相差多少？计算超过一半时的均值减去至多一半时的均值。'
        kind='SPILLOVER_EFFECT';arms=((0,1),(0,0))
    population='评价名单在抽签前固定为'+'、'.join(members)+'。'+('只评价这个服务点，不与其他点做平均。' if len(members)==1 else '每个入选站各算一份，取等权平均，不按工单量加权。')
    remaining='两端分别在符合该端自身使用状态和合作对象状态的完整安排中，按照原试点抽签概率平均。没有固定其余对象的使用名单，也没有改用新的分配概率。'
    scope_nodes=list(nodes);scope_arms=[(0,0),(0,1),(1,0),(1,1)]
    if name in ('cleaning_target_only','cleaning_missing_arm'):
        scope_nodes=nodes[:3];scope_arms=[(1,0),(0,0)] if name=='cleaning_target_only' else [(1,0)]
        info='本理论研究只可使用东庭站、西庭站、湖畔站在以下情况下的逐站总体条件平均结果：合作站至多一半使用工具，本站使用工具'+('或本站不使用工具。' if name=='cleaning_target_only' else '。')
        info+='其他站或其他状态的总体均值均未提供。这里声明这些总体均值可用，不提供数值，也不是样本估计。'
    elif name=='linen_sample':
        scope_arms=[]
        info='目前只有四个服务点在本月试点中得到的有限样本记录，以及按本人是否开启、合作状态0或1分组的样本平均完成时间。没有声明任何精确总体均值或总体分布可用。'
    else:
        info='本理论研究可以使用完整名单中每个对象在本人使用或不使用、合作状态0或1组成的全部四个状态下的总体条件平均结果。这里只声明总体均值可用，没有给出数值，不是有限样本平均。该范围包括评价名单以外的对象。'
    consistency=('负责人对“实际观察结果等于实际完整使用安排下对应的潜在结果”尚未决定是否采用。' if name=='cleaning_pending_full' else
                 '负责人明确拟采用：实际观察结果等于实际完整使用安排下对应的潜在结果。')
    docs=dict(
        study=intro+'完整研究名单为'+'、'.join(nodes)+'。每个'+unit+'是一个研究对象。'+action+'编码为1，不使用编码为0。结果是'+outcome+'。',
        network='完整合作边为'+'；'.join(a+'与'+b for a,b in edges)+'。合作均为双向，其他对象对没有边，也没有自环或重复边。合作网络在原试点抽签前固定，评价期间不变。',
        assignment='原试点中每个对象分别独立抽签；完整规则为'+'；'.join(n+'使用工具的概率为'+p for n,p in zip(nodes,rates))+'。',
        exposure='合作对象中严格超过一半使用工具，合作状态为1；至多一半使用为0。平票和没有合作对象均为0。这是记录合作状态的分组规则。',
        population=population,remaining=remaining,
        science='研究负责人为本次合成研究明确拟采用：完整使用名单与所有对象在所有完整安排下的潜在结果独立；相关条件一阶矩存在且有限。'+consistency,
        information=info,
        context='两端比较均针对本月，采用同一业务背景及同一结果定义。声明的信息也对应这同一原试点和同一结果口径。')
    if name=='linen_extra_full':docs['extra']='研究负责人还明确采用额外条件：每个服务点在每种完整使用名单下的平均补送完成时间不超过8小时。该上界与其他条件同时成立。'
    order=['context','information','assignment','study','population','exposure','network','science','remaining']
    if 'extra' in docs:order.insert(1,'extra')
    question=intro+'\n'+population+'\n'+goal+'\n'+remaining
    case=BusinessCase(case_id='A4-SCOPE-'+name,business_question=question,sources=[SourceDocument(source_id=k,text=docs[k]) for k in order])
    data=dict(name=name,nodes=nodes,members=members,edges=edges,probabilities=dict(zip(nodes,rates)),unit=unit,treatment=action,
        outcome=outcome,docs=docs,questions={'q1':goal,'q2':goal},kind=kind,arms=arms,aggregation='SINGLE' if len(members)==1 else 'EQUAL_MEAN',
        memo=False,scope_nodes=scope_nodes,scope_arms=scope_arms)
    return case,data


def setup(name):
    case,data=material(name);s=intake.start(case,reading_format='canonical',fact_format='short_refs')
    s=intake.receive_candidate(s,reference_a0(case,data),request_sha256=s.request_sha256)
    q=approve(dispatch.prepare_reader(s,'q1')['query_worksheet']);e=dispatch.prepare_reader(s,'q1',query_review=q)
    if e['state']!='READY_TO_READ':raise ValueError('REFERENCE_A0_NOT_READY')
    raw=base_facts(e,data);info=raw['information'][0]
    info['outcome_nodes']=data['scope_nodes']
    info['arm_cells']=[dict(node=n,own=a,exposure=x) for n in data['scope_nodes'] for a,x in data['scope_arms']]
    if name=='linen_sample':info.update(operator='FINITE_SAMPLE',availability='FINITE_SAMPLE')
    if name=='cleaning_pending_full':raw['scientific_statements']['consistency']['status']='UNDECIDED'
    if 'extra' in data['docs']:
        ids=[k for k,v in reference_catalog(e['bundle'],binding=e['fact_binding_sha256'])['aliases'].items() if v['doc_id']=='extra']
        raw['additional_restrictions']=[dict(text=data['docs']['extra'],source_ids=ids)]
    return s,e,data,raw
