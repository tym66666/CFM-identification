from cfm_id_bridge.scientific_binding import sha
from cfm_id.capability_registry import registrations
from cfm_id.research_route_catalog import resolve,inventory
from cfm_id.iv_route_contract import (IVProblem,IVCell,IVReadingReview,IVScienceReview,IVReview,
    VERSION,READING_DECISIONS,SCIENCE_DECISIONS,digest)
from cfm_id.iv_research import prepare,submit

OBS={(0,0,0):0.0,(0,0,1):1.0,(0,1,0):0.0,(0,1,1):0.0,
     (1,0,0):0.0,(1,0,1):0.75,(1,1,0):0.125,(1,1,1):0.125}

def problem():
    return IVProblem(version=VERSION,target='LATE',cells=[IVCell(z=z,d=d,y=y,probability=str(v)) for (z,d,y),v in OBS.items()],
        monotonicity=True,instrument='offer',treatment='participation',outcome='binary outcome',
        population='All eligible participants in the study population',context='Study period 2026',
        source_ids=['table-1'],source_sha256='a'*64,
        assumptions=['instrument_independence','exclusion_restriction','monotonicity_direction','consistency_and_binary_outcome','no_interference','positive_instrument_support'])

def review(p):
    h=digest(p)
    return IVReview(version=VERSION,problem_sha256=h,
        reading_review=IVReadingReview(authority='SYNTHETIC_TEST',reviewer='Reader 1',evidence='Checked variable coding and all eight conditional probability cells against source table.',problem_sha256=h,decisions={k:'ACCEPTED' for k in READING_DECISIONS}),
        science_review=IVScienceReview(authority='SYNTHETIC_TEST',reviewer='Reviewer 1',evidence='Separately reviewed instrument independence, exclusion, monotonicity and consistency declarations.',problem_sha256=h,decisions={k:'ACCEPTED' for k in SCIENCE_DECISIONS}))

def test_iv_route_is_registered_and_inventory_visible():
    reg=resolve('BINARY_IV_LATE_ATE')
    assert reg.problem_type is IVProblem
    assert reg.business_entry is None
    assert any(r.capability.route_id=='BINARY_IV_LATE_ATE' for r in registrations())
    assert all(row['route_id']!='IV' for row in inventory()['planned_routes'])

def test_prepare_requires_review_and_submit_replays_negative_late():
    p=problem()
    assert prepare(p)['state']=='REVIEW_REQUIRED'
    out=submit(p,review=review(p),research_protocol_selected=True)
    assert out['state']=='POINT' and out['claim']['value']==-0.5
    assert out['certificate_replayed'] is True
    assert out['production_admission'] is False and out['estimation_handoff_allowed'] is False

def test_stale_or_pending_review_never_runs_backend():
    p=problem();r=review(p).model_copy(update={'problem_sha256':'b'*64})
    out=submit(p,review=r,research_protocol_selected=True)
    assert out['state']=='CHECK_BLOCKED' and out['backend_called'] is False


def test_source_bound_business_reader_keeps_reading_and_science_reviews_separate():
    from cfm_id_llm.iv_reading import inspect_candidate,submit_reviewed
    from cfm_id_bridge.scientific_binding import sha
    p=problem()
    catalog={'table-1':{'uri':'https://example.org/study/table-1','sha256':'a'*64,'locator':'Table 1, rows 1-8'}}
    p=p.model_copy(update={'source_sha256':sha(catalog)})
    candidate={'problem':p.model_dump(mode='json'),'source_catalog':catalog}
    inspected=inspect_candidate(candidate)
    assert inspected['state']=='REVIEW_REQUIRED'
    assert inspected['reading_worksheet']['is_approval'] is False
    assert inspected['science_worksheet']['is_approval'] is False
    r=review(p)
    result=submit_reviewed(candidate,reading_review=r.reading_review.model_dump(),
        science_review=r.science_review.model_dump(),research_protocol_selected=True)
    assert result['state']=='POINT'
    assert result['reading_review_recorded'] and result['science_review_recorded']
    assert result['reading_approval_is_not_scientific_proof'] is True

def test_ate_route_uses_its_own_target_and_review_scope():
    p0=problem()
    p=IVProblem(version=VERSION,target='ATE',cells=p0.cells,monotonicity=True,
        instrument=p0.instrument,treatment=p0.treatment,outcome=p0.outcome,
        population=p0.population,context=p0.context,source_ids=p0.source_ids,
        source_sha256=p0.source_sha256,
        assumptions=list(SCIENCE_DECISIONS))
    h=digest(p)
    from cfm_id.iv_route_contract import IVReadingReview,IVScienceReview
    r=IVReview(version=VERSION,problem_sha256=h,
        reading_review=IVReadingReview(authority='SYNTHETIC_TEST',reviewer='Reader 1',evidence='Checked ATE target, treatment/outcome coding, source and full conditional table.',problem_sha256=h,decisions={k:'ACCEPTED' for k in READING_DECISIONS}),
        science_review=IVScienceReview(authority='SYNTHETIC_TEST',reviewer='Reviewer 1',evidence='Reviewed instrument independence, exclusion and consistency declarations for ATE.',problem_sha256=h,decisions={k:'ACCEPTED' for k in SCIENCE_DECISIONS}))
    out=submit(p,review=r,research_protocol_selected=True)
    assert out['state'] in ('POINT','PARTIAL')
    assert out['certificate_replayed'] is True
    assert out['certificate']['target']['kind']=='ATE'


def test_iv_is_registered_for_explicit_research_not_automatic_business():
    from cfm_id import capability_registry as registry
    data = registry.inventory()
    route = next(r for r in data['formal_research_adapters'] if r['route_id'] == 'BINARY_IV_LATE_ATE')
    assert route['business_entry'] is None
    assert registry.reader_for('BINARY_IV_CANDIDATE', 'ATE') is None
    assert registry.reader_for('BINARY_IV_CANDIDATE', 'LATE') is None
    assert not any(b.reader_id == 'BINARY_IV_FACTS' for b in registry.business_bindings())
