"""Independent replay for a signed contrast on one finite mean model.

Full binary vectors, direct adjacency counts and exact arithmetic are rebuilt
here. No producer, SupportEngine, exposure classifier or coefficient helper is
imported. Only typed model validation and input binding are shared. The theorem
and outcome-realization obligations are in BOUNDED_CONTRAST_MATH_ZH.txt.
"""
from copy import deepcopy
from fractions import Fraction as F
from itertools import product

from cfm_id_bridge.scientific_binding import sha
from .bounded_policy_contract import rational
from .bounded_contrast_contract import (
    VERSION, validate_pair, input_digest, target_coordinates,
)


def _require(condition):
    # Proof checks must survive python -O.
    if not condition:
        raise ValueError('BOUNDED_CONTRAST_CERTIFICATE_INVALID')


def replay(certificate, *, inquiries, information):
    try:
        _check(certificate, inquiries, information)
        return True
    except (ValueError, TypeError, KeyError, AttributeError, IndexError,
            ZeroDivisionError, OverflowError, AssertionError):
        return False


def _check(certificate, inquiries, information):
    st, targets, known, bounds = validate_pair(inquiries, information)
    _require(type(certificate) is dict)
    cert = deepcopy(certificate)
    digest = cert.pop('certificate_sha256')
    _require(sha(cert) == digest)
    _require(set(cert) == {
        'version', 'theorem', 'input_sha256', 'target_sha256', 'status',
        'lower', 'upper', 'width', 'logical_range', 'informative', 'sharp',
        'model_scope', 'cells', 'bound_terms', 'realization',
        'production_admission', 'estimation_handoff_allowed',
    })
    _require(cert['version'] == VERSION)
    _require(cert['theorem'] == 'FINITE_SIGNATURE_MEAN_BOX_CONTRAST')
    _require(cert['input_sha256'] == input_digest(inquiries, information))
    _require(cert['target_sha256'] == sha(target_coordinates(inquiries)))
    _require(cert['model_scope'] == information['first'].model_scope)
    _require(cert['sharp'] is True and cert['production_admission'] is False)
    _require(cert['estimation_handoff_allowed'] is False)

    nodes = st.node_order
    n = len(nodes)
    indexes = {node: i for i, node in enumerate(nodes)}
    neighbors = [[] for _ in nodes]
    for left, right in st.undirected_edges:
        neighbors[indexes[left]].append(indexes[right])
        neighbors[indexes[right]].append(indexes[left])

    def cell(i, vector):
        return (nodes[i], vector[i],
                int(2 * sum(vector[j] for j in neighbors[i]) > len(neighbors[i])))

    vectors = list(product((0, 1), repeat=n))
    observed = [z for z in vectors if sum(z) == st.design().m]
    cells = {cell(i, z) for z in vectors for i in range(n)}
    ordered_cells = sorted(cells, key=lambda c: (indexes[c[0]], c[1], c[2]))
    counts = {c: 0 for c in cells}
    for z in observed:
        for i in range(n):
            counts[cell(i, z)] += 1
    _require(observed and set(known) <= cells)
    _require(all(counts[c] > 0 for c in known))
    masses = {c: F(counts[c], len(observed)) for c in cells}

    # A single full table is shared by both policies. Non-target and cancelled
    # coordinates remain constrained by ALL declared A4 information and bounds.
    _require(type(cert['cells']) is list and len(cert['cells']) == len(cells))
    rows = {}
    for row in cert['cells']:
        _require(type(row) is dict and set(row) == {
            'cell', 'support', 'a4_value', 'lower_world', 'upper_world',
        })
        coord = row['cell']
        _require(type(coord) is list and len(coord) == 3 and type(coord[0]) is str
                 and type(coord[1]) is int and type(coord[2]) is int)
        c = tuple(coord)
        _require(c in cells and c not in rows)
        rows[c] = row
        _require(rational(row['support']) == masses[c])
        _require(row['a4_value'] == (str(known[c]) if c in known else None))
        for side in ('lower_world', 'upper_world'):
            value = rational(row[side])
            low, high = bounds[c[0]]
            _require(low <= value <= high)
            if c in known:
                _require(value == known[c])

    # Check the actual observable conditional averages in both complete worlds.
    for side in ('lower_world', 'upper_world'):
        sums = {c: F(0) for c in known}
        for z in observed:
            for i in range(n):
                c = cell(i, z)
                if c in known:
                    sums[c] += rational(rows[c][side])
        _require(all(sums[c] / counts[c] == known[c] for c in known))

    # Recompute the signed coefficients independently; never subtract two
    # independently optimized intervals. Cancellation precedes missing-A4 checks.
    coefficients = {c: F(0) for c in cells}
    for i, weight in enumerate(targets['first'].unit_weights):
        coefficients[cell(i, targets['first'].policy_assignment)] += F(weight)
        coefficients[cell(i, targets['second'].policy_assignment)] -= F(weight)

    terms = []
    logical = [F(0), F(0)]
    for c in ordered_cells:
        coefficient = coefficients[c]
        if not coefficient:
            continue
        _require(masses[c] == 0 or c in known)
        low, high = bounds[c[0]]
        logical[0] += min(coefficient * low, coefficient * high)
        logical[1] += max(coefficient * low, coefficient * high)
        a, b = (known[c], known[c]) if c in known else (low, high)
        terms.append(dict(
            cell=list(c), coefficient=str(coefficient),
            basis='A4_EQUALITY' if c in known else 'MEAN_BOUNDS',
            cell_lower=str(a), cell_upper=str(b),
            lower_contribution=str(min(coefficient * a, coefficient * b)),
            upper_contribution=str(max(coefficient * a, coefficient * b)),
        ))
    # These exact terms prove validity for every model in the declared box.
    _require(type(cert['bound_terms']) is list)
    _require(all(type(term) is dict for term in cert['bound_terms']))
    # sha intentionally canonicalizes Fractions and tuples for input binding;
    # the proof's public term schema must nevertheless contain JSON-native
    # lists and canonical rational strings, without such silent coercions.
    _require(cert['bound_terms'] == terms)
    _require(sha(cert['bound_terms']) == sha(terms))
    low, high = rational(cert['lower']), rational(cert['upper'])
    _require(low == sum((F(t['lower_contribution']) for t in terms), F(0)))
    _require(high == sum((F(t['upper_contribution']) for t in terms), F(0)))

    # Evaluate the ORIGINAL two policies in each same feasible world. This is
    # stronger than merely replaying a producer's claimed merged objective.
    for side, endpoint in (('lower_world', low), ('upper_world', high)):
        first_value = sum((F(w) * rational(rows[cell(i, targets['first'].policy_assignment)][side])
                           for i, w in enumerate(targets['first'].unit_weights)), F(0))
        second_value = sum((F(w) * rational(rows[cell(i, targets['second'].policy_assignment)][side])
                            for i, w in enumerate(targets['second'].unit_weights)), F(0))
        _require(first_value - second_value == endpoint)
    _require(cert['width'] == str(high - low))
    _require(cert['logical_range'] == list(map(str, logical)))
    _require(type(cert['informative']) is bool)
    _require(cert['informative'] == (low > logical[0] or high < logical[1]))
    _require(cert['status'] == ('POINT' if low == high else 'PARTIAL'))
    expected_realization = ('BERNOULLI_PER_NODE_SIGNATURE' if st.outcome_kind == 'binary'
                            else 'DETERMINISTIC_PER_NODE_SIGNATURE')
    _require(cert['realization'] == expected_realization)
