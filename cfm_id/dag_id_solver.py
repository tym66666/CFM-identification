"""General identification by the ID algorithm of Shpitser & Pearl (2006).

The algorithm manipulates ``P`` symbolically: it never needs numbers, only the
shape of the graph. What it returns is an expression tree, not a formula string
and not a number::

    {'operation': 'SUM', 'over': ['W2'], 'operand': {...}}
    {'operation': 'PRODUCT', 'operands': [{...}, {...}]}
    {'operation': 'MARGINAL', 'keep': ['X', 'W2'], 'of': {...}}
    {'operation': 'CONDITIONAL', 'outcome': ['Y'], 'given': ['X'], 'of': {...}}
    {'operation': 'OBSERVED_JOINT'}

Every tree evaluates to a distribution over its free variables, so a caller can
check the result numerically without re-running this module.

Line numbers refer to Fig. 3 of the paper. Two of the branch tests (the ancestor
test on line 2 and the ``W`` test on line 3) admit more than one reading in the
compact notation; this module takes them the way the worked examples in the
paper exercise them, which is also the convention used by published
implementations.
"""
from cfm_id_bridge.scientific_binding import sha

from .dag_id_contract import VERSION, Unavailable, fail, validate
from .dag_id_graph import (
    ancestors,
    c_components,
    describe,
    induced,
    parents,
    remove_incoming,
    topological_order,
    without_nodes,
)

MAX_RECURSION = 200

FAILED_REASON = 'NO_UNIFORM_IDENTIFICATION_FORMULA_IN_THIS_GRAPH'
RESOURCE_REASON = 'DAG_ID_RECURSION_LIMIT'


def _reach_to_roots(g, keep, roots):
    """Nodes of ``keep`` that reach ``roots`` along directed edges inside ``keep``."""
    reverse = {}
    for a, b in g['directed']:
        if a in keep and b in keep:
            reverse.setdefault(b, set()).add(a)
    seen, stack = set(roots), list(roots)
    while stack:
        node = stack.pop()
        for parent in reverse.get(node, ()):
            if parent not in seen:
                seen.add(parent)
                stack.append(parent)
    return seen


def _subgraph(g, nodes):
    nodes = set(nodes)
    return {
        'nodes': sorted(nodes),
        'directed': sorted((a, b) for a, b in g['directed'] if a in nodes and b in nodes),
        'bidirected': sorted(
            tuple(sorted((a, b))) for a, b in g['bidirected'] if {a, b} <= nodes
        ),
    }


def _forest(g, nodes, roots):
    """Edge subgraph on ``nodes`` kept only where it can reach ``roots``.

    A C-forest needs every node to have a directed path to the root set and at
    most one child. Trimming to the nodes that reach ``roots`` gives the first
    property; the second is a property of the graph and is reported, not forced.
    """
    keep = _reach_to_roots(g, set(nodes), set(roots))
    sub = _subgraph(g, keep)
    children = {}
    for a, b in sub['directed']:
        children.setdefault(a, []).append(b)
    leaves = sorted(v for v in keep if v not in children)
    return {
        'forest': sub,
        'roots': leaves,
        'every_node_has_at_most_one_child': all(len(c) <= 1 for c in children.values()),
    }


def _hedge(g, x, y, surviving):
    """Materialise the C-forest pair promised by Theorem 6.

    The trimming picture of Definition 6: the intervention cuts incoming arrows
    in the part that the grown forest added, so the smaller forest is the one
    that survives ``do(x)`` and must avoid X; the larger one is that forest plus
    the branches the intervention removed. Both share the root set and both are
    C-forests. When the pruning needed to satisfy "at most one child" is not
    unique, we report that instead of inventing a pair.
    """
    trimmed = _forest(g, surviving, (set(surviving) & ancestors(remove_incoming(g, x), y)) or surviving)
    container = next((b for b in c_components(g) if surviving <= b), set(surviving))
    grown = _forest(g, container, trimmed['roots'] or surviving)
    hedge = {
        'definition': 'SHPITSER_PEARL_2006_DEFINITION_6',
        'trimmed_forest': trimmed['forest'],
        'grown_forest': grown['forest'],
        'roots': list(trimmed['roots']),
        'root_set': list(grown['roots']),
        'nested': set(trimmed['forest']['nodes']) <= set(grown['forest']['nodes']),
        'grown_strictly_contains_trimmed': (
            set(grown['forest']['nodes']) > set(trimmed['forest']['nodes'])
        ),
        'trimmed_avoids_treatment': not (set(trimmed['forest']['nodes']) & set(x)),
        'every_node_has_at_most_one_child': (
            trimmed['every_node_has_at_most_one_child']
            and grown['every_node_has_at_most_one_child']
        ),
        'roots_in_ancestors_of_outcome_after_intervention': (
            set(trimmed['roots']) <= ancestors(remove_incoming(g, x), y)
        ),
    }
    hedge['materialised'] = all(
        hedge[key] is True
        for key in (
            'nested', 'grown_strictly_contains_trimmed',
            'trimmed_avoids_treatment',
            'every_node_has_at_most_one_child',
            'roots_in_ancestors_of_outcome_after_intervention',
        )
    )
    return hedge


def _witness(g, x, y, surviving):
    """Structural evidence produced when line 5 fires.

    The failure condition (the whole graph is one C-component and removing X
    leaves one component) is what stops the algorithm; the C-forest pair of
    Theorem 6 is built alongside it so a reader can check the non-identification
    claim on the graph itself rather than on our word for it.
    """
    hedge = _hedge(g, x, y, surviving)
    return {
        'kind': 'FAILED_COMPONENT_CONDITION',
        # The sub-problem the recursion had reduced to when line 5 fired. The
        # evidence is about this graph, not the one the caller declared, so the
        # checker needs it to recompute the partition instead of guessing.
        'graph': describe(g),
        # The treatment and outcome are recorded for the same reason: after
        # line 3 the treatment set is not the declared one, and the hedge's
        # "avoids the treatment" check has to use the set this sub-problem
        # actually intervenes on.
        'treatment': sorted(x),
        'outcome': sorted(y),
        'theorem': 'SHPITSER_PEARL_2006_THEOREM_6',
        'c_components_of_graph': sorted([sorted(b) for b in c_components(g)]),
        'c_components_of_graph_minus_treatment': sorted(
            [sorted(b) for b in c_components(without_nodes(g, x))]
        ),
        'surviving_component': sorted(surviving),
        'disjoint_from_treatment': not (surviving & set(x)),
        'roots_contained_in_ancestors_of_outcome': surviving <= ancestors(g, y),
        'hedge': hedge,
        'hedge_materialised': hedge['materialised'],
        'means': FAILED_REASON,
    }


def _fail_with_witness(state, reason, witness):
    error = Unavailable(state, reason)
    error.witness = witness
    raise error


def _witness_is_on_the_trace(witness, trace):
    """True when some recorded step is exactly the sub-problem the evidence is about."""
    graph = witness.get('graph') or {}
    nodes = sorted(graph.get('nodes') or [])
    directed = sorted(tuple(edge) for edge in graph.get('directed') or [])
    bidirected = sorted(tuple(edge) for edge in graph.get('bidirected') or [])
    for step in trace:
        seen = step.get('graph') or {}
        if (sorted(seen.get('nodes') or []) == nodes
                and sorted(tuple(edge) for edge in seen.get('directed') or []) == directed
                and sorted(tuple(edge) for edge in seen.get('bidirected') or []) == bidirected
                and sorted(step.get('treatment') or []) == sorted(witness.get('treatment') or [])
                and sorted(step.get('outcome') or []) == sorted(witness.get('outcome') or [])):
            return True
    return False


def _id(g, y, x, dist, trace, depth, added=frozenset()):
    """Run the recursion on one sub-problem.

    ``added`` records the variables that line 3 put into the treatment set
    because cutting the arrows into X left them outside An(Y). Those variables
    are provably irrelevant to the target, so they must not reappear as free
    conditioning variables in the final expression: P(y | do(x), a) equals
    P(y | do(x)) for them, and carrying ``a`` through makes the expression a
    kernel on the wrong variable set. A -> B -> C is the smallest case: with
    X = {B} the recursion widens the treatment to {A, B}, and conditioning on A
    would leave an expression that no longer reads as a distribution over C.
    """
    if depth > MAX_RECURSION:
        fail('RESOURCE_LIMIT', RESOURCE_REASON)

    V = set(g['nodes'])
    # Each entry records the graph before the step and, once the branch is
    # decided, which line fired, the exact condition that admitted it and why
    # the rewrite is licensed. The reasons are the ones the paper proves for
    # that line, not a paraphrase of the emitted expression.
    step = {
        'depth': depth,
        'graph': describe(g),
        'outcome': sorted(y),
        'treatment': sorted(x),
    }
    trace.append(step)

    # Line 1: nothing to intervene on, marginalise the joint.
    if not x:
        step.update(
            line=1, rule='MARGINALISE_JOINT',
            condition={'empty_treatment': True},
            justification='With no intervention P(y) is a marginal of the declared joint, '
                          'obtained by summing out every other variable.',
        )
        return {'operation': 'SUM', 'over': sorted(V - y), 'scope': sorted(V), 'operand': dist}

    # Line 2: keep only the ancestors of the outcome.
    an = ancestors(g, y)
    if V - an:
        step.update(
            line=2, rule='RESTRICT_TO_ANCESTORS',
            condition={'dropped': sorted(V - an), 'ancestors_of_outcome': sorted(an)},
            justification='Variables outside An(Y) cannot influence Y, so the post-intervention '
                          'distribution of Y is unchanged when they are removed (rule 3 of do-calculus).',
        )
        return _id(
            induced(g, an),
            y,
            x & an,
            {'operation': 'MARGINAL', 'keep': sorted(an), 'scope': sorted(V), 'of': dist},
            trace,
            depth + 1,
            added & an,
        )

    # Line 3: variables that are neither treatment nor ancestors of Y can be
    # intervened on without changing the target.
    gx = remove_incoming(g, x)
    w = (V - x) - ancestors(gx, y)
    if w:
        step.update(
            line=3, rule='EXTEND_TREATMENT_TO_IRRELEVANT_NODES',
            condition={'added_to_treatment': sorted(w),
                       'ancestors_of_outcome_after_intervention': sorted(ancestors(gx, y))},
            justification='The added variables are not ancestors of Y once arrows into X are cut, '
                          'so intervening on them does not change the distribution of Y.',
        )
        return _id(g, y, x | w, dist, trace, depth + 1, added | w)

    # Line 4: cut the graph into C-components of G \ X and solve each block.
    blocks = c_components(without_nodes(g, x))
    if len(blocks) > 1:
        step.update(
            line=4, rule='FACTORISE_OVER_C_COMPONENTS_OF_G_MINUS_X',
            condition={'c_components_of_graph_minus_treatment': sorted(sorted(b) for b in blocks)},
            justification='P_x(y) = sum over v minus (y union x) of the product over blocks S_i of '
                          'P over v minus S_i of S_i: removing the treatment separates the blocks, '
                          'and each block is solved separately (Lemma 4).',
        )
        operands = [_id(g, block, V - block, dist, trace, depth + 1, added)
                    for block in blocks]
        return {
            'operation': 'SUM',
            'over': sorted(V - y - x),
            'scope': sorted(V),
            'operand': {'operation': 'PRODUCT', 'operands': operands},
        }

    # Line 5: one block left. If the whole graph is one C-component, no
    # uniform formula exists -- this is the only place the algorithm gives up.
    S = blocks[0]
    if len(c_components(g)) == 1:
        step.update(
            line=5, rule='FAIL_NO_UNIFORM_FORMULA',
            condition={'c_components_of_graph': [sorted(c_components(g)[0])],
                       'surviving_component': sorted(S)},
            justification='The whole graph is one C-component and G minus X leaves one component, '
                          'so the hedge of Theorem 6 exists and no uniform formula can be derived.',
        )
        witness = _witness(g, x, y, S)
        # The stopping condition is necessary for a hedge, not sufficient as
        # evidence. The pair is therefore checked independently before the run
        # is allowed to answer "not identifiable" (see ``identify``); this raise
        # is only the transport of the evidence.
        _fail_with_witness('UNSUPPORTED', FAILED_REASON, witness)

    # Line 6: the surviving block is itself a C-component, so the chain rule
    # on its topological order is already a formula in P.
    if S in c_components(g):
        order = topological_order(g, S)
        step.update(
            line=6, rule='CHAIN_RULE_ON_SURVIVING_C_COMPONENT',
            condition={'component_equals_surviving_block': sorted(S), 'order': list(order)},
            justification='S is a C-component of G and also the surviving block, so P_x(s) '
                          'factorises as the pi-product over S: each variable conditioned on '
                          'everything preceding it in the graph order, which is a formula in '
                          'the observed law (c-factor of S).',
        )
        factors = []
        full_order = topological_order(g)
        for v in order:
            # Condition on *everything preceding v in the graph order*, not only
            # on its parents. The observational Markov property would let the
            # prefix collapse to pa(v), but this product is used to express an
            # interventional law: when an intervened variable precedes v without
            # being a parent, the intervention changes the posterior of the
            # latent parents, so P(v | pa(v)) and P(v | prefix) differ. Graph
            # V2 -> V0 -> V1 with V0 <-> V1, X = V2, Y = V1 is the smallest case:
            # pa(V1) = {V0}, yet P_{v2}(v1 | v0) = P(v1 | v0, v2).
            given = [name for name in full_order[:full_order.index(v)] if name not in added]
            factors.append({
                'operation': 'CONDITIONAL',
                'outcome': [v],
                'given': sorted(given),
                'of': dist,
            })
        return {
            'operation': 'SUM',
            'over': sorted(S - y),
            'scope': sorted(V),
            'operand': {'operation': 'PRODUCT', 'operands': factors},
        }

    # Line 7: the surviving block sits inside a larger C-component of G, so the
    # recursion goes to that *container*. Removing X can only shrink a
    # component, so the block is a subset of the component holding it, never the
    # other way round. The distribution handed down is the pi-product: each
    # variable of the container is conditioned on everything preceding it, so
    # variables outside the container enter as fixed values.
    containers = [block for block in c_components(g) if S <= block]
    if not containers:
        fail('CHECK_BLOCKED', 'NO_CONTAINING_C_COMPONENT')
    container = containers[0]

    # The pi-product conditions each variable on *every* variable that precedes
    # it in the graph order, not only on its parents. That difference matters:
    # X is not a parent of Y, but given M the two are still confounded through
    # the bidirected edge, so P(Y | M) and P(Y | X, M) are different numbers.
    full_order = topological_order(g)
    step.update(
        line=7, rule='RECURSE_INTO_CONTAINING_C_COMPONENT',
        condition={'surviving_block': sorted(S), 'containing_component': sorted(container),
                   'order': list(topological_order(g, container))},
        justification='S lies inside the C-component S\' of G. Its c-factor is the pi-product '
                      'over S\' of P(v | all variables preceding v), so the same question on S\' '
                      'recovers P_x(s) from the observed law (Lemma 5).',
    )
    factors = []
    for v in topological_order(g, container):
        # Unlike line 6, the pi-product here covers a container that may hold a
        # variable line 3 added. Those variables are irrelevant to Y, but they
        # are not irrelevant to the c-factor: A -> B -> C with A <-> C is the
        # smallest case. Line 3 adds A, line 7 recurses into {A, C}, and the
        # factor for C must condition on A, because A and C share an unobserved
        # cause. The recursion then sums A out at line 2, which is what turns
        # the answer into sum_a P(c | b, a) P(a). Dropping A here gives
        # P(c | b), which is not the target.
        prefix = list(full_order[:full_order.index(v)])
        factors.append({
            'operation': 'CONDITIONAL',
            'outcome': [v],
            'given': list(prefix),
            'of': dist,
        })
    restricted = {'operation': 'PRODUCT', 'operands': factors}

    return _id(induced(g, container), y, x & container, restricted, trace, depth + 1, added)


def collect_atoms(expr, into=None):
    """Every conditional-probability atom and every marginal the tree uses."""
    into = {'conditional': [], 'marginal': []} if into is None else into
    op = expr['operation']
    if op == 'CONDITIONAL':
        into['conditional'].append({
            'outcome': list(expr['outcome']),
            'given': list(expr['given']),
        })
        collect_atoms(expr['of'], into)
    elif op == 'MARGINAL':
        into['marginal'].append(list(expr['keep']))
        collect_atoms(expr['of'], into)
    elif op == 'PRODUCT':
        for operand in expr['operands']:
            collect_atoms(operand, into)
    elif op == 'SUM':
        collect_atoms(expr['operand'], into)
    return into


def positivity_requirements(expr):
    """Denominators the formula needs: every conditioning event must be positive."""
    atoms = collect_atoms(expr)
    denominators = sorted({tuple(a['given']) for a in atoms['conditional'] if a['given']})
    return {
        'conditional_denominators': [list(d) for d in denominators],
        'requirement': 'EVERY_CONDITIONING_EVENT_HAS_POSITIVE_PROBABILITY',
        'overlapping_events': len(denominators),
    }


def identify(problem):
    """Return a POINT certificate, or raise ``Unavailable``.

    States are kept apart on purpose: a graph where no formula exists
    (UNSUPPORTED + FAILED_REASON) is not the same event as a malformed problem
    (CHECK_BLOCKED), and neither is an exhausted recursion budget
    (RESOURCE_LIMIT + RESOURCE_REASON).
    """
    p = validate(problem)
    g = p.as_graph()
    y, x = set(p.outcome), {p.treatment}

    trace = []
    try:
        expr = _id(g, y, x, {'operation': 'OBSERVED_JOINT'}, trace, 0)
    except Unavailable as error:
        witness = getattr(error, 'witness', None)
        if witness is None:
            raise
        # Stopping is not the same as proving. Line 5's condition is necessary
        # for a hedge, not sufficient as evidence, so the pair is checked
        # against the declared graph before the answer says "not identifiable".
        # Until that check passes the honest state is NO_FORMULA_YET: the
        # algorithm stopped, and nothing has been proved about the graph.
        from .dag_id_verify import check_failure

        report = check_failure(witness, p)
        if not report.get('passed'):
            downgraded = Unavailable('NO_FORMULA_YET',
                                     'NONIDENTIFICATION_EVIDENCE_NOT_VERIFIED')
            downgraded.witness = dict(witness, evidence_report=report)
            raise downgraded
        # The evidence describes the sub-problem the recursion reached. If that
        # sub-problem never appears in the trace, the evidence is about a graph
        # this run never visited, which is a defect, not a conclusion.
        if not _witness_is_on_the_trace(witness, trace):
            blocked = Unavailable('CHECK_BLOCKED', 'EVIDENCE_NOT_IN_DERIVATION')
            blocked.witness = dict(witness, evidence_report=report)
            raise blocked
        error.evidence_checked = True
        error.witness = dict(witness, evidence_report=report)
        raise

    cert = {
        'version': VERSION,
        'theorem': 'SHPITSER_PEARL_2006_ID',
        'status': 'POINT',
        'problem_sha256': sha(p),
        'target': {
            'kind': 'INTERVENTIONAL_DISTRIBUTION',
            'treatment': p.treatment,
            'outcome': list(p.outcome),
            'context': p.context,
        },
        'graph': describe(g),
        'functional': expr,
        'positivity': positivity_requirements(expr),
        'derivation': trace,
        'scope': {
            'model': 'RECURSIVE_SEMI_MARKOVIAN',
            'variables': 'FINITE_DISCRETE',
            'partial_identification': False,
            'counterfactuals': False,
        },
    }
    cert['certificate_sha256'] = sha(cert)
    return cert


def identify_or_report(problem):
    """Same as ``identify`` but returns the failure instead of raising it.

    Three outcomes are kept apart on purpose. A declared non-identification is
    UNSUPPORTED and carries a witness. A defect in this module is CHECK_BLOCKED
    with INTERNAL_ERROR and a populated ``detail``; it never claims a
    non-identification, because nothing was proved about the graph. Callers can
    therefore branch on ``status`` alone without mistaking a crash for a result.
    """
    try:
        return identify(problem)
    except Unavailable as error:
        witness = getattr(error, 'witness', None)
        return {
            'status': error.state,
            'reason': error.reason,
            'witness': witness,
            # Only an evidence-checked UNSUPPORTED is a mathematical conclusion.
            # A downgraded NO_FORMULA_YET keeps its witness so the failed checks
            # can be read, but it claims nothing about the graph.
            'nonidentification_proved': bool(
                error.state == 'UNSUPPORTED'
                and getattr(error, 'evidence_checked', False)
            ),
            'evidence_report': (witness or {}).get('evidence_report')
            if isinstance(witness, dict) else None,
        }
    except Exception as error:  # noqa: BLE001 - the boundary must not leak
        # Anything unexpected stops here instead of escaping as a raw traceback.
        # The type and message are preserved so the defect stays diagnosable.
        return {
            'status': 'CHECK_BLOCKED',
            'reason': 'INTERNAL_ERROR',
            'detail': '{}: {}'.format(type(error).__name__, error),
            'witness': None,
            'nonidentification_proved': False,
        }
