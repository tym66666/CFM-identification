"""Opt-in reviewed first-minus-second composition of existing R1b results.

This layer reads no keys, grants no scientific approval and changes no theorem.
The original ID-bound comparison is retained. Each endpoint has its own existing
business/scientific binding; a separate review binds the ordered pair. Initially
only a common uniform fixed-quota study and equal-weight mean are admitted.
"""
from copy import deepcopy
from fractions import Fraction
from typing import Literal

from pydantic import ConfigDict, Field, field_validator
from cfm_id_llm.schemas import StrictModel
from cfm_id_bridge.scientific_binding import sha, actual_scientific_sources, actual_scientific_licenses
from . import question_bound_assignment as ids
from .assignment_review import validate_assignment_review
from .intent_submission import _context_snapshot, _validate_policy
from cfm_id_llm.readers.fixed_policy_base import project as inspect_targets

ENTRY = 'FIXED_COMPARISON'
VERSION = 'fixed-comparison-1'
SIDES = ('first', 'second')


def make_request(bundle):
    system, user = ids.make_request(bundle)
    old = '若问题为比较但两端已完整，本入口仍只保留阅读结果；不会把它改成单一水平。'
    if system.count(old) != 1:
        raise ValueError('COMPARISON_READING_RULE_CHANGED')
    system = system.replace(old, '比较必须保留两个完整或含未知项的安排，不能改成单一水平。')
    system += ('\n当前选择FIXED_COMPARISON入口。first是所问相对变化的方案，second是比较基准，目标方向为first减second。'
        '例如“甲比乙多多少”为甲减乙，“从甲改为乙会增加多少”为乙减甲；不要只按文字出现顺序填写。'
        '两端使用同一评价名单和汇总方式。没有说明的条件继续填未知；只报告实际读取，不输出许可、公式或识别状态。\n')
    system += ('评价名单与汇总方式必须分别判断，某一字段未知不抹去另一字段已明确的信息。'
        '名单尚未决定，但材料已明确要求各对象等权平均时，population填null、aggregation仍填等权平均。'
        '如果权重或汇总规则本身尚未决定，aggregation才填不明确；其他只用于材料明确指定了本入口未列举的汇总方式。'
        '不能根据周围问题的名单或权重补填当前问题。\n')
    return system, user


def project(bundle, raw):
    resolved, source = ids.resolve_reading(bundle, raw)
    _, receipts = inspect_targets(bundle, resolved['reading'])
    nodes = bundle['node_order']
    targets = {}
    for qid, r in receipts.items():
        c = resolved['reading']['questions'][qid]
        if r['intent']['kind'] == '比较' and not r['missing_conditions'] and c['aggregation'] == '等权平均':
            targets[qid] = dict(node_order=list(nodes),
                first=[c['first'][n] for n in nodes], second=[c['second'][n] for n in nodes],
                unit_weights=[str(Fraction(1, len(c['population']))) if n in c['population'] else '0' for n in nodes],
                operation='first_minus_second')
    return resolved, source, receipts, targets


def preview(bundle, raw):
    out = ids.preview(bundle, raw)
    out.update(entry=ENTRY, comparison_version=VERSION)
    if 'question_binding' not in out:
        return out
    resolved, source, receipts, targets = project(bundle, raw)
    out['proposed_comparisons'] = deepcopy(targets)
    for view in out['query_views']:
        qid = view['query_id']; r = receipts[qid]
        if qid in targets:
            view.update(state='REVIEW_REQUIRED', reason_code=None)
        elif r['missing_conditions'] or r['intent']['kind'] == '不明确':
            view.update(state='NEEDS_INPUT', reason_code='COMPARISON_TARGET_INCOMPLETE')
        else:
            view.update(state='UNSUPPORTED', reason_code='COMPARISON_TARGET_NOT_ADAPTED')
    states = {v['state'] for v in out['query_views']}
    target_state = next(iter(states)) if len(states) == 1 else 'MIXED'
    out['target_reading_state'] = target_state
    out['state'] = target_state if out['assignment_review']['state'] == 'REVIEW_REQUIRED' else out['assignment_review']['state']
    return out


class ReviewedComparison(StrictModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    version: Literal['fixed-comparison-1']
    bundle_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    reading_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    ordered_targets_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    endpoint_bindings_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    reviewer: str = Field(min_length=3)
    evidence: str = Field(min_length=12)
    reviewed_comparison_direction_and_population: Literal[True]
    synthetic_fixture: Literal[True]

    @field_validator('reviewed_comparison_direction_and_population', 'synthetic_fixture', mode='before')
    @classmethod
    def explicit_boolean(cls, value):
        if type(value) is not bool or value is not True:
            raise ValueError('EXPLICIT_COMPARISON_REVIEW_REQUIRED')
        return value


class ReviewedComparisonScope(ReviewedComparison):
    """Explicit subset approval; the full input and raw reading remain bound.

    This is an independently supplied synthetic review record, not a model
    field or an authenticated reviewer signature. Omission means unreviewed,
    not an automatic finding that the omitted question was read incorrectly.
    """
    version: Literal['fixed-comparison-scope-1']
    reviewed_query_ids: list[str] = Field(min_length=1)

    @field_validator('reviewed_query_ids', mode='before')
    @classmethod
    def unique_ids(cls, value):
        if (type(value) is not list or not value
                or any(type(q) is not str or not q or q != q.strip() for q in value)
                or len(set(value)) != len(value)):
            raise ValueError('EXPLICIT_UNIQUE_QUERY_SCOPE_REQUIRED')
        return value


def _scope_targets(targets, query_ids):
    if (type(query_ids) is not list or not query_ids
            or any(type(q) is not str for q in query_ids)
            or len(set(query_ids)) != len(query_ids)
            or query_ids != [q for q in targets if q in query_ids]):
        raise ValueError('ORDERED_COMPLETE_QUERY_SCOPE_REQUIRED')
    return {q: targets[q] for q in query_ids}


def _endpoints(mapping):
    if type(mapping) is not dict or set(mapping) != set(SIDES):
        raise ValueError('EXACT_TWO_ENDPOINTS_REQUIRED')


def worksheet(bundle, raw, packets, contexts):
    """Only fingerprints: this does not manufacture a reviewer or approval."""
    _endpoints(packets); _endpoints(contexts)
    _, _, _, targets = project(bundle, raw)
    if not targets:
        raise ValueError('COMPLETE_COMPARISON_REQUIRED')
    bindings = {s: dict(packet=packets[s], context=_context_snapshot(contexts[s])) for s in SIDES}
    return dict(version=VERSION, bundle_sha256=sha(bundle), reading_sha256=sha(raw),
        ordered_targets_sha256=sha(targets), endpoint_bindings_sha256=sha(bindings))


def scoped_worksheet(bundle, raw, packets, contexts, *, reviewed_query_ids):
    """Only fingerprints for an explicit scope; never selects or approves it."""
    _endpoints(packets); _endpoints(contexts)
    _, _, _, targets = project(bundle, raw)
    selected = _scope_targets(targets, reviewed_query_ids)
    bindings = {s: dict(packet=packets[s], context=_context_snapshot(contexts[s])) for s in SIDES}
    return dict(version='fixed-comparison-scope-1', reviewed_query_ids=list(selected),
        bundle_sha256=sha(bundle), reading_sha256=sha(raw),
        ordered_targets_sha256=sha(selected), endpoint_bindings_sha256=sha(bindings))


def _endpoint_targets(targets, side):
    return {q: dict(classification='FIXED_POLICY', node_order=t['node_order'],
                   assignment=t[side], unit_weights=t['unit_weights']) for q, t in targets.items()}


def _validate(bundle, raw, packets, contexts, review, facts):
    from pfn_pipeline.identification_business import FixedPolicyInquiryV21
    _endpoints(facts)
    if type(review) not in (ReviewedComparison, ReviewedComparisonScope):
        raise ValueError('SEPARATE_COMPARISON_REVIEW_REQUIRED')
    reviewed = type(review).model_validate(review.model_dump())
    scoped = type(reviewed) is ReviewedComparisonScope
    expected = (scoped_worksheet(bundle, raw, packets, contexts, reviewed_query_ids=reviewed.reviewed_query_ids)
        if scoped else worksheet(bundle, raw, packets, contexts))
    if any(getattr(reviewed, k) != v for k, v in expected.items()):
        raise ValueError('COMPARISON_REVIEW_STALE')
    resolved, source, receipts, targets = project(bundle, raw)
    if scoped:
        targets = _scope_targets(targets, reviewed.reviewed_query_ids)
        for side in SIDES:
            if (set(packets[side]['queries']) != set(targets)
                    or set(contexts[side].core_port.crosswalks) != set(targets)):
                raise ValueError('EXACT_SCOPED_ENDPOINT_REVIEW_REQUIRED')
    fact_receipts = {}
    for side in SIDES:
        fact_receipts[side] = validate_assignment_review(bundle, raw, packets[side], contexts[side], facts[side], contract=ids.CONTRACT)
        _validate_policy(bundle, resolved['reading'], packets[side], contexts[side], _endpoint_targets(targets, side))
    for qid in targets:
        a, b = [contexts[s].core_port.bindings[qid].inquiry for s in SIDES]
        if type(a) is not FixedPolicyInquiryV21 or type(b) is not FixedPolicyInquiryV21:
            raise ValueError('FIXED_POLICY_ENDPOINTS_REQUIRED')
        if sha(a.study) != sha(b.study):
            raise ValueError('COMMON_STUDY_REQUIRED')
        if sha(actual_scientific_sources(a)) != sha(actual_scientific_sources(b)) or sha(actual_scientific_licenses(a)) != sha(actual_scientific_licenses(b)):
            raise ValueError('COMMON_SCIENTIFIC_CONTRACT_REQUIRED')
        if any(x.r2_signature is not None or x.r2_sufficiency is not None or x.r2_sources for x in (a, b)):
            raise ValueError('COMPARISON_R1B_SCOPE_REQUIRED')
    return targets, fact_receipts


def _verified_endpoints(first, second, target):
    from pfn_pipeline.identification_business import VerifiedBusinessOutcomeV21, replay_verified_business_outcome
    from pfn_pipeline.identification_policy_r1b import VerifiedFixedPolicyV19
    if set(target) != {'node_order', 'first', 'second', 'unit_weights', 'operation'} or target['operation'] != 'first_minus_second':
        raise ValueError('EXACT_ORDERED_TARGET_REQUIRED')
    for side, outcome in zip(SIDES, (first, second)):
        if (type(outcome) is not VerifiedBusinessOutcomeV21 or outcome.status != 'POINT'
                or outcome.route != 'R1B_FULL_ASSIGNMENT' or type(outcome.result) is not VerifiedFixedPolicyV19
                or not replay_verified_business_outcome(outcome)):
            raise ValueError('TWO_REPLAYED_R1B_ENDPOINTS_REQUIRED')
        t = outcome.result.target
        if (list(t.node_order) != target['node_order'] or list(t.policy_assignment) != target[side]
                or list(t.unit_weights) != target['unit_weights']):
            raise ValueError('ENDPOINT_TARGET_MISMATCH')
    a, b = first.result, second.result
    if sha(a.study) != sha(b.study) or sha(a.sources) != sha(b.sources) or sha(a.assumptions) != sha(b.assumptions):
        raise ValueError('COMMON_ENDPOINT_MODEL_REQUIRED')
    w = [Fraction(x) for x in target['unit_weights']]
    positive = [x for x in w if x > 0]
    if not positive or any(x < 0 for x in w) or sum(w) != 1 or len(set(positive)) != 1:
        raise ValueError('COMMON_EQUAL_POPULATION_REQUIRED')


def compose(first, second, *, target, binding):
    """Ordered algebraic receipt, not a new certificate issued by the Core."""
    _verified_endpoints(first, second, target)
    terms = []
    for side, sign, outcome in zip(SIDES, (1, -1), (first, second)):
        r = outcome.result
        terms.extend(dict(side=side, node=n, assignment=list(r.target.policy_assignment),
            coefficient=str(sign * Fraction(w)), observable=o)
            for n, w, o in zip(r.weighted_nodes, r.node_weights, r.required_observables))
    receipt = dict(version=VERSION, verification='TWO_CORE_REPLAYS_AND_SIGNED_COMPOSITION',
        target=deepcopy(target), binding=deepcopy(binding), study_sha256=sha(first.result.study),
        endpoint_sha256={s: sha(r.summary()) for s, r in zip(SIDES, (first, second))},
        terms=terms, identified_functional=f'({first.result.identified_functional}) - ({second.result.identified_functional})',
        new_core_theorem=False, estimation_handoff_allowed=False)
    receipt['receipt_sha256'] = sha(receipt)
    return receipt


def replay(receipt, first, second, *, target, binding):
    """Check original Core certificates and signed terms against an external target."""
    try:
        _verified_endpoints(first, second, target)
        r = deepcopy(receipt); digest = r.pop('receipt_sha256')
        if sha(r) != digest or r['target'] != target or r['binding'] != binding:
            return False
        if (set(r) != {'version','verification','target','binding','study_sha256','endpoint_sha256','terms','identified_functional','new_core_theorem','estimation_handoff_allowed'}
                or r['version'] != VERSION or r['verification'] != 'TWO_CORE_REPLAYS_AND_SIGNED_COMPOSITION'
                or r['study_sha256'] != sha(first.result.study) or r['new_core_theorem'] is not False
                or r['estimation_handoff_allowed'] is not False):
            return False
        expected = []
        for side, outcome in zip(SIDES, (first, second)):
            x = outcome.result
            if r['endpoint_sha256'][side] != sha(outcome.summary()):
                return False
            observables = dict(zip(x.weighted_nodes, x.required_observables))
            for node, weight in zip(target['node_order'], target['unit_weights']):
                if Fraction(weight):
                    coefficient = Fraction(weight) if side == 'first' else -Fraction(weight)
                    expected.append(dict(side=side, node=node, assignment=target[side], coefficient=str(coefficient), observable=observables[node]))
        return (r['terms'] == expected and set(r['endpoint_sha256']) == set(SIDES)
                and r['identified_functional'] == f'({first.result.identified_functional}) - ({second.result.identified_functional})')
    except (ValueError, TypeError, KeyError, AttributeError):
        return False


def submit(bundle, raw, *, packet=None, context=None, submission_review=None,
           assignment_review=None, synthetic_protocol_selected=False):
    """Both scientific endpoint reviews are checked before any Core invocation."""
    from pfn_pipeline.identification_business import identify_network_business_query, replay_verified_business_outcome
    out = preview(bundle, raw)
    targets = out.get('proposed_comparisons', {})
    if not targets or out.get('assignment_review', {}).get('state') != 'REVIEW_REQUIRED':
        return out
    if not synthetic_protocol_selected or any(v is None for v in (packet, context, submission_review, assignment_review)):
        return out
    try:
        targets, facts = _validate(bundle, raw, packet, context, submission_review, assignment_review)
    except (ValueError, TypeError, KeyError, AttributeError):
        out.update(state='CHECK_BLOCKED', reason_code='COMPARISON_OR_SCIENCE_REVIEW_REJECTED')
        return out
    out.update(assignment_fact_review_receipts=facts, comparison_review_sha256=sha(submission_review), identification={'results': []})
    if type(submission_review) is ReviewedComparisonScope:
        out['comparison_review_scope'] = dict(version=submission_review.version,
            reviewed_query_ids=list(targets),
            unreviewed_query_ids=[q for q in out['proposed_comparisons'] if q not in targets],
            full_bundle_sha256=sha(bundle), full_reading_sha256=sha(raw))
        for view in out['query_views']:
            if view['query_id'] in out['proposed_comparisons'] and view['query_id'] not in targets:
                view.update(state='REVIEW_REQUIRED', reason_code='COMPARISON_NOT_IN_REVIEW_SCOPE')
    for view in out['query_views']:
        qid = view['query_id']
        if qid not in targets:
            continue
        outcomes = {}; endpoint_rows = {}
        for side in SIDES:
            c = context[side]; before = len(c.core_port.calls)
            try:
                coverage = c.core_port.lookup(case=c.case, quality=c.quality, review=c.business_review, query_id=qid)
                result = identify_network_business_query(c.core_port.bindings[qid].inquiry)
                verified = (coverage.status == result.status == 'POINT'
                    and c.core_port.last_real_results[qid]['verification_level'] == 'CORE_REPLAY_VERIFIED'
                    and replay_verified_business_outcome(result))
                if coverage.status != result.status or (result.status == 'POINT' and not verified):
                    raise ValueError('ENDPOINT_RECEIPT_DISAGREES')
                outcomes[side] = result
                endpoint_rows[side] = dict(state='CORE_POINT' if verified else result.status,
                    core=result.summary(), certificate_replayed=bool(verified), reason_code=result.reason_code)
            except (ValueError, TypeError, KeyError, RuntimeError):
                endpoint_rows[side] = dict(state='CHECK_BLOCKED', certificate_replayed=False, reason_code='ENDPOINT_REPLAY_REJECTED')
            endpoint_rows[side]['core_called'] = len(c.core_port.calls) > before
        view.update(endpoints=endpoint_rows, core_called=any(v['core_called'] for v in endpoint_rows.values()),
                    certificate_replayed=False, composition_replayed=False)
        state_set = {v['state'] for v in endpoint_rows.values()}
        if state_set == {'CORE_POINT'}:
            binding = dict(query_id=qid, bundle_sha256=sha(bundle), reading_sha256=sha(raw), review_sha256=sha(submission_review))
            try:
                receipt = compose(outcomes['first'], outcomes['second'], target=targets[qid], binding=binding)
                if not replay(receipt, outcomes['first'], outcomes['second'], target=targets[qid], binding=binding):
                    raise ValueError('COMPOSITION_REPLAY_FAILED')
                view.update(state='CORE_POINT', reason_code=None, route='R1B_ENDPOINT_DIFFERENCE',
                    certificate_replayed=True, composition_replayed=True, composition=receipt)
            except (ValueError, TypeError, KeyError):
                view.update(state='CHECK_BLOCKED', reason_code='COMPOSITION_REPLAY_REJECTED')
        else:
            state = 'CHECK_BLOCKED' if 'CHECK_BLOCKED' in state_set else 'NEEDS_INPUT' if 'NEEDS_INPUT' in state_set else 'UNSUPPORTED'
            view.update(state=state, reason_code='COMPARISON_ENDPOINT_NOT_IDENTIFIED',
                nonidentification_proved=False)
        out['identification']['results'].append(deepcopy(view))
    out['core_called'] = any(v['core_called'] for v in out['query_views'])
    states = {v['state'] for v in out['query_views']}
    out['state'] = next(iter(states)) if len(states) == 1 else 'MIXED'
    return out
