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
   exact problem, so a stale or partial approval cannot reach the solver; and
   every undecided item and unexpressed restriction the material left open must
   be answered by that review item by item, with a stated reason -- "accept"
   is not an answer.
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

# The shared research entry knows four stop states. Two of this route's states
# have no word there: RESOURCE_LIMIT and NO_FORMULA_YET. Letting them through
# unchanged does not fail loudly -- run_route reads them as "not a stop, not a
# proof" and rewrites the outcome to CHECK_BLOCKED /
# MISSING_TYPED_MATHEMATICAL_EVIDENCE, which tells the user the run was
# malformed when it was really out of range. Until the shared vocabulary grows
# (proposed in docs/DAG_ID_INTEGRATION_ZH.md section 4), the state is carried in
# the reason code and in ``native_state``, and the envelope says the run stopped
# early, which is true for both.
SHARED_STOP_STATES = ('NEEDS_INPUT', 'REVIEW_REQUIRED', 'UNSUPPORTED', 'CHECK_BLOCKED')


def _for_shared_entry(result):
    """Preserve the real stop cause when the shared vocabulary has no word for it."""
    state = result.get('state')
    if state in SHARED_STOP_STATES or state == 'POINT':
        return result
    reason = result.get('reason_code')
    return dict(result, state='CHECK_BLOCKED', native_state=state,
                reason_code='{}:{}'.format(state, reason) if reason else state)


class ReadClaim(Record):
    value: bool | None
    source_ids: list[str]


class ReadVariable(Record):
    name: str
    observation: Literal['OBSERVED', 'LATENT', 'UNKNOWN']
    domain: Literal['BINARY', 'FINITE_DISCRETE', 'OTHER', 'UNKNOWN']
    source_ids: list[str]


SCOPE_DECLARATIONS = ('static_acyclic', 'graph_complete', 'latent_causes_accounted',
                      'independent_errors', 'perfect_intervention',
                      'no_between_unit_interference')


class ReadingDeclarations(Record):
    """Source-bound declarations, not a scientific approval.

    The adapter fills these from the actual reading, never from route defaults.
    The complete candidate also stays in the problem digest for provenance and
    review; the model is not asked to fill this second representation.
    """
    variables: list[ReadVariable]
    scope: dict[str, ReadClaim | None]
    information_variables: list[str]
    information_source_ids: list[str]
    positivity: ReadClaim
    candidate: dict


class GeneralIdProblem(Record):
    """A declared graph plus the information the formula may use.

    ``information``, ``unresolved`` and ``additional_restrictions`` are not
    decoration. A reading layer that drops them lets an incomplete material
    reach the solver, where the only remaining gate is the review -- and a
    review that accepts everything turns "the outcome measure is undecided"
    into a formula about a variable that was never defined. They are required
    here so the decision to ignore them has to be made explicitly.
    """

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
    information: Literal['FULL_JOINT_POPULATION_LAW', 'FINITE_SAMPLE',
                         'MARGINAL_STATISTICS', 'UNKNOWN']
    reading_declarations: ReadingDeclarations | None = None
    unresolved: list[str] = Field(
        description='材料本身的事实缺项、矛盾或未定项；交审核逐条回应，不自动放行。')
    additional_restrictions: list[str] = Field(
        description='材料另外提出、契约尚未表达的约束；交审核逐条回应，不自动放行。')


class UnresolvedResponse(Record):
    """The review's answer to one unresolved item, in the item's own words.

    ``item`` must quote the problem's unresolved entry verbatim, so a review
    cannot quietly answer a different question than the one the material asked.
    """

    item: str = Field(min_length=2)
    decision: Literal['RESOLVED', 'UNRESOLVED']
    reason: str = Field(min_length=8, max_length=2000)


class GeneralIdReview(Record):
    version: Literal['dag-general-id-1']
    problem_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    reviewer: str = Field(min_length=3, max_length=300)
    evidence: str = Field(min_length=12, max_length=4000)
    authority: Literal['EXTERNAL_RESEARCH_REVIEW', 'SYNTHETIC_TEST']
    decisions: dict[str, Literal['ACCEPTED', 'PENDING', 'REJECTED']]
    unresolved_responses: list[UnresolvedResponse] = Field(default_factory=list)
    restriction_responses: list[UnresolvedResponse] = Field(default_factory=list)


def digest(problem):
    return sha(problem)


def to_math_problem(problem):
    """Project the business contract onto the mathematics; nothing else is passed."""
    return as_problem(
        list(problem.nodes), [tuple(e) for e in problem.directed],
        [tuple(e) for e in problem.bidirected], problem.treatment,
        list(problem.outcome), problem.context,
    )


def _stop_with_items(state, reason, items):
    error = Unavailable(state, reason)
    error.items = [item for item in items if item]
    raise error


def check_reading_declarations(problem):
    """Known contradictions/missing declarations cannot be approved away.

    Legacy directly constructed problems explicitly select the finite model
    and still need an external review. A reading-based problem MUST carry the
    declarations via to_problem; None is not used by the reading adapter.
    """
    d = problem.reading_declarations
    if d is None:
        return
    candidate = d.candidate
    variables = [v.model_dump() for v in d.variables]
    scope = {k: v.model_dump() if v is not None else None for k, v in d.scope.items()}
    ci = candidate.get('information') or {}
    mapped_info = {'MARGINALS_ONLY': 'MARGINAL_STATISTICS'}.get(ci.get('kind'), ci.get('kind'))
    target = candidate.get('target') or {}
    observed = [v.name for v in d.variables if v.observation == 'OBSERVED']
    direct = sorted((r['cause'], r['effect']) for r in candidate.get('relations', [])
                    if r['kind'] == 'DIRECT_CAUSE')
    common = sorted(tuple(sorted((r['first'], r['second'])))
                    for r in candidate.get('common_causes', []))
    if (candidate.get('variables') != variables or candidate.get('scope') != scope
            or ci.get('variables') != d.information_variables
            or ci.get('source_ids') != d.information_source_ids
            or ci.get('positivity') != d.positivity.model_dump()
            or mapped_info != problem.information
            or observed != problem.nodes
            or direct != sorted(map(tuple, problem.directed))
            or common != sorted(tuple(sorted(e)) for e in problem.bidirected)
            or target.get('kind') != 'INTERVENTIONAL_DISTRIBUTION'
            or target.get('treatment') != problem.treatment
            or [target.get('outcome')] != problem.outcome
            or (target.get('context') or 'material-declared study population') != problem.context
            or [n['text'] for n in candidate.get('unresolved', [])] != problem.unresolved
            or [n['text'] for n in candidate.get('additional_restrictions', [])] != problem.additional_restrictions):
        fail('CHECK_BLOCKED', 'READING_PROBLEM_MISMATCH')
    if any(v.observation == 'UNKNOWN' for v in d.variables):
        fail('NEEDS_INPUT', 'VARIABLE_OBSERVATION_UNKNOWN')
    # Latent variables are projected into common causes and are not arguments
    # of the observed law. The finite-domain gate applies to observed variables.
    if any(v.domain not in ('BINARY', 'FINITE_DISCRETE')
           for v in d.variables if v.observation == 'OBSERVED'):
        fail('NEEDS_INPUT', 'FINITE_DISCRETE_DOMAIN_NOT_DECLARED')
    if any(r['kind'] == 'UNCERTAIN' for r in candidate.get('relations', [])):
        fail('NEEDS_INPUT', 'UNCERTAIN_CAUSAL_RELATION')
    if candidate.get('adjustment') is not None:
        fail('UNSUPPORTED', 'REQUESTED_ADJUSTMENT_NOT_SUPPORTED_BY_GENERAL_ID')
    for name in SCOPE_DECLARATIONS:
        claim = d.scope.get(name)
        if claim is None or claim.value is None:
            _stop_with_items('NEEDS_INPUT', 'SCOPE_DECLARATION_MISSING:' + name,
                             ['请明确本研究是否采用条件：' + name])
        if claim.value is False:
            fail('UNSUPPORTED', 'DECLARED_SCOPE_NOT_SATISFIED:' + name)
        if not claim.source_ids:
            fail('CHECK_BLOCKED', 'SCOPE_SOURCE_MISSING:' + name)
    if (len(set(d.information_variables)) != len(d.information_variables)
            or set(d.information_variables) != set(problem.nodes)):
        fail('NEEDS_INPUT', 'POPULATION_LAW_VARIABLE_COVERAGE_MISMATCH')
    if d.positivity.value is None:
        fail('NEEDS_INPUT', 'POSITIVITY_NOT_DECLARED')
    if d.positivity.value is False:
        fail('UNSUPPORTED', 'DECLARED_POSITIVITY_NOT_SATISFIED')
    if not d.information_source_ids or not d.positivity.source_ids or any(
            not v.source_ids for v in d.variables):
        fail('CHECK_BLOCKED', 'DECLARATION_SOURCE_MISSING')


def validate(problem):
    if isinstance(problem, dict):
        p = GeneralIdProblem.model_validate(problem)
    elif type(problem) is GeneralIdProblem:
        p = GeneralIdProblem.model_validate(problem.model_dump())
    else:
        fail('CHECK_BLOCKED', 'TYPED_GENERAL_ID_PROBLEM_REQUIRED')
    if p.graph_status != 'RESEARCHER_CONFIRMED':
        fail('NEEDS_INPUT', 'GRAPH_NOT_CONFIRMED_BY_RESEARCHER')
    # What the reading layer saw has to survive the trip to the review. A
    # sample table is not a population law: that stops here, before any
    # reviewer can be asked about it, because no answer can turn sample
    # statistics into the population law the formula reads. Everything else
    # the material left open -- undecided items and restrictions the contract
    # does not express -- is a question for the reviewer, not a blocker; the
    # review must answer each one explicitly (see ``check_review``). Not every
    # note a model writes down blocks identification: "treatment was not
    # randomly assigned" is true and irrelevant, because do-calculus exists
    # precisely for observational data.
    if p.information != 'FULL_JOINT_POPULATION_LAW':
        _stop_with_items('NEEDS_INPUT', 'INFORMATION_IS_NOT_A_POPULATION_LAW',
                         ['请明确可用的完整观测联合总体分布：' + p.information
                          + ' 不能替代总体联合分布。'])
    check_reading_declarations(p)
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
    # An undecided item is a question, and "accept" is not an answer. Every
    # item the material left open -- both ``unresolved`` notes and
    # ``additional_restrictions`` -- must be addressed by quoting it verbatim,
    # with a stated reason; anything still marked UNRESOLVED stops the run.
    # This is what keeps a blanket approval from turning an undefined outcome
    # into a formula about it. The computation itself is fixed by the confirmed
    # graph and the population law; a restriction cannot change it, it can only
    # signal that the material claims something the contract does not express,
    # which is exactly what the reviewer is here to explain or to refuse.
    items = list(problem.unresolved)
    stated = [response.item for response in r.unresolved_responses]
    if sorted(stated) != sorted(items):
        fail('CHECK_BLOCKED', 'UNRESOLVED_ITEMS_NEED_EXPLICIT_REVIEW_DECISIONS')
    open_items = [response.item for response in r.unresolved_responses
                  if response.decision == 'UNRESOLVED']
    if open_items:
        _stop_with_items('NEEDS_INPUT', 'UNRESOLVED_MATERIAL_ITEMS', open_items)
    restrictions = list(problem.additional_restrictions)
    stated_r = [response.item for response in r.restriction_responses]
    if sorted(stated_r) != sorted(restrictions):
        fail('CHECK_BLOCKED', 'ADDITIONAL_RESTRICTIONS_NEED_EXPLICIT_REVIEW_DECISIONS')
    open_restrictions = [response.item for response in r.restriction_responses
                         if response.decision == 'UNRESOLVED']
    if open_restrictions:
        _stop_with_items('NEEDS_INPUT', 'ADDITIONAL_RESTRICTIONS_NOT_EXPRESSED',
                         open_restrictions)
    # An acknowledgment cannot insert a new mathematical restriction into
    # this graph-only solver. Revise/bind an expressible problem separately.
    if restrictions:
        _stop_with_items('NEEDS_INPUT', 'ADDITIONAL_RESTRICTIONS_NOT_EXPRESSED', restrictions)
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
        items = list(getattr(error, 'items', []) or [])
        return _for_shared_entry(dict(
            state=error.state, reason_code=error.reason,
            worksheet={'clarification_questions': items} if items else None))
    return _for_shared_entry(dict(
        state='REVIEW_REQUIRED',
        reason_code=None,
        worksheet={
            'problem_sha256': digest(p),
            'decisions': list(DECISIONS),
            'graph_status': p.graph_status,
            'graph_source': p.graph_source,
            'treatment': p.treatment,
            'outcome': list(p.outcome),
            'information': p.information,
            'reading_declarations': (p.reading_declarations.model_dump()
                                     if p.reading_declarations is not None else None),
            'unresolved': list(p.unresolved),
            'additional_restrictions': list(p.additional_restrictions),
            'clarification_questions': [],
            'scope': {'model': 'RECURSIVE_SEMI_MARKOVIAN', 'variables': 'FINITE_DISCRETE',
                      'partial_identification': False, 'counterfactuals': False},
        },
        proposed_problem=math_problem.model_dump(),
    ))


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
        # Non-identification is a result, not an error: keep the evidence. The
        # evidence is checked here as well, at the boundary the caller actually
        # sees, so an UNSUPPORTED never travels on the solver's word alone. A
        # witness that does not check out is downgraded to NO_FORMULA_YET - the
        # run stopped, and nothing was proved.
        state = report.get('status', 'CHECK_BLOCKED')
        reason = report.get('reason')
        witness = report.get('witness')
        proved = False
        if state == 'UNSUPPORTED':
            from .dag_id_verify import check_failure
            evidence = check_failure(witness, math_problem)
            proved = evidence.get('passed') is True
            if not proved:
                state = 'NO_FORMULA_YET'
                reason = 'NONIDENTIFICATION_EVIDENCE_NOT_VERIFIED'
            witness = dict(witness or {}, evidence_report=evidence)
        return _for_shared_entry(dict(
            state=state, reason_code=reason, witness=witness,
            nonidentification_proved=proved,
            review_authority=r.authority, backend_called=True,
            production_admission=False, estimation_handoff_allowed=False))
    except (Unavailable, MathUnavailable) as error:
        return _for_shared_entry(dict(
            state=error.state, reason_code=error.reason,
            production_admission=False, estimation_handoff_allowed=False))


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
