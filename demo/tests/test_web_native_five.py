"""Native routes, negative admission and web presentation; no LLM score."""
from copy import deepcopy
import pytest
from demo.backend.runtime import identification_modules
identification_modules()
from examples.network_extended_reference import fixture,execute
from examples.business_dispatch_reference import approve
from cfm_id import network_extended_dispatch as d
from cfm_id_llm import network_extended_reading as reading
from demo.backend.engine import Engine,Run
from demo.backend import capabilities

NAMES=('arm','mixture','observed','stratum','nodewise')

@pytest.mark.parametrize('name',NAMES)
def test_full_registered_dispatch_and_native_json_reviews(name,tmp_path):
    from test_web_capabilities import prepare,approve as browser_approve
    e=Engine(tmp_path);r=prepare(e,name)
    e._review(r,browser_approve(r))
    assert r.result['state']=='POINT' and r.result['independent_replay'],r.result

def plan(name):
    entry,raw=fixture(name);p=d.inspect_methods(entry,raw)
    assert p['state']=='REVIEW_REQUIRED',p
    return p

@pytest.mark.parametrize('name',NAMES)
def test_native_execute_replay_and_compact_web_summary(name,tmp_path):
    p=plan(name);result=execute(p)
    assert result['state']=='POINT' and result['independent_replay'],result
    run=Run(owner='synthetic',synthetic=True,plan=p,review_kind='science')
    sheets={'plan':p['plan_worksheet']}
    for row in p['methods']:
        sheets[row['method']+'.reading_review']=row['reading_worksheet']
        sheets[row['method']+'.science_review']=row['science_worksheet']
    Engine(tmp_path)._set_review(run,'science',sheets)
    summary=capabilities.science_summary(run)
    assert summary['compact_confirmation_available'],summary
    assert len(summary['cards'])==3 and not summary['is_approval']

@pytest.mark.parametrize('name',NAMES)
@pytest.mark.parametrize('state',('PENDING','REJECTED','STALE'))
def test_no_admission_without_all_bound_reviews(name,state):
    p=plan(name);row=p['methods'][0];method=row['method']
    records={method:{'reading_review':approve(row['reading_worksheet']).model_dump(),'science_review':approve(row['science_worksheet']).model_dump()}}
    if state=='STALE':records[method]['science_review']['binding_sha256']='0'*64
    else:records[method]['science_review']['decisions'][next(iter(row['science_worksheet']['decisions']))]=state
    r=d._execute_plan(p,plan_review=approve(p['plan_worksheet']),native_reviews=records,research_protocol_selected=True)
    assert not r['backend_called'] and not r['independent_replay'] and r['state']!='POINT'

@pytest.mark.parametrize('name',NAMES)
def test_sample_only_is_not_population_information(name):
    e,c=fixture(name)
    if name in ('observed','stratum','nodewise'):
        c['information']=[dict(operator='FINITE_SAMPLE',availability='FINITE_SAMPLE',source_ids=c['information'][0]['source_ids'],outcome_nodes=c['study']['nodes'],description='有限记录，未提供总体分布')]
    else:
        for source in c['information']:source.update(operator='FINITE_SAMPLE',availability='FINITE_SAMPLE')
    result=d.inspect_methods(e,c)
    assert result['state']=='NEEDS_INPUT' and not result['backend_called'],result

@pytest.mark.parametrize('name',NAMES)
@pytest.mark.parametrize('value', (None,False))
def test_missing_and_declined_science_are_distinct(name,value):
    e,c=fixture(name)
    key='full_vector_randomization' if name in ('arm','mixture') else 'full_vector_conditional_exchangeability' if name=='observed' else 'potential_outcome_exposure_sufficiency'
    c['assumptions'][key]['value']=value
    result=d.inspect_methods(e,c)
    assert result['state']==('NEEDS_INPUT' if value is None else 'ADAPTER_NOT_CONNECTED'),result
    assert not result['backend_called']

def test_policy_probabilities_and_target_are_not_renormalized_or_collapsed():
    e,c=fixture('mixture');c['target']['components'][0]['weight']='1/2'
    assert d.inspect_methods(e,c)['state']=='CHECK_BLOCKED'
    e,c=fixture('mixture');del c['target']['components'][0]['assignment']['丙站']
    assert d.inspect_methods(e,c)['state']=='NEEDS_INPUT'

@pytest.mark.parametrize('name',('observed','stratum','nodewise'))
def test_zero_support_never_falls_back_or_claims_nonidentification(name):
    e,c=fixture(name);s=c['information'][0]
    if name=='observed':s['probabilities']['甲站']='0'
    elif name=='stratum':s['strata'][0]['probabilities']['甲站']='0'
    else:
        for x in s['profiles']:x['probabilities']['乙站']='0'
    p=d.inspect_methods(e,c);r=execute(p)
    assert r['state']!='POINT' and not r['independent_replay'],r
    assert not r.get('nonidentification_proved')

def test_covariate_cells_and_licenses_not_interchanged():
    e,c=fixture('stratum');c['target']['averaging']='OWN_AND_NEIGHBOR_BINARY_FEATURE'
    p=d.inspect_methods(e,c)
    assert p['state']=='ADAPTER_NOT_CONNECTED' and not p['backend_called']
    e,c=fixture('nodewise');c['information'][0]['covered_cells'][0]['stratum']='旺季'
    assert d.inspect_methods(e,c)['state']=='CHECK_BLOCKED'

def test_missing_source_unknown_context_and_returned_native_input_are_checked(monkeypatch):
    e,c=fixture('arm');c['target']['first']['source_ids']=[]
    assert d.inspect_methods(e,c)['state']=='NEEDS_INPUT'
    e,c=fixture('observed');c['conditioning']['kind']='UNKNOWN'
    assert d.inspect_methods(e,c)['state']=='NEEDS_INPUT'
    from pfn_pipeline import identification_business as core
    native=core.identify_network_business_query
    def wrong(q):
        r=native(q)
        if r.status=='POINT':return type(r)(r.query_type,r.status,'WRONG_ROUTE',None,r.result)
        return r
    monkeypatch.setattr(core,'identify_network_business_query',wrong)
    assert execute(plan('observed'))['state']=='CHECK_BLOCKED'

def test_alternate_existing_population_representations():
    from itertools import product
    for name,kind in [('observed','FINITE_ASSIGNMENT_LAW'),('observed','MIXTURE_ARM_LAW'),('nodewise','NODEWISE_MIXTURE_ARM_LAW')]:
        e,c=fixture(name);s=c['information'][0];ids=s['source_ids'];nodes=c['study']['nodes']
        component=dict(source_ids=ids,weight='1',probabilities={n:'1/2' for n in nodes})
        s['operator']=kind
        if kind=='FINITE_ASSIGNMENT_LAW':
            s.pop('probabilities');s.pop('covered_cells')
            s.update(assignment_masses=[dict(source_ids=ids,assignment=dict(zip(nodes,z)),probability='1/8') for z in product((0,1),repeat=3)])
        elif kind=='MIXTURE_ARM_LAW':s.pop('probabilities');s.update(mixture_components=[component])
        else:
            for p in s['profiles']:p.update(probabilities=None,mixture_components=[component])
        p=d.inspect_methods(e,c);assert p['state']=='REVIEW_REQUIRED',p
        r=execute(p);assert r['state']=='POINT' and r['independent_replay'],r


def test_operator_specific_wire_forbids_mixed_population_models():
    e,c=fixture('observed')
    c['information'][0]['profiles']=[]
    assert d.inspect_methods(e,c)['state']=='CHECK_BLOCKED'


def test_design_schema_and_runtime_reject_the_same_inactive_parameters():
    import jsonschema
    from cfm_id_llm.network_policy_reading import Assignment
    from cfm_id_llm.network_design_reading import DESIGN_FIELDS,validate_components
    schema=Assignment.model_json_schema()
    for kind,active in DESIGN_FIELDS.items():
        value=Assignment(kind=kind,source_ids=['s'],probabilities=None,fixed_count=None).model_dump()
        jsonschema.validate(value,schema)  # Missing active values remain unknown.
        forbidden='probabilities' if 'probabilities' not in active else 'fixed_count'
        value[forbidden]={'甲站':'1/2'} if forbidden=='probabilities' else 1
        with pytest.raises(jsonschema.ValidationError):jsonschema.validate(value,schema)
        with pytest.raises(ValueError,match='CONFLICTING_DESIGN_FIELDS'):
            validate_components(Assignment.model_validate(value),None,['甲站'],[])
    e,c=fixture('nodewise')
    c['information'][0]['operator']='MIXTURE_ARM_LAW'
    assert d.inspect_methods(e,c)['state']=='CHECK_BLOCKED'


@pytest.mark.parametrize('name',('observed','stratum','nodewise'))
def test_thin_population_wire_preserves_canonical_values_and_native_replay(name):
    e,old=fixture(name);c=deepcopy(old);s=c['information'][0]
    for cell in s.get('covered_cells',[]):
        for key in ('stratum','own_feature','neighbor_feature_count'):
            if cell.get(key) is None:cell.pop(key,None)
    for profile in s.get('profiles',[]):
        if profile.get('probabilities') is None:profile.pop('probabilities',None)
        if not profile.get('mixture_components'):profile.pop('mixture_components',None)
    reading.ObservationalReadingWire.model_validate(c)
    assert reading.ObservationalEffectsReading.model_validate(c)==reading.ObservationalEffectsReading.model_validate(old)
    p=d.inspect_methods(e,c);result=execute(p)
    assert result['state']=='POINT' and result['independent_replay']
    if name=='nodewise':
        s['profiles'][0]['mixture_components']=[dict(weight='1',probabilities=s['profiles'][0]['probabilities'],source_ids=s['source_ids'])]
        with pytest.raises(ValueError):reading.ObservationalReadingWire.model_validate(c)
        assert d.inspect_methods(e,c)['state']=='CHECK_BLOCKED'


@pytest.mark.parametrize('name',('arm','mixture'))
def test_fixed_background_requires_conditional_science_review(name):
    from cfm_id.network_contrast_context import SCIENCE_REQUIREMENTS
    e,c=fixture(name)
    e['reviewed_target_context']={
        'conditioning_context':dict(state='STATED',value='普通需求背景',refs=[]),
        'standardization_distribution':dict(state='UNKNOWN',value=None,refs=[])}
    p=d.inspect_methods(e,c)
    assert p['state']=='REVIEW_REQUIRED',p
    sheet=p['methods'][0]['science_worksheet']
    assert set(SCIENCE_REQUIREMENTS)<=set(sheet['decisions'])
    row=p['methods'][0]
    science=approve(sheet).model_dump()
    science['decisions']['assignment_law_and_randomization_given_fixed_background']='PENDING'
    reviews={row['method']:dict(reading_review=approve(row['reading_worksheet']).model_dump(),science_review=science)}
    result=d._execute_plan(p,plan_review=approve(p['plan_worksheet']),native_reviews=reviews,research_protocol_selected=True)
    assert result['state']!='POINT' and not result['backend_called']
