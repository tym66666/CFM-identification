"""Rejection localization must preserve validation and avoid echoing inputs."""
import copy
import json
import unittest
from unittest.mock import patch

from cfm_id_llm.providers import MockProvider
from cfm_id_llm.quality_formulator import A0QualityFormulatorV010, A0QualityValidationError
from cfm_id_llm.schemas import BusinessCase
from evaluation.nbib_semantic_eval import make_reference_only_fixture

PRIVATE = 'PRIVATE_QUOTE_OR_SOURCE_ID'


class ProvenanceDiagnosticTests(unittest.TestCase):
    def setUp(self):
        entry = {'case_id': 'LOCAL', 'business_question': '希望知道全员推广后的团队表现。',
                 'expected': [{'kind': 'FIXED_POLICY_VALUE', 'quote': '全员推广后的团队表现'}]}
        self.case = BusinessCase(case_id=entry['case_id'], business_question=entry['business_question'])
        self.raw = make_reference_only_fixture(entry)

    def reject(self):
        before = copy.deepcopy(self.raw)
        with self.assertRaises(A0QualityValidationError) as caught:
            A0QualityFormulatorV010(MockProvider(self.raw)).formulate(self.case)
        self.assertEqual(caught.exception.code, 'A0_PROVENANCE_OR_AUDIT_REJECTED')
        self.assertEqual(before, self.raw)
        self.assertNotIn(PRIVATE, str(caught.exception) + json.dumps(caught.exception.diagnostics))
        return caught.exception.diagnostics

    def test_missing_source_has_typed_path_without_source_id(self):
        self.raw['queries'][0]['business_goal']['evidence'][0]['source_id'] = PRIVATE
        d = self.reject()
        self.assertEqual(d['issues'], [{'path': ['queries', 0, 'business_goal', 'evidence', 0, 'source_id'],
                                       'code': 'EVIDENCE_SOURCE_NOT_FOUND'}])

    def test_modified_quote_has_typed_path_without_quote(self):
        self.raw['queries'][0]['business_goal']['evidence'][0]['quote'] = PRIVATE
        d = self.reject()
        self.assertEqual(d['issue_count'], 1)
        self.assertEqual(d['issues'][0], {'path': ['queries', 0, 'business_goal', 'evidence', 0, 'quote'],
                                        'code': 'EVIDENCE_QUOTE_NOT_EXACT'})

    def test_v010_semantic_fields_are_included(self):
        self.raw['queries'][0]['semantics']['comparator'] = {
            'value': '候选对照', 'basis': 'INTERPRETATION',
            'evidence': [{'source_id': 'business_question', 'quote': PRIVATE}]}
        d = self.reject()
        self.assertEqual(d['issues'][0]['path'], ['queries', 0, 'semantics', 'comparator', 'evidence', 0, 'quote'])

    def test_shared_claims_are_included(self):
        self.raw['shared_draft']['units_variables']['analysis_unit'] = {
            'value': '候选单位', 'basis': 'INTERPRETATION',
            'evidence': [{'source_id': PRIVATE, 'quote': '未知引文'}]}
        d = self.reject()
        self.assertEqual(d['issues'][0]['path'], ['shared_draft', 'units_variables', 'analysis_unit', 'evidence', 0, 'source_id'])

    def test_diagnostics_are_bounded_but_count_all_issues(self):
        claim = {'value': '候选值', 'basis': 'INTERPRETATION',
                 'evidence': [{'source_id': PRIVATE, 'quote': PRIVATE} for _ in range(8)]}
        for name in ('intervention', 'comparator', 'aggregation'):
            self.raw['queries'][0]['semantics'][name] = copy.deepcopy(claim)
        d = self.reject()
        self.assertEqual(d['issue_count'], 24)
        self.assertEqual(len(d['issues']), 20)
        self.assertTrue(d['issues_truncated'])

    def test_primary_target_check_still_precedes_provenance(self):
        self.raw['shared_draft']['target']['description']['value'] = PRIVATE
        with self.assertRaises(A0QualityValidationError) as caught:
            A0QualityFormulatorV010(MockProvider(self.raw)).formulate(self.case)
        self.assertEqual(caught.exception.code, 'A0_SCHEMA_REJECTED')
        self.assertEqual(caught.exception.diagnostics['issues'][0]['code'], 'PRIMARY_TARGET_MISMATCH')

    def test_unrelated_audit_failure_is_not_mislabeled_as_bad_quote(self):
        with patch('cfm_id_llm.quality_formulator.audit_business_quality', side_effect=ValueError(PRIVATE)):
            d = self.reject()
        self.assertEqual(d['issue_count'], 0)
        self.assertEqual(d['issues'], [])
        self.assertEqual(d['stage'], 'provenance_or_audit')

    def test_valid_draft_keeps_review_and_no_estimation_boundaries(self):
        report = A0QualityFormulatorV010(MockProvider(self.raw)).formulate(self.case)
        self.assertTrue(report.scientific_review_required)
        self.assertEqual(report.mathematical_verification, 'NOT_PERFORMED')
        self.assertFalse(report.core_called)
        self.assertFalse(report.estimation_handoff_allowed)


if __name__ == '__main__':
    unittest.main()
