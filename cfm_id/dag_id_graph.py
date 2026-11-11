"""Graph bookkeeping for general identification.

A graph is a plain dict::

    {'nodes': [...], 'directed': [(u, v), ...], 'bidirected': [(u, v), ...]}

Bidirected pairs are stored sorted, so ``(a, b)`` and ``(b, a)`` are one edge.

The three operations the ID recursion needs are:

* ``ancestors``   -- Y and everything that reaches Y along directed edges.
* ``c_components`` -- maximal sets connected by bidirected edges only.
                     These are the blocks that share unobserved causes, and the
                     blocks the recursion cuts the graph into.
* ``remove_incoming`` -- the submodel G_X used by ``do(x)``.

No identification logic lives here.
"""
from .dag_id_contract import fail

VERSION = 'dag-id-graph-1'


def parse(nodes, directed=(), bidirected=()):
    nodes = [str(n) for n in nodes]
    if len(set(nodes)) != len(nodes):
        fail('CHECK_BLOCKED', 'DUPLICATE_NODE')
    node_set = set(nodes)
    out_directed = []
    for a, b in directed:
        if a not in node_set or b not in node_set or a == b:
            fail('CHECK_BLOCKED', 'INVALID_DIRECTED_EDGE')
        out_directed.append((a, b))
    out_bidirected = []
    for a, b in bidirected:
        if a not in node_set or b not in node_set or a == b:
            fail('CHECK_BLOCKED', 'INVALID_BIDIRECTED_EDGE')
        out_bidirected.append(tuple(sorted((a, b))))
    return {'nodes': nodes, 'directed': out_directed, 'bidirected': out_bidirected}


def parents(g, v):
    return {a for a, b in g['directed'] if b == v}


def children(g, v):
    return {b for a, b in g['directed'] if a == v}


def ancestors(g, targets):
    """Ancestors of ``targets`` along directed edges, including the targets.

    Including the target set itself is the convention the ID algorithm relies
    on: line 2 compares ``V == An(Y)`` and that comparison is only meaningful
    when Y is part of its own ancestor set.
    """
    result = set(targets)
    changed = True
    while changed:
        before = len(result)
        result |= {a for a, b in g['directed'] if b in result}
        changed = len(result) != before
    return result


def descendants(g, targets):
    """Descendants of ``targets`` along directed edges, including the targets."""
    result = set(targets)
    changed = True
    while changed:
        before = len(result)
        result |= {b for a, b in g['directed'] if a in result}
        changed = len(result) != before
    return result


def c_components(g):
    """Maximal node sets connected through bidirected edges.

    Two nodes belong to the same block exactly when a chain of bidirected
    edges joins them. Everything else is a block of its own.
    """
    parent = {n: n for n in g['nodes']}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for a, b in g['bidirected']:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    blocks = {}
    for n in g['nodes']:
        blocks.setdefault(find(n), []).append(n)
    return [set(v) for v in blocks.values()]


def induced(g, keep):
    """Subgraph on ``keep``; every edge keeps both endpoints inside."""
    keep = set(keep)
    return {
        'nodes': [n for n in g['nodes'] if n in keep],
        'directed': [(a, b) for a, b in g['directed'] if a in keep and b in keep],
        'bidirected': [(a, b) for a, b in g['bidirected'] if a in keep and b in keep],
    }


def without_nodes(g, drop):
    """G \\ drop: node deletion also drops every incident edge."""
    return induced(g, set(g['nodes']) - set(drop))


def remove_incoming(g, x):
    """G_X, the graph of the submodel produced by ``do(x)``.

    Directed edges into X are cut. A bidirected edge a <-> b stands for an
    unobserved U with U -> a and U -> b; intervening on either endpoint cuts
    its half of the edge, and what remains is a latent that reaches only one
    observed node, which can be summed out. So the whole edge goes.
    """
    x = set(x)
    return {
        'nodes': list(g['nodes']),
        'directed': [(a, b) for a, b in g['directed'] if b not in x],
        'bidirected': [(a, b) for a, b in g['bidirected'] if a not in x and b not in x],
    }


def topological_order(g, subset=None):
    """A topological order of the directed edges, restricted to ``subset``."""
    keep = set(g['nodes']) if subset is None else set(subset)
    indegree = {n: 0 for n in keep}
    children_map = {n: [] for n in keep}
    for a, b in g['directed']:
        if a in keep and b in keep:
            children_map[a].append(b)
            indegree[b] += 1
    queue = [n for n in g['nodes'] if n in keep and indegree[n] == 0]
    order = []
    while queue:
        n = queue.pop(0)
        order.append(n)
        for c in children_map[n]:
            indegree[c] -= 1
            if indegree[c] == 0:
                queue.append(c)
    if len(order) != len(keep):
        fail('CHECK_BLOCKED', 'DIRECTED_CYCLE_NOT_RECURSIVE_MODEL')
    return order


def describe(g):
    """Compact, deterministic description used in certificates and traces."""
    return {
        'nodes': list(g['nodes']),
        'directed': sorted([list(e) for e in g['directed']]),
        'bidirected': sorted([list(e) for e in g['bidirected']]),
        'c_components': sorted([sorted(b) for b in c_components(g)]),
    }
