"""Exact small-block optimizer producing primal/dual or Farkas evidence.

No floating LP, no external model, and no scientific approval. The independent
verifier does not import this module or its compiler/linear algebra.
"""
from fractions import Fraction as F
from itertools import combinations, product
from json import dumps
from math import comb
from cfm_id_bridge.scientific_binding import sha
from .mean_order_contract import VERSION, MODEL, validate, input_digest, MeanOrderUnavailable


def _id(kind, *coordinates):
    return kind + ':' + dumps(coordinates[0] if len(coordinates) == 1 else coordinates,
                             ensure_ascii=False, separators=(',', ':'))


def _compile(p):
    neighbors = {n: set() for n in p.node_order}
    for a, b in p.undirected_edges:
        neighbors[a].add(b); neighbors[b].add(a)
    cells = [(n, a, e) for n in p.node_order for a in (0, 1)
             for e in ((0, 1) if neighbors[n] else (0,))]
    # Production path counts local configurations combinatorially. Replay
    # instead enumerates complete assignments, without this counting formula.
    support = {}
    for c in cells:
        n, a, e = c; degree = len(neighbors[n]); other = len(p.node_order)-degree-1
        count = sum(comb(degree, k)*comb(other, p.quota-a-k)
                    for k in range(degree+1)
                    if int(2*k > degree) == e and 0 <= p.quota-a-k <= other)
        support[c] = F(count, comb(len(p.node_order), p.quota))
    known = {(v.node, v.own, v.exposure): F(v.value) for v in p.values}
    if not set(known) <= set(cells) or any(support[c] == 0 for c in known):
        raise MeanOrderUnavailable('CHECK_BLOCKED', 'A4_REQUIRES_REALIZABLE_POSITIVE_PROBABILITY_CELL')
    bounds = {}
    for b in p.bounds:
        lo, hi = F(b.lower), F(b.upper)
        if p.outcome_kind == 'binary':
            if p.bounds_kind == 'ALMOST_SURE_OUTCOME':
                allowed = [F(v) for v in (0, 1) if lo <= v <= hi]
                lo, hi = (min(allowed), max(allowed)) if allowed else (F(1), F(0))
            else:
                lo, hi = max(lo, F(0)), min(hi, F(1))
        bounds[b.node] = lo, hi
    coeff = dict.fromkeys(cells, F(0))
    for sign, z in ((1, p.first), (-1, p.second)):
        assignment = dict(zip(p.node_order, z))
        for n, w in zip(p.node_order, p.weights):
            e = int(2*sum(assignment[j] for j in neighbors[n]) > len(neighbors[n]))
            coeff[n, assignment[n], e] += sign*F(w)
    if any(d and support[c] > 0 and c not in known for c, d in coeff.items()):
        raise MeanOrderUnavailable('NEEDS_INPUT', 'SUPPORTED_NONZERO_TARGET_A4_MEAN_MISSING')
    modes = {r.node: r.mode for r in p.node_orders}
    blocks = []
    for n in p.node_order:
        cs = [c for c in cells if c[0] == n]; pos = {c: j for j, c in enumerate(cs)}
        rows = []
        def add(cid, terms, rhs):
            a = [F(0)]*len(cs)
            for c, v in terms.items():
                a[pos[c]] = F(v)
            rows.append((cid, a, F(rhs)))
        for c in cs:
            add(_id('bound_lower', c), {c: -1}, -bounds[n][0])
            add(_id('bound_upper', c), {c: 1}, bounds[n][1])
            if c in known:
                # Equality as two inequalities keeps the certificate uniform.
                add(_id('a4_lower', c), {c: -1}, -known[c])
                add(_id('a4_upper', c), {c: 1}, known[c])
        edges = []
        if modes[n] in ('OWN', 'BOTH'):
            edges += [((n, 0, e), (n, 1, e)) for e in (0, 1) if (n, 0, e) in pos]
        if modes[n] in ('PEERS', 'BOTH') and neighbors[n]:
            edges += [((n, a, 0), (n, a, 1)) for a in (0, 1)]
        for a, b in edges:
            add(_id('order', a, b), {a: 1, b: -1}, 0)
        blocks.append((cs, rows, edges))
    return cells, support, known, bounds, coeff, blocks


def _linear(columns, target):
    """Exact rectangular full-column-rank solve; no optimizer dependency."""
    n = len(columns)
    a = [[col[i] for col in columns] + [v] for i, v in enumerate(target)]
    row = 0
    for j in range(n):
        pivot = next((i for i in range(row, len(a)) if a[i][j]), None)
        if pivot is None:
            return None
        a[row], a[pivot] = a[pivot], a[row]
        den = a[row][j]; a[row] = [x/den for x in a[row]]
        for i in range(len(a)):
            if i != row:
                v = a[i][j]; a[i] = [x-v*y for x, y in zip(a[i], a[row])]
        row += 1
    if any(not any(r[:n]) and r[n] for r in a):
        return None
    return [a[i][-1] for i in range(n)]


def _dot(a, b):
    return sum((x*y for x, y in zip(a, b)), F(0))


def analyze(problem):
    """Material completeness and supported domain only; no identified bounds."""
    return _compile(validate(problem))


def _dual(rows, world, objective):
    if not any(objective):
        return {}
    active = [r for r in rows if _dot(r[1], world) == r[2]]
    for size in range(1, len(objective)+1):
        for basis in combinations(active, size):
            multipliers = _linear([r[1] for r in basis], objective)
            if multipliers is not None and all(v >= 0 for v in multipliers):
                return {r[0]: str(v) for r, v in zip(basis, multipliers) if v}
    raise MeanOrderUnavailable('CHECK_BLOCKED', 'EXACT_OPTIMALITY_EVIDENCE_NOT_FOUND')


def _incompatibility(cs, rows, edges):
    """An order path from a lower anchor to a smaller upper anchor is Farkas.

For bounded order variables these paths characterize feasibility. Non-target
nodes and cancelled cells take part. No numeric infeasibility status is trusted.
"""
    low = {}; high = {}
    for j, c in enumerate(cs):
        lows = [(r, -r[2]) for r in rows if r[1][j] == -1 and sum(v != 0 for v in r[1]) == 1]
        highs = [(r, r[2]) for r in rows if r[1][j] == 1 and sum(v != 0 for v in r[1]) == 1]
        low[c] = max(lows, key=lambda t: t[1]); high[c] = min(highs, key=lambda t: t[1])
    for start in cs:
        paths = {start: []}; queue = [start]
        for c in queue:
            for a, b in edges:
                if a == c and b not in paths:
                    paths[b] = paths[c] + [_id('order', a, b)]; queue.append(b)
        for end, path in paths.items():
            if low[start][1] > high[end][1]:
                ids = [low[start][0][0]] + path + [high[end][0][0]]
                return {cid: '1' for cid in ids}
    return None


def solve(problem):
    """Conditional mathematics only. Use mean_order.submit for synthetic review."""
    p = validate(problem)
    cells, support, known, bounds, coeff, blocks = _compile(p)
    common = dict(version=VERSION, theorem='FINITE_MEAN_ORDER_PRIMAL_DUAL',
        input_sha256=input_digest(p), model_scope=MODEL, scientific_approval=False,
        production_admission=False, estimation_handoff_allowed=False)
    for cs, rows, edges in blocks:
        proof = _incompatibility(cs, rows, edges)
        if proof is not None:
            result = dict(common, status='INCOMPATIBLE', farkas=proof)
            result['certificate_sha256'] = sha(result)
            return result
    worlds = [dict(), dict()]; duals = [dict(), dict()]
    for cs, rows, edges in blocks:
        # Every vertex of an order/anchor polytope has coordinates in its
        # finite anchor set; unanchored equal components could be perturbed.
        anchors = sorted(set(bounds[cs[0][0]]) | {known[c] for c in cs if c in known})
        feasible = (w for w in product(*( [known[c]] if c in known else anchors for c in cs))
                    if all(_dot(r[1], w) <= r[2] for r in rows))
        objectives = [coeff[c] for c in cs]
        lo = hi = None
        for w in feasible:
            value = _dot(objectives, w)
            if lo is None or value < lo[0]: lo = value, w
            if hi is None or value > hi[0]: hi = value, w
        if lo is None:
            raise MeanOrderUnavailable('CHECK_BLOCKED', 'NO_EXACT_FEASIBILITY_WITNESS')
        for k, extreme in enumerate((lo, hi)):
            world = extreme[1]; worlds[k].update(zip(cs, world))
            direction = [-d for d in objectives] if k == 0 else objectives
            duals[k].update(_dual(rows, world, direction))
    endpoints = [sum((coeff[c]*w[c] for c in cells), F(0)) for w in worlds]
    lower, upper = endpoints
    logical = [sum((min(coeff[c]*bounds[c[0]][0], coeff[c]*bounds[c[0]][1]) for c in cells), F(0)),
               sum((max(coeff[c]*bounds[c[0]][0], coeff[c]*bounds[c[0]][1]) for c in cells), F(0))]
    result = dict(common, status='POINT' if lower == upper else 'PARTIAL',
        lower=str(lower), upper=str(upper), width=str(upper-lower),
        baseline_bounds_only_range=list(map(str, logical)),
        informative_relative_to_bounds_only=lower > logical[0] or upper < logical[1], sharp=True,
        cells=[dict(cell=list(c), support=str(support[c]), lower_world=str(worlds[0][c]),
                    upper_world=str(worlds[1][c])) for c in cells],
        lower_dual=duals[0], upper_dual=duals[1],
        realization='COMMON_UNIFORM_PER_NODE' if p.outcome_kind == 'binary'
                    else 'DETERMINISTIC_SIGNATURE_OUTCOMES')
    result['certificate_sha256'] = sha(result)
    return result
