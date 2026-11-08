"""Finite front-door audit: independent graph checks and exact rational SCMs.

These are implementation checks, not a proof of graphical completeness or a
nonidentification certificate. No API, estimation, or scientific autoapproval.
"""
import argparse
from collections import Counter
from fractions import Fraction as F
from itertools import combinations, product
import json
from pathlib import Path
from random import Random

from cfm_id.dag_frontdoor_solver import check_candidate, solve, functional
from cfm_id.dag_frontdoor_verify import independent_conditions, replay
from cfm_id.dag_frontdoor import submit
from examples.dag_frontdoor_reference import make_problem, synthetic_review, cases


def require(condition, reason):
    if not condition:
        raise ValueError('FRONTDOOR_ACCEPTANCE_FAILED: ' + reason)


def acyclic(nodes, edges):
    remaining = set(nodes)
    while remaining:
        roots = {v for v in remaining if not any(b == v and a in remaining for a, b in edges)}
        if not roots:
            return False
        remaining -= roots
    return True


def graph_audit():
    count = comparisons = proofs = 0
    patterns = Counter()
    arithmetic_graphs = []
    selected_by_size = Counter()

    def check(p):
        nonlocal count, comparisons, proofs
        count += 1
        for m in sorted(set(p.observed) - {p.treatment, p.outcome}):
            production, _ = check_candidate(p, m)
            independent = independent_conditions(p, m)
            require(production == independent, 'graph checker disagreement')
            comparisons += 1
            patterns[''.join('1' if independent[k] else '0' for k in ('FD1','FD2','FD3'))] += 1
            if all(independent.values()):
                q = p.model_copy(update={'frontdoor_variable': m})
                certificate = solve(q)
                require(replay(certificate, problem=q), 'valid graph certificate replay')
                proofs += 1
                if selected_by_size[len(p.nodes)] < 4:
                    arithmetic_graphs.append(q)
                    selected_by_size[len(p.nodes)] += 1

    nodes = ['X', 'M', 'Y', 'U']
    pairs = list(combinations(nodes, 2))
    exhaustive = 0
    for orientation in product((0, 1, 2), repeat=len(pairs)):
        edges = [[a, b] if d == 1 else [b, a] for (a, b), d in zip(pairs, orientation) if d]
        if acyclic(nodes, edges):
            check(make_problem(nodes, edges, ['U']))
            exhaustive += 1
    require(exhaustive == 543, 'four-node DAG enumeration')
    rng = Random(20261025)
    for size in (5, 6, 7, 8):
        names = ['X', 'M', 'Y'] + ['V' + str(i) for i in range(size - 3)]
        for i in range(64):
            ordering = rng.sample(names, len(names))
            edges = [[a,b] for a,b in combinations(ordering,2) if rng.random() < (0.2,0.4,0.6)[i % 3]]
            latent = [n for n in names[3:] if rng.random() < 0.5]
            check(make_problem(names, edges, latent))
    return dict(graphs=count, exhaustive_four_node_dags=exhaustive,
                sampled_larger_graphs=count-exhaustive, candidate_comparisons=comparisons,
                certified_candidates_replayed=proofs, condition_patterns=dict(patterns),
                random_seed=20261025), arithmetic_graphs


def tables_for(problem, seed):
    rng = Random(seed)
    parents = {n: sorted(a for a, b in problem.edges if b == n) for n in problem.nodes}
    tables = {n: {bits: F(rng.randint(1,10),11) for bits in product((0,1), repeat=len(parents[n]))}
              for n in sorted(problem.nodes)}
    return parents, tables


def joint(problem, parents, tables, intervention=None):
    result = {}
    for bits in product((0,1), repeat=len(problem.nodes)):
        assignment = dict(zip(problem.nodes, bits))
        mass = F(1)
        for n in problem.nodes:
            if intervention is not None and n == problem.treatment:
                mass *= int(assignment[n] == intervention)
            else:
                prob = tables[n][tuple(assignment[v] for v in parents[n])]
                mass *= prob if assignment[n] else 1-prob
        result[bits] = mass
    require(sum(result.values()) == 1, 'SCM distribution normalization')
    return result


def observed_law(problem, full):
    indexes = [problem.nodes.index(n) for n in problem.observed]
    observed = {}
    for bits, mass in full.items():
        key = tuple(bits[i] for i in indexes)
        observed[key] = observed.get(key, F(0)) + mass
    require(all(v > 0 for v in observed.values()), 'positive observed law')
    return observed


def probability(law, observed, event, given=None):
    given = {} if given is None else given
    if any(n in given and given[n] != value for n, value in event.items()):
        return F(0)
    merged = {**given, **event}
    def mass(conditions):
        return sum((p for values, p in law.items()
                    if all(values[observed.index(n)] == value for n, value in conditions.items())), F(0))
    return mass(merged) / mass(given)


def direct_formula(law, p, mediator, x, y):
    return sum((probability(law, p.observed, {mediator:m}, {p.treatment:x}) *
                sum((probability(law, p.observed, {p.outcome:y}, {p.treatment:xp, mediator:m}) *
                     probability(law, p.observed, {p.treatment:xp}) for xp in (0,1)), F(0))
                for m in (0,1)), F(0))


def evaluate_expression(expr, roles, law, observed):
    # Test-only fixed operation interpreter. No strings are executed.
    operation = expr['operation']
    if operation == 'SUM':
        binding = expr['bind']
        return sum((evaluate_expression(expr['summand'], {**roles, binding['role']: v}, law, observed)
                    for v in binding['domain']), F(0))
    if operation == 'PRODUCT':
        result = F(1)
        for factor in expr['factors']:
            result *= evaluate_expression(factor, roles, law, observed)
        return result
    require(operation in ('PROBABILITY','CONDITIONAL_PROBABILITY'), 'unknown expression operation')
    event = {r['variable']: roles[r['value_role']] for r in expr['outcomes']}
    given = {r['variable']: roles[r['value_role']] for r in expr.get('given', [])}
    return probability(law, observed, event, given)


def numeric_rows(p, mediator, seed, expression):
    parents, tables = tables_for(p, seed)
    observed = observed_law(p, joint(p, parents, tables))
    rows = []
    for x in (0,1):
        intervened = joint(p, parents, tables, intervention=x)
        for y in (0,1):
            direct = sum((mass for values, mass in intervened.items()
                          if values[p.nodes.index(p.outcome)] == y), F(0))
            formula_value = direct_formula(observed, p, mediator, x, y)
            ast_value = evaluate_expression(expression, {'intervention_value':x,'outcome_value':y},
                                            observed, p.observed)
            rows.append(dict(x=x, y=y, do_value=str(direct), formula_value=str(formula_value),
                             ast_value=str(ast_value), equal=direct == formula_value,
                             ast_matches_formula=ast_value == formula_value))
    return rows, parents, tables, observed


def serialize_model(p, parents, tables):
    return dict(nodes=p.nodes, edges=p.edges, observed=p.observed, latent=p.latent,
        conditional_probabilities=[dict(node=n, parents=parents[n],
            entries=[dict(parent_values=list(key), probability_one=str(value))
                     for key, value in tables[n].items()]) for n in p.nodes])


def arithmetic_audit(extra_graphs):
    models = comparisons = 0
    positive_rows = []
    witnesses = {}
    from copy import deepcopy
    positives = [(name, p, m, 16) for name,p,state,m in cases() if state == 'POINT']
    positives += [('graph_search_' + str(i), p, p.frontdoor_variable, 4) for i,p in enumerate(extra_graphs)]
    for name, p, m, repetitions in positives:
        certificate = solve(p)
        for seed in range(repetitions):
            rows, parents, tables, observed = numeric_rows(p, m, 7100+seed, certificate['functional']['expression'])
            require(all(r['equal'] and r['ast_matches_formula'] for r in rows), 'SCM formula equality ' + name)
            models += 1
            comparisons += len(rows)
            if seed == 0:
                positive_rows.append(dict(case=name, nodes=len(p.nodes), values=rows))
            if name == 'classic_specified':
                for error in ('inner_uses_intervention_value','weight_conditioned_on_mediator'):
                    expr = deepcopy(certificate['functional']['expression'])
                    inner = expr['summand']['factors'][1]
                    if error == 'inner_uses_intervention_value':
                        inner['summand']['factors'][0]['given'][0]['value_role'] = 'intervention_value'
                    else:
                        weight = inner['summand']['factors'][1]
                        weight.update(operation='CONDITIONAL_PROBABILITY',
                                      given=[dict(variable=m,value_role='mediator_value')])
                    wrong = evaluate_expression(expr, {'intervention_value':0,'outcome_value':1}, observed, p.observed)
                    correct = direct_formula(observed, p, m, 0, 1)
                    if wrong != correct and error not in witnesses:
                        witnesses[error] = dict(seed=7100+seed, model=serialize_model(p,parents,tables),
                            x=0,y=1,correct=str(correct),incorrect=str(wrong))
    require(len(witnesses) == 2, 'binding and weight numerical counterexamples')
    negatives = []
    named = {name:p for name,p,_,_ in cases()}
    for name, failed in [('direct_path_bypasses_m','FD1'),('x_m_confounding','FD2'),('m_y_confounding','FD3')]:
        p = named[name]
        require(independent_conditions(p,'M') == {k:k != failed for k in ('FD1','FD2','FD3')},
                'isolated failed condition')
        mismatch = 0
        witness = None
        for seed in range(16):
            rows, parents, tables, _ = numeric_rows(p,'M',8100+seed,functional(p,'M')['expression'])
            require(all(r['ast_matches_formula'] for r in rows), 'unproven expression arithmetic')
            if any(not r['equal'] for r in rows):
                mismatch += 1
                if witness is None:
                    witness = dict(seed=8100+seed, model=serialize_model(p,parents,tables), values=rows)
        require(mismatch > 0, 'missing concrete failure example')
        negatives.append(dict(case=name, failed_condition=failed, models=16,
                              mismatching_models=mismatch, first_counterexample=witness,
                              general_nonidentification_proved=False))
    return dict(positive_models=models, exact_equalities=comparisons, positive_examples=positive_rows,
                negative_models=48, negative_value_comparisons=192, negative_examples=negatives,
                expression_error_witnesses=witnesses, general_identification_proof=False)


def evaluate():
    reference = []
    for name, p, state, expected in cases():
        result = submit(p, review=synthetic_review(p), research_protocol_selected=True)
        require(result['state'] == state, 'reference ' + name)
        if state == 'POINT':
            require(result['certificate']['frontdoor_variable'] == expected and
                    replay(result['certificate'], problem=p), 'reference certificate')
        else:
            require(result['reason_code'] == expected and 'certificate' not in result, 'reference stop')
        reference.append(dict(case=name, expected_state=state, expected=expected,
                              problem=p.model_dump(), review=synthetic_review(p).model_dump(), result=result))
    graphs, extras = graph_audit()
    arithmetic = arithmetic_audit(extras)
    return dict(version='dag-frontdoor-acceptance-1', passed=True, references=reference,
                reference_states=dict(Counter(r['result']['state'] for r in reference)),
                graphs=graphs, arithmetic=arithmetic, api_calls=0, llm_accuracy_measured=False,
                production_admission=False, estimation_handoff_allowed=False,
                limitations='Finite implementation audit of a published sufficient criterion; not general ID, necessity, or formal proof.')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--allow-synthetic-reviews', action='store_true')
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args(argv)
    if not args.allow_synthetic_reviews:
        parser.error('Explicit synthetic reference selection required.')
    if args.output.exists():
        parser.error('Preserve prior evidence; use a new output path.')
    result = evaluate()
    with args.output.open('x', encoding='utf8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(json.dumps(dict(passed=result['passed'], reference_states=result['reference_states'],
                         graphs=result['graphs'],
                         positive_models=result['arithmetic']['positive_models'],
                         exact_equalities=result['arithmetic']['exact_equalities'],
                         api_calls=0)))


if __name__ == '__main__':
    main()

