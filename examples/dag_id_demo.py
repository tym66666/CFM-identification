"""Task 05 walkthrough: three graphs, the formula each one yields, and the check.

Run from the repository root:

    python examples/dag_id_demo.py

The point of the demo is the *shape* of the answer.  A formula that is only
pretty-printed cannot be checked; the tree printed here is the same object the
independent replay evaluates against a freshly generated structural model.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cfm_id.dag_id_contract import as_problem
from cfm_id.dag_id_solver import identify, identify_or_report
from cfm_id.dag_id_verify import check_failure, replay


def render(expr, depth=0):
    op = expr['operation']
    if op == 'OBSERVED_JOINT':
        return 'P(V)'
    if op == 'MARGINAL':
        return 'P_{{{}}}({})'.format(','.join(expr['keep']), render(expr['of'], depth + 1))
    if op == 'CONDITIONAL':
        given = ','.join(expr['given'])
        outcome = ','.join(expr['outcome'])
        return 'P({}{})'.format(outcome, '|' + given if given else '')
    if op == 'PRODUCT':
        parts = [render(o, depth + 1) for o in expr['operands']]
        return '(' + ' * '.join(parts) + ')'
    if op == 'SUM':
        return 'sum_{{{}}} {}'.format(','.join(expr['over']) or 'none', render(expr['operand'], depth + 1))
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
        '3. bow-arc',
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
