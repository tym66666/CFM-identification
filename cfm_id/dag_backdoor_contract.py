"""Finite classical back-door research contract. Declarations are not approvals."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator
from cfm_id_bridge.scientific_binding import sha

VERSION='dag-backdoor-1'
ROUTE='DAG_CLASSICAL_BACKDOOR'
MAX_N=8
DECISIONS=('target_and_variable_roles','complete_causal_graph_and_latents',
           'recursive_scm_and_perfect_intervention','population_law_and_strict_positivity')


class Record(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True,frozen=True)

    @field_validator('*')
    @classmethod
    def nonblank(cls,value):
        if type(value) is str and not value.strip():raise ValueError('NONBLANK_DECLARATION_REQUIRED')
        return value


class PopulationLaw(Record):
    source_id: str = Field(min_length=1,max_length=300)
    source_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    variables: list[str]
    availability: Literal['SYMBOLIC_POPULATION_LAW','FINITE_SAMPLE','MARGINALS_ONLY','UNKNOWN']
    strictly_positive_joint: bool | None
    provenance: str = Field(min_length=12,max_length=4000)


class BackdoorProblem(Record):
    version: Literal['dag-backdoor-1']
    model: Literal['RECURSIVE_SCM_EXPLICIT_LATENTS_INDEPENDENT_ERRORS']
    variable_domain: Literal['BINARY']
    nodes: list[str] = Field(min_length=2,max_length=100)
    observed: list[str]
    latent: list[str]
    edges: list[list[str]]
    graph_status: Literal['DECLARED','UNKNOWN']
    graph_source: str = Field(min_length=3,max_length=4000)
    materials_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    context: str = Field(min_length=3,max_length=4000)
    treatment: str
    outcome: str
    adjustment: list[str] | None  # None = search; [] = explicitly no adjustment.
    information: PopulationLaw
    additional_restrictions: list[str]


class BackdoorReview(Record):
    version: Literal['dag-backdoor-1']
    problem_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    reviewer: str = Field(min_length=3,max_length=300)
    evidence: str = Field(min_length=12,max_length=4000)
    authority: Literal['EXTERNAL_RESEARCH_REVIEW','SYNTHETIC_TEST']
    decisions: dict[str,Literal['ACCEPTED','PENDING','REJECTED']]


class Unavailable(ValueError):
    def __init__(self,state,reason):
        self.state,self.reason=state,reason
        super().__init__(reason)


def fail(state,reason):raise Unavailable(state,reason)


def validate(problem):
    """Shared shape/domain validation; no adjustment or d-separation algorithm."""
    if type(problem) is not BackdoorProblem:fail('CHECK_BLOCKED','TYPED_DAG_PROBLEM_REQUIRED')
    p=BackdoorProblem.model_validate(problem.model_dump())
    if len(p.nodes)>MAX_N:fail('UNSUPPORTED','DAG_REPLAY_RESOURCE_LIMIT')
    if len(set(p.nodes))!=len(p.nodes) or any(not x.strip() or len(x)>200 for x in p.nodes):
        fail('CHECK_BLOCKED','INVALID_NODE_IDENTITIES')
    obs,lat=set(p.observed),set(p.latent)
    if len(obs)!=len(p.observed) or len(lat)!=len(p.latent) or obs&lat or obs|lat!=set(p.nodes):
        fail('CHECK_BLOCKED','OBSERVED_LATENT_PARTITION_REQUIRED')
    if p.treatment==p.outcome or not {p.treatment,p.outcome}<=obs:
        fail('UNSUPPORTED','DISTINCT_OBSERVED_SINGLE_TREATMENT_OUTCOME_REQUIRED')
    if p.graph_status!='DECLARED':fail('NEEDS_INPUT','CAUSAL_GRAPH_NOT_DECLARED')
    if p.additional_restrictions:fail('UNSUPPORTED','ADDITIONAL_MODEL_RESTRICTIONS_NOT_ADAPTED')
    edges=set()
    children={n:set() for n in p.nodes};degree={n:0 for n in p.nodes}
    for edge in p.edges:
        if len(edge)!=2 or not set(edge)<=set(p.nodes) or edge[0]==edge[1] or tuple(edge) in edges:
            fail('CHECK_BLOCKED','INVALID_DIRECTED_EDGE')
        a,b=edge;edges.add((a,b));children[a].add(b);degree[b]+=1
    queue=[n for n in p.nodes if degree[n]==0];count=0
    while queue:
        n=queue.pop();count+=1
        for c in children[n]:
            degree[c]-=1
            if degree[c]==0:queue.append(c)
    if count!=len(p.nodes):fail('CHECK_BLOCKED','DIRECTED_CYCLE')
    if p.adjustment is not None:
        if len(set(p.adjustment))!=len(p.adjustment):fail('CHECK_BLOCKED','DUPLICATE_ADJUSTMENT_VARIABLE')
        if not set(p.adjustment)<=obs or set(p.adjustment)&{p.treatment,p.outcome}:
            fail('UNSUPPORTED','OBSERVED_DISJOINT_ADJUSTMENT_REQUIRED')
    law=p.information
    if law.availability!='SYMBOLIC_POPULATION_LAW':fail('NEEDS_INPUT','FULL_SYMBOLIC_POPULATION_LAW_REQUIRED')
    if set(law.variables)!=obs or len(law.variables)!=len(obs):fail('NEEDS_INPUT','COMPLETE_OBSERVED_JOINT_LAW_REQUIRED')
    if law.strictly_positive_joint is None:fail('NEEDS_INPUT','POPULATION_POSITIVITY_UNDECLARED')
    if law.strictly_positive_joint is not True:fail('UNSUPPORTED','NONPOSITIVE_LAW_NOT_ADAPTED')
    return p


def digest(problem):return sha(problem)


def check_review(problem,review):
    if review is None:fail('REVIEW_REQUIRED','EXTERNAL_REVIEW_REQUIRED')
    if type(review) is not BackdoorReview:fail('CHECK_BLOCKED','TYPED_DAG_REVIEW_REQUIRED')
    r=BackdoorReview.model_validate(review.model_dump())
    if r.problem_sha256!=digest(problem):fail('CHECK_BLOCKED','STALE_DAG_REVIEW')
    if set(r.decisions)!=set(DECISIONS):fail('CHECK_BLOCKED','EXACT_REVIEW_DECISIONS_REQUIRED')
    if 'REJECTED' in r.decisions.values():fail('CHECK_BLOCKED','SCIENTIFIC_CONDITION_REJECTED')
    if 'PENDING' in r.decisions.values():fail('REVIEW_REQUIRED','SCIENTIFIC_CONDITION_PENDING')
    return r
