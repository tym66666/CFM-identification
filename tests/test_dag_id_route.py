"""Task 05 acceptance tests for the business entry (``cfm_id/dag_id_route.py``).

These tests go through the shared research-route workflow rather than calling the
module directly, so they also check that the review gate cannot be bypassed.
"""
import unittest
from unittest.mock import patch

from cfm_id.dag_backdoor_contract import DECISIONS
from cfm_id.dag_id_route import (
    DagGeneralIdRoute, GeneralIdProblem, digest, prepare, to_math_problem,
)
from cfm_id.dag_id_solver import FAILED_REASON
from cfm_id.dag_id_verify import check_failure
from cfm_id.research_route_workflow import run_route
from examples.dag_id_route_reference import make_problem, synthetic_review


def execute(case='mixed', review=True, selected=True):
    problem = make_problem(case)
    record = synthetic_review(problem) if review is True else review
    return problem, run_route(DagGeneralIdRoute(), problem, review=record,
                              research_protocol_selected=selected)


class PointTests(unittest.TestCase):
    def test_mixed_graph_is_answered_end_to_end(self):
        problem, result = execute('mixed')
        self.assertEqual(result['state'], 'POINT')
        self.assertTrue(result['independent_replay'])
        self.assertEqual(result['mathematical_claim']['kind'], 'POINT')
        self.assertEqual(result['certificate']['target']['treatment'], 'X')

    def test_answer_is_the_same_through_the_serialised_review(self):
        problem = make_problem('mixed')
        review = synthetic_review(problem)
        typed = run_route(DagGeneralIdRoute(), problem, review=review, research_protocol_selected=True)
        wire = run_route(DagGeneralIdRoute(), problem, review=review.model_dump(),
                         research_protocol_selected=True)
        self.assertEqual(typed, wire)

    def test_backdoor_and_frontdoor_still_reproduce(self):
        """The task asks for the existing two results to be reproduced by the new entry."""
        cases = {
            'backdoor': dict(nodes=['Z', 'X', 'Y'], directed=[['Z', 'X'], ['Z', 'Y'], ['X', 'Y']],
                             bidirected=[], context='Back-door graph.'),
            'frontdoor': dict(nodes=['X', 'M', 'Y'], directed=[['X', 'M'], ['M', 'Y']],
                              bidirected=[['X', 'Y']], context='Front-door graph.'),
        }
        for name, fields in cases.items():
            with self.subTest(case=name):
                problem = GeneralIdProblem(
                    version='dag-general-id-1', model='RECURSIVE_SEMI_MARKOVIAN_DISCRETE',
                    treatment='X', outcome=['Y'], graph_status='RESEARCHER_CONFIRMED',
                    graph_source='reference example', materials_sha256='0' * 64, **fields)
                result = run_route(DagGeneralIdRoute(), problem,
                                   review=synthetic_review(problem), research_protocol_selected=True)
                self.assertEqual(result['state'], 'POINT')
                self.assertTrue(result['independent_replay'])


class NonIdentificationTests(unittest.TestCase):
    def test_bow_arc_reports_verified_non_identification(self):
        problem, result = execute('bowarc')
        self.assertEqual(result['state'], 'UNSUPPORTED')
        self.assertEqual(result['reason_code'], FAILED_REASON)
        witness = result['native_result']['witness']
        self.assertTrue(witness['hedge_materialised'])
        checked = check_failure(witness, to_math_problem(problem))
        self.assertTrue(checked['passed'], checked['detail'])

    def test_non_identification_is_not_reported_as_success(self):
        _, result = execute('bowarc')
        self.assertIsNone(result['certificate'])
        self.assertFalse(result['independent_replay'])


class GateTests(unittest.TestCase):
    def test_graph_of_unknown_provenance_is_refused(self):
        problem = make_problem('mixed').model_copy(update={'graph_status': 'UNKNOWN'})
        with patch('cfm_id.dag_id_route.solve', side_effect=AssertionError('unexpected solve')):
            result = prepare(problem)
        self.assertEqual(result['state'], 'NEEDS_INPUT')
        self.assertEqual(result['reason_code'], 'GRAPH_NOT_CONFIRMED_BY_RESEARCHER')

    def test_pending_condition_blocks_before_the_solver(self):
        problem = make_problem('mixed')
        decisions = {name: 'ACCEPTED' for name in DECISIONS}
        decisions['population_law_and_strict_positivity'] = 'PENDING'
        review = synthetic_review(problem, decisions)
        with patch('cfm_id.dag_id_route.solve', side_effect=AssertionError('unexpected solve')):
            result = run_route(DagGeneralIdRoute(), problem, review=review, research_protocol_selected=True)
        self.assertEqual(result['state'], 'REVIEW_REQUIRED')
        self.assertEqual(result['reason_code'], 'SCIENTIFIC_CONDITION_PENDING')

    def test_rejected_condition_blocks_before_the_solver(self):
        problem = make_problem('mixed')
        decisions = {name: 'ACCEPTED' for name in DECISIONS}
        decisions['recursive_scm_and_perfect_intervention'] = 'REJECTED'
        review = synthetic_review(problem, decisions)
        with patch('cfm_id.dag_id_route.solve', side_effect=AssertionError('unexpected solve')):
            result = run_route(DagGeneralIdRoute(), problem, review=review, research_protocol_selected=True)
        self.assertEqual(result['state'], 'CHECK_BLOCKED')
        self.assertEqual(result['reason_code'], 'SCIENTIFIC_CONDITION_REJECTED')

    def test_review_for_another_problem_is_stale(self):
        problem = make_problem('mixed')
        other = make_problem('bowarc')
        with patch('cfm_id.dag_id_route.solve', side_effect=AssertionError('unexpected solve')):
            result = run_route(DagGeneralIdRoute(), problem, review=synthetic_review(other),
                               research_protocol_selected=True)
        self.assertEqual(result['reason_code'], 'STALE_GENERAL_ID_REVIEW')

    def test_missing_review_or_selection_never_reaches_the_solver(self):
        problem = make_problem('mixed')
        for review, selected in ((None, True), (synthetic_review(problem), False),
                                 (synthetic_review(problem), 'true')):
            with self.subTest(selected=selected), \
                    patch('cfm_id.dag_id_route.solve', side_effect=AssertionError('unexpected solve')):
                result = run_route(DagGeneralIdRoute(), problem, review=review,
                                   research_protocol_selected=selected)
                self.assertEqual(result['state'], 'REVIEW_REQUIRED')

    def test_problem_digest_changes_with_the_graph(self):
        self.assertNotEqual(digest(make_problem('mixed')), digest(make_problem('bowarc')))


class RejectionTests(unittest.TestCase):
    def test_cyclic_graph_is_blocked_not_crashed(self):
        problem = make_problem('mixed').model_copy(
            update={'nodes': ['X', 'Y'], 'directed': [['X', 'Y'], ['Y', 'X']],
                    'bidirected': [], 'treatment': 'X', 'outcome': ['Y']})
        result = prepare(problem)
        self.assertEqual(result['state'], 'CHECK_BLOCKED')
        self.assertEqual(result['reason_code'], 'DIRECTED_CYCLE_NOT_RECURSIVE_MODEL')

    def test_node_limit_is_reported_separately(self):
        nodes = ['N{}'.format(i) for i in range(13)]
        problem = make_problem('mixed').model_copy(
            update={'nodes': nodes, 'directed': [], 'bidirected': [],
                    'treatment': nodes[0], 'outcome': [nodes[1]]})
        result = prepare(problem)
        self.assertEqual(result['state'], 'RESOURCE_LIMIT')
        self.assertEqual(result['reason_code'], 'NODE_COUNT_OUT_OF_RANGE')


class ReadingConfirmationGateTests(unittest.TestCase):
    """A model reading is a draft; it is not a confirmed graph.

    These two cases guard the gate in the walkthrough script. Without it the
    caller fills in the confirmation itself, and a draft that extracted no
    relation at all becomes a formula for P(Y) - arithmetically correct,
    semantically unsupported. That failure was produced by a real model run.
    """

    class _Reading:
        def __init__(self, relations, common_causes=()):
            self.variables = [type('V', (), {'name': 'X', 'observation': 'OBSERVED'})(),
                              type('V', (), {'name': 'Y', 'observation': 'OBSERVED'})()]
            self.relations = [type('R', (), {'cause': a, 'effect': b, 'kind': 'DIRECT_CAUSE'})()
                              for a, b in relations]
            self.common_causes = [type('C', (), {'first': a, 'second': b})()
                                  for a, b in common_causes]

    def setUp(self):
        from examples.dag_id_llm_reading import confirmation
        self.confirmation = confirmation

    def test_a_draft_without_any_relation_cannot_be_confirmed(self):
        confirmed, blocker = self.confirmation(self._Reading([]))
        self.assertFalse(confirmed)
        self.assertEqual(blocker, 'NO_CAUSAL_STRUCTURE_READ')

    def test_one_relation_or_one_shared_cause_is_enough_to_proceed(self):
        self.assertEqual(self.confirmation(self._Reading([('X', 'Y')])), (True, None))
        self.assertEqual(self.confirmation(self._Reading([], [('X', 'Y')])), (True, None))


if __name__ == '__main__':
    unittest.main(verbosity=2)
