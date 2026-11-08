from copy import deepcopy
import unittest
from pathlib import Path
from unittest.mock import patch
from evaluation.nbib_acceptance import (
    registry, material_input, material_request, canonical_material_request,
    original_a0_input, public_path, check_public, entry,
    classify_attempt, summarize_attempts,
)


class BenchmarkAcceptanceTests(unittest.TestCase):
    def test_tracks_keep_originals_revisions_and_used_regression_separate(self):
        r = registry()
        self.assertEqual(r['tracks'], {'NBIB_RAW': 21, 'NBIB_CONTROLLED_REVISION': 3, 'SYNTHETIC_REGRESSION': 13})
        self.assertEqual(len(r['entries']), 37)
        for row in r['entries']:
            if row['track'] != 'NBIB_RAW':
                self.assertFalse(row['heldout_claim_allowed'])
                self.assertEqual(row['split'], 'DEVELOPMENT_REGRESSION')

    def test_model_intake_cannot_read_private_gold_or_scientific_packets(self):
        native = Path.read_text
        def guarded(path, *args, **kwargs):
            if 'research_only' in path.parts or 'gold' in path.parts:
                raise AssertionError('Private reference accessed during model intake')
            return native(path, *args, **kwargs)
        with patch.object(Path, 'read_text', guarded):
            for row in registry()['entries']:
                if row['track'] != 'NBIB_RAW':
                    system, user = material_request(row['id'])
                    self.assertNotIn('SYNTHETIC_BENCHMARK_ONLY', system + user)
            raw = original_a0_input('NBIB-002')
            self.assertIn('某站点', raw.business_question)

    def test_mapping_order_does_not_change_request_but_values_still_do(self):
        b = material_input('NBIB-021-clarified')
        def reverse(v):
            if isinstance(v, dict): return {k: reverse(v[k]) for k in reversed(v)}
            if isinstance(v, list): return [reverse(x) for x in v]
            return v
        self.assertEqual(canonical_material_request(b), canonical_material_request(reverse(b)))
        changed = deepcopy(b)
        changed['documents']['target_clarification.txt'] += '\n补充：仍保留全部64站。'
        self.assertNotEqual(canonical_material_request(b), canonical_material_request(changed))

    def test_public_integrity_rejects_changed_digest(self):
        item = deepcopy(entry('H25-service_arm'))
        name = next(iter(item['public_files']))
        item['public_files'][name] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'PUBLIC_FILE_CHANGED'):
            check_public(item)

    def test_reference_paths_and_parent_escape_rejected(self):
        for name in ('evaluation/nbib_acceptance/research_only/formal_references.json', '../secrets/key.txt'):
            with self.assertRaisesRegex(ValueError, 'PUBLIC_PATH_REQUIRED'):
                public_path(name)

    def test_generic_science_refusal_is_not_semantic_success(self):
        row = dict(track='NBIB_RAW', transport_complete=True, contract_passed=True,
                   query_count=2, scientific_gate_passed=True, semantic_passed=None)
        self.assertEqual(classify_attempt(row, 2), 'SEMANTICS_NOT_SCORED')
        row['semantic_passed'] = True
        self.assertEqual(classify_attempt(row, 2), 'BUSINESS_SEMANTICS_PASS_ONLY')

    def test_missing_query_or_failed_certificate_cannot_pass(self):
        row = dict(track='NBIB_CONTROLLED_REVISION', transport_complete=True, contract_passed=True,
                   query_count=1, semantic_passed=True, expected_decision_passed=True,
                   point_present=True, point_replay_passed=False)
        self.assertEqual(classify_attempt(row, 2), 'QUERY_COVERAGE_FAILURE')
        row['query_count'] = 2
        self.assertEqual(classify_attempt(row, 2), 'CERTIFICATE_FAILURE')

    def test_failures_and_versions_never_collapse_to_best_of(self):
        base = dict(run_id='r1', case_id='H25-service_arm', track='SYNTHETIC_REGRESSION',
                    adapter_version='a', profile_sha256='profile-a', prompt_sha256='x', transport_complete=True,
                    contract_passed=True, query_count=1, semantic_passed=True,
                    expected_decision_passed=True, point_present=True, point_replay_passed=True)
        rows = [base, {**base, 'run_id':'r2', 'semantic_passed':False},
                {**base, 'run_id':'r3', 'adapter_version':'b', 'transport_complete':False}]
        summary = summarize_attempts(rows)
        self.assertEqual(len(summary), 2)
        self.assertEqual(summary[0]['status_counts'], {'PASS':1, 'SEMANTIC_FAILURE':1})
        self.assertEqual(summary[1]['status_counts'], {'TRANSPORT_FAILURE':1})
        with self.assertRaisesRegex(ValueError, 'DUPLICATE_ATTEMPT'):
            summarize_attempts([base, base])

    def test_one_profile_can_score_different_question_prompts_together(self):
        base = dict(run_id='r1', case_id='H25-service_arm', track='SYNTHETIC_REGRESSION',
                    adapter_version='a', profile_sha256='same-frozen-pipeline', prompt_sha256='input-one',
                    transport_complete=False)
        second = {**base, 'run_id':'r2', 'case_id':'H25-factory_arm', 'prompt_sha256':'input-two'}
        summary = summarize_attempts([base, second])
        self.assertEqual(len(summary), 1)
        self.assertEqual(summary[0]['attempts'], 2)
        self.assertEqual({r['prompt_sha256'] for r in summary[0]['rows']}, {'input-one','input-two'})


if __name__ == '__main__':
    unittest.main()
