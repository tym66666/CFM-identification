"""Fixed-background adapter acceptance; hand-authored readings, zero API calls."""
from copy import deepcopy
import json
import pytest
from cfm_id import business_intake as intake, business_dispatch as dispatch, business_case
from cfm_id import network_contrast_dispatch as contrast, network_contrast_context as context
from cfm_id_llm import query_conditioning_contract as conditioning
from cfm_id_llm.network_policy_reading import reference_catalog
from cfm_id_llm.evidence_refs import build_catalog
from cfm_id_llm.compact_reference_contract import CONTRACT as SHORT
from cfm_id_llm.schemas import SourceDocument
from examples import network_contrast_dispatch_reference as base
from examples import network_mean_order_dispatch_reference as orders
from examples import network_r2_contrast_reference as r2
from examples.business_dispatch_reference import approve
from tests_gateway.test_inline_evidence_slots import wire
from tests_gateway.test_compact_short_refs import encode_fixture
from tests_gateway.test_business_field_review import sheet, record, submit


BACKGROUND = '各研究对象每天营业八小时，营业安排在采用工具前已经确定'


def setup(route='orders', *, condition='STATED', **options):
    seed, old_entry, old_options = (orders.setup(**options) if route=='orders' else
        r2.setup(**options) if route=='r2' else base.setup('point' if route=='r1b' else 'partial', **options))
    source = ('本次比较限定在'+BACKGROUND+'的背景下。文中两端政策的目标、原试点完整分配律、'
        '分配独立性、全部总体信息、科学条件、界限及所采用的均值顺序，均指该背景；'
        '所列总体信息和模型完整性声明也仅对该背景作出。不混合不同营业安排。')
    case = seed.case.model_copy(update=dict(business_question=seed.case.business_question+' 本问限定在每天营业八小时的背景下。',
        sources=[*seed.case.sources, SourceDocument(source_id='background', text=source)]))
    raw = wire(seed.candidate, operation='INTERVENTION_MINUS_COMPARATOR')
    # Rebuild cited A0 values after changing the source question. This is a
    # frozen reference fixture, never a repair applied to a model response.
    old_catalog, catalog = build_catalog(seed.case), build_catalog(case)
    source_refs = {item['ref']:next(row['ref'] for row in catalog if row['source_id']==item['source_id'] and row['quote']==item['quote'])
                   for item in old_catalog}
    def remap(value, mapping, field):
        if isinstance(value,dict):return {k:([mapping[v] for v in x] if k==field else remap(x,mapping,field)) for k,x in value.items()}
        if isinstance(value,list):return [remap(x,mapping,field) for x in value]
        return value
    raw = remap(raw, source_refs, 'refs')
    raw['queries'][0]['goal']['value'] = case.business_question
    refs=[row['ref'] for row in catalog if row['source_id']=='background']
    value = dict(state=condition, value=BACKGROUND, refs=refs) if condition=='STATED' else (
        dict(state='MISSING',reason='背景尚未决定',refs=refs) if condition=='MISSING' else 'UNKNOWN')
    raw['queries'][0]['semantics'][conditioning.FIELD]=value
    s=intake.start(case, a0_response_contract=conditioning.CONTRACT,
        a0_reference_contract=SHORT,target_summary_contract='target-summary-3',
        network_fact_contract=seed.network_fact_contract)
    s=intake.receive_candidate(s,encode_fixture(s,raw),request_sha256=s.request_sha256)
    review=submit(s,record(sheet(s)))['query_review']
    e=dispatch.prepare_reader(s,'q1',query_review=review)
    if e['state']!='READY_TO_READ':return s,e,None
    old_refs=reference_catalog(old_entry['bundle'],binding=old_entry['fact_binding_sha256'])
    new_refs=reference_catalog(e['bundle'],binding=e['fact_binding_sha256'])
    mapping={key:next(k for k,r in new_refs['aliases'].items() if r['doc_id']==v['doc_id'] and
        (r['text']==v['text'] or r['doc_id'] in ('__question__','business_question'))) for key,v in old_refs['aliases'].items()}
    facts=remap(old_options['candidate'],mapping,'source_ids')
    facts['reference_context']=new_refs['context']
    facts['study']['context'] += '；固定背景：'+BACKGROUND
    facts['study']['source_ids'] += [k for k,v in new_refs['aliases'].items() if v['doc_id']=='background']
    return s,e,dict(query_review=review,candidate=facts,request_sha256=e['request_sha256'])


@pytest.mark.parametrize('route,expected',[('r1b','POINT'),('r2','POINT'),('box','PARTIAL'),('orders','PARTIAL')])
def test_existing_routes_preserve_condition_direction_and_replay(route,expected):
    s,e,o=setup(route);assert e['state']=='READY_TO_READ',e
    before=deepcopy(o['candidate']);p=dispatch.inspect_methods(s,'q1',**o)
    assert p['state']=='REVIEW_REQUIRED',p
    item=p['target_conditioning_review']
    assert item['reviewed_query']==e['reviewed_target_context'] and not item['is_approval']
    assert item['fact_conditioning']['definition']==before['study']['context']
    assert item['scientific_requirements']==context.SCIENCE_REQUIREMENTS
    a=base.approval_records(p);r=dispatch.execute(s,'q1',**o,**a)
    assert r['state']==expected and r['independent_replay'],r
    assert r['mathematical_claim']['target']['context']==before['study']['context']
    assert r['mathematical_claim']['target']['operation']=='first_minus_second'
    assert o['candidate']==before and not r['production_admission']
    if route=='orders':
        from cfm_id.mean_order_contract import MeanOrderProblem
        from cfm_id.mean_order_verify import replay
        answer=r['answers'][0];problem=MeanOrderProblem.model_validate(answer['native_evidence']['problem'])
        assert problem.context==before['study']['context'] and replay(answer['certificate'],problem=problem)
        assert r['mathematical_claim']['interval']==['1/5','1']
        payload=dict(o,**{k:v for k,v in a.items() if k!='research_protocol_selected'})
        whole=business_case.execute_case(s,{'q1':payload},case_review=approve(business_case.prepare_case(s)['case_worksheet']),research_protocol_selected=True)
        assert whole['state']=='ALL_QUERIES_IDENTIFIED'


@pytest.mark.parametrize('key',[conditioning.MATCH_DECISION,*context.SCIENCE_REQUIREMENTS])
@pytest.mark.parametrize('decision',['PENDING','REJECTED','OMIT'])
def test_no_scope_review_no_backend(monkeypatch,key,decision):
    s,e,o=setup();p=dispatch.inspect_methods(s,'q1',**o);a=base.approval_records(p)
    method=p['methods'][0]['method']
    r=a['native_reviews'][method]['reading_review' if key==conditioning.MATCH_DECISION else 'science_review']
    if decision=='OMIT':r.decisions.pop(key)
    else:r.decisions[key]=decision
    monkeypatch.setattr(contrast.mean_order,'execute_reviewed',lambda *a,**k:pytest.fail('unreviewed background'))
    result=dispatch.execute(s,'q1',**o,**a)
    assert result['state'] in ('REVIEW_REQUIRED','CHECK_BLOCKED')
    assert not result['backend_called'] and result['mathematical_claim'] is None


@pytest.mark.parametrize('mutation',['context','direction','population','source'])
def test_changed_facts_cannot_reuse_reviews(mutation):
    s,e,o=setup();p=dispatch.inspect_methods(s,'q1',**o);a=base.approval_records(p)
    c=o['candidate'];t=c['target']
    if mutation=='context':c['study']['context']='另一营业安排，必须重新审核'
    elif mutation=='direction':t['first'],t['second']=t['second'],t['first']
    elif mutation=='population':t['second']['population']=['甲店']
    else:c['study']['source_ids']=['unknown_source']
    result=dispatch.execute(s,'q1',**o,**a)
    assert not result['backend_called'] and result['mathematical_claim'] is None


def test_missing_background_and_standardization_keep_distinct_stops():
    s,e,_=setup(condition='MISSING')
    assert e['state']=='NEEDS_INPUT' and e['request'] is None
    s,e,o=setup();ctx=deepcopy(e['reviewed_target_context'])
    ctx['standardization_distribution']=dict(state='STATED',value='按历史营业安排分布平均',refs=['fixture'])
    assert conditioning.admission(ctx,contrast.FAMILY)==('ADAPTER_NOT_CONNECTED','STANDARDIZED_CONTRAST_TARGET_NOT_CONNECTED')
    ctx['standardization_distribution']=dict(state='MISSING',reason='尚未决定',refs=['fixture'])
    assert conditioning.admission(ctx,contrast.FAMILY)==('NEEDS_INPUT','TARGET_STANDARDIZATION_UNRESOLVED')


def test_unknown_condition_does_not_invent_a_new_requirement():
    s,e,o=setup(condition='UNKNOWN');p=dispatch.inspect_methods(s,'q1',**o)
    assert 'target_conditioning_review' not in p
    for row in p['methods']:
        assert conditioning.MATCH_DECISION not in row['reading_worksheet']['decisions']
        assert not set(context.SCIENCE_REQUIREMENTS)&row['science_worksheet']['decisions'].keys()


def test_fixed_background_assumption_ladder_and_direction():
    intervals=[]
    for mode in ('BOTH','OWN','NONE'):
        s,e,o=setup(mode=mode);p=dispatch.inspect_methods(s,'q1',**o)
        r=dispatch.execute(s,'q1',**o,**base.approval_records(p))
        assert r['independent_replay'];intervals.append(r['mathematical_claim']['interval'])
    assert intervals==[['1/5','1'],['-1/5','1'],['-1','1']]
    s,e,o=setup(reverse=True);p=dispatch.inspect_methods(s,'q1',**o)
    r=dispatch.execute(s,'q1',**o,**base.approval_records(p))
    assert r['mathematical_claim']['interval']==['-1','-1/5'] and r['independent_replay']


def test_native_changed_background_fails_certificate_replay():
    from cfm_id.mean_order_contract import MeanOrderProblem
    from cfm_id.mean_order_verify import replay
    s,e,o=setup();p=dispatch.inspect_methods(s,'q1',**o)
    r=dispatch.execute(s,'q1',**o,**base.approval_records(p));answer=r['answers'][0]
    problem=MeanOrderProblem.model_validate(answer['native_evidence']['problem'])
    problem=problem.model_copy(update={'context':'另一背景'})
    assert replay(answer['certificate'],problem=problem) is False


def test_recheck_and_save_restore_preserve_context_and_invalidate_old_reviews(tmp_path):
    from cfm_id.fact_reading_revision import prepare_recheck
    from tests_gateway.test_fact_reading_revision import feedback, accept_changes
    s,e,o=setup();p=dispatch.inspect_methods(s,'q1',**o);a=base.approval_records(p)
    path=tmp_path/'case.json';intake.save(s,path);restored=intake.restore(path)
    assert dispatch.prepare_reader(restored,'q1',query_review=o['query_review'])==e
    bad=deepcopy(o);bad['candidate']['study']['context']='只有同一考核周，漏掉了营业安排'
    pending=prepare_recheck(s,'q1',**bad)
    fresh=prepare_recheck(s,'q1',**bad,feedback=feedback(pending['feedback_worksheet'],path='/study/context',doc='background'))
    assert fresh['reviewed_target_context']==e['reviewed_target_context']
    public=json.loads(fresh['request']['user'].split('独立复查定位（不是新增事实）：\n')[1])
    assert any(row.get('description')==conditioning.CONTRAST_DESCRIPTION for row in public['public_field_constraints'])
    corrected=deepcopy(o['candidate'])
    corrected['reference_context']=reference_catalog(fresh['bundle'],binding=fresh['fact_binding_sha256'])['context']
    new=dict(query_review=o['query_review'],candidate=corrected,request_sha256=fresh['request_sha256'],reading_revision=fresh['reading_revision'])
    changed=dispatch.inspect_methods(s,'q1',**new)
    new['change_review']=accept_changes(changed['reading_change_worksheet'])
    assert not dispatch.execute(s,'q1',**new,**a)['backend_called']
    p=dispatch.inspect_methods(s,'q1',**new)
    result=dispatch.execute(s,'q1',**new,**base.approval_records(p))
    assert result['state']=='PARTIAL' and result['independent_replay']


@pytest.mark.parametrize('defect',['sample_only','missing_order','different_background'])
def test_fixed_background_does_not_grant_missing_mathematical_conditions(defect):
    s,e,o=setup();c=o['candidate']
    if defect=='sample_only':c['information'][0].update(operator='FINITE_SAMPLE',availability='FINITE_SAMPLE',signature_cells=[])
    elif defect=='missing_order':c['mean_order_model']['order_reading']['claims'].pop()
    else:c['target']['shared_outcome_and_context']['value']=False
    r=dispatch.execute(s,'q1',**o,research_protocol_selected=True)
    assert r['state']==('ADAPTER_NOT_CONNECTED' if defect=='different_background' else 'NEEDS_INPUT')
    assert not r['backend_called'] and r['mathematical_claim'] is None
