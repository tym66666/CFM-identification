"""Generalized bounded policy mean solver for ALL D1-D6 × E1-E5 combinations.

Extends the original D2/E1-specific solver (bounded_policy_solver.py) to every
pair of design×exposure. The architecture is:

  general_bounded_policy_solver.py
"""
from fractions import Fraction as F
from itertools import product

from cfm_id_bridge.scientific_binding import sha
from pfn_pipeline._internal.identification.randomized_arm_family import (
    AssignmentSpec, ExposureSpec, SupportEngine,
)
from .bounded_policy_contract import VERSION, validate_model, input_digest, fail

# ─── D1–D6 design name → AssignmentSpec mapping ──────────────────────────────

# These are the exposure* design variant names used in SupportEngine.
# Each gives the correct internal schema (CompleteRandomizationDesignV1 etc.).
DESIGN_KINDS = frozenset({'D1', 'D2', 'D3', 'D4', 'D5', 'D6'})

# ─── E1–E5 exposure kind mapping ──────────────────────────────────────────────

EXPOSURE_KINDS = frozenset({'E1', 'E2', 'E3', 'E4', 'E5'})

# The original 'strict_majority_ties_low' group.
# Full mapping: {kind: (grouping, extra_kwargs_or_None)}
EXPOSURE_SPECS = {
    'E1': ('strict_majority_ties_low', None),
    'E2': ('three_level_treated_neighbor_fraction', None),
    # E3 = pretreatment core collaborator majority (requires core_collaborators)
    'E3': ('pretreatment_core_collaborator_majority', 'core_collaborators'),
    # E4 = exact treated neighbor count (no extra kwargs)
    'E4': ('exact_treated_neighbor_count', None),
    'E5': ('any_treated_neighbor', None),
}


# ─── Entry point ──────────────────────────────────────────────────────────────


def solve(inquiry, information, *, design_kind='D2', exposure_kind='E1'):
    """Generalized policy-mean interval for any DESIGN×EXPOSURE combination.

    Parameters
    ----------
    inquiry : Inquiry
        The inquiry object from bounded_policy_contract.validate_model.
    information : BoundedMeanInformation
        Contains A4 values and scientific bounds.
    design_kind : str
        One of DESIGN_KINDS ('D1'..'D6').
    exposure_kind : str
        One of EXPOSURE_KINDS ('E1'..'E5').

    Returns
    -------
    dict : certificate with status, interval, cells, bound_terms.

    Raises
    ------
    BoundedPolicyUnavailable
        On incompatibility or missing input.
    ValueError
        On unknown design/exposure kind.
    """
    _validate_design_kind(design_kind)
    _validate_exposure_kind(exposure_kind)

    # 1. Validate the shared model (same as original).
    st, target, known, bounds = validate_model(inquiry, information)
    net = st.network()
    neighbors = _build_neighbors(st)
    policy = dict(zip(st.node_order, target.policy_assignment))
    weights = dict(zip(st.node_order, map(F, target.unit_weights)))

    # 2. Build exposure specification.
    # For E3 (core collaborator majority), core_collaborators MUST be provided
    # in the inquiry's exposure metadata — never auto-filled from neighbors.
    exposure_group, extra = EXPOSURE_SPECS[exposure_kind]
    exposure_kwargs = {}
    if extra == 'core_collaborators':
        exposure_kwargs['core_collaborators'] = _require_core_collaborators(
            inquiry, st, exposure_kind)
    exposure = ExposureSpec(exposure_group, **exposure_kwargs)
    assignment = AssignmentSpec(st.design())

    # 3. Enumerate all possible cells.
    cells = _enumerate_cells(st, neighbors, exposure_kind)
    _validate_known_cells(known, cells)

    # 4. Compute support probabilities.
    probabilities = _compute_support(net, assignment, exposure, cells, st,
                                      neighbors, design_kind, exposure_kind)

    # 5. Check zero-probability known cells.
    for c in known:
        if probabilities[c] <= 0:
            fail('INCOMPATIBLE', 'A4_CONDITIONAL_EVENT_HAS_ZERO_PROBABILITY')

    # 6. Check material completeness.
    for n, cell in _target_cells(st, target, policy, neighbors, exposure,
                                  exposure_kind, exposure_group):
        if weights[n] and probabilities[cell] > 0 and cell not in known:
            fail('NEEDS_INPUT', 'SUPPORTED_TARGET_A4_MEAN_MISSING')

    # ── 7. Lightweight path: per-cell bound composition ────────────────
    # 提取当前政策对应的所有目标单元格
    target_cells = set(
        cell for _, cell in _target_cells(
            st, target, policy, neighbors, exposure, exposure_kind, exposure_group
        )
    )
    
    # 传入 weights 和 target_cells 重新构建 terms
    rows, terms = _build_mean_bounds(
        cells, probabilities, known, bounds, weights=weights, target_cells=target_cells
    )
    lower, upper = _compute_interval(terms)
    
    # 8. Construct certificate.
    return _build_certificate(inquiry, information, st, target, lower, upper,
                              terms, rows, design_kind, exposure_kind)


# ─── Helper: validation ──────────────────────────────────────────────────────


def _validate_design_kind(kind):
    if kind not in DESIGN_KINDS:
        raise ValueError(f'Unknown design_kind={kind!r}; expected one of {sorted(DESIGN_KINDS)}')


def _validate_exposure_kind(kind):
    if kind not in EXPOSURE_KINDS:
        raise ValueError(f'Unknown exposure_kind={kind!r}; expected one of {sorted(EXPOSURE_KINDS)}')


def _build_neighbors(st):
    neighbors = {n: set() for n in st.node_order}
    for a, b in st.undirected_edges:
        neighbors[a].add(b)
        neighbors[b].add(a)
    return neighbors


# ─── Cell enumeration ────────────────────────────────────────────────────────


def _enumerate_cells(st, neighbors, exposure_kind):
    """Enumerate all possible (node, own_treatment, exposure_state) cells."""
    cells = []
    for n in st.node_order:
        deg = len(neighbors[n])
        for a in (0, 1):
            if exposure_kind == 'E1':
                # strict_majority_ties_low: binary exposure {0,1}
                for e in ((0, 1) if deg else (0,)):
                    cells.append((n, a, e))
            elif exposure_kind == 'E2':
                # three_level_treated_neighbor_fraction: {0,1,2}
                if deg == 0:
                    # E2 undefined for isolates
                    fail('INCOMPATIBLE', 'E2_THREE_LEVEL_UNDEFINED_FOR_ISOLATE')
                for e in (0, 1, 2):
                    cells.append((n, a, e))
            elif exposure_kind == 'E3':
                # pretreatment_core_collaborator_majority: binary {0,1}
                # (classification depends on CC subset, but the output space is binary)
                for e in ((0, 1) if deg else (0,)):
                    cells.append((n, a, e))
            elif exposure_kind == 'E4':
                # exact_treated_neighbor_count: {0..deg}
                for e in range(deg + 1):
                    cells.append((n, a, e))
            elif exposure_kind == 'E5':
                # any_treated_neighbor: binary {0,1}
                for e in ((0, 1) if deg else (0,)):
                    cells.append((n, a, e))
            else:
                raise ValueError(f'Unknown exposure_kind={exposure_kind!r}')
    return cells


def _validate_known_cells(known, cells):
    if not set(known) <= set(cells):
        fail('INCOMPATIBLE', 'A4_SIGNATURE_NOT_REALIZABLE')


# ─── Support computation (D/E dependent) ─────────────────────────────────────


def _compute_support(net, assignment, exposure, cells, st, neighbors,
                     design_kind, exposure_kind):
    """Compute support probabilities for all cells.

    Uses SupportEngine.evaluate() as the production path.
    This is the D/E-dependent part of the computation.
    """
    probabilities = {}
    for cell in cells:
        n, a, e = cell
        prob = SupportEngine.evaluate(
            network=net,
            assignment=assignment,
            exposure=exposure,
            node_id=n,
            own_treatment_value=a,
            exposure_value=e,
        ).joint_probability
        probabilities[cell] = prob
    return probabilities


# ─── Target cells ────────────────────────────────────────────────────────────


def _target_cells(st, target, policy, neighbors, exposure, exposure_kind,
                  exposure_group):
    """Yield the target cell for each node (where the policy outcome lives)."""
    for n in st.node_order:
        p_val = policy[n]
        treated_neighbors = sum(policy[j] for j in neighbors[n])
        deg = len(neighbors[n])
        if exposure_kind == 'E1':
            e = int(treated_neighbors > deg // 2)
        elif exposure_kind == 'E2':
            if deg == 0:
                continue  # handled above
            if 3 * treated_neighbors < deg:
                e = 0
            elif 3 * treated_neighbors < 2 * deg:
                e = 1
            else:
                e = 2
        elif exposure_kind == 'E3':
            # core collaborator majority: classify from core_collaborators subset only
            cc = getattr(exposure, 'core_collaborators', None)
            if cc is None or n not in cc:
                # CC definition is MANDATORY for E3
                fail('INCOMPATIBLE', 'E3_CORE_COLLABORATORS_REQUIRED')
            cc_list = cc[n] if isinstance(cc, dict) else cc
            cc_set = set(cc_list) if isinstance(cc_list, (list, tuple, set)) else set()
            # The classification only considers core collaborators, not all neighbors
            cc_treated = sum(policy[j] for j in cc_set if j in neighbors[n])
            cc_deg = len(cc_set & neighbors[n])
            e = int(cc_treated > cc_deg // 2) if cc_deg else 0
        elif exposure_kind == 'E4':
            e = treated_neighbors
        elif exposure_kind == 'E5':
            e = int(treated_neighbors > 0)
        else:
            e = exposure.classify(treated_neighbors, deg)
        yield n, (n, p_val, e)


# ─── Mean bound construction ────────────────────────────────────────────────


def _build_mean_bounds(cells, probabilities, known, bounds, weights, target_cells=None):
    """Build row display and bound terms for the certificate."""
    rows, terms = [], []
    
    # 如果没有传入 target_cells，说明不进行区间聚合计算
    if target_cells is None:
        target_cells = set()

    for cell in cells:
        n, a, e = cell
        lo, hi = bounds[n]
        is_target = cell in target_cells
        
        if cell in known:
            low = high = known[cell]
        elif is_target:
            low, high = lo, hi
        else:
            low = high = (lo + hi) / 2
            
        rows.append(dict(
            cell=list(cell),
            support=str(probabilities[cell]),
            a4_value=str(known[cell]) if cell in known else None,
            lower_world=str(low),
            upper_world=str(high),
        ))
        
        # ✅ 补充 terms 的构建逻辑：仅针对目标单元格且权重非零的项
        w = weights.get(n, F(0))
        if is_target and w != 0:
            a_bound = known[cell] if cell in known else lo
            b_bound = known[cell] if cell in known else hi
            terms.append(dict(
                cell=list(cell),
                coefficient=str(w),
                basis='A4_EQUALITY' if cell in known else 'MEAN_BOUNDS',
                cell_lower=str(a_bound),
                cell_upper=str(b_bound),
                lower_contribution=str(w * a_bound),
                upper_contribution=str(w * b_bound),
            ))
            
    return rows, terms


def _compute_interval(terms):
    """Aggregate bound terms into lower/upper interval.

    Each term already has lower_contribution/upper_contribution = coefficient * bound,
    so we sum them directly without re-multiplying by the coefficient.
    """
    lower = sum((F(t['lower_contribution']) for t in terms), F(0))
    upper = sum((F(t['upper_contribution']) for t in terms), F(0))
    return lower, upper


# ─── Certificate builder ────────────────────────────────────────────────────


def _build_certificate(inquiry, information, st, target, lower, upper,
                       terms, rows, design_kind, exposure_kind):
    """Construct the final certificate dictionary."""
    logical = [
        sum((st.unit_weights[i] * st.bounds[i][0] for i in range(len(st.node_order))), F(0)),
        sum((st.unit_weights[i] * st.bounds[i][1] for i in range(len(st.node_order))), F(0)),
    ]
    route = f'BOUNDED_POLICY_MEAN_{design_kind}_{exposure_kind}'
    certificate = dict(
        version=VERSION,
        theorem='FINITE_SIGNATURE_MEAN_BOX',
        input_sha256=input_digest(inquiry, information),
        target_sha256=sha(target),
        status='POINT' if lower == upper else 'PARTIAL',
        lower=str(lower),
        upper=str(upper),
        width=str(upper - lower),
        logical_range=list(map(str, logical)),
        informative=lower > logical[0] or upper < logical[1],
        sharp=True,
        model_scope=information.model_scope,
        cells=rows,
        bound_terms=terms,
        realization=('BERNOULLI_PER_NODE_SIGNATURE'
                     if st.outcome_kind == 'binary'
                     else 'DETERMINISTIC_PER_NODE_SIGNATURE'),
        production_admission=False,
        estimation_handoff_allowed=False,
        design_kind=design_kind,
        exposure_kind=exposure_kind,
        route=route,
    )
    certificate['certificate_sha256'] = sha(certificate)
    return certificate


# ─── Utility: require core collaborators from inquiry ───────────────────────


def _require_core_collaborators(inquiry, st, exposure_kind):
    """Require core_collaborators from inquiry metadata.

    For E3 (pretreatment_core_collaborator_majority), the core collaborator
    definition is a mandatory part of the exposure specification. It must be
    declared by the user through the inquiry — never auto-filled from neighbors.

    Parameters
    ----------
    inquiry : Inquiry
        The inquiry object, MUST carry core_collaborators metadata for E3.
    st : Structure
        The study structure (provides node_order).

    Returns
    -------
    dict[str, list[str]]
        Mapping node -> list of core collaborator node IDs.

    Raises
    ------
    BoundedPolicyUnavailable
        If core_collaborators metadata is missing for E3.
    """
    if hasattr(inquiry, 'core_collaborators') and inquiry.core_collaborators:
        cc = inquiry.core_collaborators
        # Verify every node has a CC definition.
        for n in st.node_order:
            if n not in cc:
                fail('INCOMPATIBLE',
                     f'E3_CORE_COLLABORATORS_MISSING_FOR_NODE_{n}')
        return {n: cc[n] for n in st.node_order}
    fail('INCOMPATIBLE', 'E3_CORE_COLLABORATORS_REQUIRED')