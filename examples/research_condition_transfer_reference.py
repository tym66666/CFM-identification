"""Held-out businesses for the unchanged reader and condition-version interface.

All public prose and private hypothetical references are authored before any
model call. Requests never contain numeric A4, expected results, or approvals.
"""
from copy import deepcopy
from cfm_id.question_bound_assignment import question_catalog
from cfm_id.source_locations import build_catalog
from evaluation import mean_order_factored_reading as reading
from examples.mean_order_business_fixture import make_case
from examples.mean_order_workflow_fixture import export_fixture


def _case(name, *, nodes,edges,population,first,second,mode,intro,question,lines,interval,negative=None):
    c=make_case(nodes=nodes,edges=edges,population=population,quota=2,first=first,second=second,mode=mode)
    b=c['bundle'];b['case_id']='CONDITION_TRANSFER_'+('COLD_CHAIN' if name.startswith('cold') else 'RETAIL')
    b['documents']['study.txt']=intro+'\n'+b['documents']['study.txt']
    b['documents']['goal.txt']=question;b['question_slots']={'q1':question}
    b['documents']['conditions.txt']='以下分别说明本次研究的条件和已有材料，不能当作已经完成的科学审核。\n'+'\n'.join(lines)
    catalog=build_catalog(b['documents'])
    canonical=deepcopy(c['expected_candidate'])
    canonical['comparison']['reading']['intents']['q1']['question_id']=question_catalog(b)['q1']['question_id']
    canonical['comparison']['reported_assignment']['source_ids']=[k for k,v in catalog.items()
        if v['doc_id']=='study.txt' and v['text'].strip()==c['base']['claims']['assignment']]
    assert len(canonical['comparison']['reported_assignment']['source_ids'])==1
    for row,line in zip(canonical['order_reading']['claims'],lines):
        row['source_ids']=[k for k,v in catalog.items() if v['doc_id']=='conditions.txt' and v['text'].strip()==line]
        assert len(row['source_ids'])==1
    wire=reading.reference_wire(b,canonical)
    if negative=='observation':
        wire['order_reading']['claims'][1].update(declaration='仅报告观察',quantity='历史样本统计',scope='HISTORICAL_SUPPORT')
    elif negative=='scope':
        wire['order_reading']['claims'][1]['scope']='UNKNOWN'
    canonical=reading.to_canonical(b,wire)
    c['candidate']=deepcopy(canonical);c['expected_candidate']=deepcopy(canonical)
    fixture=export_fixture(c,references=[wire],provenance='Predeclared held-out hypothetical business, graph, population, A4 and condition semantics; no real-world approval.')
    state='NEEDS_INPUT' if interval is None else 'POINT' if interval[0]==interval[1] else 'PARTIAL'
    return dict(name=name,bundle=deepcopy(b),fixture=fixture,reference=wire,expected_state=state,expected_interval=interval)


def cases():
    cold_nodes=['一站','二站','三站','四站','五站']
    cold=dict(nodes=cold_nodes,edges=[[cold_nodes[i],cold_nodes[i+1]] for i in range(4)],
        population=['二站','四站'],first=[1]*5,second=[0]*5,
        intro='我们是一家冷链配送企业，下面五个服务小组分别负责五个配送站当天的作业。相连站点会协作，不相连的站点没有直接协作。',
        question='我们想比较两种安排：甲是五个站全都用辅助系统，乙是五个站全都不用。只关心二站和四站，两个站同等看待；按时完成任务的比例，甲比乙平均高多少？其他三个站不计入评价，但仍在合作网络里。')
    own='这次准备采用以下条件，之后仍要审核：对一站、二站、三站、四站、五站，只把本站从不用改成用系统，其他站用法不变，在同一研究背景下，本站的平均完成率不会更低。这里指所有用法，包括试点从没抽到的名单。'
    peers='另一条准备采用但待审核的条件也针对一站、二站、三站、四站、五站：本站和其余站的用法不变，只让任一合作邻站从不用改成用系统，本站在同一研究背景下的平均完成率不会更低。不限于试点抽过的名单，全部可能使用安排都包含在内。'
    no_peers='对于一站、二站、三站、四站、五站，我们明确把“合作邻站增加使用不会降低本站平均完成率”这项条件拿掉，本轮不采用。'
    observation='关于一站、二站、三站、四站、五站的同伴关系，我们仅报告原试点的历史记录：按实际使用情况分组看，合作邻站使用较多时，本站按时完成比例较高。这只是试点记录中的样本统计，不能说明潜在结果，也没有试点外安排的证据。'
    retail_nodes=['中仓','北店','南店','东店','西店']
    retail=dict(nodes=retail_nodes,edges=[['中仓',n] for n in retail_nodes[1:]],
        population=['北店'],first=[1]*5,second=[1,0,0,0,0],
        intro='我们是一家连锁零售企业，中仓负责仓配，北店、南店、东店、西店是四家门店。以下服务小组是这些单位的作业团队，各店只和中仓直接协作。',
        question='甲是中仓和四家门店全都用辅助系统；乙是只有中仓用，北店、南店、东店、西店都不用。只评价北店这一家，不把其他门店或中仓算进评价对象。甲比乙，北店平均按时完成任务的比例会高多少？')
    own2='对中仓、北店、南店、东店、西店，我们愿意提出这项待审核条件：固定其余单位的用法，某单位自己启用系统之后，在同一研究背景下的平均完成率至少和不用时一样。这句话覆盖所有可能安排，含原试点没有出现过的安排。'
    peers2='对中仓、北店、南店、东店、西店，还拟采用另一项待审核条件：本单位和其余单位用法不变，只给一个合作邻居启用系统，本单位在同一研究背景下的平均完成率至少和切换前一样。全部完整安排都按这个条件讨论，不限于试点抽到的名单。'
    no_own2='对中仓、北店、南店、东店、西店，这个版本不再采用“自己使用不会降低自身平均完成率”的条件，明确不作该假设。'
    no_peers2='对中仓、北店、南店、东店、西店，这个版本也不再采用“合作邻居增加使用不会降低本单位平均完成率”的条件，明确不作该假设。'
    scope='对中仓、北店、南店、东店、西店，我们拟采用以下同伴条件：本单位和其余单位用法不变，只给一个合作邻居启用系统，本单位在同一研究背景下的平均完成率至少和切换前一样。至于只在试点覆盖的名单内采用，还是连试点之外的完整安排也采用，我们还没有确定。'
    return [
        _case('cold_both',**cold,mode='BOTH',lines=[own,peers],interval=['3/5','1']),
        _case('cold_own',**cold,mode='OWN',lines=[own,no_peers],interval=['2/5','1']),
        _case('cold_observed',**cold,mode='BOTH',lines=[own,observation],interval=None,negative='observation'),
        _case('retail_both',**retail,mode='BOTH',lines=[own2,peers2],interval=['3/5','3/5']),
        _case('retail_none',**retail,mode='NONE',lines=[no_own2,no_peers2],interval=['3/5','3/5']),
        _case('retail_scope_unknown',**retail,mode='BOTH',lines=[own2,scope],interval=None,negative='scope'),
    ]
