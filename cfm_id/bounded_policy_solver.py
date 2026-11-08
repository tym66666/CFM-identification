"""Exact box bounds and constructive mean tables for the limited D2/E1 model."""
from fractions import Fraction as F

from cfm_id_bridge.scientific_binding import sha
from pfn_pipeline._internal.identification.randomized_arm_family import (
    AssignmentSpec, ExposureSpec, SupportEngine,
)
from .bounded_policy_contract import VERSION, validate_model, input_digest, fail


def solve(inquiry, information):
    st, target, known, bounds = validate_model(inquiry, information)
    net = st.network()
    neighbors = {n: set() for n in st.node_order}
    for a, b in st.undirected_edges:
        neighbors[a].add(b); neighbors[b].add(a)
    exposure = ExposureSpec('strict_majority_ties_low')
    assignment = AssignmentSpec(st.design())
    policy = dict(zip(st.node_order, target.policy_assignment))
    weights = dict(zip(st.node_order, map(F, target.unit_weights)))
    targets = {n: (n, policy[n], exposure.classify(
        sum(policy[j] for j in neighbors[n]), len(neighbors[n]))) for n in st.node_order}
    cells, probabilities = [], {}
    for n in st.node_order:
        for a in (0, 1):
            for e in ((0, 1) if neighbors[n] else (0,)):
                cell = n, a, e
                cells.append(cell)
                probabilities[cell] = SupportEngine.evaluate(network=net, assignment=assignment,
                    exposure=exposure, node_id=n, own_treatment_value=a,
                    exposure_value=e).joint_probability
    if not set(known) <= set(cells):
        fail('INCOMPATIBLE', 'A4_SIGNATURE_NOT_REALIZABLE')
    if any(probabilities[c] <= 0 for c in known):
        fail('INCOMPATIBLE', 'A4_CONDITIONAL_EVENT_HAS_ZERO_PROBABILITY')
    for n, cell in targets.items():
        if weights[n] and probabilities[cell] > 0 and cell not in known:
            # Material incompleteness is never relabeled as support failure.
            fail('NEEDS_INPUT', 'SUPPORTED_TARGET_A4_MEAN_MISSING')
    rows, terms = [], []
    for cell in cells:
        n, a, e = cell
        lo, hi = bounds[n]
        if cell in known:
            low = high = known[cell]
        elif cell == targets[n] and weights[n]:
            low, high = lo, hi
        else:
            low = high = (lo + hi) / 2
        rows.append(dict(cell=list(cell), support=str(probabilities[cell]),
            a4_value=str(known[cell]) if cell in known else None,
            lower_world=str(low), upper_world=str(high)))
    for n in st.node_order:
        if not weights[n]:
            continue
        cell = targets[n]
        lo, hi = (known[cell], known[cell]) if cell in known else bounds[n]
        terms.append(dict(cell=list(cell), coefficient=str(weights[n]),
            basis='A4_EQUALITY' if cell in known else 'MEAN_BOUNDS',
            lower=str(lo), upper=str(hi)))
    lower = sum((F(t['coefficient']) * F(t['lower']) for t in terms), F(0))
    upper = sum((F(t['coefficient']) * F(t['upper']) for t in terms), F(0))
    logical = [sum((weights[n] * bounds[n][j] for n in st.node_order), F(0)) for j in (0, 1)]
    certificate = dict(version=VERSION, theorem='FINITE_SIGNATURE_MEAN_BOX',
        input_sha256=input_digest(inquiry, information), target_sha256=sha(target),
        status='POINT' if lower == upper else 'PARTIAL', lower=str(lower), upper=str(upper),
        width=str(upper-lower), logical_range=list(map(str, logical)),
        informative=lower > logical[0] or upper < logical[1], sharp=True,
        model_scope=information.model_scope, cells=rows, bound_terms=terms,
        realization='BERNOULLI_PER_NODE_SIGNATURE' if st.outcome_kind == 'binary'
            else 'DETERMINISTIC_PER_NODE_SIGNATURE',
        production_admission=False, estimation_handoff_allowed=False)
    certificate['certificate_sha256'] = sha(certificate)
    return certificate
