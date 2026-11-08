"""Closed, explicit research inventory; metadata is not applicability or approval."""
from .capability_registry import Registration, registrations, separate_entries

VERSION='research-route-catalog-2'


def resolve(route_id):
    if type(route_id) is not str:raise ValueError('EXACT_REGISTERED_ROUTE_ID_REQUIRED')
    for r in registrations():
        if r.capability.route_id==route_id:return r
    raise ValueError('ROUTE_NOT_REGISTERED_IN_THIS_ENTRY')


def inventory():
    separate=[dict(**r,callable_here=False,automatic_fallback=False) for r in separate_entries()]
    return dict(version=VERSION,scope='Current explicit research adapters and selected maintained business lanes; not all historical backends.',
        input_level='EXPLICIT_MATHEMATICAL_PROBLEM',automatic_route_inference=False,
        implemented_routes=[r.describe() for r in registrations()],separate_entries=separate,
        planned_routes=[
            dict(route_id='DAG_SET_OR_CONDITIONAL_FRONTDOOR',status='NOT_IMPLEMENTED',callable_here=False),
            dict(route_id='IV',status='NO_REGISTERED_CONTRACT_IN_THIS_ENTRY',callable_here=False),
            dict(route_id='GENERAL_GRAPHICAL_ID',status='NO_REGISTERED_CONTRACT_IN_THIS_ENTRY',callable_here=False)],
        result_contract=dict(
            proved_states=['POINT','PARTIAL','INCOMPATIBLE'],
            stopping_states=['NEEDS_INPUT','REVIEW_REQUIRED','UNSUPPORTED','CHECK_BLOCKED'],
            point_representation='Route-specific symbolic functional or exact singleton interval.',
            partial_representation='Current registered interval route certifies sharp bounds; arbitrary outer bounds are not admitted.',
            incompatible_representation='Verified constraint contradiction, never an identification interval.',
            required='Published claims must match their certificate and pass native independent replay.',
            unsupported_is_not_nonidentification=True,
            llm_unverified_is_not_proved=True,
            stop_has_no_mathematical_claim_or_certificate=True),
        default_core_modified=False,production_admission=False,estimation_handoff_allowed=False)

def schemas(route_id):
    r=resolve(route_id)
    return dict(route=r.describe(),problem=r.problem_type.model_json_schema(),review=r.review_type.model_json_schema())

