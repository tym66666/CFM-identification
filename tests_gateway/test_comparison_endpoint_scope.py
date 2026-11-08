"""Bound comparison endpoints retain full text and every scientific gate."""
from copy import deepcopy
import unittest
from unittest.mock import patch

import cfm_id_bridge.bridge as bridge
from cfm_id_llm.candidate_queries import CandidateSafetyError
from cfm_id_llm.trusted_core import RealCoreCoveragePortV012, _conservative_target_match
from cfm_id import bounded_contrast as entry
from cfm_id.intent_submission import _context_snapshot
from cfm_id.question_bound_assignment import question_catalog
from examples.bounded_contrast_fixture import make_case, reviews
from examples.partial_contrast_reference import joint_review, vertex_reference
from examples import fixed_comparison_fixture as fixed
from cfm_id import fixed_comparison


def payload(reverse=False):
    nodes = list('ABCD')
    first, second = ([0]*4, [1]*4) if reverse else ([1]*4, [0]*4)
    p = make_case(nodes, list(zip(nodes[:-1], nodes[1:])), 2,
                  first, second, nodes, serial=88)
    goal = ('问题1：方案甲是所有小组全部使用辅助系统；方案乙是所有小组都不用辅助系统。'
            '只评价A、B、C、D，各小组权重相同。'
            + ('从方案甲改为方案乙，按时完成任务的比例平均会增加多少？' if reverse
               else '甲相比乙，按时完成任务的比例平均会高多少？'))
    p['bundle']['documents']['goal.txt'] = goal
    p['bundle']['question_slots']['q1'] = goal
    p['raw']['reading']['intents']['q1']['question_id'] = question_catalog(p['bundle'])['q1']['question_id']
    return p


def lookup(context):
    return context.core_port.lookup(case=context.case, quality=context.quality,
                                    review=context.business_review, query_id='q1')


class ComparisonEndpointScopeTests(unittest.TestCase):
    def test_complete_comparison_all_treated_wording_both_directions(self):
        for reverse in (False, True):
            with self.subTest(reverse=reverse):
                p = payload(reverse); r = reviews(p); j = joint_review(p, r)
                original = deepcopy(p['raw'])
                out = entry.submit(p['bundle'], p['raw'], query_id='q1',
                    information=p['information'], joint_review=j, **r)
                self.assertEqual(out['state'], 'PARTIAL')
                self.assertTrue(out['bounded_certificate_replayed'])
                self.assertEqual(p['raw'], original)
                from fractions import Fraction
                self.assertEqual(tuple(Fraction(out['bounded_result'][k]) for k in ('lower','upper')),
                                 vertex_reference(p))
                for c in r['context'].values():
                    query = c.quality.draft.queries[0]
                    self.assertEqual(query.business_goal.value, p['bundle']['question_slots']['q1'])
                    self.assertEqual(query.target.description.value, query.business_goal.value)
                    self.assertEqual(len(c.core_port.calls), 1)

    def test_single_policy_guard_and_unscoped_port_still_block(self):
        p = payload(); r = reviews(p); c = r['context']['second']
        query = c.quality.draft.queries[0]
        with self.assertRaisesRegex(CandidateSafetyError, 'All-treated'):
            _conservative_target_match(query, dict(classification='FIXED_POLICY',
                node_order=list('ABCD'), assignment=[0]*4))
        unscoped = RealCoreCoveragePortV012(bindings=c.core_port.bindings,
                                          crosswalks=c.core_port.crosswalks)
        with self.assertRaisesRegex(CandidateSafetyError, 'All-treated'):
            unscoped.lookup(case=c.case, quality=c.quality, review=c.business_review, query_id='q1')
        self.assertEqual(unscoped.calls, [])

    def test_source_is_frozen_from_caller_and_snapshot_owns_its_copy(self):
        p = payload(); r = reviews(p); c = r['context']['first']
        stored = deepcopy(c.core_port.comparison_endpoint_sources)
        p['raw']['reading']['questions']['q1']['first']['A'] = 0
        self.assertEqual(c.core_port.comparison_endpoint_sources, stored)
        snap = _context_snapshot(c)
        snap['comparison_endpoint_sources']['q1']['side'] = 'second'
        self.assertEqual(c.core_port.comparison_endpoint_sources, stored)

    def test_empty_scope_preserves_historical_context_snapshot_shape(self):
        p = payload(); c = reviews(p)['context']['first']
        c.core_port.comparison_endpoint_sources = {}
        self.assertEqual(set(_context_snapshot(c)),
            {'case','quality','review','approval','bindings','crosswalks'})

    def test_changed_side_or_source_rejected_before_core(self):
        for mutation in ('side','source_text','query_id','raw_target','population','source_missing'):
            with self.subTest(mutation=mutation):
                p = payload(); c = reviews(p)['context']['first']
                src = c.core_port.comparison_endpoint_sources['q1']
                if mutation == 'side': src['side'] = 'second'
                elif mutation == 'source_text': src['bundle']['documents']['study.txt'] += '另一个来源'
                elif mutation == 'query_id': src['query_id'] = 'q2'
                elif mutation == 'raw_target': src['raw']['reading']['questions']['q1']['first']['A'] = 0
                elif mutation == 'population': src['raw']['reading']['questions']['q1']['population'] = ['A']
                else: del src['raw']
                with patch.object(bridge, 'run_verified_multiquery_v29') as core:
                    with self.assertRaisesRegex(CandidateSafetyError, 'Bound comparison endpoint'):
                        lookup(c)
                    core.assert_not_called()
                self.assertEqual(c.core_port.calls, [])

    def test_noncomparison_reading_is_not_a_bypass_flag(self):
        p = payload(); c = reviews(p)['context']['first']
        src = c.core_port.comparison_endpoint_sources['q1']
        src['raw']['reading']['intents']['q1']['kind'] = '水平'
        with patch.object(bridge, 'run_verified_multiquery_v29') as core:
            with self.assertRaises(CandidateSafetyError): lookup(c)
            core.assert_not_called()

    def test_endpoint_scope_does_not_bypass_missing_scientific_review(self):
        from dataclasses import replace
        p = payload(); r = reviews(p); c = r['context']['second']
        b = c.core_port.bindings['q1']
        c.core_port.bindings['q1'] = replace(b, admission=b.admission.model_copy(
            update={'approved_scientific_binding':None}))
        j = joint_review(p, r)
        out = entry.submit(p['bundle'],p['raw'],query_id='q1',
            information=p['information'],joint_review=j,**r)
        self.assertEqual(out['state'],'CHECK_BLOCKED')
        self.assertFalse(out['bounded_backend_called'])
        self.assertNotIn('bounded_result',out)

    def test_source_change_invalidates_existing_joint_review(self):
        p = payload(); r = reviews(p); j = joint_review(p, r)
        r['context']['first'].core_port.comparison_endpoint_sources['q1']['side'] = 'second'
        with patch.object(bridge, 'run_verified_multiquery_v29') as core:
            out = entry.submit(p['bundle'],p['raw'],query_id='q1',
                information=p['information'],joint_review=j,**r)
            core.assert_not_called()
        self.assertEqual(out['state'],'CHECK_BLOCKED')
        self.assertEqual(out['reason_code'],'CONTRAST_REVIEW_STALE')
        self.assertFalse(out['bounded_backend_called'])

    def test_missing_conditions_in_scope_rejected_at_lookup(self):
        for field in ('second','population'):
            p = payload(); c = reviews(p)['context']['first']
            q = c.core_port.comparison_endpoint_sources['q1']['raw']['reading']['questions']['q1']
            if field == 'second': q[field]['D'] = None
            else: q[field] = None
            with patch.object(bridge, 'run_verified_multiquery_v29') as core:
                with self.assertRaises(CandidateSafetyError): lookup(c)
                core.assert_not_called()

    def test_missing_conditions_in_actual_reading_remain_blocked_without_core(self):
        for field in ('second','population'):
            p = payload()
            q = p['raw']['reading']['questions']['q1']
            if field == 'second': q[field]['D'] = None
            else: q[field] = None
            with patch.object(bridge, 'run_verified_multiquery_v29') as core:
                out = entry.submit(p['bundle'],p['raw'],query_id='q1')
                core.assert_not_called()
            self.assertEqual(out['state'],'NEEDS_INPUT')
            self.assertFalse(out['core_called'])
            self.assertFalse(out['bounded_backend_called'])
            self.assertNotIn('bounded_result',out)
            self.assertNotIn('identification',out)

    def test_existing_point_comparison_uses_structural_endpoint_sources(self):
        b = fixed.public_bundle(only=['q1'])
        raw = fixed.reference(b); r = fixed.reviews(b,raw)
        self.assertEqual(set(r['context']['first'].core_port.comparison_endpoint_sources),{'q1'})
        out = fixed_comparison.submit(b,raw,**r)
        self.assertEqual(out['query_views'][0]['state'],'CORE_POINT')
        self.assertTrue(out['query_views'][0]['composition_replayed'])

    def test_constructor_rejects_unbound_query_and_nonmapping_source(self):
        p = payload(); c = reviews(p)['context']['first']
        for src in ({'q2':{}}, []):
            with self.assertRaises(CandidateSafetyError):
                RealCoreCoveragePortV012(bindings=c.core_port.bindings,
                    crosswalks=c.core_port.crosswalks,comparison_endpoint_sources=src)


if __name__ == '__main__':
    unittest.main()
