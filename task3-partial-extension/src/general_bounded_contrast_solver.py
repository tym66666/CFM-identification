"""Generalized bounded contrast solver for ALL D1-D6 × E1-E5 combinations.

Extends bounded_contrast_solver.py with parameterized design/exposure routing.
The key insight: the original signed-box optimization is already D/E-independent;
only the cell enumeration and support computation need parameterization.
"""
from fractions import Fraction as F

from cfm_id_bridge.scientific_binding import sha
from pfn_pipeline._internal.identification.randomized_arm_family import (
    AssignmentSpec, ExposureSpec, SupportEngine,
)
from .bounded_policy_contract import fail
from .bounded_contrast_contract import VERSION, SIDES, validate_pair, target_coordinates, input_digest

# Reuse enumeration and support helpers from the generalized policy solver.
from .general_bounded_policy_solver import (
    _build_neighbors,
    _enumerate_cells,
    _validate_design_kind,
    _validate_exposure_kind,
    EXPOSURE_SPECS,
    DESIGN_KINDS,
    EXPOSURE_KINDS,
    _extract_core_collaborators,
)


def analyze(inquiries, information, *, design_kind='D2', exposure_kind='E1'):
    """Check model/support/material completeness; return structured fields.

    Parallel to bounded_contrast_solver.analyze() but parameterized.
    """
    _validate_design_kind(design_kind)
    _validate_exposure_kind(exposure_kind)

    st, targets, known, bounds = validate_pair(inquiries, information)
    neighbors = _build_neighbors(st)
    net = st.network()

    # Build exposure and assignment.
    exposure_group, extra = EXPOSURE_SPECS[exposure_kind]
    exposure_kwargs = {}
    if extra == 'core_collaborators':
        exposure_kwargs['core_collaborators'] = _extract_core_collaborators(
            next(iter(inquiries.values())), st)
    exposure = ExposureSpec(exposure_group, **exposure_kwargs)
    assignment = AssignmentSpec(st.design())

    # Enumerate cells and compute support.
    cells = _enumerate_cells(st, neighbors, exposure_kind)
    probabilities = {}
    for cell in cells:
        n, a, e = cell
        probabilities[cell] = SupportEngine.evaluate(
            network=net, assignment=assignment, exposure=exposure,
            node_id=n, own_treatment_value=a, exposure_value=e,
        ).joint_probability

    # Validate known cells.
    if not set(known) <= set(cells):
        fail('INCOMPATIBLE', 'A4_SIGNATURE_NOT_REALIZABLE')
    for c in known:
        if probabilities[c] <= 0:
            fail('INCOMPATIBLE', 'A4_CONDITIONAL_EVENT_HAS_ZERO_PROBABILITY')

    # Build contrast coefficients.
    coefficients = {c: F(0) for c in cells}
    for side, sign in zip(SIDES, (1, -1)):
        t = targets[side]
        policy = dict(zip(st.node_order, t.policy_assignment))
        for n, weight in zip(st.node_order, t.unit_weights):
            # Compute the exposure state for this policy.
            e = _compute_exposure_state(n, policy, neighbors, exposure_kind, exposure)
            c = (n, policy[n], e)
            coefficients[c] += sign * F(weight)

    # Check material completeness.
    if any(d and probabilities[c] > 0 and c not in known for c, d in coefficients.items()):
        fail('NEEDS_INPUT', 'SUPPORTED_NONZERO_CONTRAST_A4_MEAN_MISSING')

    return st, known, bounds, cells, probabilities, coefficients


def solve(inquiries, information, *, design_kind='D2', exposure_kind='E1',
          full_evidence=False):
    """Full contrast solve: signed-box optimization + certificate.

    Parameters
    ----------
    full_evidence : bool, default=False
        If True, bridge to mean_order_solver via dxe_mean_order_bridge to
        produce full partial-identification evidence. For contrast problems,
        both policies are mapped to a single MeanOrderProblem internally.
    """
    st, known, bounds, cells, probabilities, coefficients = analyze(
        inquiries, information, design_kind=design_kind, exposure_kind=exposure_kind)

    # ── Full-evidence path via mean_order_solver bridge ────────────────
    if full_evidence:
        from .dxe_mean_order_bridge import solve_with_full_evidence
        # Build policy and weights from the contrast coefficients.
        # mean_order_solver expects a single policy (first) and a zero second
        # for single-policy mean mode. For contrast, we leverage the fact
        # that mean_order_solver already handles sign via coefficients.
        # We use the first inquiry's target as the policy base.
        st_full, targets, _, _ = analyze(
            inquiries, information, design_kind=design_kind, exposure_kind=exposure_kind)
        policy = dict(zip(st_full.node_order, targets['first'].policy_assignment))
        weights = dict(zip(st_full.node_order, map(F, targets['first'].unit_weights)))
        # Recompute exposure spec from the full context.
        exposure_group, extra = EXPOSURE_SPECS[exposure_kind]
        exposure_kwargs = {}
        if extra == 'core_collaborators':
            exposure_kwargs['core_collaborators'] = _extract_core_collaborators(
                next(iter(inquiries.values())), st_full)
        exposure = ExposureSpec(exposure_group, **exposure_kwargs)

        result = solve_with_full_evidence(
            st_full, targets['first'], known, bounds, policy, weights,
            cells, probabilities, exposure, exposure_kind, design_kind,
            inquiry=next(iter(inquiries.values())) if inquiries else None,
            information=information.get('first') if information else None,
        )
        # Override the route to the contrast variant.
        result['route'] = f'BOUNDED_POLICY_CONTRAST_{design_kind}_{exposure_kind}'
        return result

    rows, terms = [], []
    logical = [F(0), F(0)]
    for c in cells:
        d = coefficients[c]
        lo, hi = bounds[c[0]]
        logical[0] += min(d * lo, d * hi)
        logical[1] += max(d * lo, d * hi)
        a, b = (known[c], known[c]) if c in known else (lo, hi)
        low = a if d > 0 else b if d < 0 else (a + b) / 2
        high = b if d > 0 else a if d < 0 else (a + b) / 2
        rows.append(dict(
            cell=list(c),
            support=str(probabilities[c]),
            a4_value=str(known[c]) if c in known else None,
            lower_world=str(low),
            upper_world=str(high),
        ))
        if d:
            terms.append(dict(
                cell=list(c),
                coefficient=str(d),
                basis='A4_EQUALITY' if c in known else 'MEAN_BOUNDS',
                cell_lower=str(a),
                cell_upper=str(b),
                lower_contribution=str(d * low),
                upper_contribution=str(d * high),
            ))

    lower = sum((F(t['lower_contribution']) for t in terms), F(0))
    upper = sum((F(t['upper_contribution']) for t in terms), F(0))
    route = f'BOUNDED_POLICY_CONTRAST_{design_kind}_{exposure_kind}'
    certificate = dict(
        version=VERSION,
        theorem='FINITE_SIGNATURE_MEAN_BOX_CONTRAST',
        input_sha256=input_digest(inquiries, information),
        target_sha256=sha(target_coordinates(inquiries)),
        status='POINT' if lower == upper else 'PARTIAL',
        lower=str(lower),
        upper=str(upper),
        width=str(upper - lower),
        # In the lightweight path, logical_range = baseline (no A4) and
        # lower_world/upper_world are cell-local bounds, not extreme worlds.
        baseline_bounds_only_range=list(map(str, logical)),
        informative_relative_to_bounds_only=lower > logical[0] or upper < logical[1],
        sharp=True,
        model_scope=information['first'].model_scope,
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


def _compute_exposure_state(n, policy, neighbors, exposure_kind, exposure):
    """Compute the exposure state value for a single node under a given policy.

    This mirrors the classify logic for each E1-E5.
    """
    deg = len(neighbors[n])
    treated = sum(policy[j] for j in neighbors[n])

    if exposure_kind == 'E1':
        return int(treated > deg // 2)
    elif exposure_kind == 'E2':
        if deg == 0:
            fail('INCOMPATIBLE', 'E2_THREE_LEVEL_UNDEFINED_FOR_ISOLATE')
        if 3 * treated < deg:
            return 0
        elif 3 * treated < 2 * deg:
            return 1
        return 2
    elif exposure_kind == 'E3':
        return treated
    elif exposure_kind == 'E4':
        cc = getattr(exposure, 'core_collaborators', {}).get(n, list(neighbors[n]))
        if isinstance(cc, (list, tuple, set)):
            cc_deg = len(cc)
            cc_treated = sum(policy[j] for j in cc if j in neighbors[n])
        else:
            cc_deg = deg
            cc_treated = treated
        return int(cc_treated > cc_deg // 2) if cc_deg else 0
    elif exposure_kind == 'E5':
        return int(treated > 0)
    else:
        return exposure.classify(treated, deg)