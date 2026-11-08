"""Source accounting is distinct from, and never replaces, causal admission."""
from copy import deepcopy
import json
import pytest
from cfm_id import business_intake as intake, business_dispatch as dispatch
from cfm_id import reading_material_handoff as handoff, reading_impact_review as impact
from cfm_id import fact_source_review as source, fact_reading_revision as revision
from cfm_id.business_reading_config import ReadingConfig
from cfm_id_llm.schemas import SourceDocument
from cfm_id_llm.evidence_refs import build_catalog
from cfm_id_llm.compact_reference_contract import CONTRACT as SHORT
from examples.network_design_exposure_reference import material, a0_reference, fact_reference
from examples.network_dispatch_reference import approval_records
from tests_gateway.test_inline_evidence_slots import wire
from tests_gateway.test_compact_short_refs import encode_fixture
from tests_gateway.test_business_field_review import sheet, record, submit
from tests_gateway.test_fact_source_review import record as source_record
from tests_gateway.test_fact_reading_revision import feedback, accept_changes


def fixture(family='policy', *, enabled=True, represented=False, shared=False):
    case,data=material('D1','E5',family)
    note='运营部门另外保存了上月部分门店的回访记录，供后续估计使用；本材料没有列出记录覆盖的门店名单。'
    case=case.model_copy(update={'sources':[*case.sources,SourceDocument(source_id='records',text=note)]})
    raw=wire(a0_reference(case,data),operation='NOT_APPLICABLE' if family=='policy' else 'INTERVENTION_MINUS_COMPARATOR')
    raw['queries'][0]['semantics']['conditioning_context']='UNKNOWN'
    ids=[r['ref'] for r in build_catalog(case) if r['source_id']=='records']
    raw['common']['sample_data_description']=dict(state='STATED',value=note,refs=ids)
    if shared:raw['common']['available_information']['refs']+=ids
    config=dict(a0_response_contract='query-conditioning-1',a0_reference_contract=SHORT,
        target_summary_contract='target-summary-3',network_fact_contract='network-source-selections-alignment-1')
    if enabled:config['material_handoff']=handoff.VERSION
    s=intake.start(case,**config)
    s=intake.receive_candidate(s,encode_fixture(s,raw),request_sha256=s.request_sha256)
    q=submit(s,record(sheet(s)))['query_review']
    e=dispatch.prepare_reader(s,'q1',query_review=q)
    assert e['state']=='READY_TO_READ', e
    candidate=fact_reference(e,data)
    if represented:
        refs=handoff.references(e)
        candidate['information'].append(dict(operator='FINITE_SAMPLE',availability='FINITE_SAMPLE',
            outcome_nodes=[],assignment_cells=[],signature_cells=[],
            source_ids=[k for k,v in refs['aliases'].items() if v['doc_id']=='records']))
    return s,e,dict(query_review=q,candidate=candidate,request_sha256=e['request_sha256']),data


def reviewed(e,raw,*,omitted=True):
    w=impact.prepare(e,raw);r=source_record(w);r['version']=impact.VERSION
    r['material_decisions']={}
    for key,item in w['material_items'].items():
        is_note=key=='sample_data_description'
        r['material_decisions'][key]=dict(
            disposition='OMITTED_ESTIMATION_NOTE' if is_note and omitted else 'REPRESENTED',
            fact_paths=[] if is_note and omitted else ['/information/1' if is_note else '/information/0'],
            source_ids=item['source_ids'],reason='Synthetic independent review of the full original source and its role.',
            pure_record_description=is_note and omitted,no_values_definitions_or_scientific_content=is_note and omitted)
    return r


@pytest.mark.parametrize('family',['policy','contrast'])
@pytest.mark.parametrize('represented',[False,True])
def test_reading_completeness_and_verified_point_are_distinct(family,represented):
    s,e,o,_=fixture(family,represented=represented);raw=deepcopy(o['candidate'])
    assert handoff.omissions(e,raw)[0]['status']==('CITATION_LINKED_REQUIRES_REVIEW' if represented else 'NO_INFORMATION_RECORD_LINK')
    o['source_review']=reviewed(e,raw,omitted=not represented)
    plan=dispatch.inspect_methods(s,'q1',**o)
    assert plan['state']=='REVIEW_REQUIRED' and 'plan_worksheet' in plan, plan
    assert not dispatch.execute(s,'q1',**o,research_protocol_selected=True)['backend_called']
    result=dispatch.execute(s,'q1',**o,**approval_records(plan))
    assert result['state']=='POINT' and result['independent_replay'],result
    assert result['reading_assessment']['material_completeness']==('COMPLETE' if represented else 'INCOMPLETE')
    assert result['identification_assessment']['verified'] and o['candidate']==raw
    assert not result['source_review_receipt']['citations_repaired']
    assert not result['source_review_receipt']['scientific_approval']


def test_handoff_is_required_pending_not_an_auto_approval():
    s,e,o,_=fixture();p=dispatch.inspect_methods(s,'q1',**o)
    assert p['state']=='REVIEW_REQUIRED' and 'plan_worksheet' not in p and not p['backend_called']
    assert p['reading_assessment']['identification_inputs']=='PENDING'
    assert all(x['disposition']=='PENDING' for x in p['source_review_worksheet']['material_decisions'].values())
    r=reviewed(e,o['candidate']);r['material_decisions']['sample_data_description']['disposition']='PENDING'
    result=dispatch.execute(s,'q1',**o,source_review=r,research_protocol_selected=True)
    assert not result['backend_called'] and not result['identification_assessment']['verified']
    old=source_record(source.prepare(e,o['candidate']))
    assert dispatch.execute(s,'q1',**o,source_review=old)['reason_code']=='MATERIAL_ACCOUNTING_REVIEW_VERSION_REQUIRED'
    o['candidate']['information'][0]['source_ids']=['foreign']
    invalid=dispatch.inspect_methods(s,'q1',**o)
    assert invalid['reading_assessment']['format']=='REJECTED_OR_STALE'
    assert invalid['reading_assessment']['field_review']['source_coverage']=='NOT_ASSESSED'
    assert not invalid['identification_assessment']['verified']


@pytest.mark.parametrize('defect',['shared_source','used_source','only_sample','pop_omission','false_classification','rejected_target','rejected_citation','wrong_sample_scope'])
def test_material_exception_cannot_excuse_identification_or_provided_fact_errors(defect):
    s,e,o,_=fixture(shared=defect=='shared_source',represented=defect=='wrong_sample_scope')
    raw=o['candidate'];refs=handoff.references(e)
    sample_ids=[k for k,v in refs['aliases'].items() if v['doc_id']=='records']
    if defect=='used_source':raw['study']['source_ids']+=sample_ids
    elif defect=='only_sample':raw['information'][0].update(operator='FINITE_SAMPLE',availability='FINITE_SAMPLE')
    elif defect=='pop_omission':raw['information']=[]
    elif defect=='wrong_sample_scope':raw['information'][1]['outcome_nodes']=list(raw['study']['nodes'])
    r=reviewed(e,raw,omitted=defect!='wrong_sample_scope')
    if defect=='false_classification':r['material_decisions']['sample_data_description']['pure_record_description']=False
    elif defect=='rejected_target':r['decisions']['/target']['field_role']='REJECTED'
    elif defect=='rejected_citation':r['decisions']['/information/0']['source_coverage']='REJECTED'
    elif defect=='wrong_sample_scope':r['decisions']['/information/1']['source_coverage']='REJECTED'
    before=deepcopy(raw);result=dispatch.execute(s,'q1',**o,source_review=r,research_protocol_selected=True)
    assert result['state']=='READING_RECHECK_REQUIRED' and not result['backend_called'], result
    assert result['reading_assessment']['identification_inputs']=='REJECTED' and raw==before


@pytest.mark.parametrize('status',['UNDECIDED','NOT_ADOPTED'])
def test_complete_reading_of_missing_or_refused_science_never_certifies(status):
    s,e,o,_=fixture(represented=True)
    o['candidate']['scientific_statements']['consistency']['status']=status
    o['source_review']=reviewed(e,o['candidate'],omitted=False)
    result=dispatch.execute(s,'q1',**o,research_protocol_selected=True)
    assert not result['backend_called'] and not result['identification_assessment']['verified']
    assert result['reading_assessment']['material_completeness']=='COMPLETE'


def test_request_only_adds_original_locators_and_recheck_rebinds_all_reviews(tmp_path):
    s,e,o,data=fixture(represented=True);before=deepcopy(o['candidate'])
    payload=json.loads(e['request']['user'].split('原材料交接清单（不是新事实或许可）：\n')[1])
    assert set(payload['items'][0])=={'item_id','a0_field','a0_state','source_ids'}
    old=reviewed(e,before,omitted=False);plan=dispatch.inspect_methods(s,'q1',**o,source_review=old)
    approvals=approval_records(plan)
    saved=tmp_path/'intake.json';intake.save(s,saved);assert intake.restore(saved)==s
    # New mistaken reading requires a genuine correction, not merely new IDs.
    o['candidate']['information'][1]['outcome_nodes']=list(o['candidate']['study']['nodes'])
    before=deepcopy(o['candidate'])
    w=revision.prepare_recheck(s,'q1',**o)['feedback_worksheet']
    fresh=revision.prepare_recheck(s,'q1',**o,feedback=feedback(w,path='/information/1',doc='records'))
    assert fresh['material_inventory']==e['material_inventory']
    public=json.loads(fresh['request']['user'].split('原材料交接清单（不是新事实或许可）：\n')[1].split('\n\n独立复查定位')[0])
    assert all(sid in handoff.references(fresh)['aliases'] for item in public['items'] for sid in item['source_ids'])
    raw=fact_reference(fresh,data);sample=deepcopy(before['information'][1]);sample['outcome_nodes']=[]
    sample['source_ids']=[k for k,v in handoff.references(fresh)['aliases'].items() if v['doc_id']=='records'];raw['information'].append(sample)
    new=dict(query_review=o['query_review'],candidate=raw,request_sha256=fresh['request_sha256'],reading_revision=fresh['reading_revision'])
    pending=dispatch.inspect_methods(s,'q1',**new)
    new['change_review']=accept_changes(pending['reading_change_worksheet'])
    assert dispatch.execute(s,'q1',**new,source_review=old,**approvals)['state']=='CHECK_BLOCKED'
    new['source_review']=reviewed(fresh,raw,omitted=False)
    p=dispatch.inspect_methods(s,'q1',**new);result=dispatch.execute(s,'q1',**new,**approval_records(p))
    assert result['state']=='POINT' and result['independent_replay'] and o['candidate']==before


def test_default_serialization_and_strict_legacy_review_unchanged():
    assert 'material_handoff' not in ReadingConfig().model_dump(mode='json')
    s,e,o,_=fixture(enabled=False)
    assert 'material_handoff' not in s.model_dump(mode='json') and 'material_inventory' not in e
    assert '原材料交接清单' not in e['request']['user']
    r=source_record(source.prepare(e,o['candidate']));r['decisions']['']['field_role']='REJECTED'
    assert dispatch.execute(s,'q1',**o,source_review=r)['state']=='READING_RECHECK_REQUIRED'
    changed=intake.configure_material_handoff(s)
    assert dispatch.prepare_reader(changed,'q1',query_review=o['query_review'])['state']!='READY_TO_READ'


def test_joint_sharp_partial_needs_complete_materials_without_note_exception():
    from examples import network_contrast_dispatch_reference as example
    case,data=example.material('partial');note='另外保留一轮逐店结果记录供后续估计，未提供覆盖名单。'
    case=case.model_copy(update={'sources':[*case.sources,SourceDocument(source_id='records',text=note)]})
    raw=example.a0_reference(case)
    for field,doc in [('sample_data_description','records'),('available_information','information')]:
        raw['common'][field]=dict(state='STATED',value=case.source_map()[doc],refs=[r['ref'] for r in build_catalog(case) if r['source_id']==doc])
    s=intake.start(case,a0_reference_contract=SHORT,material_handoff=handoff.VERSION)
    s=intake.receive_candidate(s,encode_fixture(s,raw),request_sha256=s.request_sha256)
    q=submit(s,record(sheet(s)))['query_review'];e=dispatch.prepare_reader(s,'q1',query_review=q)
    candidate=example.fact_reference(e,data);sample=dict(operator='FINITE_SAMPLE',availability='FINITE_SAMPLE',
        outcome_nodes=[],assignment_cells=[],signature_cells=[],source_ids=[k for k,v in handoff.references(e)['aliases'].items() if v['doc_id']=='records'])
    o=dict(query_review=q,candidate=candidate,request_sha256=e['request_sha256'],source_review=reviewed(e,candidate))
    stopped=dispatch.execute(s,'q1',**o,research_protocol_selected=True)
    assert stopped['state']=='READING_RECHECK_REQUIRED' and not stopped['backend_called']
    candidate['information'].append(sample);o['source_review']=reviewed(e,candidate,omitted=False)
    complete=dispatch.execute(s,'q1',**o,research_protocol_selected=True)
    assert complete['reading_assessment']['material_completeness']=='COMPLETE'
    # Complete material remains in the review. Finite records are not A4 and
    # need not block an independently supplied complete population model.
    assert complete['state']=='REVIEW_REQUIRED' and not complete['backend_called']
    p=dispatch.inspect_methods(s,'q1',**o)
    snapshot=deepcopy(candidate)
    with_sample=dispatch.execute(s,'q1',**o,**approval_records(p))
    assert with_sample['state']=='PARTIAL' and with_sample['independent_replay']
    assert with_sample['mathematical_claim']['sharp'] and candidate==snapshot
    rejected=deepcopy(o)
    rejected['source_review']['decisions']['/information/1']['source_coverage']='REJECTED'
    assert not dispatch.execute(s,'q1',**rejected,**approval_records(p))['backend_called']
    case,data=example.material('partial');raw=example.a0_reference(case)
    raw['common']['available_information']=dict(state='STATED',value=case.source_map()['information'],
        refs=[r['ref'] for r in build_catalog(case) if r['source_id']=='information'])
    s=intake.start(case,a0_reference_contract=SHORT,material_handoff=handoff.VERSION)
    s=intake.receive_candidate(s,encode_fixture(s,raw),request_sha256=s.request_sha256)
    q=submit(s,record(sheet(s)))['query_review'];e=dispatch.prepare_reader(s,'q1',query_review=q)
    candidate=example.fact_reference(e,data)
    o=dict(query_review=q,candidate=candidate,request_sha256=e['request_sha256'],source_review=reviewed(e,candidate,omitted=False))
    p=dispatch.inspect_methods(s,'q1',**o);r=dispatch.execute(s,'q1',**o,**approval_records(p))
    assert r['state']=='PARTIAL' and r['independent_replay'] and r['mathematical_claim']['sharp']
    assert with_sample['mathematical_claim']['interval']==r['mathematical_claim']['interval']
    assert r['reading_assessment']['material_completeness']=='COMPLETE'


def test_cli_uses_the_same_pending_review_contract(tmp_path):
    from cfm_id.business_dispatch_cli import main
    s,e,o,_=fixture();intake.save(s,tmp_path/'intake.json')
    for name,value in [('query',o['query_review']),('entry',e),('candidate',o['candidate'])]:
        intake.write_json(tmp_path/(name+'.json'),value)
    code=main(['source-review-plan','--intake',str(tmp_path/'intake.json'),'--query','q1',
        '--query-review',str(tmp_path/'query.json'),'--reader-plan',str(tmp_path/'entry.json'),
        '--candidate',str(tmp_path/'candidate.json'),'--output',str(tmp_path/'worksheet.json')])
    result=intake.read_json(tmp_path/'worksheet.json')
    assert code==0 and result['source_review_worksheet']==source.prepare(e,o['candidate'])
    assert result['source_review_worksheet']['version']==impact.VERSION and result['api_calls']==0
