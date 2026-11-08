import json
import unittest
from evaluation.business_materials_cases import fixtures
from evaluation import business_materials_compact_json as baseline,business_materials_optional_tables as current
from tests_gateway.test_business_materials_plan_references import reference

class InputSpecificPromptTests(unittest.TestCase):
    def test_no_probability_table_restores_exact_validated_request(self):
        cs=[c for c in fixtures() if not c['bundle']['structure']['cluster_rates']]
        self.assertTrue(cs)
        for c in cs:self.assertEqual(current.make_request(c['bundle']),baseline.make_request(c['bundle']))

    def test_binding_hint_is_present_only_with_actual_complete_table(self):
        for c in fixtures():
            _,user=current.make_request(c['bundle']);message=json.loads(user)
            rates=c['bundle']['structure']['cluster_rates']
            self.assertEqual('available_local_design_binding' in message,bool(rates))
            if rates:
                hint=message['available_local_design_binding']
                self.assertEqual(hint['groups'],sorted(rates))
                self.assertFalse(hint['independence_or_causal_license_implied'])

    def test_missing_quotas_remain_rejected_instead_of_filled(self):
        c=next(c for c in fixtures() if c['case_id']=='NBIB-021-clarified')
        raw=reference(c);raw['study']['group_parameters']=None
        result=current.evaluate_draft(c['bundle'],raw,c['packet'],synthetic_protocol_selected=True)
        self.assertEqual(result['reason_code'],'COMPLETE_CLUSTER_PROBABILITY_TABLE_REQUIRED')
        self.assertFalse(result['results']);self.assertFalse(result['production_admission'])

if __name__=='__main__':unittest.main()
