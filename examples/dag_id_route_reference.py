"""Reference fixtures for the task 05 business entry.

These graphs come from the paper and from this repository's own examples. They
exist to exercise the code path, not to answer a business question: the task
explicitly forbids using a co-occurrence network in place of a causal graph that
a researcher has confirmed. Replace the fixture, do not relax the gate.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cfm_id.dag_backdoor_contract import DECISIONS
from cfm_id.dag_id_route import GeneralIdProblem, GeneralIdReview, digest

CASES = {
    # Beyond back-door and front-door: Z confounds X and Y, X is confounded with
    # Y directly, and the effect also runs through M.
    'mixed': dict(
        nodes=['Z', 'X', 'M', 'Y'],
        directed=[['Z', 'X'], ['Z', 'Y'], ['X', 'M'], ['M', 'Y']],
        bidirected=[['X', 'Y']],
        context='Mixed graph: back-door fails on X<->Y, front-door fails on Z->Y.',
    ),
    # The canonical non-identifiable graph.
    'bowarc': dict(
        nodes=['X', 'Y'],
        directed=[['X', 'Y']],
        bidirected=[['X', 'Y']],
        context='Bow arc: no mediator, so no uniform formula exists.',
    ),
}


def make_problem(case='mixed'):
    return GeneralIdProblem(
        version='dag-general-id-1', model='RECURSIVE_SEMI_MARKOVIAN_DISCRETE',
        treatment='X', outcome=['Y'],
        graph_status='RESEARCHER_CONFIRMED',
        graph_source='reference example shipped with the task 05 tests',
        materials_sha256='0' * 64, **CASES[case],
    )


def synthetic_review(problem, decisions=None, authority='SYNTHETIC_TEST'):
    """A review record for tests only; never a claim that a researcher approved."""
    return GeneralIdReview(
        version='dag-general-id-1', problem_sha256=digest(problem),
        reviewer='synthetic test reviewer',
        evidence='synthetic review used only by tests, not a research opinion',
        authority=authority,
        decisions=decisions or {name: 'ACCEPTED' for name in DECISIONS},
    )


def main():
    from cfm_id.dag_id_route import DagGeneralIdRoute
    from cfm_id.research_route_workflow import run_route

    for case in CASES:
        problem = make_problem(case)
        result = run_route(DagGeneralIdRoute(), problem, review=synthetic_review(problem),
                           research_protocol_selected=True)
        print('=' * 72)
        print(case)
        print('state        :', result['state'])
        print('reason       :', result.get('reason_code'))
        print('replay       :', result['independent_replay'])
        certificate = result.get('certificate')
        if certificate:
            print('formula      :', certificate['functional']['operation'])
        witness = (result.get('native_result') or {}).get('witness')
        if witness:
            print('hedge        :', witness['hedge']['trimmed_forest']['nodes'],
                  'inside', witness['hedge']['grown_forest']['nodes'],
                  '| materialised:', witness['hedge_materialised'])


if __name__ == '__main__':
    main()
