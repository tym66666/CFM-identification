"""Independent replay for general identification.

This module never imports ``dag_id_solver`` or ``dag_id_graph``. It takes the
certificate as data, rebuilds the target numerically from a freshly generated
structural model, and compares. If the tree and the model disagree the check
fails, which is the only way to know the formula is right without asking the
solver to grade itself.

The numeric oracle works from the definition of ``do``:

1. draw a concrete recursive SCM consistent with the declared graph,
2. compute the observed joint P(V) by summing over the latent variables,
3. compute P_x(Y) by cutting the mechanisms that feed X,
4. evaluate the certificate's expression tree on the same P(V).

Steps 3 and 4 are independent computations; agreement to 1e-9 is evidence that
the formula encodes the right distribution.
"""
import itertools
import random

from .dag_id_contract import Unavailable, fail

TOLERANCE = 1e-9
DOMAIN = (0, 1)


# --------------------------------------------------------------------------
# expression tree
# --------------------------------------------------------------------------

def tree_variables(expr, joint_variables):
    op = expr['operation']
    if op == 'OBSERVED_JOINT':
        return frozenset(joint_variables)
    if op == 'MARGINAL':
        inner = tree_variables(expr['of'], joint_variables)
        scope = frozenset(expr.get('scope', inner))
        return (inner - scope) | frozenset(expr['keep'])
    if op == 'CONDITIONAL':
        return frozenset(expr['outcome'])
    if op == 'PRODUCT':
        out = set()
        for operand in expr['operands']:
            out |= tree_variables(operand, joint_variables)
        return frozenset(out)
    if op == 'SUM':
        inner = tree_variables(expr['operand'], joint_variables)
        scope = frozenset(expr.get('scope', inner))
        return inner - (set(expr['over']) & scope)
    fail('CHECK_BLOCKED', 'UNKNOWN_EXPRESSION_OPERATION')


def _all_values(variables, domains):
    ordered = sorted(variables)
    if not ordered:
        yield ()
        return
    for combo in itertools.product(*(domains[v] for v in ordered)):
        yield tuple(zip(ordered, combo))


def _domains_of(table, variables):
    domains = {v: set() for v in variables}
    for key in table:
        for variable, value in key:
            if variable in domains:
                domains[variable].add(value)
    return {v: sorted(domains[v]) or list(DOMAIN) for v in variables}


def _marginalise(table, variables, keep, scope):
    """Sum out the graph variables that are not wanted.

    Variables outside ``scope`` are conditioning context handed down by the
    recursion (for instance M while the target lives on {X, Y}); they must
    survive, because an enclosing sum binds them later.
    """
    keep = frozenset(keep)
    to_sum = (variables & frozenset(scope)) - keep
    result_vars = variables - to_sum
    result = {}
    for key, probability in table.items():
        assignment = dict(key)
        sub = tuple(sorted((k, assignment[k]) for k in result_vars))
        result[sub] = result.get(sub, 0.0) + probability
    return result_vars, result


def _condition(table, outcome, given, env, bound):
    """P(outcome | given) from a table.

    A conditioning variable is pinned only when it carries the treated value
    *and* is not bound by an enclosing sum. X plays both roles in the front-door
    formula: P(m | x) uses the intervention value, while P(y | x, m) sits inside
    sum_x and must sweep every value of x.
    """
    outcome, given = frozenset(outcome), frozenset(given)
    pinned_names = (given & set(env)) - set(bound)
    free = given - pinned_names
    result_vars = outcome | free
    numerator, denominator = {}, {}
    pinned = pinned_names
    for key, probability in table.items():
        assignment = dict(key)
        # A pinned conditioning variable selects rows; it never rewrites them.
        # Variables that are merely free in this factor (for instance X inside
        # the inner sum of the front-door formula) must keep sweeping their
        # whole domain, otherwise the sum over x collapses to the treated value.
        if any(assignment.get(name, value) != value for name, value in env.items() if name in pinned):
            continue
        assignment.update({k: v for k, v in env.items() if k in pinned})
        g_key = tuple(sorted((k, assignment[k]) for k in given))
        denominator[g_key] = denominator.get(g_key, 0.0) + probability
        r_key = tuple(sorted((k, assignment[k]) for k in result_vars))
        numerator[(g_key, r_key)] = numerator.get((g_key, r_key), 0.0) + probability
    result = {}
    for (g_key, r_key), probability in numerator.items():
        total = denominator[g_key]
        if total <= 0.0:
            fail('UNSUPPORTED', 'ZERO_PROBABILITY_CONDITIONING_EVENT')
        result[r_key] = probability / total
    return result_vars, result


def _product(parts, env, bound):
    variables = frozenset().union(*[v for v, _ in parts])
    domains = {}
    for v, table in parts:
        domains.update(_domains_of(table, v))
    total = {}
    for key in _all_values(variables, domains):
        assignment = dict(key)
        for name, value in env.items():
            if name in bound:
                continue
            assignment.setdefault(name, value)
        value = 1.0
        for v, table in parts:
            sub = tuple(sorted((k, assignment[k]) for k in v))
            value *= table.get(sub, 0.0)
        total[key] = value
    return variables, total


def _sum_out(table, variables, over, scope):
    to_sum = frozenset(over) & frozenset(scope) & variables
    result_vars = variables - to_sum
    result = {}
    for key, probability in table.items():
        assignment = dict(key)
        sub = tuple(sorted((k, assignment[k]) for k in result_vars))
        result[sub] = result.get(sub, 0.0) + probability
    return result_vars, result


def evaluate(expr, joint_variables, joint_table, env=None, bound=None):
    """Evaluate an expression tree on a concrete observed joint P(V).

    ``env`` carries values that are not free in the tree, in particular the
    value the treatment is set to. They behave as constants while the tree's
    own variables are enumerated.
    """
    env = dict(env or {})
    bound = set(bound or set())
    op = expr['operation']
    if op == 'OBSERVED_JOINT':
        return frozenset(joint_variables), joint_table
    if op == 'MARGINAL':
        scope = expr.get('scope', list(joint_variables))
        inner_bound = bound | (set(scope) - set(expr['keep']))
        variables, table = evaluate(expr['of'], joint_variables, joint_table, env, inner_bound)
        return _marginalise(table, variables, expr['keep'], scope)
    if op == 'CONDITIONAL':
        _, table = evaluate(expr['of'], joint_variables, joint_table, env, bound)
        return _condition(table, expr['outcome'], expr['given'], env, bound)
    if op == 'PRODUCT':
        return _product(
            [evaluate(o, joint_variables, joint_table, env, bound) for o in expr['operands']],
            env,
            bound,
        )
    if op == 'SUM':
        scope = expr.get('scope', list(joint_variables))
        inner_bound = bound | (set(expr['over']) & set(scope))
        variables, table = evaluate(expr['operand'], joint_variables, joint_table, env, inner_bound)
        return _sum_out(table, variables, expr['over'], scope)
    fail('CHECK_BLOCKED', 'UNKNOWN_EXPRESSION_OPERATION')


def probability_of(expr, joint_variables, joint_table, assignment, env=None):
    """P_x(assignment) according to the certificate's formula."""
    variables, table = evaluate(expr, joint_variables, joint_table, env, set())
    missing = set(assignment) - set(variables)
    if missing:
        fail('CHECK_BLOCKED', 'TARGET_VARIABLE_ABSENT_FROM_FORMULA')
    key = tuple(sorted(assignment.items()))
    return table.get(key, 0.0)


# --------------------------------------------------------------------------
# numeric oracle: a concrete SCM consistent with the declared graph
# --------------------------------------------------------------------------

def _topological(graph):
    nodes = list(graph['nodes'])
    indegree = {n: 0 for n in nodes}
    children = {n: [] for n in nodes}
    for a, b in graph['directed']:
        children[a].append(b)
        indegree[b] += 1
    queue = [n for n in nodes if indegree[n] == 0]
    order = []
    while queue:
        node = queue.pop(0)
        order.append(node)
        for child in children[node]:
            indegree[child] -= 1
            if indegree[child] == 0:
                queue.append(child)
    if len(order) != len(nodes):
        fail('CHECK_BLOCKED', 'DIRECTED_CYCLE_NOT_RECURSIVE_MODEL')
    return order


def _build_scm(graph, seed):
    rng = random.Random(seed)
    nodes = list(graph['nodes'])
    order = _topological(graph)

    directed_parents = {v: [] for v in nodes}
    for a, b in graph['directed']:
        directed_parents[b].append(a)

    latents = []
    latent_of = {v: [] for v in nodes}
    for index, (a, b) in enumerate(sorted(graph['bidirected'])):
        name = 'U{}'.format(index)
        latents.append(name)
        latent_of[a].append(name)
        latent_of[b].append(name)

    mechanism = {}
    for node in order:
        parents = sorted(directed_parents[node] + latent_of[node])
        for combo in itertools.product(DOMAIN, repeat=len(parents)):
            config = tuple(zip(parents, combo))
            mechanism[(node, config)] = 0.15 + 0.7 * rng.random()

    return {
        'nodes': nodes,
        'order': order,
        'latents': latents,
        'directed_parents': directed_parents,
        'latent_of': latent_of,
        'mechanism': mechanism,
    }


def _probability(scm, assignment, latent_values, fixed):
    total = 1.0
    for node in scm['order']:
        if node in fixed:
            continue
        parents = sorted(scm['directed_parents'][node] + scm['latent_of'][node])
        config = tuple(
            (name, latent_values[name] if name in latent_values else assignment[name])
            for name in parents
        )
        q = scm['mechanism'][(node, config)]
        total *= q if assignment[node] == 1 else (1.0 - q)
    return total


def observed_joint(graph, seed=7):
    """P(V) implied by a concrete SCM, as a table keyed by sorted assignments."""
    scm = _build_scm(graph, seed)
    nodes = scm['nodes']
    table = {}
    latent_prior = 0.5 ** len(scm['latents'])
    for latent_combo in itertools.product(DOMAIN, repeat=len(scm['latents'])):
        latent_values = dict(zip(scm['latents'], latent_combo))
        for combo in itertools.product(DOMAIN, repeat=len(nodes)):
            assignment = dict(zip(nodes, combo))
            probability = latent_prior * _probability(
                scm, assignment, latent_values, fixed=set()
            )
            key = tuple(sorted(assignment.items()))
            table[key] = table.get(key, 0.0) + probability
    return nodes, table


def interventional_joint(graph, treatment, treatment_value, seed=7):
    """P_x(V) by cutting every mechanism that feeds X."""
    scm = _build_scm(graph, seed)
    nodes = scm['nodes']
    table = {}
    latent_prior = 0.5 ** len(scm['latents'])
    for latent_combo in itertools.product(DOMAIN, repeat=len(scm['latents'])):
        latent_values = dict(zip(scm['latents'], latent_combo))
        for combo in itertools.product(DOMAIN, repeat=len(nodes)):
            assignment = dict(zip(nodes, combo))
            if assignment[treatment] != treatment_value:
                continue
            probability = latent_prior * _probability(
                scm, assignment, latent_values, fixed={treatment}
            )
            key = tuple(sorted(assignment.items()))
            table[key] = table.get(key, 0.0) + probability
    return nodes, table


# --------------------------------------------------------------------------
# derivation: recompute why each step was legal
# --------------------------------------------------------------------------

def _ancestors(nodes, directed, targets):
    reverse = {}
    for a, b in directed:
        reverse.setdefault(b, set()).add(a)
    seen, stack = set(targets), list(targets)
    while stack:
        node = stack.pop()
        for parent in reverse.get(node, ()):
            if parent not in seen:
                seen.add(parent)
                stack.append(parent)
    return seen


def _components(nodes, bidirected):
    parent = {v: v for v in nodes}

    def find(v):
        while parent[v] != v:
            parent[v] = parent[parent[v]]
            v = parent[v]
        return v

    for a, b in bidirected:
        if a in parent and b in parent:
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[ra] = rb
    grouped = {}
    for v in nodes:
        grouped.setdefault(find(v), set()).add(v)
    return [frozenset(block) for block in grouped.values()]


def _line_of(nodes, directed, bidirected, outcome, treatment):
    """The first rule that applies to this sub-problem, recomputed here.

    The order is the order of the paper: each rule is only reachable when every
    earlier one failed. Recomputing the order is what turns the trace from a
    narrative into an obligation -- a step that cites a rule which did not apply
    is rejected even when the numbers happen to agree.
    """
    V = set(nodes)
    Y, X = set(outcome), set(treatment)
    if not X:
        return 1, {'empty_treatment': True}
    an = _ancestors(nodes, directed, Y)
    if V - an:
        return 2, {'dropped': sorted(V - an), 'ancestors_of_outcome': sorted(an)}
    cut = [edge for edge in directed if edge[1] not in X]
    after = _ancestors(nodes, cut, Y)
    widened = (V - X) - after
    if widened:
        return 3, {'added_to_treatment': sorted(widened),
                   'ancestors_of_outcome_after_intervention': sorted(after)}
    rest = sorted(V - X)
    blocks = _components(rest, [edge for edge in bidirected
                                if edge[0] in rest and edge[1] in rest])
    if len(blocks) > 1:
        return 4, {'c_components_of_graph_minus_treatment':
                   sorted([sorted(b) for b in blocks])}
    whole = _components(sorted(V), bidirected)
    if len(whole) == 1:
        return 5, {'c_components_of_graph': [sorted(whole[0])],
                   'surviving_component': sorted(blocks[0])}
    if blocks[0] in set(whole):
        return 6, {'component_equals_surviving_block': sorted(blocks[0])}
    return 7, {'surviving_block': sorted(blocks[0])}


def check_derivation(certificate, problem):
    """Rebuild each step's premise from the graph the step claims to work on.

    Returns a report rather than raising: a failed step is a finding, and the
    caller decides what to do with it. ``completed`` says whether every step was
    checked; when it is False the derivation is unverified, which is not the
    same as verified-and-wrong.
    """
    steps = certificate.get('derivation') or []
    if not steps:
        return {'passed': False, 'completed': False, 'steps': [],
                'reason': 'NO_DERIVATION_STEPS'}

    findings, ok, completed = [], True, True
    first = steps[0]
    if (sorted(first.get('graph', {}).get('nodes', [])) != sorted(problem.nodes)
            or sorted(first.get('outcome') or []) != sorted(problem.outcome)
            or sorted(first.get('treatment') or []) != [problem.treatment]):
        ok = False
        findings.append({'depth': 0, 'problem': 'FIRST_STEP_IS_NOT_THE_ASKED_PROBLEM'})

    for step in steps:
        graph = step.get('graph') or {}
        nodes = list(graph.get('nodes') or [])
        directed = [tuple(edge) for edge in graph.get('directed') or []]
        bidirected = [tuple(edge) for edge in graph.get('bidirected') or []]
        outcome, treatment = step.get('outcome') or [], step.get('treatment') or []
        try:
            line, condition = _line_of(nodes, directed, bidirected, outcome, treatment)
        except Exception:  # noqa: BLE001 - an unreadable step is a finding too
            completed = False
            findings.append({'depth': step.get('depth'), 'problem': 'STEP_NOT_RECOMPUTABLE'})
            continue
        if step.get('line') != line:
            ok = False
            findings.append({'depth': step.get('depth'), 'problem': 'WRONG_RULE',
                             'stated': step.get('line'), 'recomputed': line})
            continue
        stated = step.get('condition') or {}
        for key, value in condition.items():
            if key in stated and stated[key] != value:
                ok = False
                findings.append({'depth': step.get('depth'), 'problem': 'WRONG_CONDITION',
                                 'key': key, 'stated': stated[key], 'recomputed': value})
    return {'passed': ok, 'completed': completed, 'steps': len(steps),
            'findings': findings}


# --------------------------------------------------------------------------
# replay
# --------------------------------------------------------------------------

REQUIRED = (
    'version', 'status', 'problem_sha256', 'target', 'graph',
    'functional', 'positivity', 'derivation', 'certificate_sha256',
)


def _trace(expr, joint_variables):
    """Return (ok, reason). Walks every branch back to OBSERVED_JOINT."""
    op = expr.get('operation') if isinstance(expr, dict) else None
    if op == 'OBSERVED_JOINT':
        return True, None
    if op == 'MARGINAL':
        return _trace(expr['of'], joint_variables)
    if op == 'CONDITIONAL':
        return _trace(expr['of'], joint_variables)
    if op == 'PRODUCT':
        for operand in expr['operands']:
            ok, reason = _trace(operand, joint_variables)
            if not ok:
                return ok, reason
        return True, None
    if op == 'SUM':
        return _trace(expr['operand'], joint_variables)
    return False, 'UNKNOWN_EXPRESSION_OPERATION'


def _free_variables(expr, bound=frozenset(), into=None):
    """Variables an atom reads that no enclosing sum binds.

    Everything an atom conditions on or reports must either be the treatment,
    part of the target, or bound by a sum on the way down. Anything else means
    the expression is a kernel on variables the question never mentioned.
    """
    into = set() if into is None else into
    op = expr['operation']
    if op == 'OBSERVED_JOINT':
        return into
    if op == 'MARGINAL':
        return _free_variables(expr['of'], bound, into)
    if op == 'CONDITIONAL':
        for name in list(expr['outcome']) + list(expr['given']):
            if name not in bound:
                into.add(name)
        return _free_variables(expr['of'], bound, into)
    if op == 'PRODUCT':
        for operand in expr['operands']:
            _free_variables(operand, bound, into)
        return into
    if op == 'SUM':
        return _free_variables(expr['operand'], bound | set(expr['over']), into)
    fail('CHECK_BLOCKED', 'UNKNOWN_EXPRESSION_OPERATION')


def _same_graph(certificate_graph, graph):
    return (
        sorted(certificate_graph['nodes']) == sorted(graph['nodes'])
        and sorted(tuple(edge) for edge in certificate_graph['directed'])
        == sorted(tuple(edge) for edge in graph['directed'])
        and sorted(tuple(edge) for edge in certificate_graph['bidirected'])
        == sorted(tuple(edge) for edge in graph['bidirected'])
    )


def replay(certificate, problem, seeds=(7, 11, 23), tolerance=TOLERANCE):
    """Recompute the target from scratch and compare with the certificate."""
    from cfm_id_bridge.scientific_binding import sha

    checks = []

    missing = [key for key in REQUIRED if key not in certificate]
    checks.append({
        'name': 'certificate_fields',
        'passed': not missing,
        'detail': 'missing={}'.format(missing) if missing else 'all fields present',
    })
    if missing:
        return {'passed': False, 'checks': checks, 'reported_errors': []}

    checks.append({
        'name': 'status_is_point',
        'passed': certificate['status'] == 'POINT',
        'detail': certificate['status'],
    })

    body = {k: v for k, v in certificate.items() if k != 'certificate_sha256'}
    checks.append({
        'name': 'certificate_digest',
        'passed': sha(body) == certificate['certificate_sha256'],
        'detail': 'sha256 over every field except certificate_sha256',
    })

    checks.append({
        'name': 'problem_binding',
        'passed': certificate['problem_sha256'] == sha(problem),
        'detail': 'certificate must point at this exact problem',
    })

    # A digest only proves the certificate is internally consistent. It cannot
    # tell whether the answer is about the question that was asked, because a
    # certificate for P(M | do(X)) carries its own digest just as happily. The
    # target is therefore compared field by field, and the expression must not
    # read any variable the question did not mention.
    target = certificate['target'] or {}
    stated = (
        target.get('treatment'),
        tuple(sorted(target.get('outcome') or [])),
        _same_graph(certificate['graph'], problem.as_graph()),
    )
    asked = (problem.treatment, tuple(sorted(problem.outcome)), True)
    checks.append({
        'name': 'question_binding',
        'passed': stated == asked,
        'detail': 'asks for {} -> {}; certificate answers {} -> {}; graph {}'.format(
            problem.treatment, sorted(problem.outcome),
            target.get('treatment'), sorted(target.get('outcome') or []),
            'same' if stated[2] else 'different',
        ),
    })

    allowed = {problem.treatment} | set(problem.outcome)
    free = _free_variables(certificate['functional'])
    checks.append({
        'name': 'formula_reads_only_the_asked_variables',
        'passed': free <= allowed,
        'detail': 'reads {}; allowed {}'.format(sorted(free), sorted(allowed)),
    })

    derivation = check_derivation(certificate, problem)
    checks.append({
        'name': 'derivation_steps_recompute',
        'passed': derivation['passed'],
        'detail': '{} steps, {} findings'.format(
            derivation.get('steps', 0), len(derivation.get('findings') or [])),
        'findings': derivation.get('findings') or [],
    })

    graph = problem.as_graph()
    ok, reason = _trace(certificate['functional'], graph['nodes'])
    checks.append({
        'name': 'expression_tree_well_formed',
        'passed': ok,
        'detail': reason or 'every branch reaches the observed joint',
    })

    errors = []
    numeric = []
    if certificate['status'] == 'POINT':
        for seed in seeds:
            joint_nodes, joint_table = observed_joint(graph, seed=seed)
            for treatment_value in DOMAIN:
                _, treated = interventional_joint(
                    graph, certificate['target']['treatment'], treatment_value, seed=seed
                )
                for outcome_values in itertools.product(
                    DOMAIN, repeat=len(certificate['target']['outcome'])
                ):
                    assignment = dict(zip(certificate['target']['outcome'], outcome_values))
                    truth = 0.0
                    for key, probability in treated.items():
                        row = dict(key)
                        if all(row[k] == v for k, v in assignment.items()):
                            truth += probability
                    try:
                        claimed = probability_of(
                            certificate['functional'],
                            joint_nodes,
                            joint_table,
                            assignment,
                            env={certificate['target']['treatment']: treatment_value},
                        )
                    except Unavailable as error:
                        errors.append('seed={} value={} {}'.format(seed, treatment_value, error.reason))
                        continue
                    if abs(truth - claimed) > tolerance:
                        errors.append(
                            'seed={} do({}={}) {} truth={:.12f} formula={:.12f}'.format(
                                seed, certificate['target']['treatment'], treatment_value,
                                dict(assignment), truth, claimed,
                            )
                        )
                    numeric.append(abs(truth - claimed))
    checks.append({
        'name': 'numeric_agreement_with_fresh_scm',
        'passed': not errors,
        'detail': '{} comparisons, max |diff| = {:.2e}'.format(
            len(numeric), max(numeric) if numeric else float('nan')
        ),
        'errors': errors[:5],
    })

    return {
        'passed': all(check['passed'] for check in checks),
        'checks': checks,
        'reported_errors': errors,
    }


def _connected(nodes, bidirected):
    """Union-find over bidirected edges: the C-component structure of a forest."""
    parent = {v: v for v in nodes}

    def find(v):
        while parent[v] != v:
            parent[v] = parent[parent[v]]
            v = parent[v]
        return v

    for a, b in bidirected:
        if a in parent and b in parent:
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[ra] = rb
    return {find(v) for v in nodes}


def _reaches(nodes, directed, roots):
    reverse = {}
    for a, b in directed:
        reverse.setdefault(b, set()).add(a)
    seen, stack = set(roots), list(roots)
    while stack:
        node = stack.pop()
        for parent in reverse.get(node, ()):
            if parent not in seen:
                seen.add(parent)
                stack.append(parent)
    return seen


def _forest_report(forest, treatment):
    nodes = set(forest.get('nodes') or [])
    directed = [tuple(e) for e in forest.get('directed') or []]
    bidirected = [tuple(sorted(e)) for e in forest.get('bidirected') or []]
    children = {}
    for a, b in directed:
        children.setdefault(a, []).append(b)
    leaves = {v for v in nodes if v not in children}
    return {
        'non_empty': bool(nodes),
        'nodes': sorted(nodes),
        'one_c_component': len(_connected(nodes, bidirected)) == 1 if nodes else False,
        'every_node_reaches_a_root': nodes == _reaches(nodes, directed, leaves),
        'at_most_one_child': all(len(c) <= 1 for c in children.values()),
        'roots': sorted(leaves),
        'avoids_treatment': not (nodes & set(treatment)),
    }


def check_hedge(hedge, problem=None):
    """Check a C-forest pair from its own edge lists, not from the solver's verdict.

    Definition 6 asks for two R-rooted C-forests, one nested in the other, the
    trimmed one disjoint from the treatment, with the root set inside the
    ancestors of the outcome once arrows into the treatment are cut.
    """
    if not isinstance(hedge, dict):
        return {'passed': False, 'detail': 'no hedge record'}
    trimmed = _forest_report(hedge.get('trimmed_forest') or {}, problem.treatment if problem else [])
    grown = _forest_report(hedge.get('grown_forest') or {}, problem.treatment if problem else [])
    checks = []
    for name, report in (('trimmed_forest', trimmed), ('grown_forest', grown)):
        for key in ('non_empty', 'one_c_component', 'every_node_reaches_a_root', 'at_most_one_child'):
            checks.append({'name': '{}.{}'.format(name, key), 'passed': report[key],
                           'detail': report['nodes']})
    trimmed_edges = {(tuple(e), 'directed') for e in (hedge.get('trimmed_forest') or {}).get('directed') or []}
    grown_edges = {(tuple(e), 'directed') for e in (hedge.get('grown_forest') or {}).get('directed') or []}
    checks.append({'name': 'trimmed_avoids_treatment', 'passed': trimmed['avoids_treatment'],
                   'detail': trimmed['nodes']})
    checks.append({'name': 'nested',
                   'passed': set(trimmed['nodes']) <= set(grown['nodes']) and trimmed_edges <= grown_edges,
                   'detail': {'trimmed': trimmed['nodes'], 'grown': grown['nodes']}})
    # Definition 6 only asks for inclusion, but a pair of equal forests witnesses
    # nothing: the intervention has to cut arrows in the part the hedge grew.
    checks.append({'name': 'grown_strictly_contains_trimmed',
                   'passed': set(grown['nodes']) > set(trimmed['nodes']),
                   'detail': {'grown_minus_trimmed': sorted(set(grown['nodes']) - set(trimmed['nodes']))}})
    checks.append({'name': 'same_root_set', 'passed': trimmed['roots'] == grown['roots'],
                   'detail': {'trimmed': trimmed['roots'], 'grown': grown['roots']}})
    if problem is not None:
        # Recompute the ancestor set of the outcome with the intervention
        # applied, from the declared graph only.
        directed = [tuple(e) for e in problem.directed]
        treatment = set(problem.treatment)
        cut = [(a, b) for a, b in directed if b not in treatment]
        reverse = {}
        for a, b in cut:
            reverse.setdefault(b, set()).add(a)
        ancestors, stack = set(problem.outcome), list(problem.outcome)
        while stack:
            node = stack.pop()
            for parent in reverse.get(node, ()):
                if parent not in ancestors:
                    ancestors.add(parent)
                    stack.append(parent)
        checks.append({'name': 'roots_in_ancestors_of_outcome_after_intervention',
                       'passed': set(trimmed['roots']) <= ancestors,
                       'detail': {'roots': trimmed['roots'], 'ancestors': sorted(ancestors)}})
    return {
        'passed': all(check['passed'] for check in checks),
        'checks': checks,
        'trimmed_forest': trimmed,
        'grown_forest': grown,
    }


def check_failure(witness, problem=None):
    """Validate the structural evidence attached to a non-identification result.

    Without the problem there is nothing to check the evidence against: the
    component lists in the witness would be self-reported. The report says so
    instead of passing, because an unchecked witness is not a proof.
    """
    if problem is None:
        checked_against_graph = False
    else:
        checked_against_graph = True
    if not witness:
        return {'passed': False, 'detail': 'no witness attached'}
    required = {
        'kind', 'theorem', 'c_components_of_graph',
        'c_components_of_graph_minus_treatment', 'surviving_component',
        'disjoint_from_treatment', 'means',
    }
    missing = sorted(required - set(witness))
    if missing:
        return {'passed': False, 'detail': 'missing={}'.format(missing)}
    if witness['kind'] != 'FAILED_COMPONENT_CONDITION':
        return {'passed': False, 'detail': 'unexpected witness kind'}
    if len(witness['c_components_of_graph']) != 1:
        return {'passed': False, 'detail': 'the whole graph must be one C-component'}
    if len(witness['c_components_of_graph_minus_treatment']) != 1:
        return {'passed': False, 'detail': 'G minus X must leave one C-component'}
    if witness['disjoint_from_treatment'] is not True:
        return {'passed': False, 'detail': 'surviving component overlaps the treatment'}

    # Rebuild both component partitions from the declared graph. A witness that
    # describes a different graph -- the same shape, different edges -- reads as
    # perfectly consistent on its own, and this is where that is caught.
    if not checked_against_graph:
        out = {'passed': True, 'completed': False, 'checked_against_graph': False,
               'detail': 'structural checks only; no graph was supplied to check the evidence against'}
        if 'hedge' in witness:
            hedge = check_hedge(witness['hedge'], None)
            out['hedge'] = hedge
            out['passed'] = hedge['passed']
        return out
    step_graph = witness.get('graph') or {}
    if not step_graph:
        return {'passed': False, 'completed': False,
                'detail': 'the witness does not say which graph it is about'}
    step_nodes = list(step_graph.get('nodes') or [])
    step_directed = [tuple(edge) for edge in step_graph.get('directed') or []]
    step_bidirected = [tuple(sorted(edge)) for edge in step_graph.get('bidirected') or []]
    # The evidence may come from a reduced sub-problem, but the reduction must
    # be a sub-graph of the declared one: no invented nodes, no invented edges.
    if (not set(step_nodes) <= set(problem.nodes)
            or not set(step_directed) <= {tuple(e) for e in problem.directed}
            or not set(step_bidirected) <= {tuple(sorted(e)) for e in problem.bidirected}):
        return {'passed': False, 'completed': True,
                'detail': 'evidence graph is not a sub-graph of the declared graph'}
    treatment = {problem.treatment}
    whole = _components(sorted(step_nodes), step_bidirected)
    rest = [node for node in step_nodes if node not in treatment]
    cut = _components(sorted(rest), [tuple(edge) for edge in step_bidirected
                                     if edge[0] in rest and edge[1] in rest])
    stated_whole = sorted([sorted(block) for block in witness['c_components_of_graph']])
    stated_cut = sorted([sorted(block)
                         for block in witness['c_components_of_graph_minus_treatment']])
    recomputed_whole = sorted([sorted(block) for block in whole])
    recomputed_cut = sorted([sorted(block) for block in cut])
    if stated_whole != recomputed_whole or stated_cut != recomputed_cut:
        return {'passed': False, 'completed': True,
                'detail': 'evidence does not belong to this graph',
                'recomputed': {'c_components_of_graph': recomputed_whole,
                               'c_components_of_graph_minus_treatment': recomputed_cut}}
    if sorted(witness['surviving_component']) not in stated_cut:
        return {'passed': False, 'completed': True,
                'detail': 'surviving component is not a component of G minus X'}
    out = {
        'passed': True,
        'detail': 'line-5 condition reproduced independently; no uniform formula in this graph',
    }
    if 'hedge' in witness:
        hedge = check_hedge(witness['hedge'], problem)
        out['hedge'] = hedge
        out['passed'] = out['passed'] and hedge['passed']
        if not hedge['passed']:
            out['detail'] = 'the C-forest pair does not satisfy Definition 6'
    elif witness.get('hedge_materialised') is True:
        out.update(passed=False, detail='claimed a materialised hedge without the pair')
    return out
