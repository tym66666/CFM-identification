"""Independent exact replay: full arrangements, coordinate flips, dual algebra.

Shares only strict input records/digest conventions. Does not call the producer,
its constraints, exposure/support engine, vertex search, or linear solver.
Explicit checks (not assert) remain active under python -O.
"""
from fractions import Fraction as F
from itertools import product
from json import dumps
from cfm_id_bridge.scientific_binding import sha
from .bounded_policy_contract import rational
from .mean_order_contract import VERSION, MODEL, validate, input_digest


def _require(ok):
    if not ok:
        raise ValueError('INVALID_MEAN_ORDER_CERTIFICATE')


def replay(certificate, *, problem):
    try:
        _check(certificate, validate(problem))
        return True
    except (ValueError, TypeError, KeyError, IndexError, AttributeError, ArithmeticError):
        return False


def _check(cert, p):
    _require(type(cert) is dict)
    common = {'version','theorem','input_sha256','model_scope','scientific_approval',
              'production_admission','estimation_handoff_allowed','status','certificate_sha256'}
    infeasible = cert.get('status') == 'INCOMPATIBLE'
    fields = {'farkas'} if infeasible else {'lower','upper','width','baseline_bounds_only_range',
        'informative_relative_to_bounds_only','sharp','cells','lower_dual','upper_dual','realization'}
    _require(set(cert) == common | fields)
    _require(cert['version'] == VERSION and cert['model_scope'] == MODEL
             and cert['theorem'] == 'FINITE_MEAN_ORDER_PRIMAL_DUAL')
    _require(cert['input_sha256'] == input_digest(p))
    _require(cert['certificate_sha256'] == sha({k:v for k,v in cert.items() if k != 'certificate_sha256'}))
    for field in ('scientific_approval','production_admission','estimation_handoff_allowed'):
        _require(cert[field] is False)
    nodes = p.node_order; n = len(nodes)
    adjacent = [[] for _ in nodes]
    for a, b in p.undirected_edges:
        i, j = nodes.index(a), nodes.index(b)
        adjacent[i].append(j); adjacent[j].append(i)
    assignments = list(product((0, 1), repeat=n))
    signatures = {}
    for z in assignments:
        signatures[z] = [(nodes[i], z[i], int(sum(z[j] for j in adjacent[i])*2 > len(adjacent[i])))
                         for i in range(n)]
    cells = sorted({c for ss in signatures.values() for c in ss}, key=lambda c:(nodes.index(c[0]),c[1],c[2]))
    supported = [z for z in assignments if sum(z) == p.quota]
    support = {c:F(sum(c in signatures[z] for z in supported),len(supported)) for c in cells}
    known = {(v.node,v.own,v.exposure):rational(v.value) for v in p.values}
    _require(set(known) <= set(cells) and all(support[c] > 0 for c in known))
    ranges = {}
    for b in p.bounds:
        lower, upper = rational(b.lower), rational(b.upper)
        if p.outcome_kind == 'binary' and p.bounds_kind == 'ALMOST_SURE_OUTCOME':
            permitted = sorted(v for v in (F(0),F(1)) if lower <= v <= upper)
            ranges[b.node] = (permitted[0],permitted[-1]) if permitted else (F(1),F(0))
        elif p.outcome_kind == 'binary':
            ranges[b.node] = max(lower,F(0)),min(upper,F(1))
        else:
            ranges[b.node] = lower,upper
    rows = {}
    def tag(kind, coord):
        return kind + ':' + dumps(coord,ensure_ascii=False,separators=(',',':'))
    for c in cells:
        low, high = ranges[c[0]]
        rows[tag('bound_lower',c)] = ({c:F(-1)},-low)
        rows[tag('bound_upper',c)] = ({c:F(1)},high)
        if c in known:
            rows[tag('a4_lower',c)] = ({c:F(-1)},-known[c])
            rows[tag('a4_upper',c)] = ({c:F(1)},known[c])
    modes = {r.node:r.mode for r in p.node_orders}
    # Reconstruct only licensed one-coordinate changes from original full
    # vectors. The producer directly builds a small abstract signature poset.
    for z in assignments:
        for j in range(n):
            if z[j]: continue
            zz = tuple(1 if k == j else v for k,v in enumerate(z))
            for i, node in enumerate(nodes):
                licensed = ((i == j and modes[node] in ('OWN','BOTH')) or
                            (j in adjacent[i] and modes[node] in ('PEERS','BOTH')))
                a,b = signatures[z][i],signatures[zz][i]
                if licensed and a != b:
                    rows[tag('order',(a,b))] = ({a:F(1),b:F(-1)},F(0))
    coefficient = dict.fromkeys(cells,F(0))
    for i,w in enumerate(p.weights):
        coefficient[signatures[tuple(p.first)][i]] += rational(w)
        coefficient[signatures[tuple(p.second)][i]] -= rational(w)
    _require(not any(d and support[c] > 0 and c not in known for c,d in coefficient.items()))

    def combine(proof):
        _require(type(proof) is dict and set(proof) <= set(rows))
        total = dict.fromkeys(cells,F(0)); rhs = F(0)
        for cid, value in proof.items():
            multiplier = rational(value)
            _require(multiplier > 0)  # sparse canonical form; zero entries omitted
            a,b = rows[cid]; rhs += multiplier*b
            for c, v in a.items(): total[c] += multiplier*v
        return total,rhs

    if infeasible:
        normal,rhs = combine(cert['farkas'])
        _require(not any(normal.values()) and rhs < 0)
        return
    _require(cert['status'] in ('POINT','PARTIAL') and cert['sharp'] is True)
    lower,upper = rational(cert['lower']),rational(cert['upper'])
    _require(lower <= upper and rational(cert['width']) == upper-lower)
    _require(cert['status'] == ('POINT' if lower == upper else 'PARTIAL'))
    _require(type(cert['cells']) is list and len(cert['cells']) == len(cells))
    worlds = [{},{}]
    for row in cert['cells']:
        _require(type(row) is dict and set(row) == {'cell','support','lower_world','upper_world'})
        c = row['cell']
        _require(type(c) is list and len(c) == 3 and type(c[0]) is str
                 and type(c[1]) is int and type(c[2]) is int)
        c = tuple(c)
        _require(c in support and c not in worlds[0] and rational(row['support']) == support[c])
        for k,field in enumerate(('lower_world','upper_world')): worlds[k][c] = rational(row[field])
    for world,endpoint in zip(worlds,(lower,upper)):
        for normal,rhs in rows.values():
            _require(sum(v*world[c] for c,v in normal.items()) <= rhs)
        # Direct policy-value calculation, not a producer's coefficient list.
        value = sum(rational(w)*(world[signatures[tuple(p.first)][i]]-
                               world[signatures[tuple(p.second)][i]]) for i,w in enumerate(p.weights))
        _require(value == endpoint)
        for c,b in known.items():
            observed = [world[signatures[z][nodes.index(c[0])]] for z in supported if c in signatures[z]]
            _require(sum(observed)/len(observed) == b)
    for field,sign,endpoint in (('lower_dual',-1,lower),('upper_dual',1,upper)):
        normal,rhs = combine(cert[field])
        _require(all(normal[c] == sign*coefficient[c] for c in cells) and rhs == sign*endpoint)
    baseline = [F(0),F(0)]
    for c,d in coefficient.items():
        a,b = ranges[c[0]]
        baseline[0] += min(d*a,d*b); baseline[1] += max(d*a,d*b)
    _require(type(cert['baseline_bounds_only_range']) is list
             and cert['baseline_bounds_only_range'] == list(map(str,baseline)))
    expected = lower > baseline[0] or upper < baseline[1]
    _require(type(cert['informative_relative_to_bounds_only']) is bool
             and cert['informative_relative_to_bounds_only'] == expected)
    _require(cert['realization'] == ('COMMON_UNIFORM_PER_NODE' if p.outcome_kind == 'binary'
                                    else 'DETERMINISTIC_SIGNATURE_OUTCOMES'))
