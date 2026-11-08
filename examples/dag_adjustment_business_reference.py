"""Route-independent DAG readings with frozen adjustment-route expectations.

All scientific approvals here are SYNTHETIC_TEST fixtures, never production.
"""
from copy import deepcopy
from cfm_id_llm.dag_reading import documents
from cfm_id.source_locations import build_catalog
from cfm_id.dag_business import (
    inspect_candidate,submit_reviewed,DagReadingReview,READING_DECISIONS,ADJUSTMENT_ROUTE,
)
from cfm_id.dag_adjustment_contract import AdjustmentReview,DECISIONS
from examples.dag_business_reference import semantic_score


def _case(case_id, *, pattern='side', paraphrase=False, unknown_positive=False,
          unknown_graph=False, explicit_empty=False, search=False):
    x,y,w='参加培训','完成任务','打开资料'
    context='本季度新员工'
    nodes=[x,y,w];latent=[];edges=[(x,y),(x,w)];adjustment=[w]
    descriptions={
        x:'参加培训记录每人是否参加培训，参加为1、未参加为0。',
        y:'完成任务记录每人是否按期完成任务，完成为1、未完成为0。',
        w:'打开资料记录每人是否在培训之后打开配套资料，打开为1、未打开为0。',
    }
    expected='POINT';answer=[w];reason=None
    if pattern=='mediator':
        edges=[(x,w),(w,y)];expected='UNSUPPORTED';answer=None
        reason='ADJUSTMENT_INTERSECTS_FORBIDDEN_SET'
    elif pattern=='collider':
        u='学习意愿';nodes.append(u);latent=[u]
        descriptions[u]='学习意愿在本模型中只有高和低两类，高为1、低为0，没有观测记录。'
        edges=[(x,w),(u,w),(u,y)];expected='UNSUPPORTED';answer=None
        reason='SPECIFIED_SET_FAILS_DAG_ADJUSTMENT'
    elif pattern=='maintenance':
        x,y,w,d='接受保养','故障发生','收到提醒','查看提醒'
        context='本月仓储设备';nodes=[x,y,w,d];edges=[(x,y),(x,w),(w,d)];adjustment=[d];answer=[d]
        descriptions={
            x:'接受保养记录设备是否接受保养，接受为1、未接受为0。',
            y:'故障发生记录设备在本月是否发生故障，发生为1、未发生为0。',
            w:'收到提醒记录保养后是否收到提醒，收到为1、未收到为0。',
            d:'查看提醒记录操作员是否查看了这条提醒，查看为1、未查看为0。',
        }
    elif pattern=='confounder':
        w='资深员工';nodes=[w,x,y];adjustment=[w];answer=[w]
        descriptions[w]='资深员工记录培训前工龄是否超过五年，是为1、否为0。'
        edges=[(w,x),(w,y),(x,y)]
    question='在'+context+'中，如果将所有对象的“'+x+'”分别统一设为0和1、其他机制保持原样，“'+y+'”的总体分布怎样用已有总体信息表示？'
    if search:
        adjustment=None;answer=[]
        question+='请寻找合适的调整方式，我们没有指定控制变量。'
    elif explicit_empty:
        adjustment=[];answer=None;expected='UNSUPPORTED';reason='SPECIFIED_SET_FAILS_DAG_ADJUSTMENT'
        question+='请检查完全不控制任何变量时能否这样计算，不能自动增加控制变量。'
    elif paraphrase:
        question+='业务方要求先按“'+adjustment[0]+'”分层，再按其总体占比合回去；请检查这个方案，不要更换所控制的变量。'
    else:
        question+='请按业务方指定的控制变量“'+adjustment[0]+'”检查调整方案，不要改用其他控制变量。'
    docs={
        'variables':'\n'.join(descriptions[n]+('这些记录均已观测。' if n not in latent else '') for n in nodes),
        'relations':'\n'.join(a+('会直接改变'+b+'。' if paraphrase else '直接影响'+b+'。') for a,b in edges),
        'context':'研究对象与时期：'+context+'。',
        'model':'本次拟采用固定的、无时间反馈的有向无环结构模型。\n'
                '以上列出了本模型的全部直接因果关系，没有其他直接因果边。\n'
                '所有共同原因均已显式列在变量清单中，不另有遗漏的共同原因。\n'
                '模型中各结构方程的剩余随机噪声相互独立。\n'
                '所问干预直接设定处理变量，其他变量的结构机制保持不变。',
        'information':'全部有观测记录变量的完整联合总体分布作为已知符号信息提供，不是个体样本频率。\n'
                      '这些观测变量每一种联合0/1取值组合的总体概率都严格大于零。',
    }
    if unknown_positive:
        docs['information']=docs['information'].splitlines()[0]+'\n尚未确定每种联合取值的总体概率是否都大于零。'
        expected='NEEDS_INPUT';answer=None;reason='MISSING_OR_AMBIGUOUS_DAG_DECLARATIONS'
    if unknown_graph:
        lines=docs['model'].splitlines();lines[1]='所列直接因果关系是否完整尚未核实。'
        docs['model']='\n'.join(lines)
        expected='NEEDS_INPUT';answer=None;reason='MISSING_OR_AMBIGUOUS_DAG_DECLARATIONS'
    bundle=dict(case_id=case_id,documents=docs,question=question)
    catalog=build_catalog(documents(bundle))
    def ids(doc,index=None):
        all_ids=[k for k,v in catalog.items() if v['doc_id']==doc]
        return all_ids if index is None else [all_ids[index]]
    scope_names=['static_acyclic','graph_complete','latent_causes_accounted','independent_errors','perfect_intervention']
    scope={name:dict(value=None if unknown_graph and name=='graph_complete' else True,
                    source_ids=[] if unknown_graph and name=='graph_complete' else ids('model',i))
           for i,name in enumerate(scope_names)}
    reference=dict(version='dag-reading-1',
        variables=[dict(name=n,observation='LATENT' if n in latent else 'OBSERVED',domain='BINARY',source_ids=ids('variables',i))
                   for i,n in enumerate(nodes)],
        relations=[dict(cause=a,effect=b,kind='DIRECT_CAUSE',source_ids=ids('relations',i)) for i,(a,b) in enumerate(edges)],
        target=dict(kind='INTERVENTIONAL_DISTRIBUTION',treatment=x,outcome=y,context=context,source_ids=ids('__question__')),
        scope=scope,information=dict(kind='FULL_JOINT_POPULATION_LAW',variables=[n for n in nodes if n not in latent],
            source_ids=ids('information',0),positivity=dict(value=None if unknown_positive else True,
                                                          source_ids=[] if unknown_positive else ids('information',1))),
        adjustment=adjustment,adjustment_source_ids=ids('__question__') if adjustment is not None else [],
        additional_restrictions=[],unresolved=[])
    return dict(bundle=bundle,reference=reference,route_id=ADJUSTMENT_ROUTE,
                expected_state=expected,expected_adjustment=answer,expected_reason=reason)


def cases():
    return [
        _case('AB01_training_side'),
        _case('AB02_training_paraphrase',paraphrase=True),
        _case('AB03_maintenance',pattern='maintenance'),
        _case('AB04_mediator',pattern='mediator'),
        _case('AB05_collider',pattern='collider'),
        _case('AB06_unknown_positive',unknown_positive=True),
        _case('AB07_explicit_empty',pattern='confounder',explicit_empty=True),
        _case('AB08_unspecified',search=True),
        _case('AB09_unknown_graph',unknown_graph=True),
    ]


def reference_reviews(bundle,wire):
    view=inspect_candidate(bundle,wire,route_id=ADJUSTMENT_ROUTE)
    if view['state']!='REVIEW_REQUIRED':raise ValueError('REVIEW_READY_REFERENCE_REQUIRED')
    common=dict(reviewer='Frozen synthetic protocol author',
                evidence='Offline synthetic assumptions and source-bound candidate reviewed against independently frozen references.',
                authority='SYNTHETIC_TEST')
    reading={k:v for k,v in view['reading_worksheet'].items() if k!='is_approval'}
    science={k:v for k,v in view['science_worksheet'].items() if k!='is_approval'}
    reading.update(**common,decisions={k:'ACCEPTED' for k in READING_DECISIONS})
    science.update(**common,decisions={k:'ACCEPTED' for k in DECISIONS})
    return DagReadingReview.model_validate(reading),AdjustmentReview.model_validate(science)


def assess(case,wire):
    bundle=case['bundle']
    score=semantic_score(bundle,wire,case['reference'])
    view=inspect_candidate(bundle,wire,route_id=ADJUSTMENT_ROUTE)
    if score['passed'] and view['state']=='REVIEW_REQUIRED':
        reading,science=reference_reviews(bundle,wire)
        view=submit_reviewed(bundle,wire,reading_review=reading,science_review=science,
                             research_protocol_selected=True,route_id=ADJUSTMENT_ROUTE)
    elif not score['passed']:
        view['reference_review_withheld']=True
    state=view['state']==case['expected_state']
    proof=(view['independent_replay'] and view['certificate']['adjustment']==case['expected_adjustment']
           if case['expected_state']=='POINT' else view['certificate'] is None and
           view['reason_code']==case['expected_reason'])
    return dict(passed=bool(score['passed'] and state and proof),score=score,result=deepcopy(view),
                expected_state=case['expected_state'],synthetic_only=True,
                real_world_semantic_accuracy=False)
