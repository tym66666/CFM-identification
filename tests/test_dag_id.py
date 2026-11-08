"""Task 05 acceptance tests: general identification over recursive semi-Markovian graphs.

Every POINT test is replayed against a freshly generated structural model, so a
formula that looks plausible but encodes the wrong distribution fails here.
"""
import random
import unittest
from unittest import mock

from cfm_id.dag_id_contract import STATUSES, Unavailable, as_problem
from cfm_id.dag_id_graph import ancestors, c_components, parse, remove_incoming
from cfm_id.dag_id_solver import collect_atoms, identify, identify_or_report
from cfm_id.dag_id_verify import check_failure, observed_joint, replay

BACKDOOR = (["Z", "X", "Y"], [("Z", "X"), ("Z", "Y"), ("X", "Y")], [], "X", ["Y"])
CHAIN = (["X", "M", "Y"], [("X", "M"), ("M", "Y")], [], "X", ["Y"])
# A downstream query on a plain chain. Line 3 widens the treatment to {A, B}
# because A stops being an ancestor of C once the arrows into B are cut; the
# widened variable must not survive into the expression as a free condition.
MIDCHAIN = (["A", "B", "C"], [("A", "B"), ("B", "C")], [], "B", ["C"])
FRONTDOOR = (["X", "M", "Y"], [("X", "M"), ("M", "Y")], [("X", "Y")], "X", ["Y"])
BOWARC = (["X", "Y"], [("X", "Y")], [("X", "Y")], "X", ["Y"])
MIXED = (
    ["Z", "X", "M", "Y"],
    [("Z", "X"), ("Z", "Y"), ("X", "M"), ("M", "Y")],
    [("X", "Y")],
    "X",
    ["Y"],
)
# Two parallel mediators plus a direct X <-> Y edge. No admissible back-door
# set exists (the mediators are descendants of X) and no single mediator is a
# front-door variable (a mediator does not intercept the other branch), yet the
# recursion still returns a formula. This is the case the dedicated routes
# cannot answer at all, so it carries the scope claim.
PARALLEL_MEDIATORS = (
    ["X", "M1", "M2", "Y"],
    [("X", "M1"), ("M1", "Y"), ("X", "M2"), ("M2", "Y")],
    [("X", "Y")],
    "X",
    ["Y"],
)
FIG1A = (
    ["W1", "X", "W2", "Y1", "Y2"],
    [("X", "Y1"), ("W2", "Y2")],
    [("W1", "X"), ("X", "W2")],
    "X",
    ["Y1", "Y2"],
)
CONFOUNDED_CHAIN = (
    ["U", "X", "M", "Y"],
    [("X", "M"), ("M", "Y")],
    [("U", "X"), ("U", "Y")],
    "X",
    ["Y"],
)


def problem(case, context=''):
    nodes, directed, bidirected, treatment, outcome = case
    return as_problem(nodes, directed, bidirected, treatment, outcome, context)


class GraphTests(unittest.TestCase):
    def test_ancestors_include_the_target_set(self):
        g = parse(["Z", "X", "Y"], [("Z", "X"), ("X", "Y")])
        self.assertEqual(ancestors(g, ["Y"]), {"Z", "X", "Y"})
        self.assertEqual(ancestors(g, ["Z"]), {"Z"})

    def test_ancestors_do_not_follow_bidirected_edges(self):
        g = parse(["W", "X", "Y"], [("X", "Y")], [("W", "X")])
        self.assertEqual(ancestors(g, ["Y"]), {"X", "Y"})

    def test_c_components_follow_bidirected_chains_only(self):
        g = parse(["W1", "X", "W2", "Y1", "Y2"],
                  [("X", "Y1"), ("W2", "Y2")],
                  [("W1", "X"), ("X", "W2")])
        blocks = sorted(sorted(b) for b in c_components(g))
        self.assertEqual(blocks, [["W1", "W2", "X"], ["Y1"], ["Y2"]])

    def test_cutting_one_bidirected_edge_splits_the_block(self):
        g = parse(["W1", "X", "W2"], [], [("W1", "X"), ("X", "W2")])
        g2 = parse(["W1", "X", "W2"], [], [("W1", "X")])
        self.assertEqual(len(c_components(g)), 1)
        self.assertEqual(sorted(sorted(b) for b in c_components(g2)), [["W1", "X"], ["W2"]])

    def test_intervening_removes_bidirected_edges_at_the_treatment(self):
        g = parse(["X", "M", "Y"], [("X", "M"), ("M", "Y")], [("X", "Y")])
        gx = remove_incoming(g, {"X"})
        self.assertEqual(gx['bidirected'], [])
        self.assertEqual(gx['directed'], [("X", "M"), ("M", "Y")])


class IdentificationTests(unittest.TestCase):
    def assertPointAndVerified(self, case, seeds=(7, 11, 23)):
        p = problem(case)
        certificate = identify(p)
        self.assertEqual(certificate['status'], 'POINT')
        result = replay(certificate, p, seeds=seeds)
        failed = [c['detail'] for c in result['checks'] if not c['passed']]
        self.assertTrue(result['passed'], failed)
        return certificate

    def test_backdoor_graph(self):
        self.assertPointAndVerified(BACKDOOR)

    def test_unconfounded_chain(self):
        self.assertPointAndVerified(CHAIN)

    def test_intervening_mid_chain_does_not_leak_the_upstream_variable(self):
        """A -> B -> C, P(C | do(B)) is P(C | B).

        Line 3 widens the treatment to {A, B}, and A is then irrelevant. A
        prefix-conditioned expression would emit P(C | A, B): still a number,
        no longer a distribution over C alone, and it fails numeric replay.
        """
        certificate = self.assertPointAndVerified(MIDCHAIN)
        atoms = collect_atoms(certificate['functional'])
        self.assertEqual([atom['given'] for atom in atoms['conditional']], [["B"]])

    def test_frontdoor_graph(self):
        self.assertPointAndVerified(FRONTDOOR)

    def test_mixed_frontdoor_and_backdoor(self):
        """A graph the dedicated routes do not settle on their own: the
        back-door criterion fails on X <-> Y, and Z reaches Y directly."""
        self.assertPointAndVerified(MIXED)

    def test_parallel_mediators_with_a_direct_confounded_edge(self):
        """Two mediators in parallel plus X <-> Y. The last factor is a marginal
        over the treatment, not a condition on it: summing X out is what
        restores the unobserved common cause. Conditioning on X there would give
        P(Y|X) instead, which differs from the interventional distribution."""
        certificate = self.assertPointAndVerified(PARALLEL_MEDIATORS)
        atoms = collect_atoms(certificate["functional"])
        conditional = [atom["given"] for atom in atoms["conditional"]]
        self.assertEqual(sorted(given for given in conditional if given),
                         [["X"], ["X"], ["X", "M1", "M2"]])
        # The unconditional atom is P(X) itself; it is the term the recursion
        # sums over, and it is what replaces the unobserved common cause.
        self.assertIn([], conditional)
        self.assertEqual(certificate["positivity"]["conditional_denominators"],
                         [["X"], ["X", "M1", "M2"]])

    def test_the_three_dedicated_routes_all_refuse_that_graph(self):
        """The scope claim has to be shown, not asserted. The same graph is
        written with one explicit latent per bidirected edge and put to each
        dedicated solver; all three decline, so the formula is not something an
        existing route could have produced."""
        from examples.dag_backdoor_reference import make_problem as backdoor_problem
        from examples.dag_frontdoor_reference import make_problem as frontdoor_problem
        from cfm_id.dag_backdoor_solver import solve as backdoor_solve
        from cfm_id.dag_frontdoor_solver import solve as frontdoor_solve
        from cfm_id.dag_adjustment_solver import solve as adjustment_solve
        from cfm_id.dag_adjustment_contract import AdjustmentProblem, VERSION as ADJUSTMENT_VERSION

        nodes = ["X", "M1", "M2", "Y", "U0"]
        edges = [["X", "M1"], ["M1", "Y"], ["X", "M2"], ["M2", "Y"],
                 ["U0", "X"], ["U0", "Y"]]
        latent = ["U0"]

        def adjustment_problem():
            return AdjustmentProblem(**{**backdoor_problem(nodes, edges, latent).model_dump(),
                                        "version": ADJUSTMENT_VERSION})

        routes = (
            ("back-door", backdoor_solve, lambda: backdoor_problem(nodes, edges, latent)),
            ("front-door", frontdoor_solve, lambda: frontdoor_problem(nodes, edges, latent)),
            ("adjustment", adjustment_solve, adjustment_problem),
        )
        refused = {}
        for route, solve, build in routes:
            # Each module reports refusal through its own Unavailable subclass,
            # all of them ValueError descendants with a machine-readable reason.
            with self.assertRaises(ValueError) as caught:
                solve(build())
            refused[route] = caught.exception.reason
        self.assertEqual(refused, {
            "back-door": "NO_CLASSICAL_BACKDOOR_SET",
            "front-door": "NO_SINGLE_VARIABLE_FRONTDOOR",
            "adjustment": "NO_OBSERVED_DAG_ADJUSTMENT_SET",
        })

    def test_paper_figure_1a_joint_outcome(self):
        certificate = self.assertPointAndVerified(FIG1A)
        self.assertEqual(sorted(certificate['target']['outcome']), ["Y1", "Y2"])

    def test_bow_arc_is_not_identified(self):
        p = problem(BOWARC)
        result = identify_or_report(p)
        self.assertEqual(result['status'], 'UNSUPPORTED')
        self.assertEqual(result['reason'], 'NO_UNIFORM_IDENTIFICATION_FORMULA_IN_THIS_GRAPH')
        self.assertTrue(result['nonidentification_proved'])
        self.assertTrue(check_failure(result['witness'])['passed'])

    def test_failure_is_not_confused_with_a_program_error(self):
        result = identify_or_report(problem(BOWARC))
        self.assertNotIn(result['status'], ('CHECK_BLOCKED', 'NEEDS_INPUT'))

    def test_an_unexpected_defect_becomes_a_structured_state(self):
        """A crash inside the solver must not reach the caller as a traceback,
        and must never be reported as a non-identification."""
        with mock.patch('cfm_id.dag_id_solver._id', side_effect=ZeroDivisionError('boom')):
            result = identify_or_report(problem(BACKDOOR))
        self.assertEqual(result['status'], 'CHECK_BLOCKED')
        self.assertEqual(result['reason'], 'INTERNAL_ERROR')
        self.assertIn('ZeroDivisionError', result['detail'])
        self.assertFalse(result['nonidentification_proved'])
        self.assertIsNone(result['witness'])

    def test_confounded_chain_without_mediator_is_identified(self):
        """X <-> Y through U, with M in between: the front-door logic applies
        even though the graph is not the textbook two-edge picture."""
        self.assertPointAndVerified(CONFOUNDED_CHAIN)


class CertificateTests(unittest.TestCase):
    def test_certificate_is_bound_to_its_problem(self):
        p = problem(BACKDOOR)
        certificate = identify(p)
        other = problem(BACKDOOR, context='a different context')
        self.assertNotEqual(certificate['problem_sha256'], identify(other)['problem_sha256'])

    def test_tampered_certificate_is_rejected(self):
        p = problem(BACKDOOR)
        certificate = identify(p)
        certificate['functional']['over'] = []
        self.assertFalse(replay(certificate, p)['passed'])

    def test_positivity_requirements_cover_every_conditioning_event(self):
        """Section 3 states the front-door denominators exactly: [['X'], ['X', 'M']].

        Not just "contains one of them": every conditional atom in the tree must
        appear, and nothing else may be listed.
        """
        p = problem(FRONTDOOR)
        certificate = identify(p)
        denominators = certificate['positivity']['conditional_denominators']
        self.assertEqual(denominators, [['X'], ['X', 'M']])

        atoms = set()

        def walk(expr):
            if not isinstance(expr, dict) or 'operation' not in expr:
                return
            if expr['operation'] == 'CONDITIONAL':
                atoms.add(frozenset(expr['given']))
            for key in ('operand', 'of'):
                walk(expr.get(key))
            for item in expr.get('operands') or []:
                walk(item)

        walk(certificate['functional'])
        # A conditional with no conditioning event is a marginal, so it needs no
        # denominator: P(x) carries no positivity requirement, P(y|x,m) does.
        self.assertIn(frozenset(), atoms)
        self.assertEqual({a for a in atoms if a},
                         {frozenset(d) for d in denominators})

    def test_derivation_trace_is_recorded(self):
        p = problem(FRONTDOOR)
        certificate = identify(p)
        self.assertGreater(len(certificate['derivation']), 2)
        self.assertIn('graph', certificate['derivation'][0])

    def test_every_step_says_why_it_is_legal(self):
        """The task asks which variables are summed, which multiply, and why each step holds."""
        p = problem(FRONTDOOR)
        certificate = identify(p)
        for step in certificate['derivation']:
            self.assertIn(step['line'], (1, 2, 3, 4, 5, 6, 7))
            self.assertTrue(step['rule'])
            self.assertTrue(step['justification'])
            self.assertIsInstance(step['condition'], dict)

    def test_line_numbers_follow_the_published_algorithm(self):
        """Step 1 must be line 2 when an irrelevant node can be dropped first."""
        p = problem((["U", "Z", "X", "Y"], [("Z", "X"), ("Z", "Y"), ("X", "Y")], [], "X", ["Y"]))
        steps = identify(p)['derivation']
        self.assertEqual(steps[0]['line'], 2)
        self.assertEqual(steps[0]['condition']['dropped'], ['U'])
        self.assertNotIn(5, [step['line'] for step in steps])


class FailureEvidenceTests(unittest.TestCase):
    def test_failure_materialises_a_c_forest_pair(self):
        p = problem(BOWARC)
        report = identify_or_report(p)
        self.assertEqual(report['status'], 'UNSUPPORTED')
        self.assertTrue(report['nonidentification_proved'])
        witness = report['witness']
        self.assertTrue(witness['hedge_materialised'])
        self.assertEqual(witness['hedge']['trimmed_forest']['nodes'], ['Y'])
        self.assertEqual(witness['hedge']['grown_forest']['nodes'], ['X', 'Y'])
        self.assertIn('Y', witness['hedge']['roots'])

    def test_failure_evidence_passes_independent_hedge_check(self):
        p = problem(BOWARC)
        witness = identify_or_report(p)['witness']
        result = check_failure(witness, p)
        self.assertTrue(result['passed'], result['detail'])
        self.assertTrue(result['hedge']['passed'])
        names = {check['name'] for check in result['hedge']['checks']}
        self.assertIn('trimmed_avoids_treatment', names)
        self.assertIn('roots_in_ancestors_of_outcome_after_intervention', names)

    def test_altered_hedge_is_rejected(self):
        p = problem(BOWARC)
        witness = identify_or_report(p)['witness']
        witness['hedge']['grown_forest']['nodes'] = ['Y']
        witness['hedge']['grown_forest']['directed'] = []
        witness['hedge']['grown_forest']['bidirected'] = []
        self.assertFalse(check_failure(witness, p)['passed'])

    def test_claiming_a_hedge_without_the_pair_is_rejected(self):
        p = problem(BOWARC)
        witness = identify_or_report(p)['witness']
        witness.pop('hedge')
        self.assertFalse(check_failure(witness, p)['passed'])

    def test_prefix_conditioning_when_the_treatment_precedes_a_non_child(self):
        """Regression: conditioning on parents instead of the graph-order prefix.

        Graph V2 -> V0 -> V1 with V0 <-> V1, X = V2, Y = V1. V0 is the only
        parent of V1, but the intervention on V2 changes the posterior of the
        latent parent of V0 and V1, so P_{v2}(v1 | v0) = P(v1 | v0, v2) and the
        parents-only product is off by ~1e-2. Hand-written graphs never hit it.
        """
        p = as_problem(['V2', 'V0', 'V1'], [('V2', 'V0'), ('V0', 'V1')],
                       [('V0', 'V1')], 'V2', ['V1'])
        certificate = identify(p)
        self.assertTrue(replay(certificate, p)['passed'])

        def atoms(expr, into=None):
            into = [] if into is None else into
            if expr['operation'] == 'CONDITIONAL':
                into.append((expr['outcome'], expr['given']))
                atoms(expr['of'], into)
            for key in ('operand', 'operands'):
                child = expr.get(key)
                if isinstance(child, dict):
                    atoms(child, into)
                elif isinstance(child, list):
                    for item in child:
                        atoms(item, into)
            return into

        given_of_v1 = [g for outcome, g in atoms(certificate['functional'])
                       if outcome == ['V1']]
        self.assertTrue(given_of_v1, 'V1 must appear as a conditional atom')
        self.assertIn('V2', given_of_v1[0],
                      'V1 must be conditioned on V2 even though V2 is not its parent')


class RejectionTests(unittest.TestCase):
    def test_cyclic_graph_is_rejected(self):
        with self.assertRaises(Unavailable) as caught:
            identify(as_problem(["X", "Y"], [("X", "Y"), ("Y", "X")], [], "X", ["Y"]))
        self.assertEqual(caught.exception.reason, 'DIRECTED_CYCLE_NOT_RECURSIVE_MODEL')

    def test_treatment_cannot_be_an_outcome(self):
        with self.assertRaises(Unavailable) as caught:
            identify(as_problem(["X", "Y"], [("X", "Y")], [], "X", ["X"]))
        self.assertEqual(caught.exception.reason, 'TREATMENT_MUST_NOT_BE_AN_OUTCOME')

    def test_resource_limit_is_reported_separately(self):
        nodes = ['N{}'.format(i) for i in range(13)]
        with self.assertRaises(Unavailable) as caught:
            identify(as_problem(nodes, [], [], 'N0', ['N1']))
        self.assertEqual(caught.exception.reason, 'NODE_COUNT_OUT_OF_RANGE')
        # An oversized request must not borrow the non-identification state:
        # nothing was proved about this graph, so it cannot read as "unsupported".
        self.assertEqual(caught.exception.state, 'RESOURCE_LIMIT')
        self.assertNotEqual(caught.exception.state, 'UNSUPPORTED')

    def test_model_size_counts_shared_causes_not_just_nodes(self):
        """Replay enumerates 2^n assignments over 2^b latent configurations, so
        cost is driven by nodes and bidirected edges together. Eight nodes with
        seven shared causes is as expensive as fifteen bare nodes, and must be
        reported as a scale limit rather than as a review problem or a
        non-identification."""
        nodes = ['N{}'.format(i) for i in range(8)]
        directed = [(nodes[i], nodes[i + 1]) for i in range(7)]
        shared = [(nodes[i], nodes[i + 1]) for i in range(7)]
        with self.assertRaises(Unavailable) as caught:
            identify(as_problem(nodes, directed, shared, nodes[0], [nodes[-1]]))
        self.assertEqual(caught.exception.reason, 'MODEL_SIZE_OUT_OF_RANGE')
        self.assertEqual(caught.exception.state, 'RESOURCE_LIMIT')
        # The same node set without shared causes is inside the declared scale,
        # so the refusal above is about size and not about node count alone.
        identify(as_problem(nodes, directed, [], nodes[0], [nodes[-1]]))

    def test_the_six_outcomes_are_distinct_states(self):
        self.assertEqual(
            STATUSES,
            ('POINT', 'UNSUPPORTED', 'NO_FORMULA_YET',
             'RESOURCE_LIMIT', 'NEEDS_INPUT', 'CHECK_BLOCKED'))

    def test_zero_denominator_is_not_silently_zero(self):
        """A formula that needs P(x) > 0 must fail loudly when it is violated."""
        from cfm_id.dag_id_verify import probability_of

        p = problem(CHAIN)
        certificate = identify(p)
        graph = p.as_graph()
        nodes, joint = observed_joint(graph, seed=7)
        degenerate = {k: 0.0 for k in joint}
        with self.assertRaises(Unavailable):
            probability_of(certificate['functional'], nodes, degenerate, {'Y': 0}, {'X': 0})


class EvidenceTests(unittest.TestCase):
    """The document makes behavioural claims; these tests are what makes them true.

    Everything here guards a sentence in docs/DAG_ID_MATH_ZH.md that would
    otherwise be a comment nobody checks.
    """

    def test_verifier_never_imports_the_solver_or_the_graph_module(self):
        """Section 5: independence is a property of the file, not of a promise.

        A comment saying "never imports" can be broken by one added line; this
        walks the module's imports and refuses.
        """
        import ast
        import pathlib

        source = (pathlib.Path(__file__).resolve().parent.parent
                  / 'cfm_id' / 'dag_id_verify.py').read_text(encoding='utf8')
        imported = set()
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ''
                imported.update('{}.{}'.format(module, alias.name) for alias in node.names)
                imported.add(module)
        forbidden = {
            'cfm_id.dag_id_solver', 'cfm_id.dag_id_graph',
            '.dag_id_solver', '.dag_id_graph', 'dag_id_solver', 'dag_id_graph',
        }
        self.assertFalse(imported & forbidden,
                         'verifier imports the thing it is supposed to check: {}'
                         .format(sorted(imported & forbidden)))

    def test_numeric_check_catches_a_formula_that_is_structurally_valid(self):
        """Only the sixth check can catch a formula that is well formed but wrong.

        Simulates the pre-fix line-6 defect: a conditional loses a variable it
        must condition on. Digest and problem binding are re-sealed, so the
        failure can only come from the numeric comparison.
        """
        from cfm_id_bridge.scientific_binding import sha

        p = problem(FRONTDOOR)
        certificate = identify(p)

        def strip_x(expr):
            if not isinstance(expr, dict) or 'operation' not in expr:
                return False
            if expr['operation'] == 'CONDITIONAL' and expr['outcome'] == ['Y']:
                expr['given'] = [v for v in expr['given'] if v != 'X']
                return True
            children = []
            for key in ('operand', 'of'):
                if isinstance(expr.get(key), dict):
                    children.append(expr[key])
            children.extend(expr.get('operands') or [])
            return any(strip_x(child) for child in children)

        self.assertTrue(strip_x(certificate['functional']), 'no Y atom to tamper with')
        body = {k: v for k, v in certificate.items() if k != 'certificate_sha256'}
        certificate['certificate_sha256'] = sha(body)

        result = replay(certificate, p)
        self.assertFalse(result['passed'])
        failed = [c['name'] for c in result['checks'] if not c['passed']]
        self.assertEqual(failed, ['numeric_agreement_with_fresh_scm'])

    def test_replay_reports_the_nine_documented_checks(self):
        p = problem(FRONTDOOR)
        checks = replay(identify(p), p)['checks']
        self.assertEqual([c['name'] for c in checks], [
            'certificate_fields', 'status_is_point', 'certificate_digest',
            'problem_binding', 'question_binding',
            'formula_reads_only_the_asked_variables',
            'derivation_steps_recompute',
            'expression_tree_well_formed',
            'numeric_agreement_with_fresh_scm'])
        self.assertEqual(len(checks), 9)

    def test_a_step_that_cites_the_wrong_rule_is_rejected(self):
        """Numbers can agree while the reason is invented. The trace is
        recomputed rule by rule, so a step is only accepted when the rule it
        cites is the one that actually applies to that sub-problem."""
        p = problem(FRONTDOOR)
        certificate = identify(p)
        self.assertTrue(replay(certificate, p)['passed'])

        tampered = dict(certificate)
        tampered['derivation'] = [dict(step) for step in certificate['derivation']]
        tampered['derivation'][1]['line'] = 6
        body = {k: v for k, v in tampered.items() if k != 'certificate_sha256'}
        from cfm_id_bridge.scientific_binding import sha as digest
        tampered['certificate_sha256'] = digest(body)

        result = replay(tampered, p)
        self.assertFalse(result['passed'])
        derivation = [c for c in result['checks']
                      if c['name'] == 'derivation_steps_recompute'][0]
        self.assertFalse(derivation['passed'])
        self.assertIn('WRONG_RULE', [f['problem'] for f in derivation['findings']])

    def test_a_correct_answer_to_a_different_question_is_rejected(self):
        """The digest is not a question check. A certificate for P(M | do(X))
        is internally consistent; replayed against a question about Y it must
        still fail, on three separate checks."""
        p_answer = problem((MIXED[0], MIXED[1], MIXED[2], "X", ["M"]))
        p_asked = problem(MIXED)
        result = replay(identify(p_answer), p_asked)
        self.assertFalse(result['passed'])
        failed = {c['name'] for c in result['checks'] if not c['passed']}
        self.assertIn('question_binding', failed)
        self.assertIn('formula_reads_only_the_asked_variables', failed)

    def test_replay_compares_three_seeds_and_two_interventions(self):
        """Section 5 claims 3 seeds x 2 intervention values x every outcome value."""
        p = problem(FRONTDOOR)   # one binary outcome -> 3 * 2 * 2 = 12 comparisons
        numeric = [c for c in replay(identify(p), p)['checks']
                   if c['name'] == 'numeric_agreement_with_fresh_scm'][0]
        self.assertIn('12 comparisons', numeric['detail'])

    def test_observed_joint_is_a_probability_distribution(self):
        """Section 5: latent variables are summed with their prior, so the law sums to 1.

        The historical defect here was a joint summing to 2 because the latent
        prior was left out.
        """
        p = problem(FRONTDOOR)
        nodes, joint = observed_joint(p.as_graph(), seed=7)
        self.assertAlmostEqual(sum(joint.values()), 1.0, places=12)
        self.assertTrue(all(0.0 <= value <= 1.0 for value in joint.values()))

    def test_frontdoor_formula_matches_the_documented_shape(self):
        """Section 7 quotes sum_m P(m|x) sum_x P(x) P(y|x,m); this pins that shape.

        Numeric replay proves the formula is *equivalent* to the target. This
        proves it is the *documented* expression and not merely some other
        formula that happens to evaluate to the same numbers.
        """
        p = problem(FRONTDOOR)
        functional = identify(p)['functional']
        self.assertEqual(functional['operation'], 'SUM')
        self.assertEqual(functional['over'], ['M'])

        atoms = set()

        def walk(expr):
            if not isinstance(expr, dict) or 'operation' not in expr:
                return
            if expr['operation'] == 'CONDITIONAL':
                atoms.add((tuple(expr['outcome']), frozenset(expr['given'])))
            for key in ('operand', 'of'):
                walk(expr.get(key))
            if expr['operation'] == 'MARGINAL':
                walk(expr['of'])
            for item in expr.get('operands') or []:
                walk(item)

        walk(functional)
        self.assertEqual(atoms, {
            (('M',), frozenset({'X'})),          # P(m | x)
            (('X',), frozenset()),               # P(x), the inner sum
            (('Y',), frozenset({'X', 'M'})),     # P(y | x, m): x must be present
        })

    def test_hedge_evidence_is_the_documented_thirteen_checks(self):
        p = problem(BOWARC)
        result = check_failure(identify_or_report(p)['witness'], p)
        self.assertEqual(len(result['hedge']['checks']), 13)
        self.assertTrue(all(c['passed'] for c in result['hedge']['checks']))


class RandomisedGraphTests(unittest.TestCase):
    """Random ADMGs: the solver must always answer, and every POINT must replay.

    Deterministic (fixed seed) so failures are reproducible. This is the layer
    that found the line-6 prefix defect; the hand-written graphs above pass with
    or without the fix, so they cannot guard it.
    """

    SEED = 20261106
    GRAPHS = 160

    @staticmethod
    def _random_graph(rng, n):
        nodes = ['V{}'.format(i) for i in range(n)]
        order = nodes[:]
        rng.shuffle(order)
        directed = [(order[i], order[j])
                    for i in range(n) for j in range(i + 1, n) if rng.random() < 0.28]
        bidirected = []
        for i in range(n):
            for j in range(i + 1, n):
                paired = (order[i], order[j]) in directed or (order[j], order[i]) in directed
                if rng.random() < (0.12 if paired else 0.15):
                    bidirected.append((order[i], order[j]))
        return dict(nodes=nodes, directed=directed, bidirected=bidirected,
                    treatment=order[0], outcome=[order[-1]])

    def test_random_graphs_are_total_and_numerically_sound(self):
        rng = random.Random(self.SEED)
        for trial in range(self.GRAPHS):
            case = self._random_graph(rng, rng.choice([3, 4, 5, 6]))
            with self.subTest(trial=trial, **case):
                p = as_problem(**case)
                report = identify_or_report(p)
                self.assertIn(report['status'], ('POINT', 'UNSUPPORTED'))
                if report['status'] == 'POINT':
                    check = replay(identify(p), p)
                    self.assertTrue(check['passed'], check.get('detail'))
                else:
                    checked = check_failure(report['witness'], p)
                    self.assertTrue(checked['passed'], checked['detail'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
