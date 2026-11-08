"""Only adds maintenance-level tests. No changes to existing identification theorems."""
from __future__ import annotations
from pathlib import Path
from contextlib import redirect_stdout
from io import StringIO
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch
import json
import subprocess

from examples.minimal_r3_a4_representation_ablation import generate
from scripts.audit_r3_representation_boundaries import summarize
from scripts import diagnose_legacy_pfn_smoke as smoke


class MinimalCoreMaintenanceDiagnostics(TestCase):
    def test_one_r3_target_same_full_factorized_one_component_mixture(self):
        evidence=generate()
        self.assertEqual(set(evidence['representations']),
                         {'full','factorized','mixture_single_component'})
        for result in evidence['representations'].values():
            self.assertEqual(result['status'],'POINT')
            self.assertTrue(result['theorem_replay'])
            self.assertEqual(result['arm_support'],['1/8','3/8'])
        self.assertTrue(all(evidence['cross_representation_equivalence'].values()))
        self.assertEqual(evidence['ablation']['remove_exchangeability'],'NEEDS_INPUT')
        self.assertEqual(evidence['ablation']['replace_A4_with_sample_only'],'NEEDS_INPUT')
        self.assertFalse(evidence['scientific_assumptions_verified_in_real_world'])
        self.assertFalse(evidence['estimation_performed'])

    def test_locked_r3_minimal_golden_snapshot(self):
        path=Path(__file__).resolve().parents[1]/'assets/benchmark_assets_stabilization'/'minimal_r3_representation_expected.json'
        expected=json.loads(path.read_text(encoding='utf-8'))
        self.assertEqual(generate(),expected)

    def test_readonly_r3_module_audit_and_target_separation(self):
        result=summarize()
        self.assertEqual(len(result['records']),7)
        self.assertEqual(len({r['file'] for r in result['records']}),7)
        self.assertIn('NODEWISE_ADJUSTED',result['distinct_causal_target_classes'])
        self.assertEqual(result['decision'],'FREEZE_ALGORITHMS_RETAIN_DISTINCT_VERIFIERS_FOR_NOW')
        self.assertTrue(all(r['lines']>20 for r in result['records']))

    def test_pfn_timeout_results_in_explicit_failure_not_pass(self):
        with TemporaryDirectory() as tmp:
            report=Path(tmp)/'report.json'
            timeout=subprocess.TimeoutExpired(cmd=['test'],timeout=0.001,output=b'CFM_PHASE_BEGIN train_model\n')
            with patch.object(smoke.subprocess,'run',side_effect=timeout):
                with redirect_stdout(StringIO()):
                    code=smoke.main(['--report',str(report),'--timeout','0.01','--stack-after','0.005'])
            value=json.loads(report.read_text())
            self.assertEqual(code,124)
            self.assertEqual(value['status'],'TIMEOUT')
            self.assertIn('CFM_PHASE_BEGIN train_model',value['phase_events'])
            self.assertIn('CFM_WATCHDOG_TIMEOUT',report.with_suffix('.log').read_text())

    def test_pfn_success_needs_exit_zero(self):
        with TemporaryDirectory() as tmp:
            report=Path(tmp)/'report.json'
            fake=subprocess.CompletedProcess(args=['test'],returncode=1,stdout='CFM_PHASE_BEGIN train_model\nFAIL')
            with patch.object(smoke.subprocess,'run',return_value=fake):
                with redirect_stdout(StringIO()):
                    code=smoke.main(['--report',str(report)])
            self.assertEqual(code,1)
            self.assertEqual(json.loads(report.read_text())['status'],'FAIL')
