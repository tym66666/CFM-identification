"""Separate single-variable front-door contract; declarations are not approvals."""
from typing import Literal
from pydantic import Field
from .dag_backdoor_contract import (
    Record, PopulationLaw, BackdoorProblem, validate as validate_shape,
    DECISIONS, Unavailable, fail,
)
from cfm_id_bridge.scientific_binding import sha

VERSION = 'dag-frontdoor-1'
ROUTE = 'DAG_CLASSICAL_FRONTDOOR'
THEOREM = 'CLASSICAL_SINGLE_VARIABLE_FRONTDOOR_SUFFICIENT'
CLAIM_SCOPE = 'SUFFICIENT_POINT_ONLY_FOR_DECLARED_BINARY_SCM'


class FrontdoorProblem(Record):
    version: Literal['dag-frontdoor-1']
    model: Literal['RECURSIVE_SCM_EXPLICIT_LATENTS_INDEPENDENT_ERRORS']
    variable_domain: Literal['BINARY']
    nodes: list[str] = Field(min_length=2, max_length=100)
    observed: list[str]
    latent: list[str]
    edges: list[list[str]]
    graph_status: Literal['DECLARED', 'UNKNOWN']
    graph_source: str = Field(min_length=3, max_length=4000)
    materials_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    context: str = Field(min_length=3, max_length=4000)
    treatment: str | None
    outcome: str | None
    frontdoor_variable: str | None  # Required null explicitly permits singleton search.
    information: PopulationLaw
    additional_restrictions: list[str]


class FrontdoorReview(Record):
    version: Literal['dag-frontdoor-1']
    problem_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    reviewer: str = Field(min_length=3, max_length=300)
    evidence: str = Field(min_length=12, max_length=4000)
    authority: Literal['EXTERNAL_RESEARCH_REVIEW', 'SYNTHETIC_TEST']
    decisions: dict[str, Literal['ACCEPTED', 'PENDING', 'REJECTED']]


def validate(problem):
    if type(problem) is not FrontdoorProblem:
        fail('CHECK_BLOCKED', 'TYPED_FRONTDOOR_PROBLEM_REQUIRED')
    p = FrontdoorProblem.model_validate(problem.model_dump())
    if p.treatment is None or p.outcome is None:
        fail('NEEDS_INPUT', 'TREATMENT_AND_OUTCOME_REQUIRED')
    # Reuse only existing graph/SCM/population SHAPE validation. No adjustment
    # field is admitted in the front-door wire type, and no back-door rule runs.
    data = p.model_dump()
    data.pop('frontdoor_variable')
    data.update(version='dag-backdoor-1', adjustment=None)
    validate_shape(BackdoorProblem.model_validate(data))
    m = p.frontdoor_variable
    if m is not None:
        if m not in p.nodes:
            fail('CHECK_BLOCKED', 'UNKNOWN_FRONTDOOR_VARIABLE')
        if m not in p.observed or m in (p.treatment, p.outcome):
            fail('UNSUPPORTED', 'DISTINCT_OBSERVED_FRONTDOOR_VARIABLE_REQUIRED')
    return p


def digest(problem):
    return sha(problem)


def check_review(problem, review):
    if review is None:
        fail('REVIEW_REQUIRED', 'EXTERNAL_REVIEW_REQUIRED')
    if type(review) is not FrontdoorReview:
        fail('CHECK_BLOCKED', 'TYPED_FRONTDOOR_REVIEW_REQUIRED')
    r = FrontdoorReview.model_validate(review.model_dump())
    if r.problem_sha256 != digest(problem):
        fail('CHECK_BLOCKED', 'STALE_FRONTDOOR_REVIEW')
    if set(r.decisions) != set(DECISIONS):
        fail('CHECK_BLOCKED', 'EXACT_REVIEW_DECISIONS_REQUIRED')
    if 'REJECTED' in r.decisions.values():
        fail('CHECK_BLOCKED', 'SCIENTIFIC_CONDITION_REJECTED')
    if 'PENDING' in r.decisions.values():
        fail('REVIEW_REQUIRED', 'SCIENTIFIC_CONDITION_PENDING')
    return r

