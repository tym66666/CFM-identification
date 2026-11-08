"""Independent directed/active-path replay; never imports a solver or its formula."""
from itertools import combinations
from .dag_frontdoor_contract import validate, digest, VERSION, THEOREM, CLAIM_SCOPE
from cfm_id_bridge.scientific_binding import sha


def _closure(nodes, edges):
    reach = {n: {n} for n in nodes}
    for a, b in edges:
        reach[a].add(b)
    for k in nodes:
        for n in nodes:
            if k in reach[n]:
                reach[n] |= reach[k]
    return reach


def _directed_paths(edges, start, end):
    paths = []
    def walk(path):
        if path[-1] == end:
            paths.append(path)
            return
        for a, b in edges:
            if a == path[-1] and b not in path:
                walk(path + [b])
    walk([start])
    return paths


def _has_active_path(nodes, edges, start, end, conditioned):
    arrows = set(map(tuple, edges))
    adjacency = {n: set() for n in nodes}
    for a, b in arrows:
        adjacency[a].add(b)
        adjacency[b].add(a)
    reach = _closure(nodes, edges)
    z = set(conditioned)
    def walk(path):
        if path[-1] == end:
            for a, b, c in zip(path, path[1:], path[2:]):
                collider = (a, b) in arrows and (c, b) in arrows
                if collider and not (reach[b] & z):
                    return False
                if not collider and b in z:
                    return False
            return True
        return any(walk(path + [n]) for n in sorted(adjacency[path[-1]] - set(path)))
    return walk([start])


def independent_conditions(problem, mediator):
    x, y = problem.treatment, problem.outcome
    graph2 = [e for e in problem.edges if e[0] != x]
    graph3 = [e for e in problem.edges if e[0] != mediator]
    return dict(
        FD1=all(mediator in path for path in _directed_paths(problem.edges, x, y)),
        FD2=not _has_active_path(problem.nodes, graph2, x, mediator, []),
        FD3=not _has_active_path(problem.nodes, graph3, mediator, y, [x]),
    )


def _moral_trace(nodes, edges, start, end, conditioned):
    # Reconstruct solver diagnostics independently; validity above uses paths.
    closure = _closure(nodes, edges)
    relevant = {start, end, *conditioned}
    ancestors = {n for n in nodes if closure[n] & relevant}
    arrows = set(map(tuple, edges))
    moral = []
    for a, b in combinations(sorted(ancestors), 2):
        if ((a, b) in arrows or (b, a) in arrows or
                any((a, c) in arrows and (b, c) in arrows for c in ancestors)):
            moral.append([a, b])
    reached = {start}
    while True:
        added = {b if a in reached else a for a, b in moral
                 if (a in reached or b in reached) and
                 a not in conditioned and b not in conditioned} - reached
        if not added:
            break
        reached |= added
    return dict(ancestral_nodes=sorted(ancestors), moral_edges=moral,
                reachable_after_conditioning=sorted(reached))


def _trace(problem, mediator):
    x, y = problem.treatment, problem.outcome
    reachable = [v for v in problem.nodes if v != mediator and any(
        mediator not in path for path in _directed_paths(problem.edges, x, v))]
    graph2 = [e for e in problem.edges if e[0] != x]
    graph3 = [e for e in problem.edges if e[0] != mediator]
    return dict(
        FD1=dict(removed_node=mediator, reachable_without_node=sorted(reachable)),
        FD2=dict(removed_outgoing_from=x,
                 **_moral_trace(problem.nodes, graph2, x, mediator, [])),
        FD3=dict(removed_outgoing_from=mediator,
                 **_moral_trace(problem.nodes, graph3, mediator, y, [x])))


def _functional(p, m):
    # Independently spell out each free/bound coordinate; no expression compiler.
    return {
        'operation': 'CLASSICAL_FRONTDOOR', 'source_id': p.information.source_id,
        'free_values': {
            'intervention_value': {'variable': p.treatment, 'domain': [0, 1]},
            'outcome_value': {'variable': p.outcome, 'domain': [0, 1]}},
        'expression': {
            'operation': 'SUM',
            'bind': {'variable': m, 'role': 'mediator_value', 'domain': [0, 1]},
            'summand': {'operation': 'PRODUCT', 'factors': [
                {'operation': 'CONDITIONAL_PROBABILITY',
                 'outcomes': [{'variable': m, 'value_role': 'mediator_value'}],
                 'given': [{'variable': p.treatment, 'value_role': 'intervention_value'}]},
                {'operation': 'SUM',
                 'bind': {'variable': p.treatment, 'role': 'treatment_marginal_value', 'domain': [0, 1]},
                 'summand': {'operation': 'PRODUCT', 'factors': [
                     {'operation': 'CONDITIONAL_PROBABILITY',
                      'outcomes': [{'variable': p.outcome, 'value_role': 'outcome_value'}],
                      'given': [{'variable': p.treatment, 'value_role': 'treatment_marginal_value'},
                                {'variable': m, 'value_role': 'mediator_value'}]},
                     {'operation': 'PROBABILITY',
                      'outcomes': [{'variable': p.treatment, 'value_role': 'treatment_marginal_value'}]}
                 ]}}
            ]}
        }
    }


def replay(certificate, *, problem):
    try:
        p = validate(problem)
        c = certificate
        keys = {'version', 'theorem', 'claim_scope', 'status', 'problem_sha256', 'materials_sha256',
                'information_sha256', 'target', 'frontdoor_variable', 'selection', 'conditions',
                'graphical_trace', 'functional', 'positivity', 'numeric_value', 'certificate_sha256'}
        if type(c) is not dict or set(c) != keys:
            return False
        m = c['frontdoor_variable']
        if type(m) is not str or m not in set(p.observed) - {p.treatment, p.outcome}:
            return False
        if p.frontdoor_variable is not None and m != p.frontdoor_variable:
            return False
        if not all(independent_conditions(p, m).values()):
            return False
        expected = dict(
            version=VERSION, theorem=THEOREM, claim_scope=CLAIM_SCOPE, status='POINT',
            problem_sha256=digest(p), materials_sha256=p.materials_sha256,
            information_sha256=sha(p.information),
            target=dict(kind='INTERVENTIONAL_DISTRIBUTION', treatment=p.treatment,
                        outcome=p.outcome, context=p.context),
            frontdoor_variable=m,
            selection=dict(mode='SPECIFIED' if p.frontdoor_variable is not None else 'SEARCH_SINGLETON',
                           requested=p.frontdoor_variable),
            conditions=dict(FD1=True, FD2=True, FD3=True),
            graphical_trace=_trace(p, m), functional=_functional(p, m),
            positivity='DECLARED_STRICT_POSITIVE_OBSERVED_JOINT', numeric_value=None)
        expected['certificate_sha256'] = sha(expected)
        # Canonical hash equality also distinguishes bool/int and extra fields.
        return sha(c) == sha(expected)
    except (ValueError, TypeError, KeyError, AttributeError):
        return False

