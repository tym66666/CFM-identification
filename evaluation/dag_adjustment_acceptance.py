"""Offline finite audit; not a proof of binary necessity or a live LLM benchmark.

Run with --synthetic-protocol --output <new JSON path>. Never loads an API key.
"""
import argparse
import json
from collections import Counter
from fractions import Fraction as F
from itertools import combinations, product
from pathlib import Path

from cfm_id.dag_adjustment_contract import AdjustmentProblem
from cfm_id.dag_adjustment_solver import graph_parts, moral_separation, solve
from cfm_id.dag_adjustment_verify import original_graph_check, replay
from cfm_id.dag_adjustment_adapter import DagAdjustmentRoute
from cfm_id.research_route_workflow import run_route
from cfm_id.dag_backdoor_solver import (
    descendants as classical_descendants, moral_separation as classical_separation,
)
from examples.dag_adjustment_reference import cases, make_problem, synthetic_review


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def subsets(items):
    for size in range(len(items) + 1):
        yield from combinations(items, size)


def four_node_graphs():
    nodes = list('ABCD')
    possible = list(combinations(nodes, 2))
    for flags in product((0, 1), repeat=6):
        yield nodes, [list(e) for e, flag in zip(possible, flags) if flag]


def graphical_audit():
    counts = Counter()
    for nodes, edges in four_node_graphs():
        counts['topologically_ordered_graphs'] += 1
        for x in nodes:
            for y in nodes:
                if x == y:
                    continue
                remaining = [v for v in nodes if v not in (x, y)]
                proper, forbidden, trace = graph_parts(nodes, edges, x, y)
                old_forbidden = classical_descendants(nodes, edges, x)
                old_graph = [(a, b) for a, b in edges if a != x]
                valid, classical = set(), set()
                for z in subsets(remaining):
                    answer = not (set(z) & forbidden) and moral_separation(
                        nodes, proper, x, y, z)[0]
                    independent, independent_trace, _ = original_graph_check(nodes, edges, x, y, z)
                    require(answer == independent, ('algorithm disagreement', edges, x, y, z))
                    require(trace == independent_trace, ('trace disagreement', edges, x, y, z))
                    old_answer = not (set(z) & old_forbidden) and classical_separation(
                        nodes, old_graph, x, y, z)[0]
                    require(not old_answer or answer, ('classical implication failed', edges, x, y, z))
                    if answer:
                        valid.add(frozenset(z))
                    if old_answer:
                        classical.add(frozenset(z))
                    counts['graph_target_set_comparisons'] += 1
                    counts['adjustment_valid_sets'] += int(answer)
                    counts['classical_valid_sets'] += int(old_answer)
                    counts['additional_valid_specified_sets'] += int(answer and not old_answer)
                # All choices of observed/unavailable non-target variables.
                for available in subsets(remaining):
                    new = {s for s in valid if s <= set(available)}
                    old = {s for s in classical if s <= set(available)}
                    minimal_new = {s for s in new if not any(t < s for t in new)}
                    minimal_old = {s for s in old if not any(t < s for t in old)}
                    require(minimal_new == minimal_old,
                            ('minimal-set mismatch', edges, x, y, available))
                    counts['minimal_set_family_comparisons'] += 1
    require(counts['graph_target_set_comparisons'] == 3072, 'incomplete graph audit')
    require(counts['minimal_set_family_comparisons'] == 3072, 'incomplete availability audit')
    return dict(counts)


def kernel_table(nodes, edges, seed):
    # Independent Bernoulli kernels induce a recursive SCM using independent
    # Uniform(0,1) disturbances. Every mass is positive, with exact rationals.
    table = {}
    for i, node in enumerate(nodes):
        parents = sorted(a for a, b in edges if b == node)
        values = {}
        for bits in product((0, 1), repeat=len(parents)):
            code = sum((j + 2) * (seed + j + 1) * bit for j, bit in enumerate(bits))
            values[bits] = F(1 + ((i + 1) * 3 + seed * 2 + code) % 11, 13)
        table[node] = (parents, values)
    return table


def exact_law(nodes, table, forced=None):
    rows = []
    for bits in product((0, 1), repeat=len(nodes)):
        row = dict(zip(nodes, bits))
        mass = F(1)
        for node in nodes:
            if forced is not None and node == forced[0]:
                if row[node] != forced[1]:
                    mass = F(0)
                    break
                continue
            parents, kernels = table[node]
            q = kernels[tuple(row[v] for v in parents)]
            mass *= q if row[node] else 1 - q
        rows.append((row, mass))
    require(sum(mass for _, mass in rows) == 1, 'non-normalized SCM law')
    return rows


def adjustment_value(joint, x, y, z, xv):
    # All unmentioned nodes, including latents, are explicitly marginalized.
    value = F(0)
    for bits in product((0, 1), repeat=len(z)):
        rows = [(row, m) for row, m in joint if all(row[v] == bit for v, bit in zip(z, bits))]
        pz = sum(m for _, m in rows)
        denominator = sum(m for row, m in rows if row[x] == xv)
        numerator = sum(m for row, m in rows if row[x] == xv and row[y] == 1)
        require(denominator > 0, 'unexpected positivity failure')
        value += pz * numerator / denominator
    return value


def exact_population_audit():
    counts = Counter()
    template = make_problem().model_dump()
    for nodes, edges in four_node_graphs():
        for seed in (1, 4):
            table = kernel_table(nodes, edges, seed)
            joint = exact_law(nodes, table)
            interventions = {(x, xv): exact_law(nodes, table, (x, xv))
                             for x in nodes for xv in (0, 1)}
            counts['positive_binary_scm_laws'] += 1
            for x in nodes:
                for y in nodes:
                    if x == y:
                        continue
                    remaining = [v for v in nodes if v not in (x, y)]
                    for z in subsets(remaining):
                        if not original_graph_check(nodes, edges, x, y, z)[0]:
                            continue
                        # Make every unused node latent. Adjustment must still
                        # use only the observed law of X, Y and the chosen Z.
                        observed = [v for v in nodes if v in (x, y) or v in z]
                        p = AdjustmentProblem.model_validate({
                            **template, 'nodes': nodes, 'observed': observed,
                            'latent': [v for v in nodes if v not in observed],
                            'edges': edges, 'treatment': x, 'outcome': y, 'adjustment': list(z),
                            'information': {**template['information'], 'variables': observed},
                        })
                        certificate = solve(p)
                        require(replay(certificate, problem=p), 'certificate replay failure')
                        require(certificate['adjustment'] == sorted(z), 'specified set changed')
                        counts['certificate_checks_across_scm_runs'] += 1
                        for xv in (0, 1):
                            truth = sum(m for row, m in interventions[x, xv] if row[y] == 1)
                            adjusted = adjustment_value(joint, x, y, z, xv)
                            require(truth == adjusted, ('wrong formula', edges, seed, x, y, z, xv))
                            counts['exact_intervention_formula_equalities'] += 1
    return dict(counts)


def rejected_set_witnesses():
    # Concrete failures of specified formulas. These are NOT two-world
    # nonidentification certificates and imply no general binary necessity.
    selected = {
        'mediator_forbidden', 'mediator_descendant_forbidden',
        'outcome_descendant_forbidden', 'outgoing_collider_opened',
        'collider_opened', 'collider_descendant_opened', 'wrong_empty_adjustment',
    }
    witnesses = []
    for name, p, _, _ in cases():
        if name not in selected:
            continue
        witness = None
        for seed in range(1, 16):
            table = kernel_table(p.nodes, p.edges, seed)
            joint = exact_law(p.nodes, table)
            for xv in (0, 1):
                truth = sum(m for row, m in exact_law(p.nodes, table, (p.treatment, xv))
                            if row[p.outcome] == 1)
                adjusted = adjustment_value(joint, p.treatment, p.outcome, p.adjustment, xv)
                if truth != adjusted:
                    witness = dict(case=name, kernel_seed=seed, treatment_value=xv,
                                   intervention_probability=str(truth), adjustment_value=str(adjusted),
                                   conclusion='SPECIFIED_FORMULA_FAILS_IN_THIS_SCM',
                                   nodes=p.nodes, edges=p.edges, adjustment=p.adjustment,
                                   kernels={n: {'parents': parents, 'p_one': [
                                       {'parent_values': list(bits), 'probability': str(q)}
                                       for bits, q in values.items()]}
                                       for n, (parents, values) in table.items()})
                    break
            if witness is not None:
                break
        require(witness is not None, ('missing concrete failure witness', name))
        witnesses.append(witness)
    require(len(witnesses) == len(selected), 'incomplete witness audit')
    return witnesses


def reference_audit():
    output = []
    for name, p, expected_state, expected_answer in cases():
        review = synthetic_review(p)
        result = run_route(DagAdjustmentRoute(), p, review=review, research_protocol_selected=True)
        answer = result['certificate']['adjustment'] if result['state'] == 'POINT' else result['reason_code']
        require((result['state'], answer) == (expected_state, expected_answer), ('reference failed', name, result))
        require(result['production_admission'] is False and result['estimation_handoff_allowed'] is False,
                'scope crossed')
        if expected_state == 'POINT':
            require(result['independent_replay'], ('no replay', name))
        else:
            require(result['certificate'] is None and result['mathematical_claim'] is None,
                    ('stop state published proof', name))
        output.append(dict(case=name, expected_state=expected_state, expected_answer=expected_answer,
                           problem=p.model_dump(), review=review.model_dump(), result=result))
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--synthetic-protocol', action='store_true', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Output already exists; preserve prior audit evidence.')
    report = dict(protocol='dag-adjustment-offline-acceptance-1', live_api_calls=0,
                  scope='BINARY_SUFFICIENCY_ONLY_NOT_GENERAL_ID_COMPLETENESS',
                  reference_cases=reference_audit(), graphical=graphical_audit(),
                  exact_population=exact_population_audit(),
                  specified_formula_failure_witnesses=rejected_set_witnesses())
    report['passed'] = True
    with args.output.open('x', encoding='utf-8') as out:
        json.dump(report, out, ensure_ascii=False, indent=2)
        out.write('\n')
    print(json.dumps({'passed': True, 'reference_cases': len(report['reference_cases']),
                      'graphical': report['graphical'], 'exact_population': report['exact_population'],
                      'failure_witnesses': len(report['specified_formula_failure_witnesses']),
                      'live_api_calls': 0}, ensure_ascii=False))


if __name__ == '__main__':
    main()
