"""File wiring across EVERY registered web method; synthetic contracts, not LLM scores.

These intentionally reuse the native reference fixtures. Real document reading
is evaluated separately; a fixture approval is never a model accuracy claim.
"""
from copy import deepcopy
import csv
import json
import pytest
from jsonschema import Draft202012Validator
from demo.backend.engine import Engine, Run
from demo.backend import capabilities
from cfm_id import business_dispatch as dispatch, fact_source_review
from cfm_id_llm import network_file_binding
from examples.network_dispatch_reference import approval_records
from tests_gateway.test_fact_source_review import record
from demo.tests.test_web_capabilities import NAMES, setup
import base64
DECL = dict(kind='UNDIRECTED', completeness='COMPLETE', description='试点前登记的相互调货关系，本周固定。')


def tables(tmp_path, nodes, edges):
    a=tmp_path/'nodes.csv'; b=tmp_path/'edges.csv'
    for path, rows in ((a,[['node_id'],*[[n] for n in nodes]]),(b,[['source','target'],*edges])):
        with path.open('w',encoding='utf8',newline='') as f: csv.writer(f).writerows(rows)
    return a,b


def upload(path, role):
    return dict(name=path.name,role=role,content=base64.b64encode(path.read_bytes()).decode())

CASES = (*NAMES, 'arm', 'mixture', 'observed', 'stratum', 'nodewise')


def sample_record(candidate, name):
    """Reference finite observation row, never an exact population fixture."""
    sample=dict(operator='FINITE_SAMPLE',availability='FINITE_SAMPLE',
        outcome_nodes=[n for i,n in enumerate(candidate['study']['nodes']) if i!=1],
        source_ids=candidate['study']['source_ids'])
    if name in ('observed','stratum','nodewise'):
        sample['description']='Finite observation records only, not a population law.'
    elif name in ('r3','r3_signature'):
        sample['assignment_masses']=[]
        for k in ('complete_positive_assignment_support','means_for_all_positive_assignments','same_study_and_conditioning'):
            sample[k]=dict(value=None,source_ids=[])
    else:
        for key in ('arm_cells','assignment_cells','signature_cells'):
            if key in candidate['information'][0]:sample[key]=[]
    return sample


def test_fixture_inventory_cannot_silently_omit_a_new_registered_method():
    represented = {m['method'] for name in CASES for m in setup(name)[2]['methods']}
    assert represented == set(capabilities.METHODS)
    assert {b['reader'] for b in capabilities.inventory()} == {
        dispatch.prepare_reader(s, 'q1', query_review=o['query_review'])['reader_id']
        for s, o, _ in (setup(name) for name in CASES)}


@pytest.mark.parametrize('name',('partial_mean','partial_contrast','mean_order'))
def test_sample_metadata_cannot_change_bounds_or_release_missing_a4_and_review(name):
    s,o,p=setup(name)
    baseline=dispatch.execute(s,'q1',**o,**approval_records(p))
    entry=dispatch.prepare_reader(s,'q1',query_review=o['query_review'])
    sample=sample_record(o['candidate'],name)
    o['candidate']['information'].insert(0,sample)
    o['source_review']=record(fact_source_review.prepare(entry,o['candidate']))
    p=dispatch.inspect_methods(s,'q1',**o)
    result=dispatch.execute(s,'q1',**o,**approval_records(p))
    assert result['mathematical_claim']['interval']==baseline['mathematical_claim']['interval']
    assert result['mathematical_claim']['sharp']==baseline['mathematical_claim']['sharp']
    assert result['independent_replay']
    # A finite row remains part of the original review, even though not in A4.
    rejected=deepcopy(o)
    rejected['source_review']['decisions']['/information/0']['source_coverage']='REJECTED'
    assert not dispatch.execute(s,'q1',**rejected,research_protocol_selected=True)['backend_called']
    variants=[]
    only_sample=deepcopy(o['candidate']);only_sample['information']=[sample];variants.append(only_sample)
    unknown=deepcopy(o['candidate']);unknown['information'][0]['availability']='UNKNOWN';variants.append(unknown)
    missing_closure=deepcopy(o['candidate']);missing_closure['bounded_model']['listed_means_are_complete_information']=dict(value=None,source_ids=[]);variants.append(missing_closure)
    wrong_pair=deepcopy(o['candidate']);wrong_pair['information'][0]['availability']='EXACT_POPULATION_VALUE';variants.append(wrong_pair)
    for candidate in variants:
        changed=dict(o,candidate=candidate)
        try:changed['source_review']=record(fact_source_review.prepare(entry,candidate))
        except ValueError:changed.pop('source_review',None)
        blocked=dispatch.execute(s,'q1',**changed,research_protocol_selected=True)
        assert not blocked['backend_called'] and not blocked['independent_replay']


@pytest.mark.parametrize('name', CASES)
def test_file_intake_reading_native_execution_and_refusal(tmp_path, monkeypatch, name):
    s, o, old_plan = setup(name)
    entry = dispatch.prepare_reader(s, 'q1', query_review=o['query_review'])
    native_entry = deepcopy(entry)
    original = deepcopy(o['candidate'])
    if name in ('observed','stratum','nodewise'):
        # Historical fixture contains compatibility-only null axes. The current
        # model request asks only for axes owned by its information operator.
        for info in original['information']:
            info['covered_cells']=[{k:v for k,v in c.items() if v is not None} for c in info['covered_cells']]
            for profile in info.get('profiles',[]):
                if profile.get('mixture_components') == []:del profile['mixture_components']
    dictionary = tmp_path/'definitions.csv'
    dictionary.write_text('字段,说明\ntool,yes为启用；no为未启用\nscore,本期结果；空白为未回访\n', 'utf8')
    SurfaceRun = Run
    engine = Engine(tmp_path/'runs', max_api_calls=0)
    run = SurfaceRun(owner='fixture', synthetic=True)
    payload = dict(question='核对当前研究方案中的问题和字段说明。', files=[upload(dictionary, 'data_dictionary')])
    is_network = entry['reader_id'].startswith('NETWORK_')
    if is_network:
        # Uploads must also coexist with A4 in the actual fact contract. Testing
        # only file transport misses adapters that reject accompanying samples.
        original['information'].insert(0,sample_record(original,name))
        study = original['study']
        a, b = tables(tmp_path, study['nodes'], study['edges'])
        data = tmp_path/'records.csv'
        with data.open('w', encoding='utf8', newline='') as f:
            w = csv.writer(f); w.writerow(['id','tool','score','x'])
            for i, node in reversed(list(enumerate(study['nodes']))):
                w.writerow([node, 'yes' if i % 2 else 'no', '' if i == 1 else 1, i])
        payload.update(network=DECL, table_mapping=dict(id_column='id', treatment_column='tool',
            outcome_column='score', feature_columns=['x'], treated_value='yes', untreated_value='no',
            treatment=study['treatment'], outcome=study['outcome'], context=study['context'],
            outcome_kind=study['outcome_kind'], observation_scheme='仅本表非空结果行；不等于总体信息。'))
        payload['files'] += [upload(a,'network_nodes'),upload(b,'network_edges'),upload(data,'table_data')]
    engine._start(run, payload, preview_only=True)
    assert engine.calls == 0 and run.attachment_report['receipt']['ready']
    assert 'yes为启用' in '\n'.join(x['text'] for x in run.case['sources'])
    wire_answer = deepcopy(original)
    if is_network:
        assert run.artifacts['table_import_manifest']['node_order'] == original['study']['nodes']
        assert run.artifacts['factual_data_inventory']['observed_outcome_count'] == len(original['study']['nodes'])-1
        # Inject an explicit reference-only file source into the FIXTURE request.
        # This is a wire compatibility check, not a new semantic evidence review.
        body, end = json.JSONDecoder().raw_decode(entry['request']['user'])
        sid = original['study']['source_ids'][-1]
        body['source_catalog'][sid]['text'] = run.network.source()['text']
        entry = deepcopy(entry)
        entry['request']['user'] = json.dumps(body, ensure_ascii=False)+entry['request']['user'][end:]
        wire_answer['study'].update(nodes={'from_network':run.network.token}, edges={'from_network':run.network.token})
    else:
        # A unit relationship file must never be compiled into a variable DAG.
        assert run.network is None and run.data is None
        assert network_file_binding.prepare(entry, None) == (entry, None)
    calls=[]
    def reference_call(r, request, stage):
        calls.append(stage)
        body = json.JSONDecoder().raw_decode(request['request']['user'])[0]
        Draft202012Validator(body['output_schema']).validate(wire_answer)
        return deepcopy(wire_answer)
    monkeypatch.setattr(engine, 'call', reference_call)
    expanded=engine._read_facts(run, entry)
    assert calls == ['facts'] and expanded == original
    if is_network:
        assert run.artifacts['network_file_binding']['arrays_match']
        assert run.artifacts['network_file_binding']['scientific_approval'] is False
    o['candidate']=expanded
    if is_network:
        sheet=fact_source_review.prepare(native_entry, expanded)
        o['source_review']=record(sheet)
    p=dispatch.inspect_methods(s,'q1',**o)
    assert p['state']=='REVIEW_REQUIRED',p
    assert [m['method'] for m in p['methods']] == [m['method'] for m in old_plan['methods']]
    from examples.business_dispatch_reference import approvals as dag_approvals
    reviews=approval_records(p) if is_network else dag_approvals(p)
    result=dispatch.execute(s,'q1',**o,**reviews)
    assert result['state'] == ('PARTIAL' if name in ('partial_mean','partial_contrast','mean_order') else 'POINT')
    assert result['independent_replay'] is True
    if is_network:
        assert o['candidate']['information'][0]['availability']=='FINITE_SAMPLE'
        assert all(0 not in (m['source_indices'] if 'source_indices' in m else [m['source_index']]) for m in p['methods'])
    # Successful parsing cannot supply a scientific approval.
    pending=dispatch.execute(s,'q1',**o,research_protocol_selected=True)
    assert not pending['backend_called'] and not pending['independent_replay']
    for pair in reviews['native_reviews'].values():
        key=next(iter(pair['science_review'].decisions))
        pair['science_review']=pair['science_review'].model_copy(update={
            'decisions':{**pair['science_review'].decisions,key:'REJECTED'}})
    rejected=dispatch.execute(s,'q1',**o,**reviews)
    assert not rejected['backend_called'] and not rejected['independent_replay']
