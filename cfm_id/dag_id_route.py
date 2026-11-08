"""Business entry for task 05: general identification over recursive semi-Markovian graphs.

This module is the adapter described by ``docs/EXTENSION_MAINTENANCE_ZH.md`` for
"已有数学能力接共同入口": a problem contract, a review contract, and
``prepare`` / ``submit`` that a dispatch layer can call. It is deliberately not
registered in ``capability_registry`` -- that registry is closed and owned by the
route maintainer, so the registration patch lives in
``docs/DAG_ID_INTEGRATION_ZH.md`` instead of being applied here.

Two gates run before any mathematics:

1. the graph must be declared as researcher-confirmed; a graph with an unknown
   provenance is refused with ``NEEDS_INPUT`` rather than guessed at, because a
   co-occurrence network is not a variable causal graph;
2. every scientific condition must be accepted by a typed review bound to this
   exact problem, so a stale or partial approval cannot reach the solver.
"""
from typing import Literal

from pydantic import Field

from cfm_id_bridge.scientific_binding import sha

from .research_route_workflow import RouteCapability

from .dag_backdoor_contract import DECISIONS, Record, Unavailable, fail
from .dag_id_contract import Unavailable as MathUnavailable
from .dag_id_contract import as_problem, validate as validate_math
from .dag_id_solver import identify_or_report

VERSION = 'dag-general-id-1'
ROUTE = 'DAG_GENERAL_ID'
THEOREM = 'SHPITSER_PEARL_2006_ID'
CLAIM_SCOPE = 'POINT_ONLY_FOR_DECLARED_RECURSIVE_SEMI_MARKOVIAN_GRAPH'


class GeneralIdProblem(Record):
    """A declared graph plus the information the formula may use."""

    version: Literal['dag-general-id-1']
    model: Literal['RECURSIVE_SEMI_MARKOVIAN_DISCRETE']
    nodes: list[str] = Field(min_length=2)
    directed: list[list[str]]
    bidirected: list[list[str]]
    treatment: str
    outcome: list[str] = Field(min_length=1)
    graph_status: Literal['RESEARCHER_CONFIRMED', 'UNKNOWN']
    graph_source: str = Field(min_length=3, max_length=4000)
    materials_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    context: str = Field(min_length=3, max_length=4000)


class GeneralIdReview(Record):
    version: Literal['dag-general-id-1']
    problem_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    reviewer: str = Field(min_length=3, max_length=300)
    evidence: str = Field(min_length=12, max_length=4000)
    authority: Literal['EXTERNAL_RESEARCH_REVIEW', 'SYNTHETIC_TEST']
    decisions: dict[str, Literal['ACCEPTED', 'PENDING', 'REJECTED']]


def digest(problem):
    return sha(problem)


def to_math_problem(problem):
    """Project the business contract onto the mathematics; nothing else is passed."""
    return as_problem(
        list(problem.nodes), [tuple(e) for e in problem.directed],
        [tuple(e) for e in problem.bidirected], problem.treatment,
        list(problem.outcome), problem.context,
    )


def validate(problem):
    if isinstance(problem, dict):
        p = GeneralIdProblem.model_validate(problem)
    elif type(problem) is GeneralIdProblem:
        p = GeneralIdProblem.model_validate(problem.model_dump())
    else:
        fail('CHECK_BLOCKED', 'TYPED_GENERAL_ID_PROBLEM_REQUIRED')
    if p.graph_status != 'RESEARCHER_CONFIRMED':
        fail('NEEDS_INPUT', 'GRAPH_NOT_CONFIRMED_BY_RESEARCHER')
    return p


def check_review(problem, review):
    if review is None:
        fail('REVIEW_REQUIRED', 'EXTERNAL_REVIEW_REQUIRED')
    if isinstance(review, dict):
        r = GeneralIdReview.model_validate(review)
    elif type(review) is GeneralIdReview:
        r = GeneralIdReview.model_validate(review.model_dump())
    else:
        fail('CHECK_BLOCKED', 'TYPED_GENERAL_ID_REVIEW_REQUIRED')
    if r.problem_sha256 != digest(problem):
        fail('CHECK_BLOCKED', 'STALE_GENERAL_ID_REVIEW')
    if set(r.decisions) != set(DECISIONS):
        fail('CHECK_BLOCKED', 'EXACT_REVIEW_DECISIONS_REQUIRED')
    if 'REJECTED' in r.decisions.values():
        fail('CHECK_BLOCKED', 'SCIENTIFIC_CONDITION_REJECTED')
    if 'PENDING' in r.decisions.values():
        fail('REVIEW_REQUIRED', 'SCIENTIFIC_CONDITION_PENDING')
    return r


def solve(problem):
    """The only call into the mathematics; kept separate so it can be patched."""
    return identify_or_report(problem)


def prepare(problem):
    """Report what is missing, or return the worksheet a reviewer must sign."""
    try:
        p = validate(problem)
        math_problem = to_math_problem(p)
        validate_math(math_problem)
    except (Unavailable, MathUnavailable) as error:
        return dict(state=error.state, reason_code=error.reason)
    return dict(
        state='REVIEW_REQUIRED',
        reason_code=None,
        worksheet={
            'problem_sha256': digest(p),
            'decisions': list(DECISIONS),
            'graph_status': p.graph_status,
            'graph_source': p.graph_source,
            'treatment': p.treatment,
            'outcome': list(p.outcome),
            'scope': {'model': 'RECURSIVE_SEMI_MARKOVIAN', 'variables': 'FINITE_DISCRETE',
                      'partial_identification': False, 'counterfactuals': False},
        },
        proposed_problem=math_problem.model_dump(),
    )


def submit(problem, review):
    """Run the ID algorithm only after the reviews are accepted and bound."""
    result = prepare(problem)
    if result['state'] != 'REVIEW_REQUIRED':
        # Every exit states these explicitly: a research route never promotes
        # itself to production and never hands an estimate downstream.
        return dict(result, production_admission=False, estimation_handoff_allowed=False)
    try:
        p = validate(problem)
        r = check_review(p, review)
        math_problem = to_math_problem(p)
        report = solve(math_problem)
        if report.get('status') == 'POINT':
            from .dag_id_verify import replay
            if replay(report, math_problem)['passed'] is not True:
                fail('CHECK_BLOCKED', 'INDEPENDENT_REPLAY_FAILED')
            return dict(state='POINT', reason_code=None, certificate=report,
                        review_authority=r.authority, backend_called=True,
                        production_admission=False, estimation_handoff_allowed=False)
        # Non-identification is a result, not an error: keep the evidence.
        return dict(state=report.get('status', 'CHECK_BLOCKED'),
                    reason_code=report.get('reason'), witness=report.get('witness'),
                    review_authority=r.authority, backend_called=True,
                    production_admission=False, estimation_handoff_allowed=False)
    except (Unavailable, MathUnavailable) as error:
        return dict(state=error.state, reason_code=error.reason,
                    production_admission=False, estimation_handoff_allowed=False)


class DagGeneralIdRoute:
    """Adapter shape used by ``research_route_workflow.run_route``."""

    capability = RouteCapability(
        ROUTE, 'STATIC_CAUSAL_DAG', 'INTERVENTIONAL_DISTRIBUTION',
        'FULL_SYMBOLIC_OBSERVED_LAW', 'GENERAL_ID_ALGORITHM_CERTIFICATE',
        'Recursive semi-Markovian graph, finite discrete variables, at most twelve '
        'nodes, researcher-confirmed graph, reviewed positive observed law; POINT or '
        'verified non-identification; research only.')

    def prepare(self, problem):
        return prepare(problem)

    def submit(self, problem, review):
        return submit(problem, review)

    def certificate(self, result):
        return result.get('certificate')

    def replay(self, problem, certificate):
        from .dag_id_verify import replay as replay_math
        return replay_math(certificate, to_math_problem(validate(problem)))['passed']

    def claim(self, certificate):
        return dict(kind='POINT', representation='OBSERVED_DISTRIBUTION_FUNCTIONAL',
                    target=certificate['target'], functional=certificate['functional'],
                    numeric_value=None)

    def verify_claim(self, certificate, claim):
        expected = dict(kind='POINT', representation='OBSERVED_DISTRIBUTION_FUNCTIONAL',
                        target=certificate['target'], functional=certificate['functional'],
                        numeric_value=None)
        return certificate['status'] == 'POINT' and sha(claim) == sha(expected)
