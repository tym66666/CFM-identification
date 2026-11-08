"""Portable, explicitly selected synthetic reference harness. Never production approval."""
from copy import deepcopy
from pydantic import TypeAdapter
from cfm_id_bridge.scientific_binding import sha
from pfn_pipeline.identification_business import FixedPolicyInquiryV21
from cfm_id.bounded_policy_contract import BoundedMeanInformation
from cfm_id.mean_order_contract import MeanOrderProblem
from evaluation import mean_order_workflow as workflow
from evaluation import mean_order_factored_reading as protocol, mean_order_factored_review as adapter
from evaluation.equal_weight_comparison_semantics import equivalent_target
from examples.mean_order_business_fixture import endpoint_reviews, business_review

KIND = 'FROZEN_SYNTHETIC_MEAN_ORDER_REFERENCE'
INQUIRY = TypeAdapter(FixedPolicyInquiryV21)


def export_fixture(case, *, references=None, provenance):
    base = case['base']
    return dict(kind=KIND, bundle_sha256=sha(case['bundle']), provenance=provenance,
        references=deepcopy(references or [protocol.reference_wire(case['bundle'], case['expected_candidate'])]),
        expected_candidate=deepcopy(case['expected_candidate']), science=deepcopy(case['science']),
        expected_problem=case['expected_problem'].model_dump(), expected_modes=deepcopy(case['expected_modes']),
        base=dict(claims=deepcopy(base['claims']), coordinates=deepcopy(base['coordinates']),
            inquiries={s:INQUIRY.dump_python(base['inquiries'][s], mode='json') for s in ('first','second')},
            information={s:base['information'][s].model_dump(mode='json') for s in ('first','second')}))


def _load(bundle, fixture):
    required = {'kind','bundle_sha256','provenance','references','expected_candidate','science','expected_problem','expected_modes','base'}
    if (type(fixture) is not dict or set(fixture) != required or fixture['kind'] != KIND
            or fixture['bundle_sha256'] != sha(bundle) or type(fixture['references']) is not list
            or not fixture['references'] or not fixture['provenance']):
        raise workflow.WorkflowError('EXACT_SYNTHETIC_REFERENCE_REQUIRED')
    base = deepcopy(fixture['base'])
    if set(base) != {'claims','coordinates','inquiries','information'}:
        raise workflow.WorkflowError('EXACT_SYNTHETIC_ENDPOINT_FIELDS_REQUIRED')
    if any(type(base[k]) is not dict or set(base[k]) != {'first','second'} for k in ('inquiries','information')):
        raise workflow.WorkflowError('EXACT_TWO_SYNTHETIC_ENDPOINTS_REQUIRED')
    # validate_json preserves typed nested dataclasses and tuple fields.
    import json
    base['inquiries'] = {s:INQUIRY.validate_json(json.dumps(base['inquiries'][s])) for s in ('first','second')}
    base['information'] = {s:BoundedMeanInformation.model_validate(base['information'][s]) for s in ('first','second')}
    base.update(bundle=deepcopy(bundle), raw=deepcopy(fixture['expected_candidate']['comparison']))
    return dict(base=base, bundle=deepcopy(bundle), science=deepcopy(fixture['science']),
        expected_candidate=deepcopy(fixture['expected_candidate']),
        expected_problem=MeanOrderProblem.model_validate(fixture['expected_problem']),
        expected_modes=deepcopy(fixture['expected_modes']))


def replay_synthetic(bundle, wire, fixture, *, query_id='q1'):
    bundle = workflow.public_bundle(bundle)
    case = _load(bundle, fixture)
    view = workflow.inspect_candidate(bundle, wire, query_id=query_id, science=case['science'])
    canonical = view['result'].get('reading_candidate')
    scores = []
    for reference in fixture['references']:
        canonical_reference = protocol.to_canonical(bundle, reference)
        score = protocol.wire_metrics(bundle, wire, reference)
        try:
            assignment = canonical['comparison']['reported_assignment']
            expected = canonical_reference['comparison']['reported_assignment']
            target = equivalent_target(bundle, canonical['comparison'], canonical_reference['comparison'])
            facts = all(assignment.get(k) == v for k,v in expected.items() if k != 'source_ids') and set(expected['source_ids']) <= set(assignment['source_ids'])
        except (ValueError, TypeError, KeyError):
            target = facts = False
        scores.append(dict(wire=score, target=target, assignment=facts, passed=score['passed'] and target and facts))
    exact = any(s['passed'] for s in scores)
    if exact and view['state'] == 'REVIEW_REQUIRED':
        chain = endpoint_reviews(case, canonical)
        legacy_review = business_review(case, canonical, chain)
        full = adapter.ReviewedFactoredReading(**adapter.worksheet(bundle, wire, legacy_review=legacy_review),
            reviewer='Independent frozen synthetic reference reviewer', evidence=fixture['provenance'],
            reviewed_full_wire_semantics_and_sources=True, reviewed_projection_and_losses=True, synthetic_fixture=True)
        view = workflow.submit_reviewed(bundle, wire, query_id=query_id, science=case['science'],
            review=legacy_review, factored_review=full, **chain)
    elif not exact and view['state'] == 'REVIEW_REQUIRED':
        view['result']['reason_code'] = 'INDEPENDENT_FACTORED_SEMANTIC_REVIEW_WITHHELD'
        view['answer']['reason_code'] = view['result']['reason_code']
    view['synthetic_reference_check'] = dict(passed=exact, scores=scores, fixture_sha256=sha(fixture),
        reference_provenance=fixture['provenance'], automatic_real_world_semantic_verification=False,
        notes='References are separate synthetic test assertions. No original reply is repaired; no production approval is created.')
    return view
