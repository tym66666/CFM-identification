"""Session adapters for existing fixed-policy and ordered-contrast entries.

Each lane is explicitly chosen. No new theorem, interval algebra, fallback,
approval creation, or executable context deserialization lives here.
"""
from copy import deepcopy
from cfm_id_bridge.scientific_binding import canonical_data, sha
from .capability_registry import session_lanes

LANES = session_lanes('POLICY')
POLICY, COMPARISON, BOUNDED_POLICY, BOUNDED_COMPARISON = LANES
BOUNDED = (BOUNDED_POLICY, BOUNDED_COMPARISON)
PAIRED = (COMPARISON, BOUNDED_COMPARISON)
SIDES = ('first', 'second')
CONTRACT = 'fixed-assignment-id'


def fields(lane):
    if lane not in LANES:
        raise ValueError('EXPLICIT_POLICY_SESSION_LANE_REQUIRED')
    if lane == BOUNDED_COMPARISON:
        return {'query_id', 'packet', 'context', 'information', 'assignment_review', 'joint_review'}
    base = {'packet', 'context', 'submission_review', 'assignment_review'}
    return base | {'query_id', 'information', 'bounded_review'} if lane == BOUNDED_POLICY else base


def _exact(lane, native):
    if type(native) is not dict or set(native) != fields(lane):
        raise ValueError('EXACT_POLICY_NATIVE_FIELDS_REQUIRED')
    if lane in PAIRED and (type(native['context']) is not dict or set(native['context']) != set(SIDES)):
        raise ValueError('EXACT_TWO_POLICY_CONTEXTS_REQUIRED')


def request(lane, bundle):
    from .business_entry import prepare_request
    return prepare_request(bundle, 'FIXED_COMPARISON' if lane in PAIRED else 'FIXED_POLICY', contract=CONTRACT)


def inspect(lane, bundle, candidate):
    from .business_entry import preview
    result = preview(bundle, candidate, 'FIXED_COMPARISON' if lane in PAIRED else 'FIXED_POLICY', contract=CONTRACT)
    if lane in BOUNDED and len(bundle['question_slots']) != 1:
        result.update(state='UNSUPPORTED', reason_code='SINGLE_FINITE_POLICY_QUERY_REQUIRED')
    return result


def submit(lane, bundle, candidate, native):
    _exact(lane, native)
    if lane in BOUNDED and set(bundle['question_slots']) != {native['query_id']}:
        raise ValueError('EXACT_CURRENT_FINITE_QUERY_REQUIRED')
    if lane == BOUNDED_POLICY:
        from .bounded_policy import submit as execute
    elif lane == BOUNDED_COMPARISON:
        from .bounded_contrast import submit as execute
    else:
        from .intent_submission import submit as execute
        return execute(bundle, candidate, 'FIXED_COMPARISON' if lane in PAIRED else 'FIXED_POLICY',
                       contract=CONTRACT, **native, synthetic_protocol_selected=True)
    return execute(bundle, candidate, **native, synthetic_protocol_selected=True)


def snapshot(lane, native):
    from .intent_submission import _context_snapshot
    _exact(lane, native)

    def context_record(context):
        # Plain declarations for the reviewer; never reconstructed into objects.
        value = _context_snapshot(context)
        value['inquiries'] = {qid: canonical_data(binding.inquiry)
                              for qid, binding in context.core_port.bindings.items()}
        return value

    value = dict(native)
    value['context'] = ({s: context_record(native['context'][s]) for s in SIDES}
                        if lane in PAIRED else context_record(native['context']))
    return canonical_data(dict(lane=lane, native_submission=value))


def _indexed(rows, expected):
    if type(rows) is not list or len(rows) != len(expected) or {r['query_id'] for r in rows} != set(expected):
        raise ValueError('EXACT_POLICY_RESULT_QUERY_SET_REQUIRED')
    return {row['query_id']: row for row in rows}


def _require(condition):
    if not condition:
        raise ValueError('POLICY_PUBLIC_CLAIM_EVIDENCE_MISMATCH')


def published(lane, native, submission):
    """Recheck public claims against actual reviewed inputs and native verifiers."""
    _exact(lane, submission)
    state = native['state']
    # These native entries report incompatibility diagnostically; they do not
    # supply an infeasibility certificate. Do not invent a certified claim.
    if state == 'INCOMPATIBLE':
        return None, None
    if lane in BOUNDED:
        qid = submission['query_id']
        cert = native['bounded_result']
        _require(state in ('POINT', 'PARTIAL') and cert['status'] == state
                 and native.get('bounded_certificate_replayed') is True)
        if lane == BOUNDED_POLICY:
            from .bounded_policy_verify import replay
            inquiry = submission['context'].core_port.bindings[qid].inquiry
            _require(set(submission['context'].core_port.bindings) == {qid})
            _require(replay(cert, inquiry=inquiry, information=submission['information']) is True)
        else:
            from .bounded_contrast_verify import replay
            _require(all(set(submission['context'][s].core_port.bindings) == {qid} for s in SIDES))
            inquiries = {s: submission['context'][s].core_port.bindings[qid].inquiry for s in SIDES}
            _require(replay(cert, inquiries=inquiries, information=submission['information']) is True)
        view = _indexed(native['query_views'], [qid])[qid]
        result = _indexed(native['identification']['results'], [qid])[qid]
        interval = [cert['lower'], cert['upper']]
        _require(view['state'] == state and result['status'] == state
                 and view['route'] == result['route'] == lane
                 and view.get('bounded_certificate_replayed') is True
                 and result.get('bounded_certificate_replayed') is True
                 and result['bounded_certificate_sha256'] == cert['certificate_sha256']
                 and sha(view['identified_interval']) == sha(interval)
                 and sha(result['identified_interval']) == sha(interval)
                 and view.get('sharp') is True and view.get('informative') is cert['informative'])
        return dict(kind=state, representation='EXACT_IDENTIFIED_INTERVAL', query_id=qid,
            target_sha256=cert['target_sha256'], interval=interval, width=cert['width'],
            sharp=cert['sharp'], informative=cert['informative'], logical_range=deepcopy(cert['logical_range'])), deepcopy(cert)

    from pfn_pipeline.identification_business import identify_network_business_query, replay_verified_business_outcome
    _require(state == 'CORE_POINT')
    contexts = submission['context'] if lane in PAIRED else {'policy': submission['context']}
    ids = set(next(iter(contexts.values())).core_port.bindings)
    _require(bool(ids) and all(set(c.core_port.bindings) == ids for c in contexts.values()))
    views = _indexed(native['query_views'], ids)
    rows = _indexed(native['identification']['results'], ids)
    claims, proofs = [], {}
    for qid, view in views.items():
        _require(view['state'] == 'CORE_POINT' and view.get('certificate_replayed') is True)
        actual = {}
        for side, context in contexts.items():
            outcome = identify_network_business_query(context.core_port.bindings[qid].inquiry)
            _require(outcome.status == 'POINT' and replay_verified_business_outcome(outcome) is True)
            actual[side] = outcome
        if lane == POLICY:
            row = rows[qid]; outcome = actual['policy']
            _require(row['status'] == 'POINT' and row.get('certificate_replay') is True
                     and view['route'] == outcome.route and sha(row['core']) == sha(outcome.summary()))
            proof = row['core']
            expression = proof['identification']['identified_functional']
            fingerprint = proof['identification']['target_fingerprint']
            target = canonical_data(contexts['policy'].core_port.bindings[qid].inquiry.target)
        else:
            from .fixed_comparison import replay
            first = contexts['first'].core_port.bindings[qid].inquiry.target
            second = contexts['second'].core_port.bindings[qid].inquiry.target
            target = dict(node_order=list(first.node_order), first=list(first.policy_assignment),
                          second=list(second.policy_assignment), unit_weights=list(first.unit_weights),
                          operation='first_minus_second')
            review = submission['submission_review']
            binding = dict(query_id=qid, bundle_sha256=review.bundle_sha256,
                           reading_sha256=review.reading_sha256, review_sha256=sha(review))
            proof = view['composition']
            _require(view.get('composition_replayed') is True and view['route'] == 'R1B_ENDPOINT_DIFFERENCE'
                     and sha(rows[qid]) == sha(view)
                     and replay(proof, actual['first'], actual['second'], target=target, binding=binding) is True)
            for side in SIDES:
                endpoint = view['endpoints'][side]
                _require(endpoint['state'] == 'CORE_POINT' and endpoint.get('certificate_replayed') is True
                         and sha(endpoint['core']) == sha(actual[side].summary()))
            expression = proof['identified_functional']
            fingerprint = sha(target)
        claims.append(dict(query_id=qid, route=view['route'], target_coordinates=target,
            functionals=[dict(target_fingerprint=fingerprint, expression=expression)]))
        proofs[qid] = deepcopy(proof)
    return dict(kind='POINT', representation='PER_QUERY_OBSERVED_FUNCTIONALS', queries=claims), proofs


def review_rows(lane, bundle, view, native, add):
    """Expand the actual typed declarations, not a route-independent assumption list."""
    _exact(lane, native)
    contexts = native['context'] if lane in PAIRED else {'policy': native['context']}
    qids = set(bundle['question_slots'])
    if lane in BOUNDED and qids != {native['query_id']}:
        raise ValueError('EXACT_CURRENT_FINITE_QUERY_REQUIRED')
    if any(set(c['bindings']) != qids or set(c['inquiries']) != qids for c in contexts.values()):
        raise ValueError('EXACT_POLICY_REVIEW_SCOPE_REQUIRED')
    targets = view['proposed_comparisons'] if lane in PAIRED else view['proposed_targets']
    if set(targets) != qids:
        raise ValueError('COMPLETE_POLICY_TARGETS_REQUIRED')
    for qid in sorted(qids):
        add(qid + '/target', 'A1_A3', qid + ('：甲减乙、共同评价人群与权重' if lane in PAIRED else '：固定名单、评价人群与权重'),
            targets[qid], dict(question=bundle['question_slots'][qid], question_binding=view['question_binding']))
    labels = {'known_assignment_law': '已知分配律', 'full_vector_randomization': '整个分配向量的随机化',
              'consistency': '一致性', 'fixed_pretreatment_network': '处理前固定网络',
              'finite_conditional_first_moments': '有限条件一阶矩'}
    for side, context in contexts.items():
        for qid in sorted(qids):
            prefix = qid + '/' + side
            inquiry = context['inquiries'][qid]
            bound = context['bindings'][qid]
            add(prefix + '/study', 'A1_A3', qid + ' ' + side + '：原试点、网络及数学目标',
                dict(study=inquiry['study'], target=inquiry['target'], signature=inquiry['r2_signature']),
                dict(business_intent=bound['business_intent'], assignment_review=native['assignment_review']))
            for index, source in enumerate(inquiry['r1b_sources'] + inquiry['r2_sources']):
                add(prefix + f'/source/{index}', 'A4', side + '：总体信息算子与声明范围', source,
                    dict(evidence_manifest=bound['evidence_manifest']))
            for index, condition in enumerate(inquiry['assumptions']):
                add(prefix + f'/condition/{index}', 'A5', side + '：' + labels.get(condition['name'], condition['name']),
                    condition, dict(study=inquiry['study'], admission=bound['admission']))
            if inquiry['r2_sufficiency'] is not None:
                add(prefix + '/mean_sufficiency', 'A5', side + '：均值充分性及覆盖对象（需独立审核）',
                    inquiry['r2_sufficiency'], dict(signature=inquiry['r2_signature'], admission=bound['admission']))
        if lane in BOUNDED:
            info = native['information'][side] if lane in PAIRED else native['information']
            add(side + '/information_scope', 'A4', side + '：全部精确总体均值、来源与模型范围',
                {k: v for k, v in info.items() if k not in ('values', 'bounds')})
            for index, value in enumerate(info['values']):
                add(side + f'/mean/{index}', 'A4', side + ' ' + value['node'] + '：总体均值单元', value,
                    dict(source_id=info['source_id'], provenance=info['a4_provenance']))
            for index, bound in enumerate(info['bounds']):
                add(side + f'/bound/{index}', 'A5', side + ' ' + bound['node'] + '：结果界限与适用层次',
                    dict(bound=bound, **{k: info[k] for k in ('bounds_kind', 'bounds_scope', 'outcome_definition',
                                                           'outcome_unit', 'outcome_period')}),
                    dict(provenance=info['bounds_provenance']))
    if lane == BOUNDED_COMPARISON:
        add('joint_model', 'A4', '两个政策共享同一完整均值模型，保留共同未知量',
            dict(information=native['information'], targets=targets), dict(joint_review=native['joint_review']))
    add('native_review_scope', 'REVIEW_SCOPE', '原生审核范围、目标绑定及未增加其他约束',
        dict(lane=lane, synthetic_only=True, mathematical_approval=False),
        {k: v for k, v in native.items() if k.endswith('review')})
