"""Scientific gates, frozen graphical cases and adversarial front-door certificates."""
import unittest
from copy import deepcopy
from unittest.mock import patch
from pydantic import ValidationError
from cfm_id_bridge.scientific_binding import sha
from cfm_id.dag_frontdoor_contract import FrontdoorProblem, DECISIONS, validate
from cfm_id.dag_frontdoor import prepare, submit
from cfm_id.dag_frontdoor_solver import solve, check_candidate, CriterionFailure
from cfm_id.dag_frontdoor_verify import replay, independent_conditions, _has_active_path
from cfm_id.dag_frontdoor_adapter import DagFrontdoorRoute
from cfm_id.research_route_workflow import run_route
from examples.dag_frontdoor_reference import make_problem, synthetic_review, cases


def changed(problem, **updates):
    return FrontdoorProblem.model_validate({**problem.model_dump(), **updates})


def rehash(c):
    c = deepcopy(c)
    c.pop('certificate_sha256', None)
    c['certificate_sha256'] = sha(c)
    return c


class FrontdoorTests(unittest.TestCase):
    def execute(self, p, review='fixture'):
        return submit(p, review=synthetic_review(p) if review == 'fixture' else review,
                      research_protocol_selected=True)

    def test_frozen_cases_and_independent_conditions(self):
        for name, p, expected, answer in cases():
            with self.subTest(case=name):
                result = self.execute(p)
                self.assertEqual(result['state'], expected)
                self.assertFalse(result['production_admission'])
                self.assertFalse(result['estimation_handoff_allowed'])
                if expected == 'POINT':
                    self.assertEqual(result['certificate']['frontdoor_variable'], answer)
                    self.assertTrue(replay(result['certificate'], problem=p))
                else:
                    self.assertNotIn('certificate', result)
                    self.assertEqual(result['reason_code'], answer)
                    self.assertFalse(result['criterion_diagnostic']['general_nonidentification_proved'])
                for m in set(p.observed) - {p.treatment, p.outcome}:
                    self.assertEqual(check_candidate(p, m)[0], independent_conditions(p, m))

    def test_each_condition_has_a_separate_failure(self):
        by_name = {row[0]: row[1] for row in cases()}
        for name, failed in [('direct_path_bypasses_m', 'FD1'),
                             ('x_m_confounding', 'FD2'), ('m_y_confounding', 'FD3')]:
            flags = independent_conditions(by_name[name], 'M')
            self.assertEqual(flags, {k: k != failed for k in ('FD1', 'FD2', 'FD3')})

    def test_outgoing_not_incoming_edge_deletion(self):
        p = make_problem()
        self.assertTrue(all(independent_conditions(p, 'M').values()))
        # Deleting incoming X edges would leave causal X->M unblocked.
        self.assertTrue(_has_active_path(p.nodes, [e for e in p.edges if e[1] != 'X'], 'X', 'M', []))
        # Deleting incoming M edges would leave causal M->Y unblocked.
        self.assertTrue(_has_active_path(p.nodes, [e for e in p.edges if e[1] != 'M'], 'M', 'Y', ['X']))

    def test_collider_descendant_activation_is_recomputed(self):
        p = {row[0]: row[1] for row in cases()}['collider_descendant_opened_by_x']
        g = [e for e in p.edges if e[0] != 'M']
        self.assertFalse(_has_active_path(p.nodes, g, 'M', 'Y', []))
        self.assertTrue(_has_active_path(p.nodes, g, 'M', 'Y', ['X']))
        # Removing the collider-descendant edge closes it again.
        self.assertFalse(_has_active_path(p.nodes, [e for e in g if e != ['C','X']], 'M', 'Y', ['X']))

    def test_specified_wrong_variable_never_silently_replaced(self):
        p = {row[0]: row[1] for row in cases()}['wrong_specified_while_m_works']
        self.assertEqual(self.execute(p)['state'], 'UNSUPPORTED')
        self.assertEqual(solve(changed(p, frontdoor_variable=None))['frontdoor_variable'], 'M')

    def test_frontdoor_succeeds_when_both_adjustment_routes_have_no_set(self):
        from cfm_id.dag_backdoor_contract import BackdoorProblem, Unavailable
        from cfm_id.dag_adjustment_contract import AdjustmentProblem
        from cfm_id.dag_backdoor_solver import solve as bd_solve
        from cfm_id.dag_adjustment_solver import solve as adj_solve
        p = make_problem()
        data = p.model_dump()
        data.pop('frontdoor_variable')
        data['adjustment'] = None
        for cls, version, solver in [(BackdoorProblem, 'dag-backdoor-1', bd_solve),
                                      (AdjustmentProblem, 'dag-adjustment-1', adj_solve)]:
            with self.assertRaises(Unavailable):
                solver(cls.model_validate({**data, 'version': version}))
        self.assertEqual(self.execute(p)['state'], 'POINT')

    def test_prepare_missing_review_or_selection_cannot_solve(self):
        p = make_problem()
        with patch('cfm_id.dag_frontdoor.solve', side_effect=AssertionError('premature solve')):
            self.assertFalse(prepare(p)['worksheet']['is_approval'])
            self.assertEqual(self.execute(p, None)['state'], 'REVIEW_REQUIRED')
            for flag in (False, 1, 'true'):
                out = submit(p, review=synthetic_review(p), research_protocol_selected=flag)
                self.assertFalse(out['backend_called'])
                self.assertNotIn('certificate', out)

    def test_pending_rejected_stale_and_incomplete_reviews(self):
        p, r = make_problem(), synthetic_review(make_problem())
        variants = [
            (r.model_copy(update={'decisions': {**r.decisions, DECISIONS[0]: 'PENDING'}}), 'REVIEW_REQUIRED'),
            (r.model_copy(update={'decisions': {**r.decisions, DECISIONS[1]: 'REJECTED'}}), 'CHECK_BLOCKED'),
            (r.model_copy(update={'problem_sha256': '0'*64}), 'CHECK_BLOCKED'),
            (r.model_copy(update={'decisions': {}}), 'CHECK_BLOCKED'),
            (r.model_copy(update={'decisions': {**r.decisions, 'FD1': 'ACCEPTED'}}), 'CHECK_BLOCKED'),
        ]
        with patch('cfm_id.dag_frontdoor.solve', side_effect=AssertionError('premature solve')):
            for review, state in variants:
                out = self.execute(p, review)
                self.assertEqual(out['state'], state)
                self.assertFalse(out['backend_called'])

    def test_old_review_and_adjustment_field_cannot_cross_routes(self):
        from examples.dag_backdoor_reference import synthetic_review as old_review, make_problem as old_problem
        p = make_problem()
        self.assertEqual(self.execute(p, old_review(old_problem()))['state'], 'CHECK_BLOCKED')
        with self.assertRaises(ValidationError):
            FrontdoorProblem.model_validate({**p.model_dump(), 'adjustment': ['M']})

    def test_material_target_information_and_selector_changes_invalidate_review(self):
        p = make_problem()
        r = synthetic_review(p)
        for update in [
            {'materials_sha256': '0'*64}, {'context': 'Another population'},
            {'treatment': 'Y', 'outcome': 'X'}, {'frontdoor_variable': 'M'},
            {'information': {**p.information.model_dump(), 'source_id': 'changed-source'}},
            {'edges': p.edges + [['X','Y']]},
        ]:
            out = self.execute(changed(p, **update), r)
            self.assertEqual(out['state'], 'CHECK_BLOCKED')
            self.assertFalse(out['backend_called'])

    def test_unknown_support_and_sample_information_are_not_promoted(self):
        p = make_problem()
        for updates, expected in [
            ({'strictly_positive_joint': None}, 'NEEDS_INPUT'),
            ({'strictly_positive_joint': False}, 'UNSUPPORTED'),
            ({'availability': 'FINITE_SAMPLE'}, 'NEEDS_INPUT'),
            ({'availability': 'MARGINALS_ONLY'}, 'NEEDS_INPUT'),
            ({'variables': ['X','M']}, 'NEEDS_INPUT'),
        ]:
            q = changed(p, information={**p.information.model_dump(), **updates})
            with patch('cfm_id.dag_frontdoor.solve', side_effect=AssertionError('premature solve')):
                out = self.execute(q)
                self.assertEqual(out['state'], expected)
                self.assertFalse(out['backend_called'])

    def test_scope_and_unknown_targets_stop_explicitly(self):
        p = make_problem()
        for updates, expected in [
            ({'graph_status': 'UNKNOWN'}, 'NEEDS_INPUT'),
            ({'treatment': None}, 'NEEDS_INPUT'), ({'outcome': None}, 'NEEDS_INPUT'),
            ({'frontdoor_variable': 'U'}, 'UNSUPPORTED'),
            ({'frontdoor_variable': 'X'}, 'UNSUPPORTED'),
            ({'frontdoor_variable': 'unknown'}, 'CHECK_BLOCKED'),
            ({'additional_restrictions': ['linear']}, 'UNSUPPORTED'),
            ({'edges': p.edges + [['Y','X']]}, 'CHECK_BLOCKED'),
            ({'edges': p.edges + [p.edges[0]]}, 'CHECK_BLOCKED'),
        ]:
            self.assertEqual(self.execute(changed(p, **updates))['state'], expected)
        q = make_problem(['X','M','Y',*list('ABCDEF')], [], [], 'M')
        self.assertEqual(self.execute(q)['state'], 'UNSUPPORTED')

    def test_certificate_mutations_fail_even_with_recomputed_hash(self):
        p = make_problem()
        c = solve(p)
        mutations = [
            lambda d: d.update(version='dag-backdoor-1'),
            lambda d: d.update(theorem='CLASSICAL_BACKDOOR_SUFFICIENT'),
            lambda d: d.update(status='PARTIAL'),
            lambda d: d.update(claim_scope='GENERAL_ID_COMPLETE'),
            lambda d: d.update(materials_sha256='0'*64),
            lambda d: d.update(information_sha256='0'*64),
            lambda d: d.update(frontdoor_variable='X'),
            lambda d: d.update(numeric_value='0.5'),
            lambda d: d.update(conditions={'FD1':1,'FD2':True,'FD3':True}),
            lambda d: d['target'].update(outcome='X'),
            lambda d: d['selection'].update(requested='M'),
            lambda d: d['graphical_trace']['FD1'].update(reachable_without_node=[]),
            lambda d: d['graphical_trace']['FD2'].update(removed_outgoing_from='M'),
            lambda d: d['graphical_trace']['FD3'].update(ancestral_nodes=[]),
            lambda d: d['functional'].update(source_id='other-law'),
            lambda d: d.update(extra_claim='nonidentification'),
        ]
        for mutate in mutations:
            corrupted = deepcopy(c)
            mutate(corrupted)
            self.assertFalse(replay(rehash(corrupted), problem=p))

    def test_double_sum_roles_and_marginal_weight_cannot_be_swapped(self):
        p, c = make_problem(), solve(make_problem())
        outer = c['functional']['expression']
        self.assertEqual(outer['bind']['role'], 'mediator_value')
        inner = outer['summand']['factors'][1]
        self.assertEqual(inner['bind']['role'], 'treatment_marginal_value')
        for variant in ('inner_x', 'outer_x', 'conditional_weight', 'wrong_domain', 'missing_sum'):
            d = deepcopy(c)
            expression = d['functional']['expression']
            factor, inner = expression['summand']['factors']
            if variant == 'inner_x':
                inner['summand']['factors'][0]['given'][0]['value_role'] = 'intervention_value'
            elif variant == 'outer_x':
                factor['given'][0]['value_role'] = 'treatment_marginal_value'
            elif variant == 'conditional_weight':
                weight = inner['summand']['factors'][1]
                weight['operation'] = 'CONDITIONAL_PROBABILITY'
                weight['given'] = [{'variable':'M','value_role':'mediator_value'}]
            elif variant == 'wrong_domain':
                inner['bind']['domain'] = [0]
            else:
                d['functional']['expression'] = inner
            self.assertFalse(replay(rehash(d), problem=p))

    def test_missing_keys_and_old_route_certificates_are_rejected(self):
        from cfm_id.dag_backdoor_solver import solve as old_solve
        from examples.dag_backdoor_reference import make_problem as old_problem
        p, c = make_problem(), solve(make_problem())
        for key in c:
            d = deepcopy(c)
            d.pop(key)
            self.assertFalse(replay(d, problem=p))
        self.assertFalse(replay(old_solve(old_problem()), problem=p))
        self.assertFalse(replay([], problem=p))

    def test_independent_replay_does_not_call_production_graph_or_formula(self):
        p, c = make_problem(), solve(make_problem())
        with (patch('cfm_id.dag_frontdoor_solver.check_candidate', side_effect=AssertionError('solver graph')),
              patch('cfm_id.dag_frontdoor_solver.moral_separation', side_effect=AssertionError('solver separation')),
              patch('cfm_id.dag_frontdoor_solver.functional', side_effect=AssertionError('solver formula')),
              patch('cfm_id.dag_frontdoor_solver.solve', side_effect=AssertionError('solver'))):
            self.assertTrue(replay(c, problem=p))

    def test_replay_failure_withholds_certificate(self):
        with patch('cfm_id.dag_frontdoor.replay', return_value=False):
            out = self.execute(make_problem())
            self.assertEqual(out['state'], 'CHECK_BLOCKED')
            self.assertNotIn('certificate', out)

    def test_renaming_and_node_order_do_not_change_role_binding(self):
        p = make_problem()
        names = {'U': '潜变量', 'X': "x_prime'处理", 'M': 'intervention_value', 'Y': '结果,y'}
        data = p.model_dump()
        for key in ('nodes', 'observed', 'latent'):
            data[key] = [names[n] for n in reversed(data[key])]
        data['edges'] = [[names[a], names[b]] for a, b in reversed(data['edges'])]
        data.update(treatment=names['X'], outcome=names['Y'], frontdoor_variable=names['M'])
        data['information']['variables'] = data['observed']
        q = FrontdoorProblem.model_validate(data)
        self.assertTrue(replay(solve(q), problem=q))
        self.assertFalse(replay(solve(p), problem=q))

    def test_adapter_claim_and_shared_workflow(self):
        p = make_problem()
        a = DagFrontdoorRoute()
        out = run_route(a, p, review=synthetic_review(p), research_protocol_selected=True)
        self.assertEqual(out['state'], 'POINT')
        self.assertTrue(out['independent_replay'])
        self.assertFalse(a.verify_claim(out['certificate'], {**out['mathematical_claim'], 'numeric_value':'0.2'}))
        with patch.object(a, 'replay', return_value=False):
            failed = run_route(a, p, review=synthetic_review(p), research_protocol_selected=True)
            self.assertEqual(failed['state'], 'CHECK_BLOCKED')
            self.assertIsNone(failed['certificate'])
            self.assertIsNone(failed['mathematical_claim'])


if __name__ == '__main__':
    unittest.main()

