"""Contract for general identification over recursive semi-Markovian graphs.

Task 05 scope: acyclic directed mixed graphs (ADMG). Directed edges are causal
directions, bidirected edges stand for unobserved common causes. Variables are
finite and discrete; the observed joint law P(V) is given symbolically.

This module fixes shapes and sanity checks only. Ancestors, C-components and
the ID recursion live in ``dag_id_graph`` and ``dag_id_solver``.
"""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

VERSION = 'dag-id-1'
# Declared working range. The solver is cheap well beyond this, but the
# independent check evaluates the formula on every joint assignment, so 2**n
# is what actually costs time: at n = 12 that is 4096 rows per seed, which keeps
# a full replay under a second. Raising the bound means re-measuring that.
MAX_NODES = 12
# The independent check is what costs time, and its cost is exponential in the
# observed variables *and* in the latent ones: the oracle enumerates every
# assignment to V and every configuration of the unobserved common causes, so
# it walks 2 ** (n + b) rows, where b is the number of bidirected edges. A graph
# of six nodes with five bidirected edges is as expensive as a twelve-node graph
# with none, which is why the node count alone cannot decide the limit.
MAX_ENUMERATION_VARIABLES = 14

# Success and failure are different interfaces: never collapse them into one.
STATUSES = (
    'POINT',            # a formula was derived and certified
    'UNSUPPORTED',      # the evidence was checked against the graph: no uniform formula
    'NO_FORMULA_YET',   # the recursion stopped but the evidence did not check out,
                        # so the honest statement is "not derived yet" - a stage
                        # result, not a claim of non-identification
    'RESOURCE_LIMIT',   # the request exceeds the declared scale, nothing was computed
    'NEEDS_INPUT',      # a required declaration is missing (e.g. unconfirmed graph)
    'CHECK_BLOCKED',    # the request itself is malformed, or the run aborted early
)


class Unavailable(ValueError):
    """A problem that cannot be answered, with a machine-readable state."""

    def __init__(self, state, reason):
        self.state = state
        self.reason = reason
        super().__init__(reason)


def fail(state, reason):
    raise Unavailable(state, reason)


class DagIdProblem(BaseModel):
    """A declared graph plus a target intervention.

    ``outcome`` is a list because the target may be a joint distribution,
    e.g. P(Y1, Y2 | do(X)). ``treatment`` is a single variable.
    """

    model_config = ConfigDict(extra='forbid', strict=True, frozen=True)

    nodes: list[str] = Field(min_length=2)
    directed: list[list[str]]
    bidirected: list[list[str]]
    treatment: str
    outcome: list[str] = Field(min_length=1)
    context: str = ''

    def as_graph(self):
        return {
            'nodes': list(self.nodes),
            'directed': [tuple(e) for e in self.directed],
            'bidirected': [tuple(e) for e in self.bidirected],
        }


def _is_acyclic(nodes, directed):
    children = {n: set() for n in nodes}
    indegree = {n: 0 for n in nodes}
    for a, b in directed:
        children[a].add(b)
        indegree[b] += 1
    queue = [n for n in nodes if indegree[n] == 0]
    seen = 0
    while queue:
        n = queue.pop()
        seen += 1
        for c in children[n]:
            indegree[c] -= 1
            if indegree[c] == 0:
                queue.append(c)
    return seen == len(nodes)


def validate(problem):
    """Shape, identity and acyclicity checks. No identification reasoning."""
    if type(problem) is not DagIdProblem:
        fail('CHECK_BLOCKED', 'TYPED_DAG_ID_PROBLEM_REQUIRED')
    p = DagIdProblem.model_validate(problem.model_dump())

    if len(p.nodes) > MAX_NODES:
        # Kept out of UNSUPPORTED on purpose: an oversized graph is a request
        # that can be retried at a larger scale, while UNSUPPORTED is a
        # mathematical conclusion about the graph model. Merging the two would
        # let a caller report "not identifiable" for a problem never solved.
        fail('RESOURCE_LIMIT', 'NODE_COUNT_OUT_OF_RANGE')
    if len(set(p.nodes)) != len(p.nodes) or any(not n.strip() for n in p.nodes):
        fail('CHECK_BLOCKED', 'INVALID_NODE_IDENTITIES')

    nodes = set(p.nodes)
    if p.treatment not in nodes:
        fail('CHECK_BLOCKED', 'TREATMENT_NOT_IN_GRAPH')
    if not set(p.outcome) <= nodes:
        fail('CHECK_BLOCKED', 'OUTCOME_NOT_IN_GRAPH')
    if p.treatment in p.outcome:
        fail('CHECK_BLOCKED', 'TREATMENT_MUST_NOT_BE_AN_OUTCOME')
    if len(set(p.outcome)) != len(p.outcome):
        fail('CHECK_BLOCKED', 'DUPLICATE_OUTCOME')

    directed, seen = [], set()
    for edge in p.directed:
        if len(edge) != 2:
            fail('CHECK_BLOCKED', 'INVALID_DIRECTED_EDGE')
        a, b = edge
        if a not in nodes or b not in nodes or a == b:
            fail('CHECK_BLOCKED', 'INVALID_DIRECTED_EDGE')
        if (a, b) in seen:
            fail('CHECK_BLOCKED', 'DUPLICATE_DIRECTED_EDGE')
        seen.add((a, b))
        directed.append((a, b))

    bidirected, seen = [], set()
    for edge in p.bidirected:
        if len(edge) != 2:
            fail('CHECK_BLOCKED', 'INVALID_BIDIRECTED_EDGE')
        a, b = edge
        if a not in nodes or b not in nodes or a == b:
            fail('CHECK_BLOCKED', 'INVALID_BIDIRECTED_EDGE')
        key = tuple(sorted((a, b)))
        if key in seen:
            fail('CHECK_BLOCKED', 'DUPLICATE_BIDIRECTED_EDGE')
        seen.add(key)
        bidirected.append(key)

    if not _is_acyclic(p.nodes, directed):
        fail('CHECK_BLOCKED', 'DIRECTED_CYCLE_NOT_RECURSIVE_MODEL')

    if len(p.nodes) + len(bidirected) > MAX_ENUMERATION_VARIABLES:
        # Same state as the node cap, and for the same reason: the request is
        # answerable in principle but not at this scale. It must never surface
        # as a review problem or as a non-identification.
        fail('RESOURCE_LIMIT', 'MODEL_SIZE_OUT_OF_RANGE')

    return p


def as_problem(nodes, directed, bidirected, treatment, outcome, context=''):
    """Convenience constructor used by tests and the demo."""
    return DagIdProblem(
        nodes=list(nodes),
        directed=[list(e) for e in directed],
        bidirected=[list(e) for e in bidirected],
        treatment=treatment,
        outcome=list(outcome),
        context=context,
    )
