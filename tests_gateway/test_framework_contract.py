"""Shared lifecycle obligations for every explicitly registered session lane.

Fixtures stipulate synthetic reviews. They are never business approval policies.
Each lane gets a separate pytest node, so acceptance can detect missing coverage.
"""
from copy import deepcopy
from functools import partial
import json
from unittest.mock import patch

import pytest

from cfm_id import research_session as work, session_routes as routes, review_items
from cfm_id_bridge.scientific_binding import sha
from examples.research_item_review_reference import (
    approve_items, decide, network, mean_order, backdoor, adjustment, dag,
)
from examples.research_policy_session_reference import policy, comparison, contrast


CASES = {
    'NETWORK_D1_EFFECTS': (network, 'POINT'),
    'MEAN_ORDER_D2_E1': (mean_order, 'PARTIAL'),
    'DAG_CLASSICAL_BACKDOOR': (backdoor, 'POINT'),
    'DAG_ADJUSTMENT': (adjustment, 'POINT'),
    'DAG_CLASSICAL_FRONTDOOR': (dag, 'POINT'),
    'NETWORK_FIXED_POLICY': (policy, 'POINT'),
    'NETWORK_FIXED_COMPARISON': (comparison, 'POINT'),
    'BOUNDED_POLICY_MEAN_D2_E1': (partial(policy, 'star7', bounded=True), 'PARTIAL'),
    'BOUNDED_POLICY_CONTRAST_D2_E1': (contrast, 'PARTIAL'),
}


@pytest.fixture(params=tuple(CASES), ids=tuple(CASES))
def case(request):
    factory, expected = CASES[request.param]
    lane, bundle, candidate, native = factory()
    assert lane == request.param
    return lane, bundle, candidate, native, expected


def opened(case):
    lane, bundle, candidate, native, _ = case
    s = work.receive_candidate(work.start(lane, bundle), candidate)
    return work.begin_item_review(s, native_submission=native)


def execute(s, native=None):
    return work.execute(s, native_submission=native, research_protocol_selected=True)


def stopped(result, state):
    assert result['state'] == state
    assert result['mathematical_claim'] is None
    assert result['certificate'] is None
    assert result['independent_replay'] is False
    assert result['backend_called'] is False
    assert result['production_admission'] is False
    assert result['estimation_handoff_allowed'] is False


def test_every_registered_lane_has_explicit_acceptance():
    assert len(routes.LANES) == len(set(routes.LANES))
    assert set(CASES) == set(routes.LANES)


def test_reading_and_pending_review_cannot_execute(case):
    lane, bundle, _, native, _ = case
    s = work.start(lane, bundle)
    original = work.prepare_request(s)
    with patch.object(routes, 'submit', side_effect=AssertionError('premature execution')):
        stopped(execute(s, native), 'READING_REQUIRED')
        s = opened(case)
        stopped(execute(s, native), 'REVIEW_REQUIRED')
    assert set(review_items.decisions(s.item_review).values()) == {'PENDING'}
    assert work.prepare_request(approve_items(s)) == original == routes.request(lane, bundle)


def test_restore_requires_native_context_and_fresh_proof(case, tmp_path):
    _, _, _, native, expected = case
    s = approve_items(opened(case))
    work.save(s, tmp_path / 'session.json')
    restored = work.restore(tmp_path / 'session.json')
    with patch.object(routes, 'submit', side_effect=AssertionError('context required')):
        stopped(execute(restored), 'REVIEW_REQUIRED')
    with patch.object(routes, 'submit', wraps=routes.submit) as submit:
        result = execute(restored, native)
    submit.assert_called_once()
    assert result['state'] == expected
    assert result['mathematical_claim'] is not None and result['certificate'] is not None
    assert result['independent_replay'] is True
    assert result['production_admission'] is False
    assert result['estimation_handoff_allowed'] is False


def test_withdraw_reject_and_reaccept_require_new_finalization(case):
    native = case[3]
    s = approve_items(opened(case))
    row = next(i for i in s.item_review.items if i.category == 'A5')
    with patch.object(routes, 'submit', side_effect=AssertionError('review not complete')):
        for decision, state in [('WITHDRAWN', 'REVIEW_REQUIRED'), ('PENDING', 'REVIEW_REQUIRED'),
                                ('REJECTED', 'CHECK_BLOCKED'), ('ACCEPTED', 'REVIEW_REQUIRED')]:
            changed = decide(s, row.item_id, decision)
            assert changed.review is None
            stopped(execute(changed, native), state)


def test_material_and_candidate_changes_invalidate_approval(case):
    native = case[3]
    s = approve_items(opened(case))
    replaced = work.receive_candidate(s, s.candidate)
    bundle = deepcopy(s.bundle)
    bundle['documents']['framework_followup.txt'] = '研究时期发生变更，需重新核对目标和条件。'
    revised = work.revise_materials(s, bundle, reason='New study period needs independent review')
    with patch.object(routes, 'submit', side_effect=AssertionError('stale review')):
        for changed, state in [(replaced, 'REVIEW_REQUIRED'), (revised, 'READING_REQUIRED')]:
            assert changed.review is None and changed.item_review is None
            stopped(execute(changed, native), state)
            with pytest.raises(ValueError):
                work.record_review(changed, s.review)


def test_changed_native_review_cannot_reuse_approval(case):
    native = case[3]
    s = approve_items(opened(case))
    changed = dict(native)
    key = next(k for k in ('submission_review', 'review', 'science_review', 'joint_review') if k in native)
    changed[key] = native[key].model_copy(update={'evidence': 'Revised independent review rationale; prior binding is stale.'})
    with patch.object(routes, 'submit', side_effect=AssertionError('stale native binding')):
        stopped(execute(s, changed), 'CHECK_BLOCKED')


def test_missing_target_followup_preserves_uncertainty(case):
    lane, bundle, candidate, native, _ = case
    candidate = deepcopy(candidate)
    if lane in routes.DAG:
        candidate['target']['treatment'] = None
    else:
        reading = (candidate['comparison']['reading'] if lane == routes.MEAN_ORDER else
                   candidate if lane == routes.NETWORK else candidate['reading'])
        for row in reading['questions'].values():
            row['population'] = {'selection': '不明确', 'ids': []} if lane == routes.NETWORK else None
    s = work.receive_candidate(work.start(lane, bundle), candidate)
    with patch.object(routes, 'submit', side_effect=AssertionError('target missing')):
        stopped(execute(s, native), 'NEEDS_INPUT')
    plan = work.clarification_plan(s)
    assert plan['basis'] == 'CURRENT_READING_NOT_PROVEN_SOURCE_ABSENCE'
    assert plan['questions'] and plan['scientific_approval'] is False
    changed = work.append_reply(s, plan, plan['questions'][0]['clarification_id'], '此项尚未决定。')
    assert all(changed.bundle['documents'][k] == v for k, v in bundle['documents'].items())
    assert any('此项尚未决定。' in t for t in changed.bundle['documents'].values())
    assert changed.candidate is None and changed.review is None and changed.item_review is None
    stopped(execute(changed, native), 'READING_REQUIRED')


def test_rehashed_checkpoint_cannot_drop_review_item(case, tmp_path):
    s = approve_items(opened(case))
    work.save(s, tmp_path / 'session.json')
    checkpoint = work.read_json(tmp_path / 'session.json')
    checkpoint['payload']['item_review']['items'].pop()
    checkpoint['sha256'] = sha(checkpoint['payload'])
    work.write_json(tmp_path / 'forged.json', checkpoint)
    with pytest.raises(ValueError):
        work.restore(tmp_path / 'forged.json')


def test_d1_replies_remain_citable_without_creating_new_questions():
    from cfm_id.session_materials import append_target_reply
    from evaluation.business_materials_base import bundle_value
    lane, bundle, candidate, native = network()
    changed = bundle
    for index, reply in enumerate(('评价全体。也要评价单个对象吗？', '此项尚未决定？请保留未知。')):
        changed = append_target_reply(changed, 'q1', f'reply_{index}.txt', reply)
        assert changed['question_slots'] == bundle['question_slots']
        assert all(changed['documents'][k] == v for k, v in bundle['documents'].items())
        assert bundle_value(changed) == changed
        s = work.start(lane, changed)
        request = work.prepare_request(s)
        message = json.loads(request['user'])
        active = changed['active_goal_document']
        assert reply in message['documents'][active]
        assert any(key.startswith(active + ':') and value == reply
                   for key, value in message['source_catalog'].items())
        # The source restriction stays unchanged: current active document only.
        shape = message['output_schema']['$defs']['Question']['properties']['population_source']
        allowed = shape['anyOf'][0]['enum']
        assert any(message['source_catalog'][key] == reply for key in allowed)
        stopped(execute(s, native), 'READING_REQUIRED')
        old_candidate = work.receive_candidate(s, candidate)
        assert execute(old_candidate, native)['mathematical_claim'] is None


def test_d1_reply_chain_cannot_hide_edits_or_change_question_index():
    from cfm_id.session_materials import append_target_reply
    from evaluation.business_materials_base import bundle_value
    _, bundle, _, _ = network()
    ready = append_target_reply(bundle, 'q1', 'reply.txt', '评价范围尚未决定。')
    for mutation in ('active_text', 'reply_text', 'parent', 'target', 'record_deleted'):
        changed = deepcopy(ready)
        if mutation == 'active_text':
            changed['documents'][changed['active_goal_document']] += '\n未经记录的目标变更。'
        elif mutation == 'reply_text':
            changed['documents']['reply.txt'] = '评价全体。'
        elif mutation == 'parent':
            changed['question_clarifications'][0]['parent_active_goal_document'] = 'reply.txt'
        elif mutation == 'target':
            changed['question_slots']['q1'] = '另一个不同的问题？'
        else:
            changed['question_clarifications'] = []
            # Deleting metadata is rejected when the active supplement contains a question.
            changed['documents'][changed['active_goal_document']] += '\n是否改为单个对象？'
        with pytest.raises(ValueError):
            bundle_value(changed)


def test_mixed_query_state_keeps_ready_question_unsubmitted():
    lane, bundle, candidate, native = comparison()
    candidate['reading']['questions']['q1']['population'] = None
    s = work.receive_candidate(work.start(lane, bundle), candidate)
    with patch.object(routes, 'submit', side_effect=AssertionError('no silent query selection')):
        stopped(execute(s, native), 'MIXED')
    assert work.clarification_plan(s)['questions']


def test_d1_followup_names_the_question_and_preserves_other_targets():
    from cfm_id.business_entry import goal_variant
    from cfm_id.session_materials import append_target_reply
    from evaluation.business_materials_base import bundle_value
    _, bundle, _, _ = network()
    bundle = goal_variant(bundle, '所有站点使用后的平均延误是多少？\n只让甲站使用后的平均延误是多少？')
    changed = append_target_reply(bundle, 'q2', 'second_reply.txt', '第二问评价全体站点。')
    assert bundle_value(changed) == changed
    assert changed['question_slots'] == bundle['question_slots']
    assert '针对业务问题 q2：' + bundle['question_slots']['q2'] in changed['documents']['second_reply.txt']
    assert '第二问评价全体站点。' in changed['documents'][changed['active_goal_document']]
