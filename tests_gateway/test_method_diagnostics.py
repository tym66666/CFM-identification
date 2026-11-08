"""Native evidence projections cannot create permission or mathematical conclusions."""
from copy import deepcopy
import pytest
from cfm_id import business_dispatch as dispatch, method_diagnostics as diagnostic, method_requirements as requirements, project
from cfm_id.network_policy_dispatch import R1B,R2,R2_SCIENCE_DECISIONS
from cfm_id.network_bounded_dispatch import METHOD
from examples.network_dispatch_reference import setup,approval_records
from examples.network_bounded_dispatch_reference import setup as bounded


def by_method(report):return {r['method']:r for r in report['methods']}
def review_options(records):return {k:v for k,v in records.items() if k!='research_protocol_selected'}
def forbidden(*a,**kw):raise AssertionError('diagnostic invoked mathematics')


def test_read_only_entry_uses_native_gates_and_does_not_create_approval(monkeypatch):
    s,e,o,p=setup(design='D1');a=approval_records(p);before=deepcopy((p,a,o))
    from pfn_pipeline import identification_policy_r1b as r1b,identification_policy_r2 as r2
    monkeypatch.setattr(r1b,'identify_verified_fixed_policy',forbidden)
    monkeypatch.setattr(r2,'identify_verified_signature_policy',forbidden)
    for report in (diagnostic.describe(p,**review_options(a)),project.diagnose_methods(s,'q1',**o,**review_options(a))):
        assert not report['backend_called'] and not report['independent_replay'] and not report['grants_execution']
        assert report['mathematical_claim'] is None
        assert all(r['mathematical_applicability']=='NOT_CHECKED' for r in report['methods'])
        assert by_method(report)[R1B]['science_review']['state']=='ACCEPTED'
    assert (p,a,o)==before
    # An explanation is not a review record accepted by the executor.
    refused=dispatch.execute(s,'q1',**o,plan_review=report,native_reviews=a['native_reviews'],research_protocol_selected=True)
    assert not refused['backend_called']


def test_real_alternate_theorem_is_reported_without_new_proof_or_auto_partial():
    s,e,o,p=setup();a=approval_records(p);r=dispatch.execute(s,'q1',**o,**a)
    before=deepcopy((p,a,r));view=diagnostic.describe(p,result=r,**review_options(a));rows=by_method(view)
    assert rows[R1B]['mathematical_applicability']=='NATIVE_NOT_APPLICABLE'
    assert rows[R1B]['reason']['reason_code']=='OFF_SUPPORT_ALTERNATE_THEOREM'
    assert rows[R2]['certificate']['state']=='REPLAY_REPORTED' and rows[R2]['certificate']['conclusion']=='POINT'
    assert rows[METHOD]['planning_state']=='NOT_PLANNED_FOR_CURRENT_INPUT'
    assert not view['is_certificate'] and not view['nonidentification_proved'] and not view['minimum_or_weakest_conditions_claimed']
    assert (p,a,r)==before


def test_unstated_sufficiency_and_two_zero_support_routes_remain_distinct():
    s,e,o,p=setup();o['candidate']['mean_sufficiency'].update(value=None,scope='UNKNOWN',covered_nodes=[],source_ids=[])
    p=dispatch.inspect_methods(s,'q1',**o);v=diagnostic.describe(p);r2=by_method(v)[R2]
    assert r2['planning_state']=='EXCLUDED_BY_NATIVE_INSPECTOR'
    assert r2['mathematical_applicability']=='NOT_CHECKED' and r2['science_review']['state']=='NOT_PREPARED'
    assert r2['reason']['next_action']=='CHECK_R2_DECLARATIONS'
    s,e,o,p=setup(n=7,quota=3);a=approval_records(p);result=dispatch.execute(s,'q1',**o,**a)
    v=diagnostic.describe(p,result=result,**review_options(a))
    assert result['state']=='UNSUPPORTED' and not v['nonidentification_proved']
    assert all(by_method(v)[m]['mathematical_applicability']=='NATIVE_NOT_APPLICABLE' for m in (R1B,R2))


def test_partial_sharp_is_relative_and_missing_or_extra_model_stays_blocked():
    s,e,o,p=bounded(center_bounds=('1/4','3/4'));a=approval_records(p)
    result=dispatch.execute(s,'q1',**o,**a);v=diagnostic.describe(p,result=result,**review_options(a))
    cert=by_method(v)[METHOD]['certificate']
    assert cert['conclusion']=='PARTIAL' and cert['sharp'] and cert['sharp_scope']=='CURRENT_REVIEWED_MODEL'
    assert not cert['verified_here'] and result['mathematical_claim']['interval']==['13/28','15/28']
    for options,expected in ((dict(missing_scope=True),'NEEDS_INPUT'),(dict(extra=True),'ADAPTER_NOT_CONNECTED')):
        s,e,o,p=bounded(**options);v=project.diagnose_methods(s,'q1',**o)
        assert v['source_plan_state']==expected and not v['backend_called']
        assert all(r['execution']=='NOT_RUN' and r['certificate']['state']=='NOT_REPORTED' for r in v['methods'])
        if options.get('extra'):assert p['facts']['additional_restrictions']


@pytest.mark.parametrize('decision',['PENDING','REJECTED','STALE','WRONG_AUTHORITY'])
def test_all_branch_preflight_unchanged_and_stale_records_never_shown_accepted(decision):
    s,e,o,p=setup(design='D1');a=approval_records(p);record=a['native_reviews'][R2]['science_review']
    if decision in ('PENDING','REJECTED'):
        decisions=dict(record.decisions);decisions[R2_SCIENCE_DECISIONS[0]]=decision;update={'decisions':decisions}
    else:update={'binding_sha256':'f'*64} if decision=='STALE' else {'authority':'EXTERNAL_RESEARCH_REVIEW'}
    a['native_reviews'][R2]['science_review']=record.model_copy(update=update)
    before=dispatch.execute(s,'q1',**o,**a);v=diagnostic.describe(p,result=before,**review_options(a))
    after=dispatch.execute(s,'q1',**o,**a)
    assert before==after and not after['backend_called']
    rows=by_method(v)
    assert rows[R1B]['science_review']['state']=='ACCEPTED' and rows[R1B]['execution']=='NOT_RUN'
    assert rows[R2]['science_review']['state']==(decision if decision in ('PENDING','REJECTED') else 'INVALID')
    assert rows[R2]['outstanding_review_items'] and not v['branches_independently_authorized']


@pytest.mark.parametrize('change',['plan','query','target','method','replay','missing_evidence','missing_answer','revoked_review','state'])
def test_unbound_or_incoherent_success_cannot_be_presented_as_native_evidence(change):
    s,e,o,p=setup(design='D1',sufficiency=False);a=approval_records(p);r=dispatch.execute(s,'q1',**o,**a)
    bad=deepcopy(r)
    if change=='plan':bad['plan_sha256']='a'*64
    if change=='query':bad['query_id']='q2'
    if change=='target':bad['answers'][0]['mathematical_claim']['target']['context']='other study'
    if change=='method':bad['answers'][0]['method']='UNREGISTERED'
    if change=='replay':bad['answers'][0]['independent_replay']=False
    if change=='missing_evidence':bad['answers'][0]['native_evidence']=None
    if change=='missing_answer':bad['answers']=[]
    if change=='state':bad['state']='CHECK_BLOCKED'
    if change=='revoked_review':
        q=a['native_reviews'][R1B]['science_review'];d=dict(q.decisions);d['consistency']='REJECTED'
        a['native_reviews'][R1B]['science_review']=q.model_copy(update={'decisions':d})
    with pytest.raises(ValueError,match='DIAGNOSTIC_'):diagnostic.describe(p,result=bad,**review_options(a))


def test_condition_lists_come_from_worksheets_not_labels_and_unknown_reason_is_not_guessed():
    s,e,o,p=setup(design='D1');v=diagnostic.describe(p);rows=by_method(v)
    for row in p['methods']:
        assert [r['key'] for r in rows[row['method']]['science_review']['conditions']]==list(row['science_worksheet']['decisions'])
    assert {r['method'] for r in requirements.catalog()}=={R1B,R2,METHOD}
    assert requirements.reason('FUTURE_REASON')['next_action']=='INSPECT_NATIVE_DIAGNOSTIC'
    upstream=project.diagnose_methods(s,'q1',**dict(o,request_sha256='0'*64))
    assert not upstream['methods'] and upstream['source_plan_state']=='CHECK_BLOCKED'
    assert upstream['diagnostics_scope']=='UPSTREAM_OR_FAMILY_NOT_CONNECTED'
