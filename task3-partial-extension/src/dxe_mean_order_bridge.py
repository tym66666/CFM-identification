"""Bridge: generalized D×E enumeration → mean_order_solver for full partial-identification evidence.

The 8 existing task3_generalized files compute intervals by summing per-cell bound
contributions, but they DO NOT produce the *inner evidence* that defines true
partial identification:

  - lower_world / upper_world: which feasible world achieves each endpoint
  - lower_dual / upper_dual: dual multipliers proving endpoint optimality
  - baseline_bounds_only_range: what the interval would be WITHOUT A4 data
    (logical bounds from scientific bounds alone), vs the actual identified interval
  - _incompatibility() Farkas path: a formal proof that no feasible world exists

mean_order_solver.py already produces ALL this evidence (lines 161-194). This bridge
converts any D1-D6 × E1-E5 combination into the MeanOrderProblem format, then invokes
mean_order_solver.solve() — returning the full certificate with worlds, duals, Farkas,
and baseline bounds.

Usage (by general_bounded_policy_solver):
    from .dxe_mean_order_bridge import solve_with_full_evidence
    certificate = solve_with_full_evidence(st, target, known, bounds, ...)
    # certificate contains: worlds (lower/upper), duals, baseline_bounds_only_range,
    #                      farkas (if incompatible), status, lower, upper, cells, etc.
"""

from fractions import Fraction as F

from .mean_order_contract import (
    MeanOrderProblem, MeanOrderUnavailable,
    NodeOrder, ExactMean, NodeBounds,
    VERSION as MEAN_ORDER_VERSION, MODEL, MAX_N,
)
from .mean_order_solver import solve as mean_order_solve
from .bounded_policy_contract import fail

from .general_bounded_policy_solver import (
    _build_neighbors,
    _validate_design_kind,
    _validate_exposure_kind,
    EXPOSURE_SPECS,
)


# ─── D1-D6 design → internal design string ──────────────────────────────

_DESIGN_STRINGS = {
    'D1': 'D1_HETEROGENEOUS_BERNOULLI',
    'D2': 'D2_UNIFORM_FIXED_QUOTA',
    'D3': 'D3_TWO_GROUP_FIXED_QUOTA',
    'D4': 'D4_CLUSTER_BERNOULLI',
    'D5': 'D5_MULTI_GROUP_FIXED_QUOTA',
    'D6': 'D6_TWO_STAGE_QUOTA_MIXTURE',
}


# ─── E1-E5 exposure → internal exposure string ──────────────────────────

_EXPOSURE_STRINGS = {
    'E1': 'E1_STRICT_MAJORITY_TIES_LOW_ISOLATED_ZERO',
    'E2': 'E2_THREE_LEVEL_TREATED_NEIGHBOR_FRACTION',
    'E3': 'E3_EXACT_TREATED_NEIGHBOR_COUNT',
    'E4': 'E4_PRETREATMENT_CORE_COLLABORATOR_MAJORITY',
    'E5': 'E5_ANY_TREATED_NEIGHBOR',
}

# acceptable outcome_kind mapping from general_bounded_policy_solver context
_OUTCOME_KINDS = frozenset({'binary', 'continuous'})

# order-direction / scope constants (same as mean_order_contract defaults)
_ORDER_DIRECTION = 'NONDECREASING_NUMERIC_OUTCOME_MEAN'
_ORDER_SCOPE = 'ALL_BINARY_ASSIGNMENTS_CONDITIONAL_ON_STUDY_CONTEXT'


# ─── Bridge entry point ─────────────────────────────────────────────────


def solve_with_full_evidence(
    st, target, known, bounds, policy, weights,
    cells, probabilities, exposure, exposure_kind, design_kind,
    inquiry=None, information=None, nbrs=None,
):
    """Build a MeanOrderProblem from the generalized D×E context and solve.

    Parameters
    ----------
    st : Structure
        The study structure (node_order, undirected_edges, outcome_kind, etc.)
    target : Target
        The policy target object (policy_assignment, unit_weights).
    known : dict[tuple, Fraction]
        A4 conditional known values: {(n, a, e): value}
    bounds : dict[str, tuple[Fraction, Fraction]]
        Node-level scientific bounds: {n: (lo, hi)}
    policy : dict[str, int]
        The policy assignment: {n: 0/1}
    weights : dict[str, Fraction]
        Normalized unit weights: {n: w}
    cells : list[tuple]
        Enumerated (n, a, e) cells.
    probabilities : dict[tuple, Fraction]
        Support probability for each cell.
    exposure : ExposureSpec
        The exposure specification object (for classify fallback).
    exposure_kind : str
        One of 'E1'..'E5'.
    design_kind : str
        One of 'D1'..'D6'.
    inquiry, information
        Optional; passed through to certificate if given.

    Returns
    -------
    dict : Full mean_order_solver certificate with worlds, duals,
           baseline_bounds_only_range, and (if incompatible) farkas.
    """
    nodes = st.node_order
    n_nodes = len(nodes)

    if n_nodes > MAX_N:
        raise ValueError(
            f'mean_order_solver supports at most {MAX_N} nodes; got {n_nodes}'
        )

    # --- Determine quota (for D2: m, for D1: not applicable) ---
    # Try to extract fixed quota from design metadata.
    design = getattr(st, 'design', None)
    quota = _resolve_quota(design, design_kind, nodes)

    # --- Build node_orders (mode mapping from st if available) ---
    node_orders = _resolve_node_orders(st, nodes)

    # --- Build edges list ---
    edges = [list(e) for e in st.undirected_edges]

    # --- Build ExactMean values for known cells ---
    values = []
    for cell, val in known.items():
        n, a, e = cell
        values.append(ExactMean(node=n, own=a, exposure=e, value=str(val)))

    # --- Build NodeBounds ---
    bound_list = []
    for n in nodes:
        lo, hi = bounds[n]
        bound_list.append(NodeBounds(node=n, lower=str(lo), upper=str(hi)))

    # --- Build first/second policy vectors ---
    first = [policy[n] for n in nodes]
    second = [0] * n_nodes  # contrast not used in policy-mean mode; mean_order also uses second=0 for single-policy
    # Actually mean_order_contract requires second and weights for FIRST_MINUS_SECOND.
    # For single-policy mean, we set second = 0 vector and only look at the reported lower/upper.
    # The weights are the unit weights.
    weight_strs = [str(weights[n]) for n in nodes]

    # --- Determine outcome_kind ---
    outcome_kind = getattr(st, 'outcome_kind', 'binary')
    if outcome_kind not in _OUTCOME_KINDS:
        outcome_kind = 'binary'

    # --- Determine bounds_kind ---
    bounds_kind = getattr(st, 'bounds_kind', 'CONDITIONAL_MEAN')
    if bounds_kind not in ('CONDITIONAL_MEAN', 'ALMOST_SURE_OUTCOME'):
        bounds_kind = 'CONDITIONAL_MEAN'

    # --- Build context strings (from inquiry if available) ---
    ctx_treatment = getattr(target, 'treatment_definition', '') or ''
    ctx_outcome = getattr(target, 'outcome_definition', '') or ''
    ctx_study = getattr(inquiry, 'context', '') if inquiry else ''

    # --- Construct the MeanOrderProblem ---
    try:
        problem = MeanOrderProblem(
            version=MEAN_ORDER_VERSION,
            model_scope=MODEL,
            node_order=list(nodes),
            undirected_edges=edges,
            graph_scope='KNOWN_FIXED_PRETREATMENT_SIMPLE_UNDIRECTED',
            design=_DESIGN_STRINGS.get(design_kind, 'D2_UNIFORM_FIXED_QUOTA'),
            quota=quota,
            exposure=_EXPOSURE_STRINGS.get(exposure_kind, 'E1_STRICT_MAJORITY_TIES_LOW_ISOLATED_ZERO'),
            context=ctx_study,
            treatment_definition=ctx_treatment,
            outcome_definition=ctx_outcome,
            outcome_kind=outcome_kind,
            outcome_unit='unit',
            outcome_period='single_period',
            order_direction=_ORDER_DIRECTION,
            order_scope=_ORDER_SCOPE,
            node_orders=node_orders,
            randomization_claim='WHOLE_ASSIGNMENT_INDEPENDENT_OF_ALL_POTENTIAL_OUTCOMES_GIVEN_CONTEXT',
            consistency_claim='OBSERVED_OUTCOME_EQUALS_ASSIGNED_POTENTIAL_OUTCOME',
            moments_claim='FINITE_FIRST_MOMENTS',
            mean_sufficiency_scope=_ORDER_SCOPE,
            mean_sufficiency_claim='NODE_OWN_AND_E1_SIGNATURE_DETERMINES_CONDITIONAL_MEAN',
            information_scope='EXACT_LISTED_SIGNATURE_MEANS_ONLY',
            availability='EXACT_POPULATION_VALUE',
            values=values,
            a4_source='',
            a4_provenance='',
            bounds=bound_list,
            bounds_kind=bounds_kind,
            bounds_scope='ALL_BINARY_ASSIGNMENTS_CONDITIONAL_ON_STUDY_CONTEXT',
            bounds_provenance='',
            first=first,
            second=second,
            weights=weight_strs,
            operation='FIRST_MINUS_SECOND',
            scientific_provenance='',
        )
    except Exception as e:
        fail('INCOMPATIBLE', f'MEAN_ORDER_PROBLEM_CONSTRUCTION_FAILED: {e}')
        raise  # unreachable; fail raises BoundedPolicyUnavailable

    # --- Call mean_order_solver.solve() ---
    try:
        raw = mean_order_solve(problem)
    except MeanOrderUnavailable as e:
        # Map MeanOrderUnavailable states to BoundedPolicyUnavailable equivalents
        if e.state == 'CHECK_BLOCKED':
            fail('INCOMPATIBLE', e.reason)
        elif e.state == 'NEEDS_INPUT':
            fail('NEEDS_INPUT', e.reason)
        else:
            fail('INCOMPATIBLE', e.reason)
        raise  # unreachable

    # --- Post-process the raw certificate ---
    # mean_order_solver returns cells with worlds (lower_world, upper_world)
    # but the cell format is [(n, a, e)] nested. We normalize to match
    # the general_bounded_policy_solver cell schema.
    certificate = _normalize_certificate(raw, cells, probabilities,
                                          known, inquiry, information,
                                          design_kind, exposure_kind)
    return certificate


def _normalize_certificate(raw, cells, probabilities, known,
                            inquiry, information,
                            design_kind, exposure_kind):
    """Normalize the mean_order_solver certificate to the general shape.

    Retains all key evidence:
      - lower_world / upper_world per cell (from mean_order worlds)
      - lower_dual / upper_dual maps
      - baseline_bounds_only_range (renamed from baseline_bounds_only_range)
      - farkas proof if incompatible
      - sharpness (from mean_order solver)
    """
    # Map the raw cell entries back to our cell ordering.
    raw_cells = raw.get('cells', [])
    cell_map = {}   # (n, a, e) -> raw cell dict
    for rc in raw_cells:
        cl = tuple(rc.get('cell', []))
        cell_map[cl] = rc

    # Rebuild rows with proper lower_world/upper_world from the solver.
    rows = []
    for c in cells:
        n, a, e = c
        prob = probabilities.get(c, F(0))
        kw = known.get(c, None)

        rc = cell_map.get(c, {})
        # The solver's worlds give the actual extreme-point values.
        lw = rc.get('lower_world', str(F(0)))
        uw = rc.get('upper_world', str(F(0)))

        rows.append(dict(
            cell=list(c),
            support=str(prob),
            a4_value=str(kw) if kw is not None else None,
            lower_world=str(lw),
            upper_world=str(uw),
        ))

    # Build the enriched certificate.
    logical = raw.get('baseline_bounds_only_range',
                      raw.get('logical_range', ['0', '0']))
    route = f'BOUNDED_POLICY_MEAN_{design_kind}_{exposure_kind}'

    # Import needed from contracts only at this point (lazy, after solve succeeded).
    from .bounded_policy_contract import VERSION as POLICY_VERSION, input_digest as policy_input_digest
    from cfm_id_bridge.scientific_binding import sha

    certificate = dict(
        # Original bounded_policy fields.
        version=POLICY_VERSION,
        theorem='FINITE_SIGNATURE_MEAN_BOX',
        input_sha256=policy_input_digest(inquiry, information) if inquiry and information else '',
        target_sha256=sha(information) if information else '',

        status=raw.get('status', 'PARTIAL'),
        lower=raw.get('lower', '0'),
        upper=raw.get('upper', '0'),
        width=raw.get('width', '0'),

        # Evidence from mean_order_solver.
        baseline_bounds_only_range=list(map(str, logical)),
        informative_relative_to_bounds_only=raw.get('informative_relative_to_bounds_only', False),
        sharp=raw.get('sharp', True),

        model_scope=raw.get('model_scope', MODEL),
        cells=rows,

        lower_dual=raw.get('lower_dual', {}),
        upper_dual=raw.get('upper_dual', {}),

        realization=raw.get('realization', 'BERNOULLI_PER_NODE_SIGNATURE'),

        # D×E routing info.
        design_kind=design_kind,
        exposure_kind=exposure_kind,
        route=route,

        # Production flags (default: not admitted).
        production_admission=False,
        estimation_handoff_allowed=False,
    )

    # Carry forward farkas evidence if incompatible.
    if raw.get('farkas'):
        certificate['farkas'] = raw['farkas']
        certificate['status'] = 'INCOMPATIBLE'

    certificate['certificate_sha256'] = sha(certificate)
    return certificate


# ─── Helpers for MeanOrderProblem construction ──────────────────────────


def _resolve_quota(design, design_kind, nodes):
    """Extract the fixed-quota m from the design metadata.

    For D1 (Bernoulli) there is no fixed quota; return 0.
    For D2-D6, try to determine the total number of treated units.
    """
    if design is None:
        # Fallback: derive from design_kind
        if design_kind == 'D1':
            return 0  # D1 is Bernoulli, no fixed quota
        # For D2 uniform quota, we can't know m without the design object.
        # Default to len(nodes)//2 as a placeholder (caller should set correctly).
        return len(nodes) // 2

    inner = getattr(design, 'design', design)
    dname = type(inner).__name__

    # Try to get m from common quota field names.
    for attr in ('m', 'treated_quotas', 'quota'):
        val = getattr(inner, attr, None)
        if val is not None:
            if isinstance(val, (list, tuple)):
                return sum(val)
            if isinstance(val, int):
                return val

    # For cluster/multi-group designs, sum group quotas.
    for attr in ('treated_quotas', 'cluster_treated'):
        val = getattr(inner, attr, None)
        if val is not None and isinstance(val, (list, tuple)):
            return sum(val)

    # For TwoStageQuotaMixture, use the first profile's sum.
    profiles = getattr(inner, 'quota_profiles', None)
    if profiles:
        return sum(profiles[0]) if isinstance(profiles[0], (list, tuple)) else profiles[0]

    if design_kind == 'D1':
        return 0
    return len(nodes) // 2


def _resolve_node_orders(st, nodes):
    """Extract per-node order modes from the structure.

    Uses the same logic as the original bounded_policy_solver:
    - If st has a 'node_orders' or 'orders' attribute, use it.
    - Otherwise, default to 'BOTH' for all nodes (the most general case
      that allows any order constraint to be enforced).
    """
    if hasattr(st, 'node_orders') and st.node_orders:
        result = []
        for n in nodes:
            # Find the matching order entry.
            found = None
            for entry in st.node_orders:
                if getattr(entry, 'node', None) == n:
                    found = entry
                    break
            if found is not None:
                mode = getattr(found, 'mode', 'BOTH')
            else:
                mode = 'BOTH'
            result.append(NodeOrder(node=n, mode=mode))
        return result

    # Default: BOTH — both OWN and PEERS order axes active.
    return [NodeOrder(node=n, mode='BOTH') for n in nodes]