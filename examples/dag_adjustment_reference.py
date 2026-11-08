"""Frozen synthetic expectations for the opt-in DAG adjustment route."""
from cfm_id.dag_adjustment_contract import (
    AdjustmentProblem, AdjustmentReview, VERSION, DECISIONS, digest,
)
from examples.dag_backdoor_reference import make_problem as classical_problem


def make_problem(nodes=None, edges=None, latent=None, adjustment=None):
    # Reuse only the synthetic input factory, never its review or certificate.
    data = classical_problem(nodes, edges, latent, adjustment).model_dump()
    return AdjustmentProblem.model_validate({**data, 'version': VERSION})


def synthetic_review(problem):
    return AdjustmentReview(
        version=VERSION, problem_sha256=digest(problem),
        reviewer='Independent frozen synthetic reference',
        evidence='Graph and population conditions stipulated only for offline acceptance',
        authority='SYNTHETIC_TEST', decisions={k: 'ACCEPTED' for k in DECISIONS},
    )


def cases():
    # Freeze these expected outcomes before running either graphical algorithm.
    return [
        ('observed_confounder', make_problem(), 'POINT', ['Z']),
        ('unconfounded', make_problem(['X','Y'], [['X','Y']]), 'POINT', []),
        ('harmless_descendant', make_problem(
            ['X','Y','W'], [['X','Y'],['X','W']], adjustment=['W']), 'POINT', ['W']),
        ('confounder_and_harmless_descendant', make_problem(
            ['Z','X','Y','W'], [['Z','X'],['Z','Y'],['X','Y'],['X','W']],
            adjustment=['Z','W']), 'POINT', ['W','Z']),
        ('multilevel_harmless_descendant', make_problem(
            ['X','Y','W','D'], [['X','Y'],['X','W'],['W','D']],
            adjustment=['D']), 'POINT', ['D']),
        ('latent_path_blocked_observed', make_problem(
            ['U','Z','X','Y'], [['U','X'],['U','Z'],['Z','Y'],['X','Y']],
            ['U']), 'POINT', ['Z']),
        ('mediator_forbidden', make_problem(
            ['X','M','Y'], [['X','M'],['M','Y']], adjustment=['M']),
            'UNSUPPORTED', 'ADJUSTMENT_INTERSECTS_FORBIDDEN_SET'),
        ('mediator_descendant_forbidden', make_problem(
            ['X','M','Y','W'], [['X','M'],['M','Y'],['M','W']], adjustment=['W']),
            'UNSUPPORTED', 'ADJUSTMENT_INTERSECTS_FORBIDDEN_SET'),
        ('outcome_descendant_forbidden', make_problem(
            ['X','Y','W'], [['X','Y'],['Y','W']], adjustment=['W']),
            'UNSUPPORTED', 'ADJUSTMENT_INTERSECTS_FORBIDDEN_SET'),
        ('outgoing_collider_opened', make_problem(
            ['X','C','U','Y'], [['X','C'],['U','C'],['U','Y']], ['U'], ['C']),
            'UNSUPPORTED', 'SPECIFIED_SET_FAILS_DAG_ADJUSTMENT'),
        ('collider_opened', make_problem(
            ['X','Y','A','B','C'], [['A','X'],['A','C'],['B','C'],['B','Y'],['X','Y']],
            adjustment=['C']), 'UNSUPPORTED', 'SPECIFIED_SET_FAILS_DAG_ADJUSTMENT'),
        ('collider_descendant_opened', make_problem(
            ['X','Y','A','B','C','D'],
            [['A','X'],['A','C'],['B','C'],['B','Y'],['C','D'],['X','Y']],
            adjustment=['D']), 'UNSUPPORTED', 'SPECIFIED_SET_FAILS_DAG_ADJUSTMENT'),
        ('wrong_empty_adjustment', make_problem(adjustment=[]),
            'UNSUPPORTED', 'SPECIFIED_SET_FAILS_DAG_ADJUSTMENT'),
        ('hidden_confounder', make_problem(
            ['U','X','Y'], [['U','X'],['U','Y'],['X','Y']], ['U']),
            'UNSUPPORTED', 'NO_OBSERVED_DAG_ADJUSTMENT_SET'),
        ('outcome_parent_not_general_nonid', make_problem(
            ['X','Y'], [['Y','X']]), 'UNSUPPORTED', 'NO_OBSERVED_DAG_ADJUSTMENT_SET'),
        ('frontdoor_outside_adjustment', make_problem(
            ['U','X','M','Y'], [['U','X'],['U','Y'],['X','M'],['M','Y']], ['U']),
            'UNSUPPORTED', 'NO_OBSERVED_DAG_ADJUSTMENT_SET'),
    ]
