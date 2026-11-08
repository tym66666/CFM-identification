"""Offline end-to-end acceptance of saved real readings; no network or secrets."""
from copy import deepcopy
from dataclasses import replace
from fractions import Fraction
from itertools import product
from pathlib import Path
import argparse
import hashlib
import json

from cfm_id.business_entry import preview
from cfm_id.intent_submission import submit
from evaluation.business_core_pilot_base import canonical_hash
from evaluation.reading_semantics import semantic_payload
from evaluation.reading_target_audit import compare_target_projections
from examples.reading_science_fixture import (
    DATA, PROTOCOL_FILE, protocol, public_bundle, synthetic_context, expected_terms,
)
from pfn_pipeline.identification_business import (
    identify_network_business_query, replay_verified_business_outcome,
)
from pfn_pipeline.identification_composition import CompositionUnavailable


def load(path): return json.loads(Path(path).read_text(encoding='utf8'))
def filehash(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def recorded_cases():
    return load(DATA / 'recorded/MANIFEST.json')['records']


def saved_inputs(record):
    path = DATA / record['candidate']
    if filehash(path) != record['candidate_sha256']:
        raise ValueError('SAVED_MODEL_RESPONSE_CHANGED')
    bundle = public_bundle(record['case'])
    if canonical_hash(bundle) != record['public_bundle_sha256']:
        raise ValueError('SAVED_PUBLIC_MATERIALS_CHANGED')
    return bundle, load(path)


def _high(z, i, adjacency, exposure):
    # Intentionally independent of Core exposure and support implementations.
    count = sum(z[j] for j in adjacency[i])
    if exposure == 'any_treated_neighbor': return count >= 1
    if exposure == 'strict_majority': return 2 * count > len(adjacency[i])
    raise ValueError('EXPOSURE_NOT_SPECIFIED_BY_THIS_TEST')


def _outcome(i, z, schedule):
    """Two arbitrary finite PO schedules, allowing full-vector interference."""
    n = len(z)
    if schedule == 0:
        return (Fraction(i + 2) + (i + 1) * z[i]
            + sum(Fraction(j + 1, 3) * z[j] for j in range(n) if j != i)
            + z[i] * sum(Fraction(i + j + 2, 7) * z[j] for j in range(n) if j != i)
            + Fraction(z[(i + 2) % n] * z[(i + 3) % n], 11))
    return (Fraction(i + 5) - Fraction(i + 3, 2) * z[i]
        + Fraction(z[(i + 2) % n], 5)
        + Fraction(z[i] * (sum(z[j] for j in range(n) if j != i) ** 2), 13))


def independent_enumeration(name, composition):
    """Check Core terms/support against a separately enumerated finite model.

    Numeric results are test-oracle values, never estimated business effects.
    This supplements existing replay; it is not a formal proof of a new theorem.
    """
    p = protocol(name); b = public_bundle(name); nodes = p['node_order']; n = len(nodes)
    adjacency = [set() for _ in nodes]
    for left, right in b['structure']['edges']:
        a, c = nodes.index(left), nodes.index(right)
        adjacency[a].add(c); adjacency[c].add(a)
    terms = {t.coordinates: t.coefficient for t in composition.terms}
    if terms != expected_terms(p) or len(terms) != len(composition.terms):
        raise AssertionError('FORMULA_COORDINATES_OR_WEIGHTS_MISMATCH')
    cells = {(node, a, 1): Fraction(0) for node in p['population'] for a in (0, 1)}
    moments = [dict.fromkeys(cells, Fraction(0)), dict.fromkeys(cells, Fraction(0))]
    within_cell_values = {key: set() for key in cells}
    for z in product((0, 1), repeat=n):
        mass = Fraction(1, 2 ** n)
        for node in p['population']:
            i = nodes.index(node)
            if _high(z, i, adjacency, p['exposure']):
                key = (node, z[i], 1); cells[key] += mass
                for schedule in (0, 1): moments[schedule][key] += mass * _outcome(i, z, schedule)
                within_cell_values[key].add(_outcome(i, z, 0))
    support = {t.coordinates: Fraction(q)
        for t, q in zip(composition.terms, composition.population_arm_support)}
    if support != cells or any(v <= 0 for v in cells.values()):
        raise AssertionError('INDEPENDENT_SUPPORT_ENUMERATION_MISMATCH')
    comparisons = []
    for schedule in (0, 1):
        observable = sum(c * moments[schedule][key] / cells[key] for key, c in terms.items())
        causal = Fraction(0)
        for node in p['population']:
            i = nodes.index(node); numerator = Fraction(0); denominator = Fraction(0)
            others = [j for j in range(n) if j != i]
            for values in product((0, 1), repeat=n - 1):
                z0 = [0] * n
                for j, a in zip(others, values): z0[j] = a
                if _high(z0, i, adjacency, p['exposure']):
                    mass = Fraction(1, 2 ** (n - 1)); z1 = list(z0); z1[i] = 1
                    numerator += mass * (_outcome(i, z1, schedule) - _outcome(i, z0, schedule))
                    denominator += mass
            causal += numerator / denominator / len(p['population'])
        if observable != causal: raise AssertionError('OBSERVABLE_AND_CAUSAL_ORACLES_DISAGREE')
        comparisons.append(dict(schedule=schedule, observable_formula_value=str(observable),
            counterfactual_target_value=str(causal), equal=True, numeric_test_oracle_only=True))
    return dict(passed=True, full_assignment_count=2 ** n, term_count=len(terms),
        enumerated_joint_supports=sorted(set(str(x) for x in cells.values())),
        within_same_arm_outcomes_differ=any(len(v) > 1 for v in within_cell_values.values()),
        exposure_sufficiency_assumed=False, schedule_checks=comparisons)


def tamper_checks(outcome):
    """A changed term, support, or certificate must fail the actual replayer."""
    bundle = outcome.result; first = bundle.results[0]
    changed_term = replace(first.terms[0], coefficient=first.terms[0].coefficient + 1)
    mutations = {
        'coefficient': replace(first, terms=(changed_term,) + first.terms[1:]),
        'support': replace(first, population_arm_support=('0',) + first.population_arm_support[1:]),
        'certificate': replace(first, certificate_sha256='0' * 64),
    }
    results = {}
    for label, changed in mutations.items():
        altered = replace(outcome, result=replace(bundle, results=(changed,) + bundle.results[1:]))
        try:
            replay_verified_business_outcome(altered)
        except CompositionUnavailable:
            results[label] = True
        else:
            raise AssertionError('TAMPERED_PROOF_ACCEPTED:' + label)
    return results


def evaluate(record):
    b, raw = saved_inputs(record); original = deepcopy(raw)
    initial = preview(b, raw, 'D1_EFFECTS')
    reference = load(DATA / 'references/labels.json')[record['case']]
    expected_preview = preview(b, reference['reading'], 'D1_EFFECTS')
    projection_audit = compare_target_projections(expected_preview, initial)
    sources = reference['permitted_source_locations']
    source_checks = [raw['study'].get(k) in allowed for k, allowed in sources['study'].items()]
    source_checks += [raw['questions'][qid].get(k) in allowed
        for qid, fields in sources['questions'].items() for k, allowed in fields.items()]
    reading_audit = dict(
        semantic_fields=semantic_payload(raw, b['structure']['nodes']) == semantic_payload(reference['reading'], b['structure']['nodes']),
        complete_target=projection_audit['passed'], source_grounding=all(source_checks),
        expected_preview=initial['state'] == reference['expected_preview_state'])
    if not all(reading_audit.values()):
        raise AssertionError('READING_OR_KNOWN_CONDITIONS_CHANGED')
    no_review = submit(b, raw, 'D1_EFFECTS', synthetic_protocol_selected=True)
    if initial['core_called'] or no_review['core_called']:
        raise AssertionError('PREMATURE_CORE_CALL')
    extra = {}; expected = record['expected_state']
    if expected == 'CORE_POINT':
        packet, context, review = synthetic_context(record['case'], b, raw)
        for missing in ('packet', 'context', 'submission_review', 'selection'):
            kwargs = dict(packet=packet, context=context, submission_review=review, synthetic_protocol_selected=True)
            if missing == 'selection': kwargs['synthetic_protocol_selected'] = False
            else: kwargs[missing] = None
            absent = submit(b, raw, 'D1_EFFECTS', **kwargs)
            if absent['state'] != 'REVIEW_REQUIRED' or absent['core_called'] or context.core_port.calls:
                raise AssertionError('MISSING_REVIEW_NOT_BLOCKED:' + missing)
        result = submit(b, raw, 'D1_EFFECTS', packet=packet, context=context,
                        submission_review=review, synthetic_protocol_selected=True)
        inquiry = context.core_port.bindings['q1'].inquiry
        outcome = identify_network_business_query(inquiry)
        replay = replay_verified_business_outcome(outcome)
        if (result['state'] != expected or outcome.status != 'POINT'
                or outcome.route != 'R1A_COMPOSITION' or replay is not True
                or context.core_port.last_real_results['q1']['verification_level'] != 'CORE_REPLAY_VERIFIED'
                or not all(q['certificate_replayed'] for q in result['query_views'])):
            raise AssertionError('POINT_AND_REPLAY_REQUIRED')
        extra = dict(independent_enumeration=independent_enumeration(record['case'], outcome.result.results[0]),
            tamper_rejection=tamper_checks(outcome), core_receipts=result['review_receipts'],
            scientific_protocol_sha256=canonical_hash(protocol(record['case'])),
            packet=packet, submission_review=review.model_dump(mode='json'))
    else:
        result = no_review
        if result['state'] != expected or result['core_called']:
            raise AssertionError('NEGATIVE_MUST_REMAIN_UNRESOLVED')
        try: protocol(record['case'])
        except ValueError: pass
        else: raise AssertionError('NEGATIVE_HAS_UNINTENDED_SCIENCE')
    if raw != original: raise AssertionError('MODEL_RESPONSE_MUTATED')
    if (any(result.get(k, False) for k in ('production_admission', 'estimation_called',
            'policy_called', 'estimation_handoff_allowed')) or result.get('candidate_model_calls', 0) != 0):
        raise AssertionError('EXECUTION_SCOPE_ESCALATED')
    return dict(passed=True, model_group=record['model_group'], case=record['case'],
        candidate_sha256=record['candidate_sha256'], preview_state=initial['state'],
        final_state=result['state'], new_api_calls=0, reading_audit=reading_audit, result=result, **extra)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    args = parser.parse_args(argv); out = Path(args.output)
    out.mkdir(parents=True, exist_ok=False)
    rows = []
    for record in recorded_cases():
        result = evaluate(record); rows.append(result)
        (out / (record['model_group'] + '_' + record['case'] + '.json')).write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
        print(json.dumps({k: result[k] for k in ('case', 'model_group', 'passed', 'final_state')}, ensure_ascii=False), flush=True)
    summary = dict(completed=True, records=len(rows), new_api_calls=0,
        protocol_file_sha256=filehash(PROTOCOL_FILE), manifest_sha256=filehash(DATA / 'recorded/MANIFEST.json'),
        positives_verified=sum(r['final_state'] == 'CORE_POINT' for r in rows),
        negatives_blocked=sum(r['final_state'] == 'NEEDS_INPUT' for r in rows),
        per_model={m: dict(total=sum(r['model_group'] == m for r in rows),
            positive_verified=sum(r['model_group'] == m and r['final_state'] == 'CORE_POINT' for r in rows),
            negative_blocked=sum(r['model_group'] == m and r['final_state'] == 'NEEDS_INPUT' for r in rows))
            for m in ('deepseek', 'longcat')},
        scope='Previously saved real model responses; independent synthetic science; not new live model accuracy',
        results=[{k: r[k] for k in ('case', 'model_group', 'passed', 'preview_state', 'final_state')} for r in rows])
    (out / 'SUMMARY.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    return 0


if __name__ == '__main__': raise SystemExit(main())
