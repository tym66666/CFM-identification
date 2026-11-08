"""Synthetic reference flow, not a live LLM run or real scientific approval."""
from copy import deepcopy
from cfm_id import business_intake as intake
from cfm_id import business_dispatch as dispatch
from cfm_id.dag_business import reading_contract, route_contract
from cfm_id_llm.schemas import (BusinessCase, SourceDocument, SemanticClaim, TargetDraft,
    UnitsVariablesDraft, StructureDraft, DraftProblemSpec)
from cfm_id_llm.quality import BusinessInquiryV010, MultiQueryDraftV010


def from_case(case):
    b = case['bundle']; wire = deepcopy(case['reference'])
    business = BusinessCase(case_id=b['case_id'], business_question=b['question'],
        sources=[SourceDocument(source_id=k, text=v) for k, v in b['documents'].items()])
    def claim(text, source='business_question'):
        return SemanticClaim(value=text, basis='EXPLICIT_TEXT', evidence=[dict(source_id=source, quote=text)])
    target = TargetDraft(kind='INTERVENTIONAL_DISTRIBUTION', description=claim(b['question']))
    q = BusinessInquiryV010(query_id='q1', business_goal=claim(b['question']), target=target)
    shared = DraftProblemSpec(target=target,
        units_variables=UnitsVariablesDraft(analysis_unit=claim(wire['target']['context'], 'context'),
            treatment=claim(wire['target']['treatment']), outcome=claim(wire['target']['outcome'])),
        structure=StructureDraft(variable_causal_graph=claim(b['documents']['relations'], 'relations')))
    a0 = MultiQueryDraftV010(shared_draft=shared, primary_query_id='q1', queries=[q]).model_dump(mode='json')
    s = intake.start(business, reading_format='canonical', fact_format='source_hash')
    s = intake.receive_candidate(s, a0, request_sha256=s.request_sha256)
    if wire['version'] == 'dag-reading-1':
        # Synthetic test fixture conversion only, never applied to live answers.
        wire.update(version='dag-frontdoor-reading-2',
                    frontdoor_choice=dict(status='UNSPECIFIED', variable=None, source_ids=[]))
    return s, wire


REVIEWER = dict(reviewer='Independent synthetic protocol reviewer',
    evidence='Frozen hypothetical target and declared model independently stipulated; no real-world approval.',
    authority='SYNTHETIC_TEST')


def approve(sheet, cls=dispatch.DispatchReview):
    # Explicit test-only assumptions. Runtime has no accept-all operation.
    return cls(**{k: v for k, v in sheet.items() if k not in ('is_approval', 'decisions')},
               **REVIEWER, decisions={k: 'ACCEPTED' for k in sheet['decisions']})


def prepare(case):
    s, wire = from_case(case)
    pending = dispatch.prepare_reader(s, 'q1')
    qreview = approve(pending['query_worksheet'])
    entry = dispatch.prepare_reader(s, 'q1', query_review=qreview)
    options = dict(query_review=qreview, candidate=wire, request_sha256=entry['request_sha256'])
    return s, options, dispatch.inspect_methods(s, 'q1', **options)


def approvals(plan):
    records = {r['method']: dict(reading_review=approve(r['reading_worksheet'], reading_contract(r['method'])[2]),
                                 science_review=approve(r['science_worksheet'], route_contract(r['method'])[1]))
               for r in plan['methods']}
    return dict(plan_review=approve(plan['plan_worksheet']), native_reviews=records,
                research_protocol_selected=True)


def run(output):
    from pathlib import Path
    from examples.dag_business_reference import cases as backdoor
    from examples.dag_adjustment_business_reference import cases as adjustment
    from examples.dag_frontdoor_business_reference import _case as frontdoor
    folder = Path(output); folder.mkdir(parents=True, exist_ok=False)
    scenarios = [('observed_confounder', backdoor()[0]), ('adjustment_beyond_classical', adjustment()[0]),
                 ('unspecified_frontdoor', frontdoor('dispatch_frontdoor', 'implicit_role')),
                 ('missing_graph', backdoor()[3]), ('sample_only', backdoor()[5]),
                 ('no_supported_method', backdoor()[6])]
    rows = []
    for name, case in scenarios:
        s, options, plan = prepare(case)
        result = (dispatch.execute(s, 'q1', **options, **approvals(plan))
                  if plan['state'] == 'REVIEW_REQUIRED' else plan)
        intake.save(s, folder / (name + '_intake.json'))
        intake.write_json(folder / (name + '_plan.json'), plan)
        intake.write_json(folder / (name + '_result.json'), result)
        rows.append(dict(case=name, state=result['state'], methods=[a['method'] for a in result['answers']],
                         independent_replay=result['independent_replay']))
    summary = dict(scope='OFFLINE_SYNTHETIC_DISPATCH', api_calls=0, cases=rows,
                   llm_accuracy_measured=False, production_admission=False)
    intake.write_json(folder / 'SUMMARY.json', summary)
    return summary


if __name__ == '__main__':
    import argparse, json
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', required=True)
    p.add_argument('--allow-synthetic-reviews', action='store_true')
    args = p.parse_args()
    if not args.allow_synthetic_reviews: p.error('Explicit synthetic reference selection required')
    print(json.dumps(run(args.output), ensure_ascii=False))
