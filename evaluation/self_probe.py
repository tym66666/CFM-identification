"""Review provenance and schema of my own illustrative formulations.

This is NOT a real LLM benchmark; the same assistant authored examples and
makes the qualitative judgement. Tests here can prove schema/quote compliance,
not causal or semantic correctness. No external network calls.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path

from cfm_id_llm.audit import audit_draft
from cfm_id_llm.normalization import build_normalization_review
from cfm_id_llm.schemas import BusinessCase, DraftProblemSpec

HERE = Path(__file__).resolve().parent


def run() -> dict:
    data = json.loads((HERE/'self_authored_normalizations.json').read_text(encoding='utf-8'))
    catalog = {r['id']: r for r in json.loads((HERE/'business_cases.json').read_text(encoding='utf-8'))['cases']}
    results = []
    for r in data['items']:
        original = catalog[r['id']]
        case = BusinessCase.model_validate(original['business_case'])
        d = DraftProblemSpec.model_validate(r['self_authored_interpretation'])
        report = audit_draft(case, d, provider='ASSISTANT_SELF_AUTHORED_NO_API')
        review = build_normalization_review(case, report)
        ref_kinds = original['reference_for_developers_only']['plausible_target_kinds']
        results.append({
            'id': r['id'], 'question': case.business_question,
            'my_selected_target': d.target.kind.value,
            'developer_advisory_target_kinds': ref_kinds,
            'target_in_advisory_set': d.target.kind.value in ref_kinds,
            'quote_and_schema_audit': 'PASS',
            'review_status': report.review_status,
            'first_business_questions': [q.question for q in review.business_questions],
            'population_info_not_auto_certified': d.information_design.population_information_level.value
                in ('UNRESOLVED', 'FINITE_SAMPLE_DESCRIPTION'),
            'not_a_verified_identification': review.mathematical_verification == 'NOT_PERFORMED',
        })
    return {
        'run_kind': 'ASSISTANT_AUTHORED_NON_INDEPENDENT_OFFLINE_DEMONSTRATION',
        'live_llm_api_called': False,
        'mathematical_identification_performed': False,
        'result_not_independent_accuracy_metric': True,
        'caveat': 'Answers were authored by the same assistant. Developer labels are broad guidance, not mathematically verified independent gold standards.',
        'cases': len(results),
        'schema_and_quote_passed': sum(x['quote_and_schema_audit'] == 'PASS' for x in results),
        'target_advisory_alignment': sum(x['target_in_advisory_set'] for x in results),
        'results': results,
    }


def main(argv: list[str] | None = None):
    p = argparse.ArgumentParser(description='Offline self-authored demonstration, not online model accuracy')
    p.add_argument('--output')
    args = p.parse_args(argv)
    content = json.dumps(run(), ensure_ascii=False, indent=2) + '\n'
    if args.output:
        Path(args.output).write_text(content, encoding='utf-8')
    else:
        print(content)


if __name__ == '__main__':
    main()
