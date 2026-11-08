"""Explicit, synthetic-only D2/E1 mean-order model; not a business router.

This is a new joint-constraint contract, never an old no-coupling declaration.
See docs/MEAN_ORDER_RESEARCH_ZH.txt and docs/MEAN_ORDER_BACKEND_ZH.txt.
"""
from typing import Literal
from pydantic import Field, field_validator, model_validator
from .bounded_policy_contract import StrictRecord, ExactMean, NodeBounds, Hash, Text, rational
from cfm_id_bridge.scientific_binding import sha

VERSION = 'mean-order-d2-e1-1'
SCOPE = 'ALL_BINARY_ASSIGNMENTS_CONDITIONAL_ON_STUDY_CONTEXT'
MODEL = 'SIGNATURE_MEANS_NODE_BOUNDS_AND_DECLARED_ORDERS_ONLY'
MAX_N = 12


class MeanOrderUnavailable(ValueError):
    def __init__(self, state, reason):
        self.state, self.reason = state, reason
        super().__init__(reason)


class NodeOrder(StrictRecord):
    node: str = Field(min_length=1, max_length=200)
    mode: Literal['NONE', 'OWN', 'PEERS', 'BOTH']


class MeanOrderProblem(StrictRecord):
    version: Literal['mean-order-d2-e1-1']
    model_scope: Literal['SIGNATURE_MEANS_NODE_BOUNDS_AND_DECLARED_ORDERS_ONLY']
    node_order: list[str] = Field(min_length=1, max_length=MAX_N)
    undirected_edges: list[list[str]]
    graph_scope: Literal['KNOWN_FIXED_PRETREATMENT_SIMPLE_UNDIRECTED']
    design: Literal['D2_UNIFORM_FIXED_QUOTA']
    quota: int = Field(ge=0, le=MAX_N)
    exposure: Literal['E1_STRICT_MAJORITY_TIES_LOW_ISOLATED_ZERO']
    context: Text
    treatment_definition: Text
    outcome_definition: Text
    outcome_kind: Literal['binary', 'continuous']
    outcome_unit: str = Field(min_length=1, max_length=4000)
    outcome_period: str = Field(min_length=1, max_length=4000)
    order_direction: Literal['NONDECREASING_NUMERIC_OUTCOME_MEAN']
    order_scope: Literal['ALL_BINARY_ASSIGNMENTS_CONDITIONAL_ON_STUDY_CONTEXT']
    node_orders: list[NodeOrder] = Field(min_length=1, max_length=MAX_N)
    randomization_claim: Literal['WHOLE_ASSIGNMENT_INDEPENDENT_OF_ALL_POTENTIAL_OUTCOMES_GIVEN_CONTEXT']
    consistency_claim: Literal['OBSERVED_OUTCOME_EQUALS_ASSIGNED_POTENTIAL_OUTCOME']
    moments_claim: Literal['FINITE_FIRST_MOMENTS']
    mean_sufficiency_scope: Literal['ALL_BINARY_ASSIGNMENTS_CONDITIONAL_ON_STUDY_CONTEXT']
    mean_sufficiency_claim: Literal['NODE_OWN_AND_E1_SIGNATURE_DETERMINES_CONDITIONAL_MEAN']
    information_scope: Literal['EXACT_LISTED_SIGNATURE_MEANS_ONLY']
    availability: Literal['EXACT_POPULATION_VALUE']
    values: list[ExactMean] = Field(min_length=1, max_length=4*MAX_N)
    a4_source: Text
    a4_provenance: Text
    bounds: list[NodeBounds] = Field(min_length=1, max_length=MAX_N)
    bounds_kind: Literal['CONDITIONAL_MEAN', 'ALMOST_SURE_OUTCOME']
    bounds_scope: Literal['ALL_BINARY_ASSIGNMENTS_CONDITIONAL_ON_STUDY_CONTEXT']
    bounds_provenance: Text
    first: list[int]
    second: list[int]
    weights: list[str]
    operation: Literal['FIRST_MINUS_SECOND']
    scientific_provenance: Text

    @model_validator(mode='after')
    def complete_coordinates(self):
        nodes = self.node_order
        if len(set(nodes)) != len(nodes) or any(not n.strip() or len(n) > 200 for n in nodes):
            raise ValueError('UNIQUE_NONBLANK_NODES_REQUIRED')
        if self.quota > len(nodes):
            raise ValueError('INVALID_QUOTA')
        edges = set()
        for e in self.undirected_edges:
            if len(e) != 2 or e[0] == e[1] or not set(e) <= set(nodes):
                raise ValueError('SIMPLE_UNDIRECTED_GRAPH_REQUIRED')
            key = frozenset(e)
            if key in edges:
                raise ValueError('DUPLICATE_UNDIRECTED_EDGE')
            edges.add(key)
        for rows in (self.bounds, self.node_orders):
            if len(rows) != len(nodes) or {r.node for r in rows} != set(nodes):
                raise ValueError('EXPLICIT_ALL_NODE_DECLARATIONS_REQUIRED')
        cells = [(v.node, v.own, v.exposure) for v in self.values]
        if len(cells) != len(set(cells)) or any(c[0] not in nodes for c in cells):
            raise ValueError('UNIQUE_SCOPED_A4_CELLS_REQUIRED')
        for z in (self.first, self.second):
            if len(z) != len(nodes) or any(type(a) is not int or a not in (0, 1) for a in z):
                raise ValueError('COMPLETE_BINARY_POLICIES_REQUIRED')
        if len(self.weights) != len(nodes):
            raise ValueError('COMPLETE_COMMON_WEIGHTS_REQUIRED')
        weights = [rational(w) for w in self.weights]
        if any(w < 0 for w in weights) or sum(weights) != 1:
            raise ValueError('NONNEGATIVE_NORMALIZED_WEIGHTS_REQUIRED')
        return self


class ReviewedMeanOrder(StrictRecord):
    version: Literal['mean-order-d2-e1-1']
    problem_sha256: Hash
    reviewer: Text
    evidence: Text
    reviewed_target_direction_population: Literal[True]
    reviewed_complete_a4_and_no_unmodeled_constraints: Literal[True]
    reviewed_base_assumptions_and_all_arrangement_scope: Literal[True]
    reviewed_bounds_and_each_order_axis: Literal[True]
    synthetic_fixture: Literal[True]

    @field_validator('reviewed_target_direction_population',
        'reviewed_complete_a4_and_no_unmodeled_constraints',
        'reviewed_base_assumptions_and_all_arrangement_scope',
        'reviewed_bounds_and_each_order_axis', 'synthetic_fixture', mode='before')
    @classmethod
    def explicit_true(cls, value):
        if type(value) is not bool or value is not True:
            raise ValueError('EXPLICIT_SEPARATE_SYNTHETIC_REVIEW_REQUIRED')
        return value


def validate(problem):
    if type(problem) is not MeanOrderProblem:
        raise ValueError('TYPED_MEAN_ORDER_PROBLEM_REQUIRED')
    # Frozen Pydantic records can still contain mutated nested lists.
    return MeanOrderProblem.model_validate(problem.model_dump())


def input_digest(problem):
    return sha(dict(version=VERSION, problem=problem.model_dump()))
