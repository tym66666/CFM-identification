"""Offline acceptance accounting; this manifest never registers runtime routes."""
from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import argparse
import json
import os
import sys

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = Path(__file__).with_suffix('.json')
SUITES = Path(__file__).with_name('framework_suites.json')


def selection_matches(node, selector):
    """Exact file/function/parameter boundaries; never a substring filter."""
    return node == selector or node.startswith(selector + '::') or node.startswith(selector + '[')


def load_suites(data):
    config = json.loads(SUITES.read_text(encoding='utf8'))
    validate_suites(config, data)
    return config


def validate_suites(config, data):
    if config.get('schema') != 1 or set(config.get('suites', {})) != {'quick', 'chain'}:
        raise ValueError('INVALID_ACCEPTANCE_SUITES')
    groups = config.get('responsibilities', [])
    owners = [path for group in groups for path in group['files']]
    if (not groups or len({g['id'] for g in groups}) != len(groups)
            or any(not g['id'].strip() or not g['title'].strip() for g in groups)
            or len(owners) != len(set(owners)) or set(owners) != set(data['test_files'])):
        raise ValueError('EXACT_TEST_RESPONSIBILITY_REQUIRED')
    required = {n for row in obligations(data) for n in row['nodes']}
    for suite in config['suites'].values():
        selectors = suite['selectors']
        if (not suite['purpose'].strip() or not selectors or len(selectors) != len(set(selectors))
                or any(type(s) is not str or s.split('::')[0] not in data['test_files']
                       or not any(selection_matches(n, s) for n in required) for s in selectors)):
            raise ValueError('UNKNOWN_OR_EMPTY_ACCEPTANCE_SELECTOR')


def plan_suite(data, name='full', config=None):
    if name not in ('quick', 'chain', 'full'):
        raise ValueError('UNKNOWN_ACCEPTANCE_SUITE')
    config = load_suites(data) if config is None else config
    validate_suites(config, data)
    if name == 'full':
        return dict(name=name, purpose='Complete fixed framework and historical compatibility regression',
                    test_args=list(data['test_files']), obligation_data=data,
                    unselected_required_nodes=[], full_framework_scope=True)
    selectors = config['suites']['quick']['selectors'][:]
    if name == 'chain':
        selectors += config['suites']['chain']['selectors']
    # One test is executed once even when a selected file also contains a
    # selected function. Do not pass duplicate/overlapping pytest arguments.
    selectors = list(dict.fromkeys(selectors))
    selectors = [s for s in selectors if not any(s != t and selection_matches(s, t) for t in selectors)]
    rows = []
    omitted = []
    for row in obligations(data):
        chosen = [n for n in row['nodes'] if any(selection_matches(n, s) for s in selectors)]
        omitted.extend(n for n in row['nodes'] if n not in chosen)
        if chosen:
            rows.append(dict(id=row['id'], title=row['title'], nodes=chosen))
    subset = dict(data, lanes=[], common_obligations=[], specific_obligations=rows)
    return dict(name=name, purpose=config['suites'][name]['purpose'], test_args=selectors,
                obligation_data=subset, unselected_required_nodes=sorted(set(omitted)), full_framework_scope=False)


def load_manifest():
    from cfm_id.session_routes import LANES
    from cfm_id.research_versions import SUPPORTED
    data = json.loads(MANIFEST.read_text(encoding='utf8'))
    validate_manifest(data, LANES, SUPPORTED)
    return data


def validate_manifest(data, lanes, comparison_lanes):
    if data['schema'] != 1:
        raise ValueError('UNKNOWN_ACCEPTANCE_SCHEMA')
    if len(data['lanes']) != len(set(data['lanes'])) or set(data['lanes']) != set(lanes):
        raise ValueError('SESSION_LANE_COVERAGE_DRIFT')
    if set(data['comparison_lanes']) != set(comparison_lanes):
        raise ValueError('COMPARISON_LANE_COVERAGE_DRIFT')
    files = data['test_files']
    if not files or len(files) != len(set(files)) or any(
            not p.startswith('tests_gateway/test_') or not p.endswith('.py') or
            Path(p).as_posix() != p or '..' in Path(p).parts for p in files):
        raise ValueError('EXPLICIT_TEST_FILES_REQUIRED')
    rows = obligations(data)
    if not rows or len({r['id'] for r in rows}) != len(rows):
        raise ValueError('UNIQUE_ACCEPTANCE_OBLIGATIONS_REQUIRED')
    for row in rows:
        nodes = row['nodes']
        if not nodes or len(nodes) != len(set(nodes)) or any(
                '::' not in n or n.split('::')[0] not in files for n in nodes):
            raise ValueError('EXPLICIT_ACCEPTANCE_TEST_NODES_REQUIRED')


def obligations(data):
    common = [dict(id=r['id'], title=r['title'],
                   nodes=[r['test'] + '[' + lane + ']' for lane in data['lanes']])
              for r in data['common_obligations']]
    return common + data['specific_obligations']


class Recorder:
    """Record test nodes, including failures/skips inside unittest subtests."""
    def __init__(self):
        self.collected = []
        self.reports = {}
        self.subtests = Counter()

    def pytest_collection_finish(self, session):
        self.collected = [item.nodeid for item in session.items]

    def pytest_runtest_logreport(self, report):
        subtest = hasattr(report, 'context')
        row = dict(when=report.when, outcome=report.outcome, subtest=subtest,
                   expected_failure=bool(getattr(report, 'wasxfail', False)))
        self.reports.setdefault(report.nodeid, []).append(row)
        if subtest:
            self.subtests[report.outcome] += 1

    def statuses(self):
        result = {}
        for node in self.collected:
            reports = self.reports.get(node, [])
            if any(r['outcome'] == 'failed' for r in reports):
                state = 'failed'
            elif any(r['outcome'] == 'skipped' or r['expected_failure'] for r in reports):
                state = 'skipped_or_xfail'
            elif all(any(r['when'] == phase and r['outcome'] == 'passed' and not r['subtest']
                         for r in reports) for phase in ('setup', 'call', 'teardown')):
                state = 'passed'
            else:
                state = 'incomplete'
            result[node] = state
        return result


def summarize(data, recorder, exit_code):
    states = recorder.statuses()
    required = {n for row in obligations(data) for n in row['nodes']}
    missing = sorted(required - set(recorder.collected))
    checks = [dict(id=r['id'], title=r['title'], passed=all(states.get(n) == 'passed' for n in r['nodes']),
                   tests={n: states.get(n, 'not_collected') for n in r['nodes']}) for r in obligations(data)]
    lane_checks = {}
    for lane in data['lanes']:
        nodes = [r['test'] + '[' + lane + ']' for r in data['common_obligations']]
        lane_checks[lane] = dict(passed=all(states.get(n) == 'passed' for n in nodes),
                                tests={n: states.get(n, 'not_collected') for n in nodes})
    return dict(passed=exit_code == 0 and bool(states) and not missing and
                       all(s == 'passed' for s in states.values()),
                pytest_exit_code=int(exit_code), missing_required_nodes=missing,
                counts=dict(Counter(states.values())), subtest_counts=dict(recorder.subtests),
                tests=states, obligations=checks, lanes=lane_checks)


def source_hashes():
    # An explicit source scope; never traverse secrets, outputs, or the parent workspace.
    names = ('cfm_id', 'cfm_id_bridge', 'cfm_id_llm', 'pfn_pipeline', 'evaluation',
             'examples', 'tests_gateway', 'scripts')
    paths = {p for name in names for p in (ROOT / name).rglob('*.py') if '__pycache__' not in p.parts}
    paths.update((MANIFEST, SUITES, ROOT / 'pyproject.toml',
                  ROOT / 'tests_gateway/runtime_dependency_baseline.json'))
    return {p.relative_to(ROOT).as_posix(): sha256(p.read_bytes()).hexdigest() for p in sorted(paths)}


def write_new(path, data):
    with path.open('x', encoding='utf8') as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2)
        stream.write('\n')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--list', action='store_true', help='Show obligations without executing tests')
    parser.add_argument('--suite', choices=('quick', 'chain', 'full'), default='full',
                        help='quick: contract gates; chain: reviewed execution; full: all fixed compatibility tests (default)')
    parser.add_argument('--output', type=Path, help='New directory for this run; existing directories refused')
    args = parser.parse_args(argv)
    data = load_manifest()
    plan = plan_suite(data, args.suite)
    if args.list:
        print(json.dumps(dict(suite=args.suite, purpose=plan['purpose'], full_framework_scope=plan['full_framework_scope'],
                              test_args=plan['test_args'], responsibilities=load_suites(data)['responsibilities'],
                              lanes=plan['obligation_data']['lanes'],
                              obligations=obligations(plan['obligation_data'])), ensure_ascii=False, indent=2))
        return 0
    if args.output is None:
        parser.error('--output is required unless --list is used')
    output = args.output.resolve()
    try:
        output.mkdir(parents=True, exist_ok=False)
    except FileExistsError:
        parser.error('Output directory already exists; choose a new run directory')
    before = source_hashes()
    write_new(output / 'SOURCE_SHA256.json', before)
    write_new(output / 'MANIFEST.json', data)
    write_new(output / 'SELECTION.json', {k:v for k,v in plan.items() if k != 'obligation_data'})
    recorder = Recorder()
    old_cwd = Path.cwd()
    overrides = dict(PYTHONDONTWRITEBYTECODE='1', PYTHONUTF8='1', OMP_NUM_THREADS='1',
                     MKL_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', PYTEST_ADDOPTS='')
    previous = {k: os.environ.get(k) for k in overrides}
    try:
        os.chdir(ROOT)
        os.environ.update(overrides)
        import pytest
        exit_code = pytest.main([*plan['test_args'], '-q', '--tb=short', '-o', 'addopts=',
                                 '--junitxml=' + str(output / 'junit.xml'),
                                 '--basetemp=' + str(output / 'pytest_tmp')], plugins=[recorder])
    finally:
        os.chdir(old_cwd)
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
    result = summarize(plan['obligation_data'], recorder, exit_code)
    duplicates = sorted(n for n, count in Counter(recorder.collected).items() if count > 1)
    unexpected = sorted(n for n in recorder.collected if not any(selection_matches(n, s) for s in plan['test_args']))
    result.update(suite=args.suite, full_framework_scope=plan['full_framework_scope'],
                  unselected_required_nodes=plan['unselected_required_nodes'],
                  duplicate_collected_nodes=duplicates, unexpected_collected_nodes=unexpected)
    result.update(timestamp_utc=datetime.now(timezone.utc).isoformat(),
                  python=sys.version.split()[0], pytest=pytest.__version__, mode='OFFLINE_SYNTHETIC_FRAMEWORK',
                  source_unchanged=before == source_hashes(),
                  scope_note='Framework contract regression; not LLM accuracy, full mathematical coverage, or real scientific approval.')
    result['passed'] = result['passed'] and result['source_unchanged'] and not duplicates and not unexpected
    result['full_framework_passed'] = result['passed'] and plan['full_framework_scope']
    write_new(output / 'SUMMARY.json', result)
    print(json.dumps(dict(passed=result['passed'], counts=result['counts'],
                          subtests=result['subtest_counts'], summary=str(output / 'SUMMARY.json')), ensure_ascii=False))
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
