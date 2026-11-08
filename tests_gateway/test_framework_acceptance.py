"""Acceptance must distinguish actual pass evidence from absent/partial evidence."""
from copy import deepcopy
from types import SimpleNamespace

import pytest

from evaluation import framework_acceptance as acceptance


def record(recorder, node, when, outcome='passed', *, subtest=False, xfail=False):
    report = SimpleNamespace(nodeid=node, when=when, outcome=outcome)
    if subtest:
        report.context = ('subcase',)
    if xfail:
        report.wasxfail = 'expected failure marker'
    recorder.pytest_runtest_logreport(report)


def miniature():
    data = dict(lanes=['LANE'], common_obligations=[dict(id='C', title='Lifecycle', test='case::test')],
                specific_obligations=[])
    node = 'case::test[LANE]'
    recorder = acceptance.Recorder()
    recorder.collected = [node]
    for phase in ('setup', 'call', 'teardown'):
        record(recorder, node, phase)
    return data, recorder, node


def test_missing_or_renamed_required_node_fails_even_with_exit_zero():
    data, recorder, node = miniature()
    assert acceptance.summarize(data, recorder, 0)['passed']
    data['common_obligations'][0]['test'] = 'case::renamed'
    report = acceptance.summarize(data, recorder, 0)
    assert report['passed'] is False
    assert report['missing_required_nodes'] == ['case::renamed[LANE]']
    assert report['lanes']['LANE']['passed'] is False


def test_skip_subtest_failure_and_incomplete_run_never_pass():
    for phase, outcome, subtest, xfail in [('call', 'skipped', False, False),
                                         ('call', 'failed', True, False),
                                         ('call', 'skipped', True, False),
                                         ('teardown', 'failed', False, False),
                                         ('call', 'passed', False, True)]:
        data, recorder, node = miniature()
        record(recorder, node, phase, outcome, subtest=subtest, xfail=xfail)
        assert acceptance.summarize(data, recorder, 0)['passed'] is False
    data, recorder, node = miniature()
    recorder.reports[node] = recorder.reports[node][:-1]  # Interrupted before teardown.
    assert acceptance.summarize(data, recorder, 0)['tests'][node] == 'incomplete'
    assert acceptance.summarize(data, recorder, 0)['passed'] is False
    recorder.collected = []
    assert acceptance.summarize(data, recorder, 0)['passed'] is False


def test_lane_drift_is_rejected():
    data = acceptance.load_manifest()
    changed = deepcopy(data)
    changed['lanes'] = changed['lanes'][:-1]
    with pytest.raises(ValueError, match='SESSION_LANE_COVERAGE_DRIFT'):
        acceptance.validate_manifest(changed, data['lanes'], data['comparison_lanes'])
    changed = deepcopy(data)
    changed['comparison_lanes'] = changed['comparison_lanes'][:-1]
    with pytest.raises(ValueError, match='COMPARISON_LANE_COVERAGE_DRIFT'):
        acceptance.validate_manifest(changed, data['lanes'], data['comparison_lanes'])


def test_existing_output_is_not_overwritten(tmp_path):
    sentinel = tmp_path / 'SUMMARY.json'
    sentinel.write_text('prior evidence', encoding='utf8')
    with pytest.raises(SystemExit) as error:
        acceptance.main(['--output', str(tmp_path)])
    assert error.value.code == 2
    assert sentinel.read_text(encoding='utf8') == 'prior evidence'
    assert list(tmp_path.iterdir()) == [sentinel]


def test_environment_filter_cannot_silently_shorten_fixed_acceptance(tmp_path, monkeypatch):
    import os
    monkeypatch.setenv('PYTEST_ADDOPTS', '-k omit_framework_checks')
    def interrupted_run(args, plugins):
        assert os.environ['PYTEST_ADDOPTS'] == ''
        assert '-k' not in args
        assert args[:len(acceptance.load_manifest()['test_files'])] == acceptance.load_manifest()['test_files']
        return 5  # No reports: even an empty run must not pass.
    monkeypatch.setattr(pytest, 'main', interrupted_run)
    folder = tmp_path / 'failed_run'
    assert acceptance.main(['--output', str(folder)]) == 1
    assert os.environ['PYTEST_ADDOPTS'] == '-k omit_framework_checks'
    import json
    report = json.loads((folder / 'SUMMARY.json').read_text(encoding='utf8'))
    assert report['passed'] is False and report['missing_required_nodes']


def test_selectors_use_exact_boundaries_and_overlap_runs_once():
    match=acceptance.selection_matches
    assert match('a.py::test_x[p]','a.py::test_x')
    assert not match('a.py::test_xy[p]','a.py::test_x')
    assert not match('aa.py::test_x[p]','a.py')
    data=acceptance.load_manifest();config=acceptance.load_suites(data)
    config['suites']['chain']['selectors'].append(config['suites']['quick']['selectors'][0])
    plan=acceptance.plan_suite(data,'chain',config)
    args=plan['test_args']
    assert len(args)==len(set(args))
    assert not any(a!=b and match(a,b) for a in args for b in args)


def test_every_file_has_one_responsibility_and_unknown_files_fail():
    data=acceptance.load_manifest();config=acceptance.load_suites(data)
    for mutation in ('missing','duplicate','unknown'):
        bad=deepcopy(config);files=bad['responsibilities'][0]['files']
        if mutation=='missing':files.pop()
        elif mutation=='duplicate':files.append(files[0])
        else:files.append('tests_gateway/test_unregistered.py')
        with pytest.raises(ValueError,match='EXACT_TEST_RESPONSIBILITY_REQUIRED'):
            acceptance.validate_suites(bad,data)


def test_unknown_empty_or_prefix_only_suite_selection_is_rejected():
    data=acceptance.load_manifest();config=acceptance.load_suites(data)
    for selectors in ([],['tests_gateway/test_framework_acceptance.py::test_missing'],['tests_gateway/test_missing.py']):
        bad=deepcopy(config);bad['suites']['quick']['selectors']=selectors
        with pytest.raises(ValueError,match='UNKNOWN_OR_EMPTY_ACCEPTANCE_SELECTOR'):
            acceptance.validate_suites(bad,data)
    with pytest.raises(ValueError,match='UNKNOWN_ACCEPTANCE_SUITE'):
        acceptance.plan_suite(data,'unknown',config)


def test_suite_scopes_preserve_default_full_and_chain_lifecycle_coverage():
    data=acceptance.load_manifest()
    full=acceptance.plan_suite(data);quick=acceptance.plan_suite(data,'quick');chain=acceptance.plan_suite(data,'chain')
    assert full['test_args']==data['test_files'] and full['obligation_data']==data and full['full_framework_scope']
    assert not quick['full_framework_scope'] and not chain['full_framework_scope']
    nodes=lambda p:{n for r in acceptance.obligations(p['obligation_data']) for n in r['nodes']}
    assert nodes(quick)<nodes(chain)<nodes(full)
    assert all({row['test']+'['+lane+']' for lane in data['lanes']}<=nodes(chain) for row in data['common_obligations'])


def _fake_selected_run(args,plugins,*,extra=None):
    import os
    assert os.environ['PYTEST_ADDOPTS']==''
    plan=acceptance.plan_suite(acceptance.load_manifest(),'quick')
    assert args[:len(plan['test_args'])]==plan['test_args']
    recorder=plugins[0];recorder.collected=sorted({n for row in acceptance.obligations(plan['obligation_data']) for n in row['nodes']})
    if extra=='duplicate':recorder.collected.append(recorder.collected[0])
    elif extra=='unexpected':recorder.collected.append('tests_gateway/test_other.py::test_unrequested')
    for node in recorder.collected:
        for when in ('setup','call','teardown'):record(recorder,node,when)
    return 0


def test_successful_small_suite_never_claims_full_acceptance(tmp_path,monkeypatch):
    import json,os
    monkeypatch.setenv('PYTEST_ADDOPTS','-k hidden_filter')
    monkeypatch.setattr(pytest,'main',_fake_selected_run)
    output=tmp_path/'quick'
    assert acceptance.main(['--suite','quick','--output',str(output)])==0
    report=json.loads((output/'SUMMARY.json').read_text(encoding='utf8'))
    assert report['passed'] and not report['full_framework_passed'] and report['suite']=='quick'
    assert report['unselected_required_nodes'] and not report['missing_required_nodes']
    assert report['lanes']=={} and os.environ['PYTEST_ADDOPTS']=='-k hidden_filter'


@pytest.mark.parametrize('extra',['duplicate','unexpected'])
def test_duplicate_or_out_of_scope_collection_never_passes(tmp_path,monkeypatch,extra):
    import json
    monkeypatch.setattr(pytest,'main',lambda args,plugins:_fake_selected_run(args,plugins,extra=extra))
    output=tmp_path/extra
    assert acceptance.main(['--suite','quick','--output',str(output)])==1
    report=json.loads((output/'SUMMARY.json').read_text(encoding='utf8'))
    assert not report['passed'] and report[extra+'_collected_nodes']
