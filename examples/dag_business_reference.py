"""Frozen synthetic business references; never imported by the production reader."""
from copy import deepcopy
from cfm_id_bridge.scientific_binding import sha
from cfm_id.source_locations import build_catalog
from cfm_id_llm.dag_reading import documents,parse
from cfm_id.dag_business import inspect_candidate,submit_reviewed,DagReadingReview,READING_DECISIONS
from cfm_id.dag_backdoor_contract import BackdoorReview,DECISIONS


def _case(name,*,latent=False,blocked=False,missing=False,sample=False,association=False,mediator=False,paraphrase=False):
    x,y,z='参加培训','业绩达标','资深员工';context='本季度销售团队'
    descriptions={x:'参加培训表示是否参加，是为1、否为0；有记录。',
                  y:'业绩达标表示季度业绩是否达到统一标准，是为1、否为0；有记录。',
                  z:'资深员工表示工龄是否超过五年，是为1、否为0；有记录。'}
    nodes=[z,x,y];hidden=[];edges=[(z,x),(z,y),(x,y)]
    if latent:
        u='个人动机';descriptions[u]='个人动机分为高和低两档，高为1、低为0；没有观测记录。'
        nodes=[u,z,x,y];hidden=[u];edges=[(u,x),(u,z),(z,y),(x,y)]
        if blocked:edges=[(u,x),(u,y),(x,y)]
    if mediator:
        nodes=[x,z,y];descriptions[z]='资深员工表示本次培训之后是否取得资深资格，是为1、否为0；有记录。'
        edges=[(x,z),(z,y)]
    docs={'variables':'\n'.join(descriptions[n] for n in nodes),
          'relations':'\n'.join(a+('与'+b+'有统计相关，方向尚未确定。' if association else '直接影响'+b+'。') for a,b in edges),
          'context':'研究背景：'+context+'。',
          'model':'本次研究采用固定的无时间反馈的有向无环结构模型。\n'
                  '上述清单列出了本模型的全部直接因果关系，没有其他直接因果边。\n'
                  '所有共同原因均已在变量清单中列出，不另有遗漏的共同原因。\n'
                  '各变量结构方程中的剩余噪声相互独立。\n'
                  '研究采用直接设定培训状态、保持其他结构机制不变的干预。',
          'information':'已知所有有记录变量的完整联合总体分布，作为符号总体信息，不是样本频率。\n'
                        '所有有记录变量的每一种联合0/1取值组合，其总体概率严格大于零。'}
    if missing:docs['model']='\n'.join(docs['model'].splitlines()[i] for i in (0,3,4))
    if sample:docs['information']='只有所有有记录变量的1000条个体样本，没有给出总体联合分布。'
    if paraphrase:
        docs['relations']='资深员工会直接影响参加培训，也会直接影响业绩达标。\n参加培训还会直接影响业绩达标。'
        docs['model']=docs['model'].replace('没有其他直接因果边','本模型没有遗漏其他直接影响').replace('剩余噪声相互独立','随机扰动彼此独立')
    question='在'+context+'中，分别将“'+x+'”设为0和1、保持其他机制不变时，“'+y+'”的总体分布如何用已有总体信息表示？'
    if mediator:question+='请按业务方要求控制“资深员工”。'
    bundle=dict(case_id=name,documents=docs,question=question)
    catalog=build_catalog(documents(bundle))
    def ids(doc,index=None):
        values=[sid for sid,row in catalog.items() if row['doc_id']==doc]
        return values if index is None else [values[index]]
    true=lambda src:dict(value=True,source_ids=src)
    scope_names=['static_acyclic','graph_complete','latent_causes_accounted','independent_errors','perfect_intervention']
    scope={k:true(ids('model',i)) for i,k in enumerate(scope_names)} if not missing else {
        'static_acyclic':true(ids('model',0)),
        'graph_complete':dict(value=None,source_ids=[]),'latent_causes_accounted':dict(value=None,source_ids=[]),
        'independent_errors':true(ids('model',1)),'perfect_intervention':true(ids('model',2))}
    reference=dict(version='dag-reading-1',
        variables=[dict(name=n,observation='LATENT' if n in hidden else 'OBSERVED',domain='BINARY',source_ids=ids('variables',i)) for i,n in enumerate(nodes)],
        relations=[dict(cause=a,effect=b,kind='ASSOCIATION' if association else 'DIRECT_CAUSE',
            source_ids=ids('relations',0 if paraphrase and a==z else 1 if paraphrase else i)) for i,(a,b) in enumerate(edges)],
        target=dict(kind='INTERVENTIONAL_DISTRIBUTION',treatment=x,outcome=y,context=context,source_ids=ids('__question__')),
        scope=scope,information=dict(kind='FINITE_SAMPLE' if sample else 'FULL_JOINT_POPULATION_LAW',
            variables=[n for n in nodes if n not in hidden],source_ids=ids('information',0),
            positivity=dict(value=None,source_ids=[]) if sample else true(ids('information',1))),
        adjustment=[z] if mediator else None,adjustment_source_ids=ids('__question__') if mediator else [],
        additional_restrictions=[],unresolved=[])
    expected='NEEDS_INPUT' if missing or sample or association else 'UNSUPPORTED' if blocked or mediator else 'POINT'
    adjustment=None if expected!='POINT' else [z]
    return dict(bundle=bundle,reference=reference,expected_state=expected,expected_adjustment=adjustment)


def cases():
    return [_case('confounded_training'),_case('training_paraphrase',paraphrase=True),
        _case('latent_observed_blocker',latent=True),_case('missing_graph_closure',missing=True),
        _case('association_only',association=True,missing=True),_case('sample_only',sample=True),
        _case('unmeasured_confounder',latent=True,blocked=True),_case('requested_mediator',mediator=True)]


def semantic_score(bundle,wire,reference):
    """Independent fixed references, exact fields plus required citation coverage.

    Lexical context/name equality is conservative: a paraphrase may be rejected.
    It is not a general semantic oracle and cannot approve real business science.
    """
    try:
        actual=parse(bundle,wire).model_dump();gold=parse(bundle,reference).model_dump()
    except ValueError:return dict(passed=False,structure=False,fields={},citation_coverage=False)
    def values(d):
        if type(d) is dict:return {k:values(v) for k,v in d.items() if k not in ('source_ids','adjustment_source_ids','unresolved')}
        if type(d) is list:return [values(v) for v in d]
        return d
    def normalize(d):
        d=values(d);d['variables']=sorted(d['variables'],key=lambda v:v['name'])
        d['relations']=sorted(d['relations'],key=lambda e:(e['cause'],e['effect']))
        d['information']['variables']=sorted(d['information']['variables'])
        if d['adjustment'] is not None:d['adjustment']=sorted(d['adjustment'])
        return d
    a,g=normalize(actual),normalize(gold)
    fields={k:a[k]==g[k] for k in g}
    cited=True
    for key,identity in [('variables',lambda v:v['name']),('relations',lambda e:(e['cause'],e['effect']))]:
        rows={identity(row):row for row in actual[key]}
        for row in gold[key]:
            cited &= identity(row) in rows and set(row['source_ids'])<=set(rows[identity(row)]['source_ids'])
    for k in gold['scope']:
        expected=set(gold['scope'][k]['source_ids']);actual_ids=set(actual['scope'][k]['source_ids'])
        cited &= expected<=actual_ids or (k=='perfect_intervention' and set(gold['target']['source_ids'])<=actual_ids)
    for arow,grow in [(actual['target'],gold['target']),(actual['information'],gold['information']),
                      (actual['information']['positivity'],gold['information']['positivity'])]:
        cited &= set(grow['source_ids'])<=set(arow['source_ids'])
    cited &= set(gold['adjustment_source_ids'])<=set(actual['adjustment_source_ids'])
    return dict(passed=all(fields.values()) and bool(cited),structure=True,fields=fields,citation_coverage=bool(cited))


def reference_reviews(bundle,wire):
    view=inspect_candidate(bundle,wire)
    if view['state']!='REVIEW_REQUIRED':raise ValueError('REVIEW_READY_REFERENCE_REQUIRED')
    reading={k:v for k,v in view['reading_worksheet'].items() if k!='is_approval'}
    reading.update(reviewer='Frozen synthetic reference reviewer',evidence='Independent synthetic scenario and exact semantic/source comparison; not real-world approval.',
        authority='SYNTHETIC_TEST',decisions={k:'ACCEPTED' for k in READING_DECISIONS})
    science={k:v for k,v in view['science_worksheet'].items() if k!='is_approval'}
    science.update(reviewer='Frozen synthetic scientific protocol',evidence='Synthetic SCM assumptions explicitly stipulated by scenario author; not empirically validated.',
        authority='SYNTHETIC_TEST',decisions={k:'ACCEPTED' for k in DECISIONS})
    return DagReadingReview.model_validate(reading),BackdoorReview.model_validate(science)


def assess(case,wire):
    b=case['bundle'];score=semantic_score(b,wire,case['reference']);view=inspect_candidate(b,wire)
    if score['passed'] and view['state']=='REVIEW_REQUIRED':
        reading,science=reference_reviews(b,wire)
        view=submit_reviewed(b,wire,reading_review=reading,science_review=science,research_protocol_selected=True)
    if not score['passed']:view['reference_review_withheld']=True
    state=view['state']==case['expected_state']
    proof=case['expected_state']!='POINT' or (view['independent_replay'] and view['certificate']['adjustment']==case['expected_adjustment'])
    return dict(passed=score['passed'] and state and proof,score=score,expected_state=case['expected_state'],
        final_state=view['state'],result=view,synthetic_only=True,real_world_semantic_accuracy=False)
