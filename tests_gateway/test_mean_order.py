"""Offline mathematical/gate acceptance, not LLM or natural-language accuracy."""
from copy import deepcopy
from fractions import Fraction as F
from itertools import combinations
import unittest
from unittest.mock import patch

from cfm_id.mean_order_contract import MeanOrderProblem, ReviewedMeanOrder, MeanOrderUnavailable, input_digest
from cfm_id.mean_order_solver import solve
from cfm_id.mean_order_verify import replay
from cfm_id.mean_order import prepare, submit
from examples.mean_order_fixture import make_problem, synthetic_review


def changed(p, **updates):
    data = p.model_dump(); data.update(updates)
    return MeanOrderProblem.model_validate(data)


class MeanOrderMathTests(unittest.TestCase):
    def verified(self,p,expected):
        c = solve(p)
        self.assertTrue(replay(c,problem=p))
        if expected == 'INCOMPATIBLE':
            self.assertEqual(c['status'],expected); self.assertNotIn('lower',c)
        else:
            self.assertEqual((c['lower'],c['upper']),expected)
        return c

    def test_same_problem_relaxation_ladder(self):
        baseline = None
        for mode, expected in [('BOTH',('1/5','1')),('OWN',('-1/5','1')),('NONE',('-1','1'))]:
            p = make_problem(mode=mode)
            identity = p.model_dump(exclude={'node_orders'})
            if baseline is None: baseline = identity
            self.assertEqual(identity,baseline)
            c = self.verified(p,expected)
            self.assertEqual(c['informative_relative_to_bounds_only'],mode != 'NONE')

    def test_peer_only_can_equal_both_given_a4(self):
        self.verified(make_problem(mode='PEERS'),('1/5','1'))

    def test_nonzero_point_supported_policies(self):
        p = make_problem(first=[1,1,0,0],second=[0,0,1,1],weights=['1','0','0','0'])
        c = self.verified(p,('1/5','1/5'))
        self.assertEqual(c['status'],'POINT')

    def test_order_can_point_identify_unsupported_targets_at_boundary(self):
        p = make_problem()
        vs = [dict(node=v.node,own=v.own,exposure=v.exposure,value='1' if v.own else '0') for v in p.values]
        self.verified(changed(p,values=vs),('1','1'))

    def test_second_and_reverse_targets(self):
        p = make_problem(second=[1,1,0,0])
        self.verified(p,('1/10','1/2'))
        p = make_problem(first=[0]*4,second=[1]*4)
        self.verified(p,('-1','-1/5'))

    def test_joint_order_is_not_subtraction_of_marginal_bounds(self):
        p = make_problem(nodes=['A','B'],edges=[['A','B']],quota=1,weights=['1','0'],
            values=[dict(node='B',own=1,exposure=0,value='1/2'),dict(node='B',own=0,exposure=1,value='1/2')])
        self.verified(p,('0','1'))
        self.verified(changed(p,node_orders=[dict(node=n,mode='NONE') for n in p.node_order]),('-1','1'))

    def test_middle_signatures_are_incomparable(self):
        for a,b in [('1/5','4/5'),('4/5','1/5')]:
            p=make_problem()
            self.verified(changed(p,values=[dict(node=v.node,own=v.own,exposure=v.exposure,value=a if v.own else b)
                                           for v in p.values]),('3/5','1'))

    def test_full_cancellation_keeps_a4_and_order_constraints(self):
        p=make_problem(first=[1]*4,second=[1]*4)
        self.verified(p,('0','0'))
        vs=p.model_dump()['values']; vs[0]['value']='-1/10'
        self.verified(changed(p,values=vs),'INCOMPATIBLE')

    def test_non_target_node_order_conflict_has_farkas_proof(self):
        p=make_problem(nodes=list('ABC'),edges=[['A','B'],['B','C']],quota=1,weights=['1','0','0'],mode='OWN')
        vs=p.model_dump()['values']
        for v in vs:
            if v['node']=='C' and v['exposure']==0: v['value']='4/5' if v['own']==0 else '1/5'
        self.verified(changed(p,values=vs),'INCOMPATIBLE')

    def test_longer_order_path_conflict_has_farkas_proof(self):
        # At quota two on a degree-one endpoint, both 00 and 11 are supported.
        p=make_problem(nodes=list('ABCD'),edges=[['A','B'],['C','D']],quota=2)
        vs=[v for v in p.model_dump()['values'] if v['node'] != 'A' or (v['own'],v['exposure']) in ((0,0),(1,1))]
        for v in vs:
            if v['node']=='A': v['value']='9/10' if (v['own'],v['exposure'])==(0,0) else '1/10'
        cert=self.verified(changed(p,values=vs),'INCOMPATIBLE')
        self.assertEqual(sum(k.startswith('order:') for k in cert['farkas']),2)

    def test_node_specific_axes_and_zero_weights(self):
        modes={'A':'OWN','B':'PEERS','C':'BOTH','D':'NONE'}
        self.verified(make_problem(mode=modes),('-1/5','1'))
        self.verified(make_problem(mode=modes,weights=['1','0','0','0']),('-1/5','1'))

    def test_isolated_ties_and_degenerate_quotas(self):
        for quota in (0,1):
            for mode in ('NONE','OWN','PEERS','BOTH'):
                p=make_problem(nodes=['A'],edges=[],quota=quota,mode=mode)
                c=solve(p); self.assertTrue(replay(c,problem=p))
                self.assertEqual(len(c['cells']),2)
                self.assertTrue(all(r['cell'][2]==0 for r in c['cells']))
        for quota in (0,2,4):
            p=make_problem(nodes=list('ABCD'),edges=[['A','B'],['B','C']],quota=quota)
            self.assertTrue(replay(solve(p),problem=p))

    def test_binary_outcome_bounds_differ_from_mean_bounds(self):
        p=make_problem(bounds=[dict(node=n,lower='1/4',upper='3/4') for n in 'ABCD'])
        self.verified(p,('1/5','1/2'))
        self.verified(changed(p,bounds_kind='ALMOST_SURE_OUTCOME'),'INCOMPATIBLE')
        p=changed(p,bounds=[dict(node=n,lower='2',upper='3') for n in 'ABCD'])
        self.verified(p,'INCOMPATIBLE')

    def test_continuous_negative_bounds_and_affine_units(self):
        p=make_problem(outcome_kind='continuous')
        vs=[dict(node=v.node,own=v.own,exposure=v.exposure,value=str(10*F(v.value)-5)) for v in p.values]
        p=changed(p,values=vs,bounds=[dict(node=n,lower='-5',upper='5') for n in p.node_order])
        self.verified(p,('2','10'))

    def test_degenerate_bounds(self):
        p=make_problem(values=[dict(node=n,own=a,exposure=e,value='1/2') for n in 'ABCD' for a,e in [(1,0),(0,1)]],
                       bounds=[dict(node=n,lower='1/2',upper='1/2') for n in 'ABCD'])
        self.verified(p,('0','0'))

    def test_supported_target_missing_a4_stays_blocked(self):
        p=make_problem(first=[1,1,0,0],second=[0,0,1,1],weights=['1','0','0','0'])
        p=changed(p,values=[v.model_dump() for v in p.values if v.node != 'A'])
        with self.assertRaises(MeanOrderUnavailable) as exc: solve(p)
        self.assertEqual(exc.exception.state,'NEEDS_INPUT')
        p=changed(p,second=p.first)
        self.verified(p,('0','0'))

    def test_impossible_or_zero_support_a4_is_not_silently_used(self):
        p=make_problem(); vs=p.model_dump()['values']
        vs.append(dict(node='A',own=0,exposure=0,value='0'))
        with self.assertRaises(MeanOrderUnavailable): solve(changed(p,values=vs))

    def test_none_matches_existing_box_on_several_graphs(self):
        from examples.bounded_contrast_fixture import make_case
        from cfm_id.bounded_contrast_solver import solve as box
        for edges in [[],[['A','B'],['B','C'],['C','D']],list(combinations('ABCD',2))]:
            for first,second in [([1]*4,[0]*4),([0]*4,[1]*4),([1,0,1,0],[0,1,0,1])]:
                b=make_case(list('ABCD'),edges,2,first,second,list('ABCD'))
                info=b['information']['first']
                p=make_problem(edges=edges,mode='NONE',first=first,second=second,
                    values=[v.model_dump() for v in info.values],bounds=[v.model_dump() for v in info.bounds])
                old=box(b['inquiries'],b['information'])
                self.verified(p,(old['lower'],old['upper']))


class MeanOrderContractGateTests(unittest.TestCase):
    def test_existing_six_hook_extension_scaffold(self):
        from examples.mean_order_reference import MeanOrderReference
        from evaluation.partial_extension_acceptance import evaluate
        r=evaluate(MeanOrderReference())
        self.assertEqual(r['cases'],9)
        self.assertEqual(sum(x['independent_replay'] for x in r['rows']),5)
        self.assertEqual(sum(len(x['forged_certificates_rejected']) for x in r['rows']),20)
        self.assertFalse(r['route_registered'])

    def test_maximum_domain_and_out_of_domain_size(self):
        nodes=[f'N{i}' for i in range(12)]
        p=make_problem(nodes=nodes,quota=6)
        self.assertTrue(replay(solve(p),problem=p))
        with self.assertRaises(ValueError): make_problem(nodes=nodes+['N12'],quota=6)

    def test_missing_review_or_opt_in_never_calls_backend(self):
        p=make_problem()
        with patch('cfm_id.mean_order.solve',side_effect=AssertionError('called')):
            for kwargs in [{},{'review':synthetic_review(p)},{'synthetic_protocol_selected':True}]:
                result=submit(p,**kwargs)
                self.assertEqual(result['state'],'REVIEW_REQUIRED')
                self.assertFalse(result['bounded_backend_called'])

    def test_stale_review_on_any_target_a4_axis_or_scope_change(self):
        p=make_problem(); review=synthetic_review(p)
        edits=[dict(first=[0]*4),dict(weights=['1','0','0','0']),dict(context='Another study context'),
               dict(node_orders=[dict(node=n,mode='OWN') for n in p.node_order]),dict(outcome_period='Another study day')]
        for edit in edits:
            with self.subTest(edit=edit),patch('cfm_id.mean_order.solve',side_effect=AssertionError('called')):
                r=submit(changed(p,**edit),review=review,synthetic_protocol_selected=True)
                self.assertEqual(r['state'],'CHECK_BLOCKED')

    def test_review_does_not_convert_conditional_certificate_to_real_approval(self):
        p=make_problem(); r=submit(p,review=synthetic_review(p),synthetic_protocol_selected=True)
        self.assertEqual(r['state'],'PARTIAL'); self.assertTrue(r['bounded_certificate_replayed'])
        self.assertTrue(r['synthetic_review_checked'])
        for key in ('scientific_approval','production_admission','estimation_handoff_allowed','business_route_registered','core_called'):
            self.assertIs(r[key],False)

    def test_no_defaults_for_scientific_claims(self):
        p=make_problem().model_dump()
        for field in ('node_orders','order_scope','randomization_claim','mean_sufficiency_claim','bounds','availability','weights'):
            data=deepcopy(p); data.pop(field)
            with self.subTest(field=field),self.assertRaises(ValueError): MeanOrderProblem.model_validate(data)

    def test_unknown_coupling_and_invalid_scientific_scope_rejected(self):
        p=make_problem().model_dump()
        edits=[dict(no_peer_effect=True),dict(lipschitz='1'),dict(model_scope='FULL_JOINT_LAW'),
               dict(order_scope='HISTORICAL_SUPPORT_ONLY'),dict(availability='FINITE_SAMPLE_ESTIMATE'),
               dict(mean_sufficiency_scope='HISTORICAL_SUPPORT_ONLY'),dict(order_direction='UNKNOWN'),
               dict(design='OBSERVATIONAL'),dict(exposure='E4_EXACT_COUNT')]
        for edit in edits:
            with self.subTest(edit=edit),self.assertRaises(ValueError): MeanOrderProblem.model_validate(p|edit)

    def test_strict_numbers_and_coordinates(self):
        p=make_problem().model_dump()
        edits=[dict(quota=True),dict(first=[True,1,1,1]),dict(weights=['0.25']*4),dict(weights=['-1','1','1','0']),
               dict(undirected_edges=[['A','A']]),dict(undirected_edges=[['A','B'],['B','A']]),
               dict(node_order=['A','A','C','D']),dict(node_orders=[dict(node='A',mode='BOTH')]),dict(first=[1]),
               dict(values=[dict(node='A',own=True,exposure=1,value='1/2')])]
        for edit in edits:
            with self.subTest(edit=edit),self.assertRaises(ValueError): MeanOrderProblem.model_validate(p|edit)

    def test_nested_mutation_revalidated(self):
        p=make_problem(); p.first[0]=True
        self.assertEqual(prepare(p)['state'],'CHECK_BLOCKED')

    def test_supported_missing_material_stops_before_optimizer(self):
        p=make_problem(first=[1,1,0,0],second=[0,0,1,1],weights=['1','0','0','0'])
        p=changed(p,values=[v.model_dump() for v in p.values if v.node!='A'])
        with patch('cfm_id.mean_order.solve',side_effect=AssertionError('optimizer called')):
            r=submit(p,review=synthetic_review(p),synthetic_protocol_selected=True)
        self.assertEqual(r['state'],'NEEDS_INPUT');self.assertFalse(r['bounded_backend_called'])

    def test_legitimate_short_unit_and_period_labels(self):
        p=changed(make_problem(),outcome_unit='率',outcome_period='日')
        self.assertTrue(replay(solve(p),problem=p))

    def test_review_boolean_must_be_literal_boolean(self):
        d=synthetic_review(make_problem()).model_dump()
        for v in (1,'true',False,None):
            with self.subTest(v=v),self.assertRaises(ValueError): ReviewedMeanOrder.model_validate(d|{'reviewed_bounds_and_each_order_axis':v})

    def test_replay_failure_cannot_publish_identification(self):
        p=make_problem()
        with patch('cfm_id.mean_order.replay',return_value=False):
            r=submit(p,review=synthetic_review(p),synthetic_protocol_selected=True)
        self.assertEqual(r['state'],'CHECK_BLOCKED'); self.assertNotIn('bounded_result',r)


if __name__=='__main__': unittest.main()
