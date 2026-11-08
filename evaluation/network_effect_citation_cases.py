"""Complete prose packets for frozen citation-order component tests.

References are explicit synthetic fixtures, not model input or runtime defaults.
Seven packets represent three businesses; the memo is not an independent case.
"""
from copy import deepcopy
from cfm_id import business_intake as intake, business_dispatch as dispatch
from cfm_id_llm.schemas import BusinessCase, SourceDocument
from examples.business_dispatch_reference import approve
from examples.network_effect_dispatch_reference import a0_reference
from evaluation.network_effect_source_cases import reference_facts as base_facts

CASES=('service_all','service_memo','grocery_subset','library_single',
       'service_context_pending','grocery_science_pending','library_extra')


def material(name):
    if name not in CASES:raise ValueError('UNKNOWN_CITATION_CASE')
    family=name.split('_')[0]
    if family=='service':
        nodes=['向阳点','枫林点','滨河点','学府点','新城点'];members=nodes
        edges=list(zip(nodes,nodes[1:]));rates=['1/5','2/5','1/2','3/5','4/5']
        unit='维修服务点';action='开通备件提醒';outcome='本周每张维修单等待备件的平均小时数'
        intro='家电维修公司希望减少客户等待备件的时间。几个服务点会相互调借备件，合作点是否开通提醒可能影响本点的维修等待。'
        goal='我们想比较：合作点中开通提醒的数量超过半数时，本点开通提醒与本点未开通提醒，各自的平均等待时间相差多少？以本点开通时的均值减去本点未开通时的均值。'
        kind='DIRECT_EFFECT';arms=((1,1),(0,1))
    elif family=='grocery':
        nodes=['朝露店','星河店','青禾店','竹园店'];members=[nodes[1],nodes[3]]
        edges=list(zip(nodes,nodes[1:]+nodes[:1]));rates=['1/3','2/5','3/5','3/4']
        unit='生鲜门店';action='启用余货共享看板';outcome='本周每笔缺货调拨的平均完成分钟数'
        intro='社区生鲜连锁想了解余货共享看板能否帮助门店更快补齐缺货。门店会沿已有合作关系相互调货，邻店是否使用看板也可能影响本店。'
        goal='本店不启用看板时，合作门店中严格超过一半启用看板，与至多一半启用相比，调拨完成的平均时间有什么差别？用超过一半时的均值减去至多一半时的均值。'
        kind='SPILLOVER_EFFECT';arms=((0,1),(0,0))
    else:
        nodes=['晨光馆','清泉馆','松林馆','海棠馆','云帆馆','长风馆'];members=[nodes[4]]
        edges=[(nodes[0],nodes[1]),(nodes[1],nodes[2]),(nodes[2],nodes[0]),(nodes[3],nodes[4]),(nodes[4],nodes[5]),(nodes[5],nodes[3])]
        rates=['1/4','1/3','2/5','1/2','3/5','3/4']
        unit='图书分馆';action='使用预约流转提示';outcome='本周每笔馆际预约的平均到书天数'
        intro='城市图书馆希望缩短馆际预约的到书时间。分馆之间会交换图书，提示工具的影响可能通过既有借调合作传到其他分馆。'
        goal='对于云帆馆，如果合作分馆中使用提示工具的比例不超过一半，使用提示工具和不使用提示工具相比，预约到书的平均天数差多少？计算使用时的均值减去不使用时的均值。'
        kind='DIRECT_EFFECT';arms=((1,0),(0,0))
    population=('评价名单在试点抽签前已经确定为'+('全部'+str(len(nodes))+'个'+unit if members==nodes else '、'.join(members))+'。'
        +('只报告这个分馆的均值，不把其他分馆平均进来。' if len(members)==1 else '名单中每个对象算一份，取等权平均；不按业务量加权。'))
    remaining='每一端都按原试点抽签概率，对满足该端本对象状态和合作对象状态的全部完整安排取平均。其余对象不固定为某个名单，也不改用新的安排概率。'
    independence=('研究负责人对“完整启用名单是否与所有对象在每种完整安排下的潜在结果独立”尚未决定采用与否。'
        if name=='grocery_science_pending' else '研究负责人为本次合成推演明确拟采用：完整启用名单与所有对象在每种完整安排下的潜在结果独立。')
    docs=dict(
        study=intro+'研究的完整对象名单为'+'、'.join(nodes)+'。每个'+unit+'作为一个研究对象。'+action+'记作1，不使用记作0。结果指标为'+outcome+'。',
        network='完整合作关系是'+'；'.join(a+'与'+b for a,b in edges)+'。每条关系都可双向合作；其余对象对没有合作关系，没有自己与自己合作或重复关系。关系在试点抽签之前确定，评价期间不会改变。',
        assignment='原试点对各对象分别独立抽签，每个对象开通的概率事先确定为'+'；'.join(n+'为'+p for n,p in zip(nodes,rates))+'。这就是该试点的完整分配规则。',
        exposure='合作对象中严格超过一半使用工具，合作状态记为1；至多一半使用记为0。恰好一半、没有合作对象均记为0。这是分组的定义。',
        population=population,remaining=remaining,
        science=independence+'负责人明确拟采用的其他条件是：实际看到的结果等于该对象在实际完整启用安排下对应的潜在结果；涉及的条件一阶矩存在且有限。',
        information='本次是总体信息下的理论研究：可以使用完整名单里每个对象、本人是否启用与合作状态0或1组成的全部四个组的总体条件平均结果。提供的是这些总体均值可用的符号声明，不是试点样本平均，也没有给出数值。',
        context=('两端是否统一采用同一周、同一业务背景和同一结果定义，负责人尚未确认。' if name=='service_context_pending' else
                 '两端比较均以本周为评价期，采用同一业务背景、同一结果定义。所声明的总体均值也对应这一原试点、同一期间和结果口径。'))
    if name=='library_extra':docs['extra']='除上述条件外，研究负责人还明确采用：每个分馆在每一种完整启用安排下的平均到书时间不超过12天。该均值上界与其他条件同时成立。'
    question=intro+'\n'+population+'\n'+goal+'\n'+remaining
    order=['information','context','study','assignment','population','network','remaining','science','exposure']
    if 'extra' in docs:order.insert(1,'extra')
    memo=name=='service_memo'
    sources=([SourceDocument(source_id='business_memo',text='\n\n'.join(docs[k] for k in order))] if memo else
        [SourceDocument(source_id=k,text=docs[k]) for k in order])
    data=dict(name=name,nodes=nodes,members=members,edges=edges,probabilities=dict(zip(nodes,rates)),unit=unit,
        treatment=action,outcome=outcome,docs=docs,questions={'q1':goal,'q2':goal},kind=kind,arms=arms,
        aggregation='SINGLE' if len(members)==1 else 'EQUAL_MEAN',memo=memo)
    return BusinessCase(case_id='CITATION-ORDER-'+name,business_question=question,sources=sources),data


def reference_a0(case,data):
    raw=a0_reference(case,data);query=raw['queries'][0 if data['kind']=='DIRECT_EFFECT' else 1]
    query['query_id']='q1';raw['queries']=[query];raw['shared_draft']['target']=deepcopy(query['target'])
    if data['memo']:
        def remap(v):
            if isinstance(v,dict):return {k:('business_memo' if k=='source_id' and x!='business_question' else remap(x)) for k,x in v.items()}
            if isinstance(v,list):return [remap(x) for x in v]
            return v
        raw=remap(raw)
    return raw


def setup(name):
    case,data=material(name);s=intake.start(case,reading_format='canonical',fact_format='short_refs')
    s=intake.receive_candidate(s,reference_a0(case,data),request_sha256=s.request_sha256)
    q=approve(dispatch.prepare_reader(s,'q1')['query_worksheet']);e=dispatch.prepare_reader(s,'q1',query_review=q)
    if e['state']!='READY_TO_READ':raise ValueError('REFERENCE_A0_NOT_READY')
    raw=base_facts(e,data)
    if name=='service_context_pending':raw['target']['shared_outcome_and_context']['value']=None
    if name=='grocery_science_pending':raw['scientific_statements']['assignment_outcome_independence']['status']='UNDECIDED'
    if name=='library_extra':
        # Rebuild from original material, never from a model answer.
        from cfm_id_llm.network_effect_reading import reference_catalog
        ids=[k for k,v in reference_catalog(e['bundle'],binding=e['fact_binding_sha256'])['aliases'].items() if v['doc_id']=='extra']
        raw['additional_restrictions']=[dict(text=data['docs']['extra'],source_ids=ids)]
    return s,e,data,raw
