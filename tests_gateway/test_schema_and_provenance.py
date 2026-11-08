from __future__ import annotations
import copy
import unittest
from pydantic import ValidationError
from cfm_id_llm import BusinessCase, DraftProblemSpec
from cfm_id_llm.audit import DraftEvidenceError, fingerprint_business_case, verify_quote_provenance
from cfm_id_llm.formulator import DraftValidationError, ProblemFormulator
from cfm_id_llm.providers import MockProvider
from tests_gateway.support import case_and_draft


class SchemaAndProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.case_data, self.raw = case_and_draft()
        self.case = BusinessCase.model_validate(self.case_data)

    def test_good_example(self):
        verify_quote_provenance(self.case, DraftProblemSpec.model_validate(self.raw))

    def test_unknown_top_level_fails(self):
        self.raw['is_verified'] = True
        with self.assertRaises(ValidationError): DraftProblemSpec.model_validate(self.raw)

    def test_no_point_conclusion_can_be_injected(self):
        self.raw['identification_status'] = 'POINT'
        with self.assertRaises(ValidationError): DraftProblemSpec.model_validate(self.raw)

    def test_no_estimation_permission_can_be_injected(self):
        self.raw['estimation_handoff_allowed'] = True
        with self.assertRaises(ValidationError): DraftProblemSpec.model_validate(self.raw)

    def test_unapproved_assumption_status_rejected(self):
        self.raw['assumptions'] = [{'name': 'randomization', 'statement': 'Design is randomized',
               'status': 'CERTIFIED', 'basis': 'LLM_SUGGESTION', 'evidence': []}]
        with self.assertRaises(ValidationError): DraftProblemSpec.model_validate(self.raw)

    def test_report_never_verified(self):
        report = ProblemFormulator(MockProvider(self.raw)).formulate(self.case)
        self.assertEqual(report.mathematical_verification, 'NOT_PERFORMED')
        self.assertFalse(report.estimation_handoff_allowed)

    def test_nonexistent_quote_rejected(self):
        self.raw['target']['description']['evidence'][0]['quote'] = '绝不存在的实验协议内容xyz'
        with self.assertRaises(DraftEvidenceError): verify_quote_provenance(self.case, DraftProblemSpec.model_validate(self.raw))

    def test_unknown_source_rejected(self):
        self.raw['target']['description']['evidence'][0]['source_id'] = 'imaginary'
        with self.assertRaises(DraftEvidenceError): verify_quote_provenance(self.case, DraftProblemSpec.model_validate(self.raw))

    def test_invalid_quote_provider_error_is_not_certification(self):
        self.raw['target']['description']['evidence'][0]['quote'] = 'not in text anywhere'
        with self.assertRaises(DraftValidationError): ProblemFormulator(MockProvider(self.raw)).formulate(self.case)

    def test_empty_claim_cannot_be_explicit(self):
        self.raw['units_variables']['outcome'] = {'value': 'sales', 'basis': 'EXPLICIT_TEXT', 'evidence': []}
        with self.assertRaises(ValidationError): DraftProblemSpec.model_validate(self.raw)

    def test_unknown_claim_cannot_carry_value(self):
        self.raw['units_variables']['treatment'] = {'value': 'AI', 'basis': 'UNRESOLVED', 'evidence': []}
        with self.assertRaises(ValidationError): DraftProblemSpec.model_validate(self.raw)

    def test_input_source_ids_unique(self):
        self.case_data['sources'] = [
          {'source_id':'duplicate','text':'x','kind':'OTHER'},
          {'source_id':'duplicate','text':'y','kind':'OTHER'}]
        with self.assertRaises(ValidationError): BusinessCase.model_validate(self.case_data)

    def test_source_ids_cannot_impersonate_business_question(self):
        self.case_data['sources'] = [{'source_id':'business_question','text':'x','kind':'OTHER'}]
        with self.assertRaises(ValidationError): BusinessCase.model_validate(self.case_data)

    def test_case_fingerprint_stable_and_sensitive(self):
        a = fingerprint_business_case(self.case)
        b = fingerprint_business_case(BusinessCase.model_validate(copy.deepcopy(self.case_data)))
        self.assertEqual(a, b)
        changed=copy.deepcopy(self.case_data)
        changed['business_question']+='其他细节'
        self.assertNotEqual(a,fingerprint_business_case(BusinessCase.model_validate(changed)))

    def test_extra_source_metadata_rejected(self):
        self.case_data['sources'] = [{'source_id':'x','kind':'OTHER','text':'valid', 'authority':'CERTIFIED'}]
        with self.assertRaises(ValidationError): BusinessCase.model_validate(self.case_data)


if __name__ == '__main__': unittest.main()
