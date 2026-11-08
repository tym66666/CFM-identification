"""Task 05 walkthrough: four graphs, the formula each one yields, and the check.

Run from the repository root:

    python examples/dag_id_demo.py

The point of the demo is the *shape* of the answer.  A formula that is only
pretty-printed cannot be checked; the tree printed here is the same object the
independent replay evaluates against a freshly generated structural model.

Case 3 is the one that carries the scope claim.  It is run against the three
dedicated routes as well, on the same graph written with explicit latent
variables, so the "no dedicated route answers this" part is shown rather than
asserted.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cfm_id.dag_id_contract import as_problem
from cfm_id.dag_id_solver import identify, identify_or_report
from cfm_id.dag_id_verify import check_failure, replay


def expand_latents(nodes, directed, bidirected):
    """Write each bidirected edge as one latent parent of its two endpoints."""
    nodes = list(nodes)
    edges = [list(edge) for edge in directed]
    latent = []
    for index, (a, b) in enumerate(bidirected):
        name = 'U{}'.format(index)
        nodes.append(name)
        latent.append(name)
        edges += [[name, a], [name, b]]
    return nodes, edges, latent


def dedicated_route_verdicts(nodes, directed, bidirected, treatment, outcome):
    """Ask the three dedicated solvers the same question, on the same graph."""
    from cfm_id.dag_adjustment_contract import AdjustmentProblem, VERSION as ADJ_VERSION
    from cfm_id.dag_adjustment_solver import solve as adjustment_solve
    from cfm_id.dag_backdoor_solver import solve as backdoor_solve
    from cfm_id.dag_frontdoor_solver import solve as frontdoor_solve
    from examples.dag_backdoor_reference import make_problem as backdoor_problem
    from examples.dag_frontdoor_reference import make_problem as frontdoor_problem

    flat_nodes, flat_edges, latent = expand_latents(nodes, directed, bidirected)
    asked = [
        ('back-door', backdoor_solve,
         lambda: backdoor_problem(flat_nodes, flat_edges, latent)),
        ('front-door', frontdoor_solve,
         lambda: frontdoor_problem(flat_nodes, flat_edges, latent)),
        ('adjustment', adjustment_solve,
         lambda: AdjustmentProblem(**{**backdoor_problem(flat_nodes, flat_edges, latent).model_dump(),
                                      'version': ADJ_VERSION})),
    ]
    verdicts = []
    for name, solve, build in asked:
        try:
            certificate = solve(build())
        except Exception as error:  # the dedicated routes report refusal this way
            verdicts.append((name, 'refused', getattr(error, 'reason', type(error).__name__)))
        else:
            verdicts.append((name, 'answered', certificate.get('theorem', 'POINT')))
    return verdicts


def render(expr, depth=0):
    op = expr['operation']
    if op == 'OBSERVED_JOINT':
        return 'P(V)'
    if op == 'MARGINAL':
        dropped = [v for v in expr.get('scope', []) if v not in expr['keep']]
        inner = render(expr['of'], depth + 1)
        return 'sum_{{{}}}({})'.format(','.join(dropped), inner) if dropped else inner
    if op == 'CONDITIONAL':
        given = ','.join(expr['given'])
        outcome = ','.join(expr['outcome'])
        return 'P({}{})'.format(outcome, '|' + given if given else '')
    if op == 'PRODUCT':
        parts = [render(o, depth + 1) for o in expr['operands']]
        return '(' + ' * '.join(parts) + ')'
    if op == 'SUM':
        inner = render(expr['operand'], depth + 1)
        return 'sum_{{{}}}({})'.format(','.join(expr['over']), inner) if expr['over'] else inner
    return str(op)


CASES = [
    (
        '1. back-door',
        'Z -> X, Z -> Y, X -> Y   (no unobserved confounding)',
        (['Z', 'X', 'Y'], [('Z', 'X'), ('Z', 'Y'), ('X', 'Y')], [], 'X', ['Y']),
    ),
    (
        '2. front-door',
        'X -> M -> Y, X <-> Y   (confounding, fully mediated)',
        (['X', 'M', 'Y'], [('X', 'M'), ('M', 'Y')], [('X', 'Y')], 'X', ['Y']),
    ),
    (
        '3. beyond every dedicated route',
        'X -> M1 -> Y, X -> M2 -> Y, X <-> Y   '
        '(two parallel mediators, and a direct unobserved common cause)',
        (['X', 'M1', 'M2', 'Y'],
         [('X', 'M1'), ('M1', 'Y'), ('X', 'M2'), ('M2', 'Y')],
         [('X', 'Y')], 'X', ['Y']),
    ),
    (
        '4. bow-arc',
        'X -> Y, X <-> Y   (confounding, no mediator)',
        (['X', 'Y'], [('X', 'Y')], [('X', 'Y')], 'X', ['Y']),
    ),
]


def main():
    for title, description, case in CASES:
        nodes, directed, bidirected, treatment, outcome = case
        problem = as_problem(nodes, directed, bidirected, treatment, outcome, context=title)
        print('=' * 72)
        print(title)
        print('graph      :', description)
        print('target     : P({} | do({}))'.format(','.join(outcome), treatment))
        if title.startswith('3.'):
            print('same graph, rewritten with one explicit latent per bidirected edge,')
            print('put to the three dedicated routes:')
            for route, verdict, note in dedicated_route_verdicts(
                    nodes, directed, bidirected, treatment, outcome):
                print('   {:<12} {:<9} {}'.format(route, verdict, note))


        result = identify_or_report(problem)
        if result['status'] != 'POINT':
            print('status     :', result['status'])
            print('reason     :', result['reason'])
            witness = result.get('witness') or {}
            if witness:
                print('evidence   : C(G) =', witness['c_components_of_graph'])
                print('             C(G\\X) =', witness['c_components_of_graph_minus_treatment'])
                hedge = witness.get('hedge') or {}
                if hedge:
                    print('hedge      : trimmed', hedge['trimmed_forest']['nodes'],
                          'inside grown', hedge['grown_forest']['nodes'],
                          '| roots', hedge['roots'])
                    print('             materialised:', witness['hedge_materialised'])
                check = check_failure(witness, problem)
                print('check      :', 'passed' if check['passed'] else 'FAILED')
                for item in (check.get('hedge') or {}).get('checks', []):
                    print('   {:<52} {}'.format(item['name'], 'ok' if item['passed'] else 'FAIL'))
                print('             means:', witness['means'])
            print()
            continue

        certificate = identify(problem)
        print('status     : POINT')
        print('formula    :', render(certificate['functional']))
        print('denominators:', certificate['positivity']['conditional_denominators'])
        print('steps      :')
        for step in certificate['derivation']:
            print('   line {} {:<44} {}'.format(step['line'], step['rule'], step['justification'][:60] + '...'))
        check = replay(certificate, problem)
        print('replay     :', 'passed' if check['passed'] else 'FAILED')
        for item in check['checks']:
            print('   {:<38} {}'.format(item['name'], 'ok' if item['passed'] else 'FAIL'))
        print()


if __name__ == '__main__':
    main()
