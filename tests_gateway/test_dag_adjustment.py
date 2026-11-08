"""Protocol, scientific gates, specified sets, and adversarial replay tests."""
import unittest
from copy import deepcopy
from unittest.mock import patch

from cfm_id_bridge.scientific_binding import sha
from cfm_id.dag_adjustment_contract import AdjustmentProblem, DECISIONS, digest
from cfm_id.dag_adjustment import prepare, submit
from cfm_id.dag_adjustment_solver import solve, graph_parts, moral_separation
from cfm_id.dag_adjustment_verify import replay, original_graph_check
from cfm_id.dag_adjustment_adapter import DagAdjustmentRoute
from cfm_id.research_route_workflow import run_route
from cfm_id.dag_backdoor_contract import BackdoorProblem
from cfm_id.dag_backdoor_solver import solve as classical_solve
from cfm_id.dag_backdoor_verify import replay as classical_replay
from examples.dag_backdoor_reference import synthetic_review as classical_review
from examples.dag_adjustment_reference import make_problem, synthetic_review, cases


def changed(problem, **updates):
    return AdjustmentProblem.model_validate({**problem.model_dump(), **updates})


def classical(problem):
    return BackdoorProblem.model_validate({**problem.model_dump(), 'version': 'dag-backdoor-1'})


def rehash(certificate):
    c = deepcopy(certificate)
    c.pop('certificate_sha256', None)
    c['certificate_sha256'] = sha(c)
    return c


class AdjustmentTests(unittest.TestCase):
    def run_case(self, problem, review='fixture'):
        return submit(problem, review=synthetic_review(problem) if review == 'fixture' else review,
                      research_protocol_selected=True)

    def test_frozen_reference_outcomes(self):
        for name, p, expected, answer in cases():
            with self.subTest(case=name):
                r = self.run_case(p)
                self.assertEqual(r['state'], expected)
                self.assertFalse(r['production_admission'])
                self.assertFalse(r['estimation_handoff_allowed'])
                if expected == 'POINT':
                    self.assertEqual(r['certificate']['adjustment'], answer)
                    self.assertTrue(replay(r['certificate'], problem=p))
                else:
                    self.assertEqual(r['reason_code'], answer)
                    self.assertNotIn('certificate', r)
                    self.assertIn('criterion_diagnostic', r)

    def test_prepare_and_no_approval_never_solve(self):
        p = make_problem()
        with patch('cfm_id.dag_adjustment.solve', side_effect=AssertionError('premature solver')):
            self.assertFalse(prepare(p)['worksheet']['is_approval'])
            self.assertEqual(self.run_case(p, None)['state'], 'REVIEW_REQUIRED')
            for flag in (False, 1, 'true'):
                r = submit(p, review=synthetic_review(p), research_protocol_selected=flag)
                self.assertEqual(r['state'], 'REVIEW_REQUIRED')
                self.assertFalse(r['backend_called'])

    def test_pending_rejected_stale_and_missing_decisions(self):
        p = make_problem()
        r = synthetic_review(p)
        variants = [
            (r.model_copy(update={'decisions': {**r.decisions, DECISIONS[0]: 'PENDING'}}), 'REVIEW_REQUIRED'),
            (r.model_copy(update={'decisions': {**r.decisions, DECISIONS[1]: 'REJECTED'}}), 'CHECK_BLOCKED'),
            (r.model_copy(update={'problem_sha256': '0'*64}), 'CHECK_BLOCKED'),
            (r.model_copy(update={'decisions': {}}), 'CHECK_BLOCKED'),
            (r.model_copy(update={'decisions': {**r.decisions, 'additional': 'ACCEPTED'}}), 'CHECK_BLOCKED'),
        ]
        with patch('cfm_id.dag_adjustment.solve', side_effect=AssertionError('premature solver')):
            for review, state in variants:
                self.assertEqual(self.run_case(p, review)['state'], state)

    def test_review_bound_to_actual_material_and_set(self):
        p = make_problem()
        for q in (changed(p, materials_sha256='0'*64),
                  changed(p, context='Another synthetic population'),
                  changed(p, adjustment=['Z'])):
            r = self.run_case(q, synthetic_review(p))
            self.assertEqual(r['reason_code'], 'STALE_ADJUSTMENT_REVIEW')
            self.assertFalse(r['backend_called'])

    def test_shape_support_and_extra_assumptions_block_before_solver(self):
        p = make_problem()
        variants = [
            (changed(p, edges=p.edges + [['Y','Z']]), 'DIRECTED_CYCLE'),
            (changed(p, edges=p.edges + [['Z','X']]), 'INVALID_DIRECTED_EDGE'),
            (changed(p, graph_status='UNKNOWN'), 'CAUSAL_GRAPH_NOT_DECLARED'),
            (changed(p, additional_restrictions=['selection mechanism unknown']),
             'ADDITIONAL_MODEL_RESTRICTIONS_NOT_ADAPTED'),
        ]
        for key, value, reason in [
            ('availability', 'FINITE_SAMPLE', 'FULL_SYMBOLIC_POPULATION_LAW_REQUIRED'),
            ('strictly_positive_joint', None, 'POPULATION_POSITIVITY_UNDECLARED'),
            ('strictly_positive_joint', False, 'NONPOSITIVE_LAW_NOT_ADAPTED'),
            ('variables', ['X','Y'], 'COMPLETE_OBSERVED_JOINT_LAW_REQUIRED'),
        ]:
            variants.append((changed(p, information={**p.information.model_dump(), key: value}), reason))
        with patch('cfm_id.dag_adjustment.solve', side_effect=AssertionError('premature solver')):
            for q, reason in variants:
                result = self.run_case(q)
                self.assertEqual(result['reason_code'], reason)
                self.assertFalse(result['backend_called'])

    def test_latents_and_target_variables_cannot_be_adjusted(self):
        for z in (['U'], ['X'], ['Y']):
            p = make_problem(['U','X','Y'], [['U','X'],['U','Y']], ['U'], z)
            self.assertEqual(prepare(p)['reason_code'], 'OBSERVED_DISJOINT_ADJUSTMENT_REQUIRED')

    def test_resource_limit_is_unsupported_not_nonidentification(self):
        p = make_problem(['X','Y',*list('ABCDEFG')], [['X','Y']])
        result = prepare(p)
        self.assertEqual(result['state'], 'UNSUPPORTED')
        self.assertEqual(result['reason_code'], 'DAG_REPLAY_RESOURCE_LIMIT')
        self.assertNotIn('certificate', result)

    def test_explicit_set_not_silently_replaced_by_search(self):
        p = make_problem()
        self.assertEqual(solve(p)['adjustment'], ['Z'])
        r = self.run_case(changed(p, adjustment=[]))
        self.assertEqual(r['reason_code'], 'SPECIFIED_SET_FAILS_DAG_ADJUSTMENT')
        p = make_problem(['X','M','Y'], [['X','M'],['M','Y']], adjustment=['M'])
        self.assertEqual(self.run_case(p)['state'], 'UNSUPPORTED')
        self.assertEqual(solve(changed(p, adjustment=None))['adjustment'], [])

    def test_legal_descendant_extends_specified_sets_not_target_search(self):
        p = make_problem(['X','Y','W'], [['X','Y'],['X','W']], adjustment=['W'])
        self.assertEqual(solve(p)['adjustment'], ['W'])
        with self.assertRaisesRegex(ValueError, 'ADJUSTMENT_CONTAINS_TREATMENT_DESCENDANT'):
            classical_solve(classical(p))
        self.assertEqual(classical_solve(classical(changed(p, adjustment=None)))['adjustment'], [])

    def test_causal_first_edge_removal_must_not_remove_other_outgoing_edges(self):
        p = make_problem(['X','C','U','Y'], [['X','C'],['U','C'],['U','Y']], ['U'], ['C'])
        proper, forbidden, trace = graph_parts(p.nodes, p.edges, 'X', 'Y')
        self.assertFalse(forbidden)
        self.assertEqual(trace['removed_causal_first_edges'], [])
        self.assertIn(('X','C'), proper)
        self.assertFalse(moral_separation(p.nodes, proper, 'X', 'Y', ['C'])[0])
        ok, _, paths = original_graph_check(p.nodes, p.edges, 'X', 'Y', ['C'])
        self.assertFalse(ok)
        self.assertIn(['X','C','U','Y'], paths)

    def test_cross_protocol_problem_review_certificate_rejected(self):
        p = make_problem()
        old = classical(p)
        self.assertEqual(prepare(old)['state'], 'CHECK_BLOCKED')
        self.assertEqual(self.run_case(p, classical_review(old))['state'], 'CHECK_BLOCKED')
        self.assertFalse(replay(classical_solve(old), problem=p))
        self.assertFalse(classical_replay(solve(p), problem=old))
        self.assertFalse(replay(solve(p), problem=old))

    def test_rehashed_certificate_mutations_rejected(self):
        p = make_problem()
        c = solve(p)
        variants = []
        for key, value in [
            ('version', 'dag-backdoor-1'), ('theorem', 'GENERAL_ID'),
            ('status', 'PARTIAL'), ('claim_scope', 'BINARY_COMPLETE'),
            ('problem_sha256', '0'*64), ('information_sha256', '0'*64),
            ('adjustment', []), ('numeric_value', '1/2'), ('positivity', 'FITTED_FROM_SAMPLE'),
        ]:
            variants.append({**c, key: value})
        paths = [
            (('functional','conditional','given'), ['X']),
            (('functional','marginal','variables'), []),
            (('functional','sum_over'), []),
            (('functional','source_id'), 'another_source'),
            (('functional','empty_marginal_is_one'), 1),
            (('target','outcome'), 'Z'),
            (('target','context'), 'another population'),
            (('graphical_trace','forbidden_nodes'), []),
            (('graphical_trace','causal_path_nodes'), []),
            (('graphical_trace','removed_causal_first_edges'), []),
        ]
        for path, value in paths:
            a = deepcopy(c)
            cursor = a
            for key in path[:-1]:
                cursor = cursor[key]
            cursor[path[-1]] = value
            variants.append(a)
        variants.append({**c, 'extra_claim': 'all graphs identified'})
        for i, forged in enumerate(variants):
            with self.subTest(mutation=i):
                self.assertFalse(replay(rehash(forged), problem=p))

    def test_valid_hash_and_binding_cannot_certify_forbidden_set(self):
        p = make_problem(['X','Y','W'], [['X','Y'],['X','W']], adjustment=['W'])
        c = solve(p)
        q = changed(p, edges=[['X','W'],['W','Y']])
        c['problem_sha256'] = digest(q)
        c['graphical_trace'] = original_graph_check(q.nodes, q.edges, 'X', 'Y', ['W'])[1]
        self.assertFalse(replay(rehash(c), problem=q))

    def test_malformed_certificate_is_false(self):
        p = make_problem()
        for c in (None, [], 42, {}, {'certificate_sha256': []}):
            self.assertFalse(replay(c, problem=p))
        c = solve(p)
        for z in (['Z','Z'], [True], 'Z', None):
            self.assertFalse(replay(rehash({**c, 'adjustment': z}), problem=p))

    def test_replay_does_not_import_solver_graph_or_formula_functions(self):
        p = make_problem()
        c = solve(p)
        with (patch('cfm_id.dag_adjustment_solver.graph_parts', side_effect=AssertionError('shared graph')),
              patch('cfm_id.dag_adjustment_solver.moral_separation', side_effect=AssertionError('shared separation')),
              patch('cfm_id.dag_adjustment_solver.functional', side_effect=AssertionError('shared formula'))):
            self.assertTrue(replay(c, problem=p))

    def test_replay_failure_withholds_certificate(self):
        p = make_problem()
        with patch('cfm_id.dag_adjustment.replay', return_value=False):
            r = self.run_case(p)
            self.assertEqual(r['state'], 'CHECK_BLOCKED')
            self.assertNotIn('certificate', r)

    def test_renaming_and_order_invariance(self):
        p = make_problem()
        rename = {'Z': '先前,能力', 'X': '训练甲', 'Y': '完成乙'}
        q = changed(p, nodes=[rename[n] for n in reversed(p.nodes)],
                    observed=[rename[n] for n in reversed(p.observed)],
                    edges=[[rename[a], rename[b]] for a, b in reversed(p.edges)],
                    treatment=rename['X'], outcome=rename['Y'],
                    information={**p.information.model_dump(), 'variables': [rename[n] for n in p.observed]})
        c = solve(q)
        self.assertEqual(c['adjustment'], [rename['Z']])
        self.assertTrue(replay(c, problem=q))
        self.assertFalse(replay(solve(p), problem=q))

    def test_adapter_claim_exactly_matches_evidence(self):
        a = DagAdjustmentRoute()
        c = solve(make_problem())
        claim = a.claim(c)
        self.assertTrue(a.verify_claim(c, claim))
        changed_claim = deepcopy(claim)
        changed_claim['functional']['empty_marginal_is_one'] = 1
        self.assertFalse(a.verify_claim(c, changed_claim))
        self.assertFalse(a.verify_claim(c, {**claim, 'numeric_value': '0.5'}))

    def test_existing_workflow_positive_and_stop_states(self):
        for name, p, expected, _ in cases():
            with self.subTest(case=name):
                r = run_route(DagAdjustmentRoute(), p, review=synthetic_review(p),
                              research_protocol_selected=True)
                self.assertEqual(r['state'], expected)
                self.assertFalse(r['production_admission'])
                self.assertFalse(r['estimation_handoff_allowed'])
                if expected == 'POINT':
                    self.assertTrue(r['independent_replay'])
                    self.assertIsNotNone(r['mathematical_claim'])
                else:
                    self.assertIsNone(r['certificate'])
                    self.assertIsNone(r['mathematical_claim'])

    def test_existing_workflow_does_not_auto_approve(self):
        p = make_problem()
        r = run_route(DagAdjustmentRoute(), p, research_protocol_selected=True)
        self.assertEqual(r['state'], 'REVIEW_REQUIRED')
        self.assertFalse(r['backend_called'])


if __name__ == '__main__':
    unittest.main()
