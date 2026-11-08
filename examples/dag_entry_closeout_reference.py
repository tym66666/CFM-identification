"""Frozen declaration/approval contrasts; private labels never enter requests."""
from copy import deepcopy
from cfm_id_llm.dag_reading import documents
from cfm_id.source_locations import build_catalog
from cfm_id.dag_business import inspect_candidate,submit_reviewed,ADJUSTMENT_ROUTE
from examples.dag_business_reference import semantic_score
from examples.dag_adjustment_business_reference import cases as adjustment_cases,reference_reviews


def _case(slot,condition):
    x,y,w='设备校准','合格达标','查看记录';context='本月质检设备'
    graph_text={
        'affirmed':'本次采用的模型没有清单以外的直接因果影响，清单完整。',
        'denied':'我们已发现还有未列出的直接因果影响，所以这份关系清单不完整。',
        'unknown':'这份关系清单有没有漏掉直接影响，现在还没有结论。',
        'proposed':'分析方案已经明确提出“这份关系清单完整”作为建模假设，现提交科学审核，审核结果还未给出。',
    }
    positive_text={
        'affirmed':'每一种观测变量联合0/1取值组合的总体概率都大于零。',
        'denied':'已经明确，至少有一种观测变量联合0/1取值组合的总体概率等于零，因此严格联合正性不成立。',
        'unknown':'目前不知道是否每一种观测变量联合0/1取值组合的总体概率都大于零。',
        'proposed':'分析方案已经明确提出“每一种观测变量联合0/1取值组合的总体概率都大于零”作为假设，现提交科学审核，审核结果还未给出。',
    }
    value={'affirmed':True,'denied':False,'unknown':None,'proposed':True}[condition]
    docs={
        'variables':'设备校准记录设备是否接受校准，接受为1、未接受为0，有观测记录。\n'
                    '合格达标记录设备是否达到质检标准，达到为1、未达到为0，有观测记录。\n'
                    '查看记录记录操作人员是否查看该设备的记录，查看为1、未查看为0，有观测记录。',
        'relations':'设备校准直接影响合格达标。\n设备校准直接影响查看记录。',
        'context':'研究对象与时期：本月质检设备。',
        'model':'本次研究采用固定、无时间反馈的有向无环结构模型。\n'+graph_text[condition]+'\n'
                '所有共同原因都已列在变量清单中，不另有遗漏的共同原因。\n'
                '各结构方程的剩余随机噪声相互独立。\n'
                '干预直接设定设备校准，其他变量的结构机制保持不变。',
        'information':'全部观测变量的完整联合总体分布作为已知符号信息给出，不是样本频率。\n'+positive_text[condition],
    }
    question='在本月质检设备中，如果把所有设备的“设备校准”分别统一设为0和1，“合格达标”的总体分布怎样用已有总体信息表示？业务方指定控制“查看记录”，请检查这一方案。'
    bundle=dict(case_id=slot.split('_')[0],documents=docs,question=question);catalog=build_catalog(documents(bundle))
    def ids(doc,index=None):
        values=[k for k,v in catalog.items() if v['doc_id']==doc]
        return values if index is None else [values[index]]
    names=['static_acyclic','graph_complete','latent_causes_accounted','independent_errors','perfect_intervention']
    scope={k:dict(value=value if k=='graph_complete' else True,
                  source_ids=[] if k=='graph_complete' and value is None else ids('model',i))
           for i,k in enumerate(names)}
    reference=dict(version='dag-reading-1',
        variables=[dict(name=n,observation='OBSERVED',domain='BINARY',source_ids=ids('variables',i)) for i,n in enumerate((x,y,w))],
        relations=[dict(cause=a,effect=b,kind='DIRECT_CAUSE',source_ids=ids('relations',i)) for i,(a,b) in enumerate(((x,y),(x,w)))],
        target=dict(kind='INTERVENTIONAL_DISTRIBUTION',treatment=x,outcome=y,context=context,source_ids=ids('__question__')),
        scope=scope,information=dict(kind='FULL_JOINT_POPULATION_LAW',variables=[x,y,w],source_ids=ids('information',0),
            positivity=dict(value=value,source_ids=[] if value is None else ids('information',1))),
        adjustment=[w],adjustment_source_ids=ids('__question__'),additional_restrictions=[],unresolved=[])
    state={'affirmed':'POINT','denied':'UNSUPPORTED','unknown':'NEEDS_INPUT','proposed':'REVIEW_REQUIRED'}[condition]
    reason={'affirmed':None,'denied':'NONPOSITIVE_LAW_NOT_ADAPTED',
            'unknown':'MISSING_OR_AMBIGUOUS_DAG_DECLARATIONS','proposed':'SCIENTIFIC_CONDITION_PENDING'}[condition]
    return dict(slot=slot,group='new_'+condition,bundle=bundle,reference=reference,expected_state=state,
                expected_reason=reason,expected_adjustment=[w] if condition=='affirmed' else None,
                science_decision='PENDING' if condition=='proposed' else 'ACCEPTED',
                expected_inspection='REVIEW_REQUIRED' if condition in ('affirmed','proposed') else state)


def cases():
    rows=[_case(slot,kind) for slot,kind in [
        ('CL01_affirmed','affirmed'),('CL02_denied','denied'),
        ('CL03_unknown','unknown'),('CL04_proposed_pending','proposed')]]
    old=deepcopy(next(c for c in adjustment_cases() if c['bundle']['case_id']=='AB09_unknown_graph'))
    old.update(slot='CL05_prior_unknown',group='prior_failure_diagnostic',
               science_decision='ACCEPTED',expected_inspection='NEEDS_INPUT')
    rows.append(old)
    return rows


def assess(case,wire):
    b=case['bundle'];score=semantic_score(b,wire,case['reference'])
    view=inspect_candidate(b,wire,route_id=ADJUSTMENT_ROUTE);inspection=deepcopy(view)
    if score['passed'] and view['state']=='REVIEW_REQUIRED':
        reading,science=reference_reviews(b,wire)
        if case['science_decision']=='PENDING':
            science=science.model_copy(update={'decisions':{k:'PENDING' for k in science.decisions}})
        view=submit_reviewed(b,wire,reading_review=reading,science_review=science,
                             research_protocol_selected=True,route_id=ADJUSTMENT_ROUTE)
    if not score['passed']:view['reference_review_withheld']=True
    proof=(view['independent_replay'] and view['certificate']['adjustment']==case['expected_adjustment']
           if case['expected_state']=='POINT' else view['certificate'] is None and
           view['reason_code']==case['expected_reason'])
    metrics=dict(
        structure=score['structure'],strict_fields_and_citations=score['passed'],
        initial_state_correct=inspection['state']==case['expected_inspection'],
        final_state_correct=view['state']==case['expected_state'],
        independent_point_replay=view['independent_replay'] if case['expected_state']=='POINT' else None,
        approval_pending_not_executed=not view['backend_called'] and view['certificate'] is None if case['science_decision']=='PENDING' else None,
        free_text_review_required=bool(wire.get('unresolved')) if type(wire) is dict else None,
    )
    return dict(passed=bool(score['passed'] and metrics['initial_state_correct'] and metrics['final_state_correct'] and proof),
                score=score,metrics=metrics,inspection=inspection,result=view,final_state=view['state'],
                expected_state=case['expected_state'],synthetic_only=True,real_world_semantic_accuracy=False)
