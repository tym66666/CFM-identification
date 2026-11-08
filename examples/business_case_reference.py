"""Explicit synthetic whole-case fixture. Never imported by runtime code."""
from copy import deepcopy
from cfm_id import business_intake as intake, business_dispatch as dispatch, business_case
from cfm_id_llm.dag_query_reading import reference_catalog, VERSION
from .business_dispatch_reference import from_case, approve, approvals
from .dag_business_reference import cases


def scenario(case=None, *, two_queries=True):
    s, native = from_case(case or cases()[0])
    raw = deepcopy(s.candidate)
    if two_queries:
        first = raw['queries'][0]
        raw['queries'] = []
        for value in (0, 1):
            q = deepcopy(first)
            q['query_id'] = f'q{value+1}'
            q['business_goal']['value'] = f"将{native['target']['treatment']}设为{value}时，{native['target']['outcome']}的总体分布"
            q['target']['description'] = deepcopy(q['business_goal'])
            q['semantics']['intervention'] = deepcopy(q['business_goal'])
            raw['queries'].append(q)
        raw['shared_draft']['target'] = deepcopy(raw['queries'][0]['target'])
        s = intake.receive_candidate(s, raw, request_sha256=s.request_sha256)
    return intake.configure_fact_format(s, 'short_refs'), native


def short_fixture(entry, native, values):
    """Encode an offline reference, never convert or repair a live model reply."""
    refs = reference_catalog(entry['bundle'], binding=entry['fact_binding_sha256'])
    reverse = {row['source_id']: alias for alias,row in refs['aliases'].items()}
    def encode(value):
        if isinstance(value, dict):
            return {k: [reverse[x] for x in v] if k.endswith('source_ids') else encode(v)
                    for k,v in value.items()}
        if isinstance(value, list):
            return [encode(v) for v in value]
        return deepcopy(value)
    result = encode(native)
    result.update(version=VERSION, reference_context=refs['context'], query_scope=dict(
        kind='ALL_TREATMENT_VALUES' if values is None else 'TREATMENT_VALUES', values=values or [],
        source_ids=deepcopy(result['target']['source_ids'])))
    return result


def submission(s, native, qid, values):
    review = approve(dispatch.prepare_reader(s, qid)['query_worksheet'])
    entry = dispatch.prepare_reader(s, qid, query_review=review)
    wire = short_fixture(entry, native, values)
    row = dict(query_review=review, candidate=wire, request_sha256=entry['request_sha256'])
    plan = dispatch.inspect_methods(s, qid, **row)
    if plan['state'] == 'REVIEW_REQUIRED':
        row.update({k:v for k,v in approvals(plan).items() if k != 'research_protocol_selected'})
    return row, entry, plan


def run(output):
    from pathlib import Path
    path = Path(output)
    path.mkdir(parents=True, exist_ok=False)
    s, native = scenario()
    rows = {qid: submission(s, native, qid, [i])[0] for i,qid in enumerate(('q1','q2'))}
    review = approve(business_case.prepare_case(s)['case_worksheet'])
    incomplete = business_case.execute_case(s, {'q1': rows['q1']}, case_review=review, research_protocol_selected=True)
    complete = business_case.execute_case(s, rows, case_review=review, research_protocol_selected=True)
    intake.save(s, path/'intake.json')
    intake.write_json(path/'one_query_only.json', incomplete)
    intake.write_json(path/'whole_case.json', complete)
    summary = dict(api_calls=0, mode='EXPLICIT_SYNTHETIC_REVIEWS',
                   one_query_state=incomplete['state'], all_query_state=complete['state'],
                   independent_replay=[r['result']['independent_replay'] for r in complete['results']])
    intake.write_json(path/'SUMMARY.json', summary)
    return summary


if __name__ == '__main__':
    import argparse, json
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', required=True)
    p.add_argument('--allow-synthetic-reviews', action='store_true')
    args = p.parse_args()
    if not args.allow_synthetic_reviews:
        p.error('Explicit synthetic reference selection required')
    print(json.dumps(run(args.output)))
