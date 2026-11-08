"""Versioned NBIB tracks, public-only model intake, and honest attempt scoring."""
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path

DATA = Path(__file__).resolve().parent
PROJECT = DATA.parents[1]


def read(path):
    return json.loads(Path(path).read_text(encoding='utf8'))


def registry():
    return read(DATA / 'registry.json')


def entry(case_id):
    matches = [x for x in registry()['entries'] if x['id'] == case_id]
    if len(matches) != 1:
        raise ValueError('UNKNOWN_OR_DUPLICATE_CASE')
    return matches[0]


def public_path(relative):
    p = Path(relative)
    if p.is_absolute() or '..' in p.parts or {'research_only', 'gold'} & set(p.parts):
        raise ValueError('PUBLIC_PATH_REQUIRED')
    resolved = (PROJECT / p).resolve()
    if not resolved.is_relative_to(PROJECT) or 'public' not in p.parts:
        raise ValueError('PUBLIC_PATH_REQUIRED')
    return resolved


def check_public(item):
    files = dict(item['public_files'])
    if item['track'] == 'NBIB_CONTROLLED_REVISION':
        files.update(entry(item['source_case_id'])['public_files'])
    for name, digest in files.items():
        if hashlib.sha256(public_path(name).read_bytes()).hexdigest() != digest:
            raise ValueError('PUBLIC_FILE_CHANGED: ' + name)


def material_input(case_id):
    """Natural-language documents plus deterministically loaded public CSVs.

    This function never opens references or scientific packets. Calling it does
    not assert that the experimental D3/D4 adapter covers a raw NBIB case.
    """
    from evaluation.business_materials_intake import load_bundle
    item = entry(case_id)
    check_public(item)
    folder = public_path(item['public_directory'])
    text = {name: public_path(path).read_text(encoding='utf8')
            for name, path in item.get('clarification_files', {}).items()}
    return load_bundle(item['source_case_id'], public_root=folder.parent,
                       clarification=text.get('target_clarification.txt'),
                       design_addendum=text.get('design_addendum.txt'))


def original_a0_input(case_id):
    from evaluation.nbib_semantic_eval import load_public_business_case
    item = entry(case_id)
    if item['track'] != 'NBIB_RAW':
        raise ValueError('RAW_NBIB_CASE_REQUIRED')
    check_public(item)
    folder = public_path(item['public_directory'])
    return load_public_business_case(case_id, root=folder.parent).case


def canonical_material_request(bundle):
    from evaluation.business_materials_optional_tables import make_request
    # Only mapping serialization is standardized; list order, text, IDs,
    # probabilities, and every target coordinate remain unchanged.
    canonical = json.loads(json.dumps(bundle, ensure_ascii=False, sort_keys=True))
    return make_request(canonical)


def material_request(case_id):
    return canonical_material_request(material_input(case_id))


def validate(*, replay_references=False):
    data = registry()
    entries = data['entries']
    if len({x['id'] for x in entries}) != len(entries):
        raise ValueError('DUPLICATE_CASE_ID')
    counts = dict(Counter(x['track'] for x in entries))
    if counts != data['tracks']:
        raise ValueError('TRACK_COUNT_MISMATCH')
    for item in entries:
        check_public(item)
        if item['track'] != 'NBIB_RAW' and (
                item['split'] != 'DEVELOPMENT_REGRESSION' or item['heldout_claim_allowed'] is not False):
            raise ValueError('DEVELOPMENT_DATA_MUST_NOT_BE_BLIND_HOLDOUT')
    raw = read(DATA / 'research_only/raw_acceptance.json')['cases']
    if len(raw) != 21 or sum(len(x['queries']) for x in raw) != 29:
        raise ValueError('RAW_ACCEPTANCE_COVERAGE_INVALID')
    if any(x['acceptance'] is not None for x in raw):
        raise ValueError('UNEVALUATED_BASELINE_CANNOT_BE_PREFILLED')
    result = dict(version=data['version'], tracks=counts, inputs=len(entries),
                  original_queries=29, original_files_unchanged=True,
                  blind_holdout_cases=0, api_calls=0, references_replayed=0, point_replays=0)
    if replay_references:
        from evaluation.business_core_pilot_base import canonical_hash
        from evaluation.business_materials_optional_tables import evaluate_draft
        references = read(DATA / 'research_only/formal_references.json')
        frozen = read(DATA / 'research_only/frozen_prompts.json')
        for case_id, reference in references.items():
            bundle = material_input(case_id)
            system, user = material_request(case_id)
            if canonical_hash(bundle) != frozen[case_id]['input_sha256']:
                raise ValueError('INPUT_CHANGED')
            if hashlib.sha256((system + '\n' + user).encode()).hexdigest() != frozen[case_id]['prompt_sha256']:
                raise ValueError('PROMPT_CHANGED')
            actual = evaluate_draft(bundle, reference['raw_reading'], reference['science_packet'],
                                    synthetic_protocol_selected=True)
            if json.loads(json.dumps(actual)) != reference['expected_result']:
                raise ValueError('REFERENCE_REPLAY_MISMATCH: ' + case_id)
            result['references_replayed'] += 1
            result['point_replays'] += sum(q['certificate_replay'] for q in actual['results'])
    return result


def classify_attempt(row, expected_query_count):
    """No gold decision, generic refusal, or valid JSON alone is a semantic pass."""
    if row.get('transport_complete') is not True:
        return 'TRANSPORT_FAILURE'
    if row.get('contract_passed') is not True:
        return 'CONTRACT_FAILURE'
    if type(row.get('query_count')) is not int or row['query_count'] != expected_query_count:
        return 'QUERY_COVERAGE_FAILURE'
    if row.get('semantic_passed') is None:
        return 'SEMANTICS_NOT_SCORED'
    if row['semantic_passed'] is not True:
        return 'SEMANTIC_FAILURE'
    if row.get('track') == 'NBIB_RAW':
        return 'BUSINESS_SEMANTICS_PASS_ONLY'
    if row.get('expected_decision_passed') is not True:
        return 'IDENTIFICATION_EXPECTATION_FAILURE'
    if type(row.get('point_present')) is not bool:
        return 'IDENTIFICATION_EVIDENCE_NOT_SCORED'
    if row.get('point_present') is True and row.get('point_replay_passed') is not True:
        return 'CERTIFICATE_FAILURE'
    return 'PASS'


def summarize_attempts(rows):
    """Group by frozen pipeline/config profile, retaining each input's prompt hash.

    Different business inputs naturally have different full prompt hashes. That
    must not split one benchmark version into one group per question.
    """
    groups = defaultdict(list)
    seen = set()
    for row in rows:
        if row['run_id'] in seen:
            raise ValueError('DUPLICATE_ATTEMPT')
        seen.add(row['run_id'])
        item = entry(row['case_id'])
        if row['track'] != item['track']:
            raise ValueError('TRACK_MISMATCH')
        key = (row['track'], row['adapter_version'], row['profile_sha256'])
        status = classify_attempt(row, item['query_count'])
        groups[key].append(dict(run_id=row['run_id'], case_id=row['case_id'], status=status,
                               prompt_sha256=row['prompt_sha256']))
    return [dict(track=key[0], adapter_version=key[1], profile_sha256=key[2],
                 attempts=len(values), status_counts=dict(Counter(v['status'] for v in values)),
                 rows=values) for key, values in sorted(groups.items())]
