from copy import deepcopy
import unittest
from evaluation import business_materials_compact_json as old,business_materials_probability_tables as new
from evaluation.business_materials_cases import fixtures
from tests_gateway.test_business_materials_plan_references import reference

class TableBindingTests(unittest.TestCase):
    def test_null_table_binding_preserves_every_original_target_and_math_decision(self):
        for c in fixtures():
            a=reference(c); b=deepcopy(a)
            if c['bundle']['structure']['cluster_rates']: b['study']['group_parameters']=None
            self.assertEqual(old.project(c['bundle'],a),new.project(c['bundle'],b))
            x=old.evaluate_draft(c['bundle'],a,c['packet'],synthetic_protocol_selected=True)
            y=new.evaluate_draft(c['bundle'],b,c['packet'],synthetic_protocol_selected=True)
            for k in ('status','reason_code','results','study_reading','proposed_targets'):
                self.assertEqual(x.get(k),y.get(k),k)

    def test_probabilities_never_create_independence_or_science(self):
        c=next(c for c in fixtures() if c['case_id']=='NBIB-020-original')
        raw=reference(c); raw['study']['group_parameters']=None
        result=new.evaluate_draft(c['bundle'],raw,c['packet'],synthetic_protocol_selected=True)
        self.assertIsNone(result['study_reading']['draws_independent'])
        self.assertEqual(result['status'],'NEEDS_INPUT'); self.assertFalse(result['production_admission'])
        self.assertFalse(result['local_design_table_binding']['independence_inferred'])

    def test_no_table_cannot_fill_missing_quotas(self):
        c=next(c for c in fixtures() if c['case_id']=='NBIB-021-clarified')
        raw=reference(c); raw['study']['group_parameters']=None
        result=new.evaluate_draft(c['bundle'],raw,c['packet'],synthetic_protocol_selected=True)
        self.assertEqual(result['reason_code'],'COMPLETE_CLUSTER_PROBABILITY_TABLE_REQUIRED')

    def test_conflicting_model_parameters_not_silently_replaced(self):
        c=next(c for c in fixtures() if c['case_id']=='NBIB-003-single-store')
        raw=reference(c); raw['study']['group_parameters'][0]['probability']='1/3'
        result=new.evaluate_draft(c['bundle'],raw,c['packet'],synthetic_protocol_selected=True)
        self.assertEqual(result['status'],'REJECTED')
        self.assertEqual(result['reason_code'],'MODEL_PROBABILITY_CONFLICTS_WITH_TABLE')

if __name__=='__main__': unittest.main()
