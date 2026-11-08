"""Signed box optimization with shared endpoint worlds; not interval subtraction."""
from fractions import Fraction as F
from cfm_id_bridge.scientific_binding import sha
from pfn_pipeline._internal.identification.randomized_arm_family import (
    AssignmentSpec, ExposureSpec, SupportEngine,
)
from .bounded_policy_contract import fail
from .bounded_contrast_contract import VERSION, SIDES, validate_pair, target_coordinates, input_digest


def analyze(inquiries, information):
    """Check model/support/material completeness; return no identified interval."""
    st, targets, known, bounds = validate_pair(inquiries, information)
    neighbors = {n: set() for n in st.node_order}
    for a, b in st.undirected_edges:
        neighbors[a].add(b); neighbors[b].add(a)
    exposure = ExposureSpec('strict_majority_ties_low')
    assignment = AssignmentSpec(st.design())
    cells, probabilities = [], {}
    for n in st.node_order:
        for a in (0, 1):
            for e in ((0, 1) if neighbors[n] else (0,)):
                c = n, a, e
                cells.append(c)
                probabilities[c] = SupportEngine.evaluate(network=st.network(), assignment=assignment,
                    exposure=exposure, node_id=n, own_treatment_value=a,
                    exposure_value=e).joint_probability
    if not set(known) <= set(cells):
        fail('INCOMPATIBLE', 'A4_SIGNATURE_NOT_REALIZABLE')
    if any(probabilities[c] <= 0 for c in known):
        fail('INCOMPATIBLE', 'A4_CONDITIONAL_EVENT_HAS_ZERO_PROBABILITY')
    coefficients = {c: F(0) for c in cells}
    for side, sign in zip(SIDES, (1, -1)):
        t = targets[side]; policy = dict(zip(st.node_order, t.policy_assignment))
        for n, weight in zip(st.node_order, t.unit_weights):
            c = n, policy[n], exposure.classify(sum(policy[j] for j in neighbors[n]), len(neighbors[n]))
            coefficients[c] += sign * F(weight)
    # Cancellation precedes the material-completeness rule; declared A4 is never discarded.
    if any(d and probabilities[c] > 0 and c not in known for c, d in coefficients.items()):
        fail('NEEDS_INPUT', 'SUPPORTED_NONZERO_CONTRAST_A4_MEAN_MISSING')
    return st, known, bounds, cells, probabilities, coefficients


def solve(inquiries, information):
    st, known, bounds, cells, probabilities, coefficients = analyze(inquiries, information)
    rows, terms = [], []
    logical = [F(0), F(0)]
    for c in cells:
        d = coefficients[c]; lo, hi = bounds[c[0]]
        logical[0] += min(d*lo, d*hi); logical[1] += max(d*lo, d*hi)
        a, b = (known[c], known[c]) if c in known else (lo, hi)
        low, high = (a, b) if d > 0 else (b, a) if d < 0 else ((a+b)/2, (a+b)/2)
        rows.append(dict(cell=list(c), support=str(probabilities[c]),
            a4_value=str(known[c]) if c in known else None,
            lower_world=str(low), upper_world=str(high)))
        if d:
            terms.append(dict(cell=list(c), coefficient=str(d),
                basis='A4_EQUALITY' if c in known else 'MEAN_BOUNDS',
                cell_lower=str(a), cell_upper=str(b),
                lower_contribution=str(d*low), upper_contribution=str(d*high)))
    lower = sum((F(t['lower_contribution']) for t in terms), F(0))
    upper = sum((F(t['upper_contribution']) for t in terms), F(0))
    certificate = dict(version=VERSION, theorem='FINITE_SIGNATURE_MEAN_BOX_CONTRAST',
        input_sha256=input_digest(inquiries, information), target_sha256=sha(target_coordinates(inquiries)),
        status='POINT' if lower == upper else 'PARTIAL', lower=str(lower), upper=str(upper),
        width=str(upper-lower), logical_range=list(map(str, logical)),
        informative=lower > logical[0] or upper < logical[1], sharp=True,
        model_scope=information['first'].model_scope, cells=rows, bound_terms=terms,
        realization='BERNOULLI_PER_NODE_SIGNATURE' if st.outcome_kind == 'binary'
            else 'DETERMINISTIC_PER_NODE_SIGNATURE',
        production_admission=False, estimation_handoff_allowed=False)
    certificate['certificate_sha256'] = sha(certificate)
    return certificate
