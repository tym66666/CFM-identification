"""Closed bindings for three distinct views of existing Identification capability.

Registration never establishes applicability, supplies a review, or enables a
fallback. Only audited structure/target fields select a reader; its existing
inspector, native contracts and independent verifiers retain all authority.
"""
from dataclasses import asdict, dataclass
from typing import Callable
from .research_route_workflow import RouteCapability


class RegistryError(ValueError):
    """A wiring error, not a scientific coverage or identification conclusion."""


@dataclass(frozen=True)
class MethodBinding:
    method_id: str
    native_route_ids: tuple[str, ...]
    producers: tuple[Callable, ...]
    replayers: tuple[Callable, ...]


@dataclass(frozen=True)
class BusinessBinding:
    reader_id: str
    structure: str
    target_kinds: tuple[str, ...]
    scope: str
    methods: tuple[MethodBinding, ...]
    inspect: Callable
    decode_reviews: Callable
    execute: Callable
    note_review: bool = False
    information_evidence_review: bool = False
    assignment_family: str | None = None


def business_bindings():
    # Static imports only. Caller text can never choose an import or function.
    from . import iv_business_dispatch as iv, iv_late_solver, iv_late_verify, iv_ate_solver, iv_ate_verify
    from . import network_policy_dispatch as mean, network_contrast_dispatch as contrast
    from . import network_bounded_dispatch as bounded, dag_method_dispatch as dag
    from . import network_effect_dispatch as effects
    from . import network_observational_policy_dispatch as observational
    from . import network_extended_dispatch as extended
    from cfm_id_llm import network_extended_reading as extended_reading
    from .workflows import policy_difference
    from . import bounded_policy_solver, bounded_policy_verify
    from . import bounded_contrast_solver, bounded_contrast_verify, fixed_comparison
    from . import network_mean_order_dispatch as order, mean_order_solver, mean_order_verify
    from pfn_pipeline import identification_policy_r1b as r1b, identification_policy_r2 as r2
    from pfn_pipeline import identification_business as network
    from pfn_pipeline.identification_batch import identify_randomized_network_batch
    from pfn_pipeline.identification_composition import identify_verified_linear_target,replay_verified_composition
    dag_routes = {r.capability.route_id: r for r in registrations()}
    bindings = (
        BusinessBinding(iv.FAMILY, "BINARY_IV_CANDIDATE", ("LATE", "ATE"),
            "Binary IV candidate only; missing instrument or unsupported model never establishes identification.",
            (MethodBinding(iv.METHOD, (iv.METHOD,), (iv_late_solver.identify_late, iv_ate_solver.solve_ate_bounds),
                (iv_late_verify.verify_late_result, iv_ate_verify.verify_ate_result)),),
            iv.inspect_methods, iv.native_reviews_from_json, iv._execute_plan),
        BusinessBinding(mean.FAMILY, 'UNIT_NETWORK', ('FIXED_POLICY_VALUE',),
            'One complete fixed policy, declared evaluation population and equal mean; native scope checks remain required.',
            (MethodBinding(mean.R1B, (mean.R1B,), (r1b.identify_verified_fixed_policy,), (r1b.replay_verified_fixed_policy,)),
             MethodBinding(mean.R2, (mean.R2,), (r2.identify_verified_signature_policy,), (r2.replay_verified_signature_policy,)),
             MethodBinding(bounded.METHOD, (bounded.METHOD,), (bounded_policy_solver.solve,), (bounded_policy_verify.replay,))),
            mean.inspect_methods, mean.native_reviews_from_json, mean._execute_plan, True, True),
        BusinessBinding(contrast.FAMILY, 'UNIT_NETWORK', ('TOTAL_EFFECT',),
            'Only first minus second of two complete fixed policies with one population, outcome and context; not arbitrary total effects.',
            (MethodBinding(contrast.POINT_METHOD, (mean.R1B,),
                (network.identify_network_business_query, fixed_comparison.compose),
                (network.replay_verified_business_outcome, fixed_comparison.replay)),
             MethodBinding(contrast.R2_METHOD, (mean.R2,),
                (network.identify_network_business_query, policy_difference.compose),
                (network.replay_verified_business_outcome, policy_difference.replay)),
             MethodBinding(contrast.BOUNDED_METHOD, (contrast.BOUNDED_METHOD,),
                (bounded_contrast_solver.solve,), (bounded_contrast_verify.replay,)),
             MethodBinding(order.METHOD, (order.METHOD,),
                (mean_order_solver.solve,), (mean_order_verify.replay,))),
            contrast.inspect_methods, contrast.native_reviews_from_json, contrast._execute_plan, True, True),
        BusinessBinding('VARIABLE_DAG_FACTS', 'VARIABLE_DAG', ('INTERVENTIONAL_DISTRIBUTION',),
            'Existing finite variable DAG contracts only; no network/DAG composition.',
            tuple(MethodBinding(method, (method,), (dag_routes[method].adapter_type.submit,),
                (dag_routes[method].adapter_type.replay,)) for method in dag.METHODS),
            dag.inspect_methods, dag.native_reviews_from_json, dag._execute_plan),
        BusinessBinding(effects.FAMILY, 'UNIT_NETWORK', effects.TARGET_KINDS,
            'Direct, spillover and local total contrasts under the original conditional design; explicit fixed evaluation population and reviews. D1/strict-majority supports external review; other native D1-D6/E1-E5 combinations retain synthetic-only admission. Complete-policy TOTAL_EFFECT uses the separate contrast reader.',
            (MethodBinding(effects.METHOD,(effects.METHOD,),
                (identify_randomized_network_batch,network.identify_network_business_query,identify_verified_linear_target),
                (network.replay_verified_business_outcome,replay_verified_composition)),),
            effects.inspect_methods,effects.native_reviews_from_json,effects._execute_plan,True),
        BusinessBinding(observational.FAMILY, 'UNIT_NETWORK', ('FIXED_POLICY_VALUE',),
            'Finite observational policy mean at fixed pretreatment W; explicit population law and conditional exchangeability. Full-policy support, or separately reviewed all-assignment mean sufficiency and signature support. Synthetic research review.',
            (MethodBinding(observational.METHOD,(observational.METHOD,),
                (network.identify_network_business_query,), (network.replay_verified_business_outcome,)),
             MethodBinding(observational.SIGNATURE_METHOD,(observational.SIGNATURE_METHOD,),
                (network.identify_network_business_query,), (network.replay_verified_business_outcome,))),
            observational.inspect_methods,observational.native_reviews_from_json,observational._execute_plan,
            note_review=True,assignment_family='OBSERVATIONAL'),
    ) + tuple(BusinessBinding(family,'UNIT_NETWORK',kinds,scope,
        tuple(MethodBinding(m,(m,),(network.identify_network_business_query,),
            (network.replay_verified_business_outcome,)) for m in extended.METHODS[family]),
        extended.inspect_methods,extended.native_reviews_from_json,extended._execute_plan,
        note_review=True,assignment_family=regime)
        for family,kinds,scope,regime in (
            (extended_reading.ARM,('NETWORK_DESIGN_STANDARDIZED_ARM_MEAN',),
             'One explicit node-arm mean under original conditional design; D1-D6/E1-E5, synthetic review.',None),
            (extended_reading.MIX,('STOCHASTIC_POLICY_VALUE',),
             'Explicit finite complete policies and positive weights; each component independently verified R1b; synthetic review.',None),
            (extended_reading.OBS,effects.TARGET_KINDS,
             'Fixed-W observed-law standardized effects or separately licensed shared-stratum/local-binary-covariate exposure effects; native A4 and scope guards retained; synthetic review.','OBSERVATIONAL')))
    keys = [(b.structure, kind, b.assignment_family) for b in bindings for kind in b.target_kinds]
    if len(set(keys)) != len(keys) or len({b.reader_id for b in bindings}) != len(bindings):
        raise RegistryError('DUPLICATE_BUSINESS_REGISTRATION')
    for b in bindings:
        if not b.target_kinds:
            raise RegistryError('EMPTY_TARGET_REGISTRATION')
        ids = [m.method_id for m in b.methods]
        if not ids or len(set(ids)) != len(ids):
            raise RegistryError('DUPLICATE_OR_EMPTY_METHOD_REGISTRATION')
        if not all(callable(f) for f in (b.inspect, b.decode_reviews, b.execute)):
            raise RegistryError('MISSING_BUSINESS_HANDLER')
        for m in b.methods:
            if not m.native_route_ids or not m.producers or not m.replayers or not all(
                    callable(f) for f in (*m.producers, *m.replayers)):
                raise RegistryError('MISSING_NATIVE_PRODUCER_OR_REPLAYER')
    return bindings


def business_binding(reader_id):
    if type(reader_id) is str:
        for b in business_bindings():
            if b.reader_id == reader_id:
                return b
    raise RegistryError('UNREGISTERED_BUSINESS_READER')


def reader_for(structure, target_kind, *, assignment_family=None):
    """Select reading only, after the caller has checked the business review."""
    # OBSERVATIONAL is already an A0 fact label, not a theorem or a license.
    # Never send an explicitly observational target to a randomized contract.
    regime = 'OBSERVATIONAL' if structure=='UNIT_NETWORK' and assignment_family=='OBSERVATIONAL' else None
    for b in business_bindings():
        if b.structure == structure and target_kind in b.target_kinds and b.assignment_family==regime:
            return b
    return None


def plan_binding(plan, *, reader_id=None):
    """Reject unknown/cross-family plans before decoding or executing reviews.

    Legacy DAG plans omit fact_family. Accept that format only when every
    planned method is a registered DAG method; never default an unknown family
    or a network plan to the DAG decoder. This check does not approve the plan.
    """
    if type(plan) is not dict or type(plan.get('methods')) is not list or not plan['methods']:
        raise RegistryError('NONEMPTY_REGISTERED_METHOD_PLAN_REQUIRED')
    family = plan.get('fact_family', 'VARIABLE_DAG_FACTS')
    b = business_binding(family)
    if reader_id is not None and reader_id != b.reader_id:
        raise RegistryError('READER_AND_PLAN_FAMILY_MISMATCH')
    methods = [r.get('method') if type(r) is dict else None for r in plan['methods']]
    allowed = {m.method_id for m in b.methods}
    if any(type(m) is not str or m not in allowed for m in methods) or len(set(methods)) != len(methods):
        raise RegistryError('UNREGISTERED_OR_DUPLICATE_PLANNED_METHOD')
    return b


@dataclass(frozen=True)
class SessionBinding:
    lane_id: str
    group: str


def session_bindings():
    # Internal, explicit research sessions, not categories a business user selects.
    return (
        SessionBinding('NETWORK_D1_EFFECTS', 'NETWORK_EFFECTS'),
        SessionBinding('MEAN_ORDER_D2_E1', 'MEAN_ORDER'),
        SessionBinding('DAG_CLASSICAL_BACKDOOR', 'DAG'),
        SessionBinding('DAG_ADJUSTMENT', 'DAG'),
        SessionBinding('DAG_CLASSICAL_FRONTDOOR', 'DAG'),
        SessionBinding('NETWORK_FIXED_POLICY', 'POLICY'),
        SessionBinding('NETWORK_FIXED_COMPARISON', 'POLICY'),
        SessionBinding('BOUNDED_POLICY_MEAN_D2_E1', 'POLICY'),
        SessionBinding('BOUNDED_POLICY_CONTRAST_D2_E1', 'POLICY'),
    )


def session_lanes(group=None):
    return tuple(s.lane_id for s in session_bindings() if group is None or s.group == group)


def _name(f):
    return f.__module__ + '.' + f.__qualname__


def inventory():
    """Fresh descriptive JSON. Editing it never changes executable bindings."""
    bindings = business_bindings()
    readers = [dict(reader_id=b.reader_id, structure=b.structure, target_kinds=list(b.target_kinds), scope=b.scope,
        **(dict(assignment_family=b.assignment_family) if b.assignment_family is not None else {}),
        inspect=_name(b.inspect), decode_reviews=_name(b.decode_reviews), execute=_name(b.execute),
        methods=[dict(method_id=m.method_id, native_route_ids=list(m.native_route_ids),
            producers=[_name(f) for f in m.producers], replayers=[_name(f) for f in m.replayers]) for m in b.methods])
        for b in bindings]
    connected = {r for b in bindings for m in b.methods for r in m.native_route_ids}
    native = [dict(r, common_business_routes=[x for x in r['route_ids'] if x in connected],
        native_only_routes=[x for x in r['route_ids'] if x not in connected]) for r in separate_entries()]
    return dict(version='identification-capability-registry-2',
        scope='Maintained capabilities only; not an inventory of all historical backends.',
        formal_research_adapters=[r.describe() for r in registrations()],
        separate_native_entries=native, common_business_readers=readers,
        internal_research_sessions=[dict(lane_id=s.lane_id, group=s.group) for s in session_bindings()],
        registration_is_applicability=False, creates_reviews=False, automatic_fallback=False,
        production_admission=False, estimation_handoff_allowed=False)


# Native registration records also feed the legacy research catalog.

@dataclass(frozen=True)
class Registration:
    adapter_type:type
    problem_type:type
    review_type:type
    version:str
    review_scope:str
    review_form:str
    claim_kinds:tuple[str,...]
    business_entry:str|None
    @property
    def capability(self)->RouteCapability:return self.adapter_type.capability
    def describe(self):
        return dict(**asdict(self.capability),problem_version=self.version,
            problem_type=self.problem_type.__name__,review_type=self.review_type.__name__,
            review_scope=self.review_scope,review_form=self.review_form,claim_kinds=list(self.claim_kinds),
            callable_here=True,requires_explicit_selection=True,creates_reviews=False,
            business_entry=self.business_entry,
            business_reading_checked_by_this_entry=False,production_admission=False,
            estimation_handoff_allowed=False)

def registrations():
    # Fixed imports only. Neither material text nor route IDs choose a module path.
    from .research_route_adapters import DagBackdoorRoute,MeanOrderRoute
    from .dag_adjustment_adapter import DagAdjustmentRoute
    from .dag_frontdoor_adapter import DagFrontdoorRoute
    from .dag_frontdoor_contract import FrontdoorProblem,FrontdoorReview
    from .iv_route_contract import IVProblem,IVReview
    from .iv_research_adapter import BinaryIVRoute
    from .dag_backdoor_contract import BackdoorProblem,BackdoorReview
    from .dag_adjustment_contract import AdjustmentProblem,AdjustmentReview
    from .mean_order_contract import MeanOrderProblem,ReviewedMeanOrder
    return (
        Registration(DagBackdoorRoute,BackdoorProblem,BackdoorReview,'dag-backdoor-1',
            'EXTERNAL_DECLARATIVE_RESEARCH_OR_SYNTHETIC_TEST','PER_CONDITION_ACCEPTED_PENDING_REJECTED',
            ('POINT',),'evaluation.dag_business_workflow'),
        Registration(DagAdjustmentRoute,AdjustmentProblem,AdjustmentReview,'dag-adjustment-1',
            'EXTERNAL_DECLARATIVE_RESEARCH_OR_SYNTHETIC_TEST','PER_CONDITION_ACCEPTED_PENDING_REJECTED',
            ('POINT',),'evaluation.dag_business_workflow'),
        Registration(MeanOrderRoute,MeanOrderProblem,ReviewedMeanOrder,'mean-order-d2-e1-1',
            'SYNTHETIC_TEST_ONLY','EXPLICIT_TRUE_SYNTHETIC_ATTESTATIONS',
            ('POINT','PARTIAL','INCOMPATIBLE'),'cfm_id.workflows.mean_order'),
        Registration(DagFrontdoorRoute,FrontdoorProblem,FrontdoorReview,'dag-frontdoor-1',
            'EXTERNAL_DECLARATIVE_RESEARCH_OR_SYNTHETIC_TEST','PER_CONDITION_ACCEPTED_PENDING_REJECTED',
            ('POINT',),'evaluation.dag_business_workflow'),
        Registration(BinaryIVRoute,IVProblem,IVReview,'binary-iv-research-1',
            'SEPARATE_SOURCE_READING_AND_SCIENTIFIC_REVIEW','PER_CONDITION_ACCEPTED_PENDING_REJECTED',
            ('POINT','PARTIAL','INCOMPATIBLE'),'cfm_id.iv_business_dispatch'),
    )

def separate_entries():
    # Current maintained lanes, not an exhaustive inventory of historical backends.
    return [
        dict(entry_id='NETWORK_POINT_EXISTING_BUSINESS',route_ids=[
            'R1A_RANDOMIZED_ARM','R1A_COMPOSITION','R1B_FULL_ASSIGNMENT','R1B_FINITE_POLICY',
            'R2_MEAN_SIGNATURE','R3_FULL_ASSIGNMENT','R3_MEAN_SIGNATURE',
            'R3_P_STANDARDIZED_EFFECTS','R3_EXPOSURE_ADJUSTED_EFFECTS','R3_NODEWISE_EXPOSURE_ADJUSTED_EFFECTS'],
            entry='pfn_pipeline.identification_business',
            reason='Native business/scientific context and route-specific reviews remain required.'),
        dict(entry_id='BOUNDED_POLICY_MEAN_D2_E1',route_ids=['BOUNDED_POLICY_MEAN_D2_E1'],
            entry='cfm_id.bounded_policy',
            reason='Preserve original POINT admission, assignment review and separately bound bounded-policy review.'),
        dict(entry_id='BOUNDED_POLICY_CONTRAST_D2_E1',route_ids=['BOUNDED_POLICY_CONTRAST_D2_E1'],
            entry='cfm_id.bounded_contrast',
            reason='Preserve both endpoint contexts, assignment reviews and joint contrast review.'),
        dict(entry_id='LLM_UNVERIFIED_RESEARCH',route_ids=[],
            entry='evaluation.business_candidate_feedback',
            reason='Restricted existing research lane; unverified prose is never a certified mathematical claim.'),
    ]
