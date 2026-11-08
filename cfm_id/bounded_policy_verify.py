"""Independent finite replay: full binary vectors, exact arithmetic, witnesses.

Does NOT import the producer, SupportEngine or its exposure/count primitives.
It shares typed input validation, not the numerical proof. This is executable
mathematical verification, not Lean/Coq or authentication of a human reviewer.
"""
from copy import deepcopy
from fractions import Fraction as F
from itertools import product

from cfm_id_bridge.scientific_binding import sha
from .bounded_policy_contract import VERSION, rational, validate_model, input_digest


def _require(condition):
    # Unlike assert, proof checks must remain active under python -O.
    if not condition:
        raise ValueError('BOUNDED_CERTIFICATE_INVALID')


def replay(certificate, *, inquiry, information):
    try:
        _check(certificate, inquiry, information)
        return True
    except (ValueError, TypeError, KeyError, AttributeError, IndexError,
            ZeroDivisionError, OverflowError, AssertionError):
        return False


def _check(certificate, inquiry, information):
    st, target, known, bounds = validate_model(inquiry, information)
    _require(type(certificate) is dict)
    cert = deepcopy(certificate)
    digest = cert.pop('certificate_sha256')
    _require(sha(cert) == digest)
    _require(set(cert) == {'version', 'theorem', 'input_sha256', 'target_sha256', 'status',
        'lower', 'upper', 'width', 'logical_range', 'informative', 'sharp', 'model_scope',
        'cells', 'bound_terms', 'realization', 'production_admission', 'estimation_handoff_allowed'})
    _require(cert['version'] == VERSION and cert['theorem'] == 'FINITE_SIGNATURE_MEAN_BOX')
    _require(cert['input_sha256'] == input_digest(inquiry, information))
    _require(cert['target_sha256'] == sha(target) and cert['model_scope'] == information.model_scope)
    _require(cert['sharp'] is True and cert['production_admission'] is False)
    _require(cert['estimation_handoff_allowed'] is False)
    n = len(st.node_order)
    indexes = {node: i for i, node in enumerate(st.node_order)}
    adjacency = [[] for _ in range(n)]
    for a, b in st.undirected_edges:
        adjacency[indexes[a]].append(indexes[b]); adjacency[indexes[b]].append(indexes[a])

    def cell(i, vector):
        return (st.node_order[i], vector[i],
            int(2 * sum(vector[j] for j in adjacency[i]) > len(adjacency[i])))

    vectors = list(product((0, 1), repeat=n))
    observable = [z for z in vectors if sum(z) == st.design().m]
    cells = {(st.node_order[i], z[i], cell(i, z)[2]) for z in vectors for i in range(n)}
    counts = {c: 0 for c in cells}
    for z in observable:
        for i in range(n):
            counts[cell(i, z)] += 1
    _require(observable and set(known) <= cells)
    _require(all(counts[c] > 0 for c in known))
    masses = {c: F(counts[c], len(observable)) for c in cells}
    _require(type(cert['cells']) is list and len(cert['cells']) == len(cells))
    rows = {}
    for row in cert['cells']:
        _require(type(row) is dict and set(row) == {'cell', 'support', 'a4_value', 'lower_world', 'upper_world'})
        coord = row['cell']
        _require(type(coord) is list and len(coord) == 3 and type(coord[0]) is str
                and type(coord[1]) is int and type(coord[2]) is int)
        c = tuple(coord)
        _require(c in cells and c not in rows)
        rows[c] = row
        _require(rational(row['support']) == masses[c])
        _require(row['a4_value'] == (str(known[c]) if c in known else None))
        for side in ('lower_world', 'upper_world'):
            v = rational(row[side]); lo, hi = bounds[c[0]]
            _require(lo <= v <= hi)
            if c in known:
                _require(v == known[c])
    # Reconstruct the complete potential-mean arrays and the actual A4 O m=b.
    for side in ('lower_world', 'upper_world'):
        sums = {c: F(0) for c in known}
        for z in observable:
            for i in range(n):
                c = cell(i, z)
                if c in known:
                    sums[c] += rational(rows[c][side])
        _require(all(sums[c] / counts[c] == known[c] for c in known))

    expected_terms = []
    logical = [F(0), F(0)]
    for i, w in enumerate(target.unit_weights):
        weight = F(w); c = cell(i, target.policy_assignment)
        lo, hi = bounds[st.node_order[i]]
        logical[0] += weight * lo; logical[1] += weight * hi
        if not weight:
            continue
        _require(weight > 0 and (masses[c] == 0 or c in known))
        a, b = (known[c], known[c]) if c in known else (lo, hi)
        expected_terms.append(dict(cell=list(c), coefficient=str(weight),
            basis='A4_EQUALITY' if c in known else 'MEAN_BOUNDS', lower=str(a), upper=str(b)))
    # Exact equality and nonnegative-bound multipliers certify universal bounds.
    _require(sha(cert['bound_terms']) == sha(expected_terms))
    low, high = rational(cert['lower']), rational(cert['upper'])
    _require(low == sum((F(t['coefficient'])*F(t['lower']) for t in expected_terms), F(0)))
    _require(high == sum((F(t['coefficient'])*F(t['upper']) for t in expected_terms), F(0)))
    for side, endpoint in (('lower_world', low), ('upper_world', high)):
        value = sum((F(w)*rational(rows[cell(i, target.policy_assignment)][side])
                     for i, w in enumerate(target.unit_weights)), F(0))
        _require(value == endpoint)  # Universal bound + attainable model = sharp.
    _require(cert['width'] == str(high-low) and cert['logical_range'] == list(map(str, logical)))
    _require(type(cert['informative']) is bool)
    _require(cert['informative'] == (low > logical[0] or high < logical[1]))
    _require(cert['status'] == ('POINT' if low == high else 'PARTIAL'))
    expected_realization = ('BERNOULLI_PER_NODE_SIGNATURE' if st.outcome_kind == 'binary'
        else 'DETERMINISTIC_PER_NODE_SIGNATURE')
    _require(cert['realization'] == expected_realization)
