"""Source roles precede coverage claims; accepted source review never grants science."""
from copy import deepcopy
from dataclasses import replace
import json
import pytest
from cfm_id import business_dispatch as d,business_intake as intake,business_case
from cfm_id import fact_source_review as source
from examples import network_dispatch_reference as mean,network_bounded_dispatch_reference as bounded
from examples import network_contrast_dispatch_reference as contrast,network_effect_dispatch_reference as effect
from examples import network_observational_policy_reference as r3
from examples.business_dispatch_reference import approve


def fixture(kind='r3'):
    call={'r1b':lambda:mean.setup(design='D1',sufficiency=False),'r2':mean.setup,'partial':bounded.setup,
        'contrast_point':lambda:contrast.setup('point'),'contrast_partial':lambda:contrast.setup('partial'),
        'effect':effect.setup,'r3':r3.setup}
    return call[kind]()[:3]


def record(w, decision='ACCEPTED'):
    # Explicit synthetic fixture decisions; never used as a model-based judge.
    return dict(version=source.VERSION,binding_sha256=w['binding_sha256'],authority=w['expected_authority'],
        reviewer='Synthetic source reviewer',evidence='Hand-authored fixture compared with original materials; not real scientific approval.',
        decisions={p:dict(**{a:decision for a in source.DIMENSIONS},reason='Explicit source review of this synthetic record and its actual references.',
        source_ids=list(w['source_catalog'])) for p in w['fields']})


def forbid_method_calls(monkeypatch):
    """Permit metadata lookup, but fail on either method inspection or execution."""
    lookup=d.capabilities.business_binding
    def forbidden(*args,**kwargs):pytest.fail('source before methods')
    monkeypatch.setattr(d.capabilities,'business_binding',lambda reader_id:
        replace(lookup(reader_id),inspect=forbidden,execute=forbidden))


@pytest.mark.parametrize('kind',['r1b','r2','partial','contrast_point','contrast_partial','effect','r3'])
def test_source_review_preserves_target_and_native_certificate_replay(kind):
    s,e,o=fixture(kind);before=deepcopy(o['candidate']);baseline=d.inspect_methods(s,'q1',**o)
    expected=d.execute(s,'q1',**o,**mean.approval_records(baseline))
    w=source.prepare(e,o['candidate']);assert w['is_approval'] is False
    assert all(v[a]=='PENDING' for v in w['decisions'].values() for a in source.DIMENSIONS)
    o['source_review']=record(w);p=d.inspect_methods(s,'q1',**o)
    assert p['state']=='REVIEW_REQUIRED' and p['source_review_receipt']['mathematical_verification']=='NOT_PERFORMED'
    assert not d.execute(s,'q1',**o,research_protocol_selected=True)['backend_called']
    result=d.execute(s,'q1',**o,**mean.approval_records(p))
    assert result['state']==expected['state'] and result['independent_replay']
    assert result['mathematical_claim']==expected['mathematical_claim'] and before==o['candidate']
    assert not result['source_review_receipt']['candidate_modified'] and not result['source_review_receipt']['scientific_approval']
    row=dict(o,**{k:v for k,v in mean.approval_records(p).items() if k!='research_protocol_selected'})
    whole=business_case.execute_case(s,{'q1':row},case_review=approve(business_case.prepare_case(s)['case_worksheet']),research_protocol_selected=True)
    assert whole['results'][0]['result']==result


@pytest.mark.parametrize('kind',['r1b','r2','partial','contrast_point','contrast_partial','effect','r3'])
@pytest.mark.parametrize('decision',['PENDING','REJECTED'])
def test_source_gate_blocks_before_method_inspection(monkeypatch,kind,decision):
    s,e,o=fixture(kind);o['source_review']=record(source.prepare(e,o['candidate']))
    o['source_review']['decisions']['']['field_role']=decision
    # Preparation may inspect registration metadata. The guard applies to
    # method inspection/execution, which must remain unreachable without review.
    forbid_method_calls(monkeypatch)
    r=d.execute(s,'q1',**o,research_protocol_selected=True)
    assert r['state']==('REVIEW_REQUIRED' if decision=='PENDING' else 'READING_RECHECK_REQUIRED')
    assert not r['backend_called'] and r['mathematical_claim'] is None and 'plan_worksheet' not in r


@pytest.mark.parametrize('axis',['field_role','value_state','source_coverage'])
def test_misplaced_material_note_is_not_automatically_a_coverage_gap(axis):
    s,e,o=fixture();o['candidate']['additional_restrictions']=[dict(text='有限回访记录仅作资料说明。',source_ids=o['candidate']['study']['source_ids'])]
    raw=deepcopy(o['candidate']);w=source.prepare(e,raw);review=record(w)
    review['decisions']['/additional_restrictions/0'][axis]='REJECTED'
    r=d.execute(s,'q1',**o,source_review=review,research_protocol_selected=True)
    assert r['state']=='READING_RECHECK_REQUIRED' and '/additional_restrictions/0' in r['rejected_fields']
    assert raw==o['candidate'] and not r['backend_called']
    # If independently accepted as a genuine additional condition, it still
    # reaches the old unsupported-model gate, never gets erased/released.
    result=d.execute(s,'q1',**o,source_review=record(w),research_protocol_selected=True)
    assert result['state']=='ADAPTER_NOT_CONNECTED' and result['facts']['additional_restrictions']
    assert not result['backend_called'] and result['source_review_receipt']


@pytest.mark.parametrize('defect',['binding','authority','unknown_source','missing_source','duplicate_source','missing_field','extra_field','blank_reason','extra_approval'])
def test_bad_review_cannot_enter_native_checks(defect):
    s,e,o=fixture();review=record(source.prepare(e,o['candidate']));row=review['decisions']['/conditioning']
    if defect=='binding':review['binding_sha256']='0'*64
    elif defect=='authority':review['authority']='EXTERNAL_RESEARCH_REVIEW'
    elif defect=='unknown_source':row['source_ids']=['foreign']
    elif defect=='missing_source':row['source_ids']=[]
    elif defect=='duplicate_source':row['source_ids']*=2
    elif defect=='missing_field':review['decisions'].pop('/conditioning')
    elif defect=='extra_field':review['decisions']['/fake']=deepcopy(row)
    elif defect=='blank_reason':row['reason']=' '
    else:row['scientific_approval']=True
    result=d.execute(s,'q1',**o,source_review=review,research_protocol_selected=True)
    assert result['state']=='CHECK_BLOCKED' and not result['backend_called']


@pytest.mark.parametrize('change',['value','source','order','extra','request'])
def test_changed_reading_or_request_invalidates_source_approval(change):
    s,e,o=fixture();review=record(source.prepare(e,o['candidate']))
    if change=='value':o['candidate']['conditioning']['definition']='different W'
    elif change=='source':o['candidate']['conditioning']['source_ids']=o['candidate']['study']['source_ids']
    elif change=='order':o['candidate']['information'][0]['assignment_masses'].reverse()
    elif change=='extra':o['candidate']['additional_restrictions']=[dict(text='结果还满足额外的跨对象关系。',source_ids=o['candidate']['study']['source_ids'])]
    else:o['request_sha256']='0'*64
    r=d.execute(s,'q1',**o,source_review=review,research_protocol_selected=True)
    assert r['state']=='CHECK_BLOCKED' and not r['backend_called']


@pytest.mark.parametrize('change',['omit','new_reviewer','new_reason'])
@pytest.mark.parametrize('kind',['r1b','r2','partial','contrast_point','contrast_partial','effect','r3'])
def test_issued_native_approvals_cannot_drop_or_change_source_review(change,kind):
    s,e,o=fixture(kind);o['source_review']=record(source.prepare(e,o['candidate']))
    p=d.inspect_methods(s,'q1',**o);a=mean.approval_records(p)
    if change=='omit':o.pop('source_review')
    elif change=='new_reviewer':o['source_review']['reviewer']='Another reviewer'
    else:o['source_review']['decisions']['']['reason']+=' New review reason.'
    r=d.execute(s,'q1',**o,**a);assert r['state']=='CHECK_BLOCKED' and not r['backend_called']


@pytest.mark.parametrize('gap',['science','sample','condition','support'])
def test_source_acceptance_never_supplies_missing_science_information_or_support(gap):
    s,e,o=r3.setup(**({'exchangeability':None} if gap=='science' else {'sample_only':True} if gap=='sample' else {'zero_support':True} if gap=='support' else {}))
    if gap=='condition':o['candidate']['conditioning']['definition']=None
    o['source_review']=record(source.prepare(e,o['candidate']));p=d.inspect_methods(s,'q1',**o)
    a=mean.approval_records(p) if p.get('plan_worksheet') else dict(research_protocol_selected=True)
    r=d.execute(s,'q1',**o,**a)
    assert r['state']==('UNSUPPORTED' if gap=='support' else 'NEEDS_INPUT')
    assert not r['independent_replay'] and (r['backend_called']==(gap=='support'))


def test_parent_or_reviewer_citations_do_not_repair_child_coverage():
    s,e,o=fixture();w=source.prepare(e,o['candidate']);path='/information/0/assignment_masses/0'
    # Each child is exposed with its original direct citation list, not parent union.
    assert w['fields'][path]['citation_groups']['source_ids']==o['candidate']['information'][0]['assignment_masses'][0]['source_ids']
    assert not w['fields'][path]['explicit_definitions']
    review=record(w);review['decisions'][path]['source_coverage']='REJECTED'
    before=deepcopy(o['candidate']);r=d.execute(s,'q1',**o,source_review=review,research_protocol_selected=True)
    assert r['state']=='READING_RECHECK_REQUIRED' and before==o['candidate']
    assert not r['source_review_receipt']['citations_repaired']


def test_existing_explicit_definition_dependencies_are_shown_separately(monkeypatch):
    from tests_gateway.test_local_field_contract import setup
    s,e,o=setup(monkeypatch,count=True)
    w=source.prepare(e,o['candidate']);arm=w['fields']['/target/reference']
    assert set(arm['explicit_definitions'])==set(o['candidate']['target']['reference']['definition_refs'])
    assert arm['citation_groups']['source_ids']==o['candidate']['target']['reference']['source_ids']
    assert all(v['source_ids'] for v in arm['explicit_definitions'].values())
    o['source_review']=record(w);p=d.inspect_methods(s,'q1',**o)
    from examples.network_effect_dispatch_reference import approval_records
    r=d.execute(s,'q1',**o,**approval_records(p));assert r['state']=='POINT' and r['independent_replay']


def test_misfiled_information_is_reclassified_without_model_edits():
    # Fully local analogue; saved live responses are replayed separately outside
    # this portable suite. Do not import test evidence into runtime modules.
    s,e,o=fixture();o['candidate']['additional_restrictions']=[dict(text='均值只作符号给定，没有提供数值。',source_ids=o['candidate']['information'][0]['source_ids'])]
    w=source.prepare(e,o['candidate']);review=record(w);review['decisions']['/additional_restrictions/0']['field_role']='REJECTED'
    assert d.inspect_methods(s,'q1',**o)['state']=='ADAPTER_NOT_CONNECTED'
    assert d.inspect_methods(s,'q1',**o,source_review=review)['state']=='READING_RECHECK_REQUIRED'


@pytest.mark.parametrize('defect',['unknown_reference','duplicate_reference','context','version','extra_field','bad_type'])
def test_invalid_wire_cannot_be_approved_as_a_source_record(defect):
    s,e,o=fixture();raw=o['candidate']
    if defect=='unknown_reference':raw['study']['source_ids']=['foreign']
    elif defect=='duplicate_reference':raw['study']['source_ids']*=2
    elif defect=='context':raw['reference_context']='foreign'
    elif defect=='version':raw['version']='unregistered'
    elif defect=='extra_field':raw['approved_by_llm']=True
    else:raw['study']['nodes']='not an ordered list'
    with pytest.raises((ValueError,TypeError)):source.prepare(e,raw)
    r=d.execute(s,'q1',**o,source_review={},research_protocol_selected=True)
    assert r['state']=='CHECK_BLOCKED' and not r['backend_called']


def test_fact_recheck_needs_new_source_and_full_change_reviews():
    from cfm_id.fact_reading_revision import prepare_recheck
    from tests_gateway.test_fact_reading_revision import feedback,accept_changes
    s,e,o=fixture();old_source=record(source.prepare(e,o['candidate']))
    old_approvals=mean.approval_records(d.inspect_methods(s,'q1',**o,source_review=old_source))
    o['candidate']['conditioning']['definition']='错误的目标背景，待复查'
    w=prepare_recheck(s,'q1',**o)['feedback_worksheet']
    fresh=prepare_recheck(s,'q1',**o,feedback=feedback(w,path='/conditioning/definition',doc='conditioning'))
    _,data=r3.material()
    new=dict(query_review=o['query_review'],candidate=r3.fact_reference(fresh,data),
        request_sha256=fresh['request_sha256'],reading_revision=fresh['reading_revision'])
    # The new response has the current reference context and needs full review.
    pending=d.inspect_methods(s,'q1',**new)
    assert pending['state']=='REVIEW_REQUIRED' and 'reading_change_worksheet' in pending
    new['change_review']=accept_changes(pending['reading_change_worksheet'])
    assert d.inspect_methods(s,'q1',**new,source_review=old_source)['state']=='CHECK_BLOCKED'
    new['source_review']=record(source.prepare(fresh,new['candidate']))
    assert not d.execute(s,'q1',**new,**old_approvals)['backend_called']
    p=d.inspect_methods(s,'q1',**new)
    r=d.execute(s,'q1',**new,**mean.approval_records(p))
    assert r['state']=='POINT' and r['independent_replay']


def test_new_source_review_survives_cli_whole_case_and_restore(tmp_path):
    from cfm_id.business_dispatch_cli import main
    from cfm_id.business_case_cli import main as whole_cli
    s,e,o=fixture();w=source.prepare(e,o['candidate']);o['source_review']=record(w)
    intake.save(s,tmp_path/'intake.json')
    for name,value in [('reader',e),('candidate',o['candidate']),('query',o['query_review']),('source',o['source_review'])]:
        intake.write_json(tmp_path/(name+'.json'),value.model_dump(mode='json') if hasattr(value,'model_dump') else value)
    base=['--intake',str(tmp_path/'intake.json'),'--query','q1','--query-review',str(tmp_path/'query.json'),
        '--reader-plan',str(tmp_path/'reader.json'),'--candidate',str(tmp_path/'candidate.json')]
    assert main(['source-review-plan',*base,'--output',str(tmp_path/'worksheet.json')])==0
    assert intake.read_json(tmp_path/'worksheet.json')['source_review_worksheet']==w
    assert main(['method-plan',*base,'--source-review',str(tmp_path/'source.json'),'--output',str(tmp_path/'plan.json')])==0
    p=intake.read_json(tmp_path/'plan.json');a=mean.approval_records(p)
    def serial(v):
        if hasattr(v,'model_dump'):return v.model_dump(mode='json')
        if type(v) is dict:return {k:serial(x) for k,x in v.items()}
        return v
    row=serial(dict(o,**{k:v for k,v in a.items() if k!='research_protocol_selected'}))
    intake.write_json(tmp_path/'submissions.json',{'q1':row});intake.write_json(tmp_path/'case.json',serial(approve(business_case.prepare_case(s)['case_worksheet'])))
    assert whole_cli(['execute','--intake',str(tmp_path/'intake.json'),'--submissions',str(tmp_path/'submissions.json'),
        '--case-review',str(tmp_path/'case.json'),'--select-research-protocol','--output',str(tmp_path/'result.json')])==0
    result=intake.read_json(tmp_path/'result.json')['results'][0]['result']
    assert result['state']=='POINT' and result['independent_replay'] and result['source_review_receipt']['review']==o['source_review']
