"""Behavioral checks for the closed mathematical registry and its offline CLI."""
import contextlib
import io
import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from cfm_id.research_route_catalog import inventory, registrations, schemas
from cfm_id.research_route_entry import run_registered_route
from evaluation.research_routes_cli import main
from examples.dag_backdoor_reference import make_problem as backdoor_problem, synthetic_review as backdoor_review
from examples.dag_adjustment_reference import make_problem as adjustment_problem, synthetic_review as adjustment_review
from examples.mean_order_fixture import make_problem as mean_problem, synthetic_review as mean_review
from examples.dag_frontdoor_reference import make_problem as frontdoor_problem, synthetic_review as frontdoor_review
from examples.iv_research_fixture import make_problem as iv_problem, synthetic_review as iv_review


def inputs():
    return [
        ('DAG_CLASSICAL_BACKDOOR', backdoor_problem(), backdoor_review, 'cfm_id.dag_backdoor'),
        ('DAG_ADJUSTMENT', adjustment_problem(), adjustment_review, 'cfm_id.dag_adjustment'),
        ('MEAN_ORDER_D2_E1', mean_problem(), mean_review, 'cfm_id.mean_order'),
        ('DAG_CLASSICAL_FRONTDOOR', frontdoor_problem(), frontdoor_review, 'cfm_id.dag_frontdoor'),
        ('BINARY_IV_LATE_ATE', iv_problem(), iv_review, 'cfm_id.iv_research'),
    ]


class RegisteredEntryTests(unittest.TestCase):
    def assert_stopped(self, result, state='CHECK_BLOCKED', backend=False):
        self.assertEqual(result['state'], state)
        self.assertIsNone(result['mathematical_claim'])
        self.assertIsNone(result['certificate'])
        self.assertFalse(result['independent_replay'])
        self.assertEqual(result['backend_called'], backend)
        self.assertFalse(result['production_admission'])
        self.assertFalse(result['estimation_handoff_allowed'])

    def test_inventory_is_explicit_and_preserves_separate_business_boundaries(self):
        value = inventory()
        routes = {r['route_id']: r for r in value['implemented_routes']}
        self.assertEqual(set(routes), {row[0] for row in inputs()})
        for route in routes.values():
            self.assertTrue(route['requires_explicit_selection'])
            self.assertFalse(route['creates_reviews'])
            self.assertFalse(route['business_reading_checked_by_this_entry'])
        self.assertFalse(value['automatic_route_inference'])
        for entry in value['separate_entries']:
            self.assertFalse(entry['callable_here'])
            self.assertFalse(entry['automatic_fallback'])
        for entry in value['planned_routes']:
            self.assertFalse(entry['callable_here'])
        self.assertEqual(routes['MEAN_ORDER_D2_E1']['review_scope'], 'SYNTHETIC_TEST_ONLY')
        self.assertNotEqual(routes['MEAN_ORDER_D2_E1']['review_form'],
                            routes['DAG_ADJUSTMENT']['review_form'])
        # A caller mutating a displayed catalog cannot change the registered scope.
        value['implemented_routes'].clear()
        value['separate_entries'][0]['route_ids'].append('INJECTED')
        self.assertEqual(len(inventory()['implemented_routes']), 5)
        self.assertEqual(routes['DAG_CLASSICAL_FRONTDOOR']['business_entry'],'evaluation.dag_business_workflow')
        self.assertNotIn('INJECTED', inventory()['separate_entries'][0]['route_ids'])

    def test_native_results_and_serialization_are_preserved_for_all_routes(self):
        for registration, (route, problem, reviewer, _) in zip(registrations(), inputs()):
            with self.subTest(route=route):
                review = reviewer(problem)
                before = deepcopy(problem.model_dump())
                native = registration.adapter_type().submit(problem, review)
                typed = run_registered_route(route, problem, review=review, research_protocol_selected=True)
                wire = run_registered_route(route, before, review=review.model_dump(),
                                            research_protocol_selected=True)
                self.assertEqual(typed, wire)
                self.assertEqual(native, typed['native_result'])
                self.assertEqual(before, problem.model_dump())
                self.assertTrue(typed['independent_replay'])
                self.assertFalse(typed['business_reading_checked'])

    def test_schemas_describe_actual_route_versions_and_required_review(self):
        for registration, (route, problem, reviewer, _) in zip(registrations(), inputs()):
            with self.subTest(route=route):
                s = schemas(route)
                self.assertEqual(s['problem']['properties']['version']['const'], problem.version)
                self.assertEqual(s['review']['properties']['version']['const'], reviewer(problem).version)
                self.assertIn('problem_sha256', s['review']['required'])
                self.assertEqual(s['route']['problem_version'], registration.version)
                self.assertEqual(s['problem']['additionalProperties'], False)
                self.assertEqual(s['review']['additionalProperties'], False)

    def test_unregistered_and_separate_entries_are_never_inferred(self):
        problem = backdoor_problem()
        for route in ('DAG_SET_OR_CONDITIONAL_FRONTDOOR', 'IV', 'GENERAL_GRAPHICAL_ID', None, 1, [],
                      'cfm_id.dag_backdoor', '../dag_backdoor', 'dag_adjustment', ''):
            with self.subTest(route=route):
                self.assert_stopped(run_registered_route(route, problem))
        for entry in inventory()['separate_entries']:
            for route in [entry['entry_id'], *entry['route_ids']]:
                result = run_registered_route(route, problem)
                self.assert_stopped(result, 'UNSUPPORTED')
                self.assertEqual(result['reason_code'], 'SEPARATE_BUSINESS_ENTRY_REQUIRED')

    def test_missing_review_or_literal_true_selection_never_calls_native_solver(self):
        for route, problem, reviewer, module in inputs():
            with self.subTest(route=route), patch(module + '.solve', side_effect=AssertionError('unexpected solve')):
                for selection, review in [(False, reviewer(problem)), (1, reviewer(problem)),
                                          ('true', reviewer(problem)), (True, None)]:
                    result = run_registered_route(route, problem, review=review,
                                                  research_protocol_selected=selection)
                    self.assert_stopped(result, 'REVIEW_REQUIRED')
                    self.assertIsNotNone(result['worksheet'])

    def test_stale_pending_rejected_and_injected_approvals_stop_before_solver(self):
        for route, problem, reviewer, module in inputs():
            with self.subTest(route=route), patch(module + '.solve', side_effect=AssertionError('unexpected solve')):
                review = reviewer(problem).model_dump()
                changed = problem.model_dump()
                changed['context'] += ' Context changed.'
                self.assert_stopped(run_registered_route(route, changed, review=review,
                                                         research_protocol_selected=True))
                injected = {**review, 'approved_by_llm': True}
                self.assert_stopped(run_registered_route(route, problem, review=injected,
                                                         research_protocol_selected=True))
                if route.startswith('DAG_'):
                    for decision, state in [('PENDING', 'REVIEW_REQUIRED'), ('REJECTED', 'CHECK_BLOCKED')]:
                        candidate = deepcopy(review)
                        candidate['decisions'][next(iter(candidate['decisions']))] = decision
                        self.assert_stopped(run_registered_route(route, problem, review=candidate,
                                                                 research_protocol_selected=True), state)
                elif route.startswith('BINARY_IV'):
                    candidate=deepcopy(review)
                    candidate['science_review']['decisions'][next(iter(candidate['science_review']['decisions']))]='PENDING'
                    self.assert_stopped(run_registered_route(route, problem, review=candidate, research_protocol_selected=True),'REVIEW_REQUIRED')
                else:
                    for field, value in [('synthetic_fixture', False), ('synthetic_fixture', 1),
                                         ('reviewed_target_direction_population', False)]:
                        candidate = {**review, field: value}
                        self.assert_stopped(run_registered_route(route, problem, review=candidate,
                                                                 research_protocol_selected=True))

    def test_nested_mutation_and_wrong_type_are_revalidated_without_echoing_data(self):
        for route, problem, reviewer, module in inputs():
            with self.subTest(route=route), patch(module + '.solve', side_effect=AssertionError('unexpected solve')):
                review = reviewer(problem)
                malformed = problem.model_dump()
                malformed['version'] = 'private-payload-not-for-diagnostics'
                result = run_registered_route(route, malformed, review=review, research_protocol_selected=True)
                self.assert_stopped(result)
                self.assertNotIn('private-payload', json.dumps(result))
                if route.startswith('DAG_'):
                    problem.nodes.append(10)
                elif route.startswith('BINARY_IV'):
                    problem.cells.append(problem.cells[0])
                else:
                    problem.first.append(1)
                self.assert_stopped(run_registered_route(route, problem, review=review,
                                                         research_protocol_selected=True))
                self.assert_stopped(run_registered_route(route, problem.model_dump_json()))

    def test_failed_replay_cannot_publish_any_route_claim(self):
        for registration, (route, problem, reviewer, _) in zip(registrations(), inputs()):
            with self.subTest(route=route), patch.object(registration.adapter_type, 'replay', return_value=False):
                result = run_registered_route(route, problem, review=reviewer(problem),
                                              research_protocol_selected=True)
                self.assert_stopped(result, backend=True)
                self.assertEqual(result['reason_code'], 'INDEPENDENT_REPLAY_FAILED')

    def test_mismatched_claim_cannot_publish_any_route_proof(self):
        for registration, (route, problem, reviewer, _) in zip(registrations(), inputs()):
            original = registration.adapter_type.claim
            def altered(self, certificate, method=original):
                return {**method(self, certificate), 'unproved_numeric_value': '999'}
            with self.subTest(route=route), patch.object(registration.adapter_type, 'claim', altered):
                result = run_registered_route(route, problem, review=reviewer(problem),
                                              research_protocol_selected=True)
                self.assert_stopped(result, backend=True)
                self.assertEqual(result['reason_code'], 'CLAIM_EVIDENCE_MISMATCH')

    def test_premature_prepare_and_missing_certificate_are_blocked_for_all_routes(self):
        for registration, (route, problem, reviewer, _) in zip(registrations(), inputs()):
            review = reviewer(problem)
            with self.subTest(route=route):
                with patch.object(registration.adapter_type, 'prepare', return_value={'state': 'POINT'}):
                    self.assert_stopped(run_registered_route(route, problem, review=review,
                                                             research_protocol_selected=True))
                native = registration.adapter_type().submit(problem, review)
                for key in ('certificate', 'bounded_result', 'incompatibility_certificate'):
                    native.pop(key, None)
                with patch.object(registration.adapter_type, 'submit', return_value=native):
                    self.assert_stopped(run_registered_route(route, problem, review=review,
                                                             research_protocol_selected=True), backend=True)


class ResearchCliTests(unittest.TestCase):
    def invoke(self, argv):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = main(argv)
        return code, json.loads(output.getvalue())

    def write(self, path, value):
        path.write_text(json.dumps(value), encoding='utf8')

    def test_list_and_all_schemas_are_inspectable_without_review_or_fixture(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            destination = folder / 'catalog.json'
            self.assertEqual(self.invoke(['list', '--output', str(destination)])[0], 0)
            self.assertEqual(json.loads(destination.read_text(encoding='utf8')), inventory())
            for route, _, _, _ in inputs():
                destination = folder / (route + '.json')
                self.assertEqual(self.invoke(['schema', '--route', route, '--output', str(destination)])[0], 0)
                self.assertEqual(json.loads(destination.read_text(encoding='utf8')), schemas(route))

    def test_prepare_then_explicit_review_submission_for_each_route(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            for route, problem, reviewer, _ in inputs():
                self.write(folder / 'problem.json', problem.model_dump())
                self.write(folder / 'review.json', reviewer(problem).model_dump())
                common = ['--route', route, '--problem', str(folder / 'problem.json')]
                prepared = folder / (route + '.prepared.json')
                submitted = folder / (route + '.submitted.json')
                self.assertEqual(self.invoke(['prepare', *common, '--output', str(prepared)])[0], 0)
                self.assertEqual(json.loads(prepared.read_text(encoding='utf8'))['state'], 'REVIEW_REQUIRED')
                self.assertEqual(self.invoke(['submit', *common, '--review', str(folder / 'review.json'),
                                              '--select-research-protocol', '--output', str(submitted)])[0], 0)
                result = json.loads(submitted.read_text(encoding='utf8'))
                self.assertTrue(result['independent_replay'])
                self.assertIn(result['state'], ('POINT', 'PARTIAL'))

    def test_missing_selection_flag_does_not_execute_or_write(self):
        with tempfile.TemporaryDirectory() as folder, patch(
                'evaluation.research_routes_cli.run_registered_route', side_effect=AssertionError('unexpected execution')):
            destination = Path(folder) / 'out.json'
            code, reply = self.invoke(['submit', '--route', 'DAG_ADJUSTMENT', '--problem', 'unused',
                                      '--review', 'unused', '--output', str(destination)])
            self.assertEqual(code, 2)
            self.assertEqual(reply['api_calls'], 0)
            self.assertFalse(destination.exists())

    def test_duplicate_nan_and_malformed_json_are_failures_without_payload_echo(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            for i, raw in enumerate(['{"private":1,"private":2}', '{"private":NaN}', '{"private":',
                                     '{"outer":{"a":1,"a":2}}']):
                source, destination = folder / 'bad.json', folder / (str(i) + '.json')
                source.write_text(raw, encoding='utf8')
                code, reply = self.invoke(['prepare', '--route', 'DAG_ADJUSTMENT', '--problem', str(source),
                                          '--output', str(destination)])
                self.assertEqual(code, 2)
                self.assertFalse(destination.exists())
                self.assertNotIn('private', json.dumps(reply))

    def test_existing_evidence_is_preserved_before_execution(self):
        with tempfile.TemporaryDirectory() as folder, patch(
                'evaluation.research_routes_cli.inventory', side_effect=AssertionError('unexpected execution')):
            destination = Path(folder) / 'old.json'
            destination.write_text('existing evidence', encoding='utf8')
            self.assertEqual(self.invoke(['list', '--output', str(destination)])[0], 2)
            self.assertEqual(destination.read_text(encoding='utf8'), 'existing evidence')

    def test_acceptance_requires_explicit_synthetic_selection(self):
        with tempfile.TemporaryDirectory() as folder, patch(
                'evaluation.research_route_acceptance.evaluate_references', side_effect=AssertionError('unexpected fixtures')):
            destination = Path(folder) / 'out.json'
            self.assertEqual(self.invoke(['acceptance', '--output', str(destination)])[0], 2)
            self.assertFalse(destination.exists())

    def test_explicit_acceptance_runs_and_saves_full_reference_report(self):
        with tempfile.TemporaryDirectory() as folder:
            destination = Path(folder) / 'out.json'
            code, reply = self.invoke(['acceptance', '--allow-synthetic-reviews', '--output', str(destination)])
            self.assertEqual(code, 0)
            report = json.loads(destination.read_text(encoding='utf8'))
            self.assertTrue(report['passed'])
            self.assertEqual(report['cases'], 92)
            self.assertEqual(report['http_calls'], 0)
            self.assertFalse(report['llm_accuracy_measured'])


if __name__ == '__main__':
    unittest.main()

