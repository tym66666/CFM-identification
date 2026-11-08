"""Same-target condition versions: independent native replay and inclusion gates."""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import unittest
from cfm_id import research_session as work, research_versions as versions, session_routes as routes
from cfm_id.research_session_cli import main as cli
from cfm_id_bridge.scientific_binding import sha
from examples.research_condition_versions_reference import reviewed, policy_bounds
from examples.research_policy_session_reference import contrast, policy
from examples.research_session_reference import mean_order, dag
from examples.research_item_review_reference import approve_items, decide
from examples.partial_contrast_reference import ladder_payloads, set_common_information


class VersionTests(unittest.TestCase):
    def pair(self, first=None, second=None):
        first=first or (lambda:policy_bounds('1/2','1/2'))
        second=second or (lambda:policy_bounds('0','1'))
        a,an=reviewed(first)
        b,bn=reviewed(second,parent=a,label='Changed scientific conditions')
        return a,an,b,bn

    def plan(self,a,an,b,bn):
        return versions.plan_comparison(a,b,before_submission=an,after_submission=bn)

    def run_pair(self,a,an,b,bn,plan=None,selected=True):
        return versions.compare_versions(a,b,plan=self.plan(a,an,b,bn) if plan is None else plan,
            before_submission=an,after_submission=bn,research_protocol_selected=selected)

    def test_fork_preserves_parent_clears_all_approvals_and_keeps_identical_reading(self):
        a,an=reviewed(lambda:policy_bounds('1/2','1/2'))
        original=deepcopy(a.model_dump())
        b=versions.fork_version(a,label='Wider bounds',reason='Explicit alternative condition version')
        self.assertEqual(a.model_dump(),original)
        self.assertNotEqual(a.session_id,b.session_id)
        self.assertEqual(a.bundle,b.bundle)
        self.assertEqual(a.candidate,b.candidate)
        self.assertIsNone(b.review)
        self.assertIsNone(b.item_review)
        self.assertTrue(b.history[-1]['reading_reused_from_identical_request'])
        self.assertEqual(b.history[-1]['parent_checkpoint_sha256'],sha(a.model_dump()))
        self.assertFalse(b.history[-1]['approvals_inherited'])
        with self.assertRaisesRegex(ValueError,'STALE_SESSION_REVIEW'):
            work.record_review(b,a.review)
        self.assertFalse(work.execute(b,native_submission=an,research_protocol_selected=True)['backend_called'])

    def test_changed_public_condition_document_requires_fresh_reading(self):
        a,an=reviewed(lambda:mean_order(mode='BOTH'))
        _,bundle,candidate,native=mean_order(mode='NONE')
        b=versions.fork_version(a,label='No order restrictions',reason='Remove separately stated mean orders',bundle=bundle)
        self.assertIsNone(b.candidate)
        self.assertFalse(b.history[-1]['reading_reused_from_identical_request'])
        self.assertEqual(work.inspect(b)['state'],'READING_REQUIRED')
        self.assertIsNone(b.review)
        b=work.receive_candidate(b,candidate)
        self.assertEqual(work.inspect(b)['state'],'REVIEW_REQUIRED')

    def test_fork_requires_explicit_label_and_reason(self):
        a,_=reviewed(policy)
        for label,reason in [('', 'Meaningful change'),('A', ' '),(None,'Meaningful change')]:
            with self.subTest(label=label),self.assertRaises(ValueError):
                versions.fork_version(a,label=label,reason=reason)

    def test_bound_ladder_point_partial_logical_range_with_fresh_replay(self):
        payloads=ladder_payloads()
        expected=[['0','0'],['-1/2','1/2'],['-1','1']]
        a,an=reviewed(lambda:contrast(payload=payloads[0]))
        for i in (1,2):
            b,bn=reviewed(lambda:contrast(payload=payloads[i]),parent=a,label='Bounds version '+str(i))
            report=self.run_pair(a,an,b,bn)
            self.assertEqual(report['state'],'COMPARED')
            self.assertEqual(report['conclusion']['model_inclusion'],'BEFORE_SUBSET_OF_AFTER')
            self.assertEqual(report['conclusion']['before_interval'],expected[i-1])
            self.assertEqual(report['conclusion']['after_interval'],expected[i])
            self.assertTrue(report['both_results_independently_replayed'])
            self.assertEqual(report['results']['after']['state'],'PARTIAL')
            if i==2:
                self.assertFalse(report['results']['after']['mathematical_claim']['informative'])
            a,an=b,bn

    def test_single_policy_wider_bounds_and_reverse_strengthening(self):
        a,an,b,bn=self.pair()
        forward=self.run_pair(a,an,b,bn)
        backward=self.run_pair(b,bn,a,an)
        self.assertEqual(forward['conclusion']['before_interval'],['1/2','1/2'])
        self.assertEqual(forward['conclusion']['after_interval'],['3/7','4/7'])
        self.assertEqual(backward['conclusion']['declaration_relation'],'STRENGTHENING')
        self.assertEqual(backward['conclusion']['model_inclusion'],'AFTER_SUBSET_OF_BEFORE')
        self.assertTrue(backward['conclusion']['after_interval_subset_of_before'])

    def test_mean_order_deletion_uses_declared_axes_and_all_arrangement_scope(self):
        a,an,b,bn=self.pair(lambda:mean_order(mode='BOTH'),lambda:mean_order(mode='OWN'))
        plan=self.plan(a,an,b,bn)
        self.assertEqual(plan['relation'],'WEAKENING')
        self.assertEqual(plan['removed_orders'],[[n,'PEERS'] for n in 'ABCD'])
        self.assertEqual(plan['added_orders'],[])
        report=self.run_pair(a,an,b,bn,plan)
        self.assertEqual(report['conclusion']['before_interval'],['1/5','1'])
        self.assertEqual(report['conclusion']['after_interval'],['-1/5','1'])

    def test_removing_redundant_orders_need_not_expand_identified_set(self):
        a,an,b,bn=self.pair(lambda:mean_order(mode='BOTH',edges=[]),lambda:mean_order(mode='NONE',edges=[]))
        report=self.run_pair(a,an,b,bn)
        self.assertEqual(report['conclusion']['declaration_relation'],'WEAKENING')
        self.assertTrue(report['conclusion']['intervals_equal'])
        self.assertFalse(report['conclusion']['strict_model_inclusion_claimed'])
        self.assertEqual(report['results']['after']['state'],'POINT')

    def test_non_nested_bound_change_preserves_results_without_inclusion_claim(self):
        a,an,b,bn=self.pair(lambda:policy_bounds('1/4','3/4'),lambda:policy_bounds('1/10','3/5'))
        report=self.run_pair(a,an,b,bn)
        self.assertEqual(report['state'],'COMPARED_UNORDERED')
        self.assertFalse(report['conclusion']['model_inclusion_checked'])
        self.assertIsNone(report['conclusion']['model_inclusion'])
        self.assertTrue(report['both_results_independently_replayed'])

    def test_swapping_order_axes_is_not_a_weakening_even_if_intervals_are_nested(self):
        a,an,b,bn=self.pair(lambda:mean_order(mode='OWN'),lambda:mean_order(mode='PEERS'))
        report=self.run_pair(a,an,b,bn)
        self.assertEqual(report['state'],'COMPARED_UNORDERED')
        self.assertIsNone(report['conclusion']['model_inclusion'])
        self.assertTrue(report['conclusion']['after_interval_subset_of_before'])

    def test_unchanged_constraints_equal_sets_despite_new_reviewer_provenance(self):
        payloads=ladder_payloads()
        changed=deepcopy(payloads[1])
        for side in ('first','second'):
            info=changed['information'][side]
            changed['information'][side]=info.model_copy(update={'bounds_provenance':'Same mathematical bounds independently documented again.'})
        a,an,b,bn=self.pair(lambda:contrast(payload=payloads[1]),lambda:contrast(payload=changed))
        report=self.run_pair(a,an,b,bn)
        self.assertEqual(report['conclusion']['declaration_relation'],'SAME_DECLARED_CONSTRAINTS')
        self.assertTrue(report['conclusion']['intervals_equal'])

    def test_a4_value_change_is_not_assumption_weakening(self):
        base=ladder_payloads()[1]
        changed=deepcopy(base)
        row=changed['information']['first'].values[0]
        set_common_information(changed,values={(row.node,row.own,row.exposure):'1/3'})
        a,an,b,bn=self.pair(lambda:contrast(payload=base),lambda:contrast(payload=changed))
        with patch.object(routes,'submit',side_effect=AssertionError('not comparable')):
            report=self.run_pair(a,an,b,bn)
        self.assertEqual(report['state'],'NOT_COMPARABLE')
        self.assertEqual(report['reason_code'],'A4_OR_FIXED_MODEL_CHANGED')
        self.assertIsNone(report['conclusion'])

    def test_bound_semantic_level_change_is_not_automatically_compared(self):
        a,an,b,bn=self.pair(lambda:policy('star7',bounded=True),lambda:policy_bounds('0','1'))
        report=self.run_pair(a,an,b,bn)
        self.assertEqual(report['state'],'NOT_COMPARABLE')
        self.assertEqual(report['reason_code'],'BOUND_SEMANTIC_LEVEL_CHANGED')
        self.assertFalse(report['backend_called'])

    def test_changed_graph_or_outcome_period_is_not_a_condition_deletion(self):
        a,an,b,bn=self.pair(lambda:mean_order(mode='BOTH'),lambda:mean_order(mode='BOTH',edges=[]))
        report=self.run_pair(a,an,b,bn)
        self.assertEqual(report['state'],'NOT_COMPARABLE')
        self.assertEqual(report['reason_code'],'A4_OR_FIXED_MODEL_CHANGED')
        # Test outcome units/period on validated descriptors; do not create a fake approval.
        desc=versions._describe(a,an)
        other=deepcopy(desc)
        other['target']['outcome_period']='another week'
        self.assertEqual(versions._relation(desc,other)['reason_code'],'MATHEMATICAL_TARGET_CHANGED')

    def test_changed_evaluation_population_direction_or_weights_is_not_same_target(self):
        a,an,b,bn=self.pair()
        description=versions._describe(a,an)
        for field,value in [('policy_assignment',[0]*7),('unit_weights',['1']+['0']*6),('context','another context')]:
            with self.subTest(field=field):
                changed=deepcopy(description)
                changed['target'][field]=value
                self.assertEqual(versions._relation(description,changed)['reason_code'],'MATHEMATICAL_TARGET_CHANGED')
        # Actual distinct populations are stopped before either backend is invoked.
        _,_,c,cn=self.pair(lambda:policy_bounds('0','1'),lambda:policy('star7',bounded=True,population=['H']))
        self.assertEqual(self.run_pair(a,an,c,cn)['state'],'NOT_COMPARABLE')

    def test_changed_question_text_is_reported_as_not_comparable(self):
        a,an=reviewed(lambda:policy_bounds('0','1'))
        bundle=deepcopy(a.bundle)
        bundle['question_slots']['q1'] += ' 请同时讨论成本。'
        bundle['documents']['goal.txt']=bundle['question_slots']['q1']
        b=versions.fork_version(a,label='Different question',reason='New business task',bundle=bundle)
        report=self.run_pair(a,an,b,an)
        self.assertEqual(report['reason_code'],'BUSINESS_QUESTION_CHANGED')
        self.assertFalse(report['backend_called'])

    def test_unadapted_and_cross_route_relations_do_not_guess_inclusion(self):
        a,an=reviewed(dag)
        b,bn=reviewed(dag,parent=a,label='DAG branch')
        report=self.run_pair(a,an,b,bn)
        self.assertEqual(report['reason_code'],'CONDITION_COMPARISON_NOT_ADAPTED')
        c,cn=reviewed(lambda:policy_bounds('0','1'))
        self.assertEqual(self.run_pair(a,an,c,cn)['reason_code'],'CROSS_ROUTE_RELATION_NOT_ADAPTED')

    def test_identical_session_cannot_masquerade_as_two_versions(self):
        a,an=reviewed(lambda:policy_bounds('0','1'))
        with self.assertRaisesRegex(ValueError,'DISTINCT_CONDITION_VERSION'):
            self.plan(a,an,a,an)

    def test_no_execution_from_plan_or_without_explicit_selection(self):
        a,an,b,bn=self.pair()
        with patch.object(routes,'submit',side_effect=AssertionError('no implicit execution')):
            plan=self.plan(a,an,b,bn)
            self.assertFalse(plan['backend_called'])
            self.assertFalse(plan['scientific_approval'])
            for selected in (False,1,'true',None):
                result=self.run_pair(a,an,b,bn,plan,selected)
                self.assertEqual(result['state'],'REVIEW_REQUIRED')
                self.assertFalse(result['backend_called'])

    def test_modified_rehashed_or_stale_plan_is_rejected(self):
        a,an,b,bn=self.pair()
        plan=self.plan(a,an,b,bn)
        changed=deepcopy(plan)
        changed['relation']='STRENGTHENING'
        changed.pop('plan_sha256')
        changed['plan_sha256']=sha(changed)
        with self.assertRaisesRegex(ValueError,'STALE_OR_CHANGED'):
            self.run_pair(a,an,b,bn,changed)
        item=b.item_review.items[0]
        new=decide(b,item.item_id,'WITHDRAWN')
        with self.assertRaisesRegex(ValueError,'STALE_OR_CHANGED'):
            self.run_pair(a,an,new,bn,plan)
        with patch.object(routes,'submit',side_effect=AssertionError('approval was withdrawn')):
            report=self.run_pair(a,an,new,bn)
        self.assertEqual(report['state'],'REVIEW_REQUIRED')

    def test_missing_fresh_item_review_or_rejected_native_review_blocks_comparison(self):
        a,an,b,bn=self.pair()
        child=versions.fork_version(a,label='Pending version',reason='Conditions still need review')
        self.assertEqual(self.run_pair(a,an,child,bn)['state'],'REVIEW_REQUIRED')
        # Same declarations but a missing native bounded review cannot be replaced by outer acceptances.
        bn['bounded_review']=None
        b=approve_items(work.begin_item_review(b,native_submission=bn))
        report=self.run_pair(a,an,b,bn)
        self.assertEqual(report['state'],'COMPARISON_BLOCKED')
        self.assertIsNone(report['conclusion'])
        self.assertFalse(report['results']['after']['backend_called'])

    def test_incompatible_order_model_keeps_farkas_proof_without_interval_comparison(self):
        from examples.mean_order_business_fixture import make_case
        from cfm_id.mean_order_contract import MeanOrderProblem

        def factory(mode):
            case=make_case(nodes=list('ABC'),edges=[['A','B'],['B','C']],quota=1,mode=mode)
            values=case['expected_problem'].model_dump()['values']
            for row in values:
                if row['node']=='C' and row['exposure']==0:
                    row['value']='4/5' if row['own']==0 else '1/5'
            set_common_information(case['base'],values={(v['node'],v['own'],v['exposure']):v['value'] for v in values})
            case['science']['model']['values']=deepcopy(values)
            case['expected_problem']=MeanOrderProblem.model_validate(case['expected_problem'].model_dump()|{'values':values})
            with patch('examples.mean_order_business_fixture.make_case',return_value=case):
                return mean_order()

        a,an,b,bn=self.pair(lambda:factory('OWN'),lambda:factory('NONE'))
        report=self.run_pair(a,an,b,bn)
        self.assertEqual(report['plan']['relation'],'WEAKENING')
        self.assertEqual(report['state'],'COMPARISON_BLOCKED')
        self.assertIsNone(report['conclusion'])
        self.assertEqual(report['results']['before']['state'],'INCOMPATIBLE')
        self.assertTrue(report['results']['before']['certificate']['farkas'])
        self.assertEqual(report['results']['after']['state'],'PARTIAL')
        self.assertTrue(report['both_results_independently_replayed'])

    def test_forced_interval_nesting_violation_never_publishes_comparison_conclusion(self):
        a,an,b,bn=self.pair()
        real=work.execute
        def wrong(*args,**kwargs):
            result=real(*args,**kwargs)
            if args[0].session_id==b.session_id:
                result['mathematical_claim']['interval']=['0','1/4']
            return result
        with patch.object(work,'execute',side_effect=wrong):
            report=self.run_pair(a,an,b,bn)
        self.assertEqual(report['state'],'CHECK_BLOCKED')
        self.assertEqual(report['reason_code'],'VERIFIED_INTERVALS_VIOLATE_DECLARED_NESTING')
        self.assertIsNone(report['conclusion'])

    def test_changed_native_input_during_execution_invalidates_whole_comparison(self):
        a,an,b,bn=self.pair()
        real=work.execute
        def mutate(*args,**kwargs):
            result=real(*args,**kwargs)
            if args[0].session_id==b.session_id:
                bn['bounded_review']=bn['bounded_review'].model_copy(update={'evidence':'Changed independently supplied review after execution.'})
            return result
        with patch.object(work,'execute',side_effect=mutate),self.assertRaisesRegex(ValueError,'CHANGED_DURING_COMPARISON'):
            self.run_pair(a,an,b,bn)

    def test_save_restore_keeps_lineage_but_saved_reports_are_not_sessions(self):
        a,an,b,bn=self.pair()
        with TemporaryDirectory() as directory:
            d=Path(directory)
            work.save(a,d/'before.json');work.save(b,d/'after.json')
            restored_a,restored_b=work.restore(d/'before.json'),work.restore(d/'after.json')
            report=self.run_pair(restored_a,an,restored_b,bn)
            self.assertEqual(report['state'],'COMPARED')
            self.assertEqual(restored_b.history,b.history)
            work.write_json(d/'report.json',report)
            with self.assertRaisesRegex(ValueError,'SESSION_CHECKPOINT_REQUIRED'):
                work.restore(d/'report.json')

    def test_cli_forks_new_checkpoint_without_approval_or_overwrite(self):
        a,an=reviewed(lambda:policy_bounds('0','1'))
        with TemporaryDirectory() as directory:
            d=Path(directory)
            work.save(a,d/'parent.json')
            args=['fork-version','--session',str(d/'parent.json'),'--label','Alternative bounds',
                  '--reason','Separate independent condition proposal','--output',str(d/'child.json')]
            self.assertEqual(cli(args),0)
            child=work.restore(d/'child.json')
            self.assertIsNone(child.review)
            self.assertEqual(child.candidate,a.candidate)
            self.assertEqual(cli(args),2)
            self.assertEqual(work.restore(d/'parent.json').model_dump(),a.model_dump())

    def test_requests_remain_native_and_do_not_include_version_history(self):
        a,an,b,bn=self.pair()
        self.assertEqual(work.prepare_request(a),work.prepare_request(b))
        self.assertEqual(work.prepare_request(b),routes.request(b.lane,b.bundle))
        self.assertNotIn('parent_checkpoint_sha256',str(work.prepare_request(b)))


if __name__=='__main__':
    unittest.main()
