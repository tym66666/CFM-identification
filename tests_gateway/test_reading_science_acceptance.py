"""End-to-end regression and negative review boundaries on real saved readings."""
from copy import deepcopy
from dataclasses import replace
from fractions import Fraction
import unittest

from cfm_id.intent_submission import submit, reviewed_projection
from evaluation.business_core_pilot_base import canonical_hash
from evaluation.reading_science_acceptance import (
    recorded_cases, saved_inputs, evaluate, independent_enumeration, tamper_checks,
)
from examples.reading_science_fixture import (
    synthetic_context, fresh_outer_review, expected_terms, protocol,
)
from pfn_pipeline.identification_business import identify_network_business_query


@unittest.skipUnless((__import__('pathlib').Path(__file__).resolve().parents[1] / 'evaluation/reading_accuracy_cases/recorded/MANIFEST.json').is_file(),
                     'Optional real LLM response archive is not distributed in the source package')
class ReadingScienceAcceptance(unittest.TestCase):
    def record(self, name='cold_chain', model='deepseek'):
        return next(r for r in recorded_cases() if r['case'] == name and r['model_group'] == model)

    def setup_case(self, name='cold_chain'):
        b, raw = saved_inputs(self.record(name))
        packet, context, review = synthetic_context(name, b, raw)
        return b, raw, packet, context, review

    def submit(self, b, raw, packet, context, review):
        return submit(b, raw, 'D1_EFFECTS', packet=packet, context=context,
            submission_review=review, synthetic_protocol_selected=True)

    def assert_stopped(self, out, context):
        self.assertNotEqual(out['state'], 'CORE_POINT')
        self.assertFalse(out['core_called'])
        self.assertEqual(context.core_port.calls, [])

    def refresh_outer_and_wire(self, b, raw, packet, context):
        # A fresh outer approval must not conceal a mismatch with independent
        # scientific/target records inside the trusted Core binding.
        context = replace(context, approval=context.approval.model_copy(update={
            'model_draft_sha256': canonical_hash(reviewed_projection(b, raw, 'D1_EFFECTS')),
            'science_packet_sha256': canonical_hash(packet)}))
        return context, fresh_outer_review(b, raw, packet, context)

    def test_all_twelve_saved_live_outputs_follow_expected_full_chain(self):
        records = recorded_cases()
        self.assertEqual(len(records), 12)
        for record in records:
            with self.subTest(model=record['model_group'], case=record['case']):
                result = evaluate(record)
                self.assertTrue(result['passed'])
                self.assertEqual(result['final_state'], record['expected_state'])
                self.assertEqual(result['new_api_calls'], 0)

    def test_public_preview_and_missing_reviews_never_invoke_science_compiler(self):
        from unittest.mock import patch
        from cfm_id.business_entry import preview
        b, raw = saved_inputs(self.record())
        with patch('evaluation.business_d1_submission.compile_inquiry', side_effect=AssertionError('PREMATURE_COMPILE')):
            self.assertEqual(preview(b, raw, 'D1_EFFECTS')['state'], 'REVIEW_REQUIRED')
            self.assertFalse(submit(b, raw, 'D1_EFFECTS', synthetic_protocol_selected=True)['core_called'])

    def test_missing_a4_or_a5_reference_with_fresh_wire_review_is_rejected(self):
        for name in ('cold_chain', 'repair_teams', 'cold_chain_subset'):
            for key in ('population_information', 'causal_licenses'):
                with self.subTest(case=name, missing=key):
                    b, raw, packet, context, _ = self.setup_case(name)
                    packet['science'].pop(key)
                    context, review = self.refresh_outer_and_wire(b, raw, packet, context)
                    self.assert_stopped(self.submit(b, raw, packet, context, review), context)

    def test_missing_exact_scientific_binding_is_rejected_even_with_fresh_outer_review(self):
        b, raw, packet, context, _ = self.setup_case()
        binding = context.core_port.bindings['q1']
        context.core_port.bindings['q1'] = replace(binding,
            admission=binding.admission.model_copy(update={'approved_scientific_binding': None}))
        review = fresh_outer_review(b, raw, packet, context)
        self.assert_stopped(self.submit(b, raw, packet, context, review), context)

    def test_missing_required_a4_cell_is_rejected_even_after_outer_review(self):
        b, raw, packet, context, _ = self.setup_case()
        binding = context.core_port.bindings['q1']; inquiry = binding.inquiry
        # Omit an actually needed cell, retaining all other recorded approvals.
        cells = tuple(c for c in inquiry.a4_source.arm_cells if c != ('site_01', 1, 1))
        changed_source = replace(inquiry.a4_source, arm_cells=cells)
        context.core_port.bindings['q1'] = replace(binding,
            inquiry=replace(inquiry, a4_source=changed_source))
        review = fresh_outer_review(b, raw, packet, context)
        self.assert_stopped(self.submit(b, raw, packet, context, review), context)

    def test_changed_population_cannot_reuse_old_review(self):
        b, raw, packet, context, review = self.setup_case()
        raw['questions']['q1']['population'] = dict(selection='指定', ids=['site_01', 'site_03'])
        self.assert_stopped(self.submit(b, raw, packet, context, review), context)

    def test_rebinding_wire_does_not_replace_independent_population(self):
        b, raw, packet, context, _ = self.setup_case()
        raw['questions']['q1']['population'] = dict(selection='指定', ids=['site_01', 'site_03'])
        context, review = self.refresh_outer_and_wire(b, raw, packet, context)
        self.assert_stopped(self.submit(b, raw, packet, context, review), context)

    def test_test_reviewer_rejects_wrong_cohort_exposure_and_contrast(self):
        for change in ('population', 'exposure', 'contrast'):
            with self.subTest(change=change):
                b, raw = saved_inputs(self.record())
                if change == 'population':
                    raw['questions']['q1']['population'] = dict(selection='指定', ids=['site_01', 'site_03'])
                elif change == 'exposure':
                    raw['study']['exposure'] = 'strict_majority'
                    for side in ('first', 'second'): raw['questions']['q1'][side]['neighbors'] = '超过一半'
                else:
                    q = raw['questions']['q1']; q['first'], q['second'] = q['second'], q['first']
                with self.assertRaises(ValueError): synthetic_context('cold_chain', b, raw)

    def test_enumerating_full_roster_is_equivalent_but_real_subset_is_not(self):
        b, raw = saved_inputs(self.record())
        raw['questions']['q1']['population'] = dict(selection='指定', ids=list(b['structure']['nodes']))
        packet, context, review = synthetic_context('cold_chain', b, raw)
        self.assertEqual(self.submit(b, raw, packet, context, review)['state'], 'CORE_POINT')
        b, raw = saved_inputs(self.record('cold_chain_subset'))
        raw['questions']['q1']['population'] = dict(selection='全体', ids=[])
        with self.assertRaises(ValueError): synthetic_context('cold_chain_subset', b, raw)

    def test_changed_public_materials_invalidate_existing_and_new_test_reviews(self):
        b, raw, packet, context, review = self.setup_case()
        b['documents']['business_question.md'] += '\n新增未经审核的条件。'
        self.assert_stopped(self.submit(b, raw, packet, context, review), context)
        with self.assertRaisesRegex(ValueError, 'FROZEN_PUBLIC_MATERIALS_CHANGED'):
            synthetic_context('cold_chain', b, raw)

    def test_probability_change_cannot_reuse_science(self):
        b, raw, packet, context, review = self.setup_case()
        table = b['tables']['design_probabilities.csv']
        table['rows'][0]['randomization_probability'] = '1/3'
        b['probability_binding']['table_sha256'] = canonical_hash(table)
        self.assert_stopped(self.submit(b, raw, packet, context, review), context)
        with self.assertRaises(ValueError): synthetic_context('cold_chain', b, raw)

    def test_negative_businesses_cannot_receive_the_positive_protocol(self):
        for name in ('convenience_stores', 'service_points', 'convenience_stores_subset'):
            with self.subTest(case=name):
                b, raw = saved_inputs(self.record(name))
                with self.assertRaisesRegex(ValueError, 'NO_SCIENTIFIC_PROTOCOL'):
                    synthetic_context(name, b, raw)
                with self.assertRaisesRegex(ValueError, 'FROZEN_PUBLIC_MATERIALS_CHANGED'):
                    synthetic_context('cold_chain', b, raw)

    def test_independent_oracle_and_replayer_reject_wrong_formula(self):
        b, raw, packet, context, review = self.setup_case('cold_chain_subset')
        outcome = identify_network_business_query(context.core_port.bindings['q1'].inquiry)
        composition = outcome.result.results[0]
        wrong = replace(composition.terms[0], coefficient=Fraction(1, 6))
        with self.assertRaisesRegex(AssertionError, 'FORMULA_COORDINATES_OR_WEIGHTS'):
            independent_enumeration('cold_chain_subset',
                replace(composition, terms=(wrong,) + composition.terms[1:]))
        self.assertEqual(tamper_checks(outcome), dict(coefficient=True, support=True, certificate=True))

    def test_subset_changes_weights_without_removing_untargeted_network_units(self):
        b, raw, packet, context, review = self.setup_case('cold_chain_subset')
        inquiry = context.core_port.bindings['q1'].inquiry
        self.assertEqual(len(inquiry.batch.template.identification_spec['network_exposure']['node_ids']), 6)
        self.assertEqual(dict(inquiry.requests[0].node_weights), {'site_01': Fraction(1, 2), 'site_03': Fraction(1, 2)})
        self.assertEqual(len(expected_terms(protocol('cold_chain_subset'))), 4)


if __name__ == '__main__': unittest.main()
