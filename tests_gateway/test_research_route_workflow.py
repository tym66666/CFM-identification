"""Exercise a single boundary with unrelated graph and network proof types."""
import unittest
from copy import deepcopy
from unittest.mock import patch
from cfm_id.research_route_workflow import run_route
from cfm_id.research_route_adapters import DagBackdoorRoute,MeanOrderRoute,capabilities
from cfm_id.mean_order_contract import MeanOrderProblem
from examples.dag_backdoor_reference import make_problem as dag_problem,synthetic_review as dag_review
from examples.mean_order_fixture import make_problem as mean_problem,synthetic_review as mean_review


class RouteWorkflowTests(unittest.TestCase):
    def go(self,adapter,p,review):
        return run_route(adapter,p,review=review,research_protocol_selected=True)

    def test_two_math_families_use_same_explicit_entry(self):
        d,m=dag_problem(),mean_problem()
        graph=self.go(DagBackdoorRoute(),d,dag_review(d))
        network=self.go(MeanOrderRoute(),m,mean_review(m))
        self.assertEqual(graph['state'],'POINT');self.assertEqual(network['state'],'PARTIAL')
        self.assertEqual(graph['mathematical_claim']['representation'],'OBSERVED_DISTRIBUTION_FUNCTIONAL')
        self.assertEqual(network['mathematical_claim']['representation'],'EXACT_IDENTIFIED_INTERVAL')
        for r in (graph,network):
            self.assertTrue(r['independent_replay']);self.assertFalse(r['production_admission'])
            self.assertFalse(r['estimation_handoff_allowed'])

    def test_existing_mean_order_proof_unchanged(self):
        from cfm_id.mean_order import submit
        p=mean_problem();review=mean_review(p)
        original=submit(p,review=review,synthetic_protocol_selected=True)
        wrapped=self.go(MeanOrderRoute(),p,review)
        self.assertEqual(original,wrapped['native_result'])
        self.assertEqual(original['bounded_result'],wrapped['certificate'])

    def test_incompatibility_keeps_distinct_proof_and_no_interval(self):
        data=mean_problem().model_dump();data['values'][0]['value']='-1/10'
        p=MeanOrderProblem.model_validate(data);r=self.go(MeanOrderRoute(),p,mean_review(p))
        self.assertEqual(r['state'],'INCOMPATIBLE');self.assertTrue(r['independent_replay'])
        self.assertEqual(r['mathematical_claim']['representation'],'CONSTRAINT_CONTRADICTION')
        self.assertNotIn('interval',r['mathematical_claim'])

    def test_review_or_selection_missing_cannot_call_backend(self):
        for adapter,p,review in [(DagBackdoorRoute(),dag_problem(),dag_review(dag_problem())),
                                 (MeanOrderRoute(),mean_problem(),mean_review(mean_problem()))]:
            with patch.object(adapter,'submit',side_effect=AssertionError('should not submit')):
                for selected,r in [(False,review),(1,review),(True,None)]:
                    out=run_route(adapter,p,review=r,research_protocol_selected=selected)
                    self.assertEqual(out['state'],'REVIEW_REQUIRED');self.assertFalse(out['backend_called'])

    def test_wrong_family_is_blocked_not_auto_converted(self):
        p=dag_problem()
        r=self.go(MeanOrderRoute(),p,dag_review(p))
        self.assertEqual(r['state'],'CHECK_BLOCKED');self.assertIsNone(r['mathematical_claim'])

    def test_wrong_review_type_and_changed_materials(self):
        p=dag_problem();review=dag_review(p)
        changed=p.model_copy(update={'materials_sha256':'0'*64})
        self.assertEqual(self.go(DagBackdoorRoute(),changed,review)['state'],'CHECK_BLOCKED')
        self.assertEqual(self.go(DagBackdoorRoute(),p,mean_review(mean_problem()))['state'],'CHECK_BLOCKED')

    def test_stop_does_not_turn_into_partial_or_nonid(self):
        p=dag_problem(['U','X','Y'],[['U','X'],['U','Y'],['X','Y']],['U'])
        r=self.go(DagBackdoorRoute(),p,dag_review(p))
        self.assertEqual(r['state'],'UNSUPPORTED');self.assertIsNone(r['mathematical_claim']);self.assertIsNone(r['certificate'])

    def test_interface_rejects_premature_result_and_promotion(self):
        p=dag_problem();review=dag_review(p);adapter=DagBackdoorRoute()
        with patch.object(adapter,'prepare',return_value={'state':'POINT'}):
            self.assertEqual(self.go(adapter,p,review)['reason_code'],'PREPARE_CROSSED_REVIEW_BOUNDARY')
        native=adapter.submit(p,review);native['production_admission']=True
        with patch.object(adapter,'submit',return_value=native):
            self.assertEqual(self.go(adapter,p,review)['reason_code'],'RESEARCH_ROUTE_PROMOTED_TO_PRODUCTION')

    def test_interface_verifies_proof_and_claim_not_just_status(self):
        p=dag_problem();review=dag_review(p);adapter=DagBackdoorRoute()
        with patch.object(adapter,'replay',return_value=False):
            r=self.go(adapter,p,review)
            self.assertEqual(r['state'],'CHECK_BLOCKED');self.assertIsNone(r['mathematical_claim'])
        correct=adapter.claim(adapter.submit(p,review)['certificate'])
        for invalid in [{**correct,'kind':'PARTIAL'},{**correct,'numeric_value':'100'},
                        {**correct,'functional':{'operation':'wrong'}}]:
            with patch.object(adapter,'claim',return_value=invalid):
                self.assertEqual(self.go(adapter,p,review)['state'],'CHECK_BLOCKED')

    def test_mutating_adapter_is_blocked_and_original_is_preserved(self):
        p=dag_problem();original=deepcopy(p.model_dump());adapter=DagBackdoorRoute();fn=adapter.prepare
        def mutate(problem):
            result=fn(problem);problem.nodes.reverse();return result
        with patch.object(adapter,'prepare',side_effect=mutate):
            r=self.go(adapter,p,dag_review(p));self.assertEqual(r['reason_code'],'PREPARE_MUTATED_INPUT')
        self.assertEqual(p.model_dump(),original)

    def test_capabilities_are_descriptive_not_autorouting(self):
        items=capabilities()
        self.assertEqual({x.route_id for x in items},{'DAG_CLASSICAL_BACKDOOR','DAG_ADJUSTMENT',
            'DAG_CLASSICAL_FRONTDOOR','MEAN_ORDER_D2_E1','BINARY_IV_LATE_ATE'})
        self.assertEqual(len(items),len({x.route_id for x in items}))
        self.assertEqual({x.model_family for x in items},
            {'STATIC_CAUSAL_DAG','FIXED_NETWORK_MEAN_ORDER','BINARY_INSTRUMENTAL_VARIABLE'})
        from cfm_id.research_route_catalog import inventory
        self.assertFalse(inventory()['automatic_route_inference'])
        self.assertFalse(inventory()['production_admission'])


if __name__=='__main__':unittest.main()
