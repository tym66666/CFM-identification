"""Regression for the small bounded PFN diagnostic, NOT a model evaluation.

Synthetic subprocess results make timeout/failure behavior deterministic while the
actual smoke test is exercised independently via the maintenance CLI.
"""
from __future__ import annotations

from contextlib import redirect_stdout, redirect_stderr
from io import StringIO
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from scripts import diagnose_legacy_pfn_smoke as diag


def successful_output(*, full=False):
    test=diag.DEFAULT_TEST if not full else 'tests.test_pipeline_smoke'
    n=9 if full else 1
    return (f'CFM_TEST {test}\nCFM_PHASE_BEGIN train_model\n'
            'CFM_PHASE_END train_model 1.0\n'
            'CFM_PHASE_BEGIN evaluate_checkpoint\n'
            'CFM_PHASE_END evaluate_checkpoint 0.1\n'
            f'Ran {n} test'+('s' if full else '')+' in 2.0s\n\nOK\n')


class MinimalPfnDiagnosticAblation(unittest.TestCase):
    def run_fake(self, completed, *args):
        with tempfile.TemporaryDirectory() as directory:
            report=Path(directory)/'trial.json'
            with patch.object(diag.subprocess,'run',side_effect=completed) as runner:
                with redirect_stdout(StringIO()):
                    ret=diag.main(['--report',str(report),*args])
            return ret,json.loads(report.read_text()),report.with_suffix('.log').read_text(),runner.call_args_list

    def test_actual_success_needs_test_count_and_stage_end_markers(self):
        result=subprocess.CompletedProcess(args=['child'],returncode=0,stdout=successful_output())
        code,data,log,calls=self.run_fake([result])
        self.assertEqual(code,0)
        self.assertEqual(data['status'],'PASS')
        self.assertEqual(data['repetitions'],1)
        self.assertEqual(len(data['runs'][0]['phase_events']),4)
        self.assertIn('Ran 1 test',log)
        self.assertEqual(calls[0].kwargs['timeout'],120)
        self.assertEqual(data['thread_env']['OMP_NUM_THREADS'],'1')

    def test_unittest_exit_zero_without_replay_evidence_not_pass(self):
        result=subprocess.CompletedProcess(args=['child'],returncode=0,stdout='OK\n')
        code,data,_,_=self.run_fake([result])
        self.assertEqual(code,1)
        self.assertEqual(data['status'],'FAIL')
        self.assertIn('CFM_PHASE_END evaluate_checkpoint ',data['runs'][0]['missing_success_markers'])

    def test_failed_run_is_never_counted_as_pass_despite_markers(self):
        result=subprocess.CompletedProcess(args=['child'],returncode=1,stdout=successful_output())
        code,data,_,_=self.run_fake([result])
        self.assertEqual(code,1)
        self.assertEqual(data['status'],'FAIL')

    def test_two_fresh_subprocesses_and_aggregated_success(self):
        fake=subprocess.CompletedProcess(args=['child'],returncode=0,stdout=successful_output(full=True))
        code,data,log,calls=self.run_fake([fake,fake],'--test','full','--repetitions','2')
        self.assertEqual(code,0)
        self.assertEqual(data['status'],'PASS')
        self.assertEqual([r['repetition'] for r in data['runs']],[1,2])
        self.assertEqual(len(calls),2)
        self.assertIn('REPETITION 2 / 2',log)
        self.assertEqual(data['test'],'tests.test_pipeline_smoke')

    def test_second_run_times_out_even_if_first_passes(self):
        fake=subprocess.CompletedProcess(args=['child'],returncode=0,stdout=successful_output())
        timeout=subprocess.TimeoutExpired(cmd=['child'],timeout=.01,output=b'CFM_PHASE_BEGIN train_model\n')
        code,data,log,_=self.run_fake([fake,timeout],'--repetitions','2','--timeout','.01')
        self.assertEqual(code,124)
        self.assertEqual(data['status'],'TIMEOUT')
        self.assertEqual([r['status'] for r in data['runs']],['PASS','TIMEOUT'])
        self.assertIn('CFM_WATCHDOG_TIMEOUT',log)

    def test_inherited_thread_mode_preserves_environment_values(self):
        fake=subprocess.CompletedProcess(args=['child'],returncode=0,stdout=successful_output())
        with patch.dict(os.environ,{'OMP_NUM_THREADS':'3','MKL_NUM_THREADS':'4','OPENBLAS_NUM_THREADS':'5'}):
            code,data,_,calls=self.run_fake([fake],'--thread-mode','inherited')
        self.assertEqual(code,0)
        self.assertEqual(data['thread_env'],{'OMP_NUM_THREADS':'3','MKL_NUM_THREADS':'4','OPENBLAS_NUM_THREADS':'5'})
        self.assertEqual(calls[0].kwargs['env']['OMP_NUM_THREADS'],'3')
        self.assertEqual(data['thread_mode'],'inherited')

    def test_repetitions_bound_is_enforced(self):
        with tempfile.TemporaryDirectory() as directory:
            with redirect_stdout(StringIO()),redirect_stderr(StringIO()),self.assertRaises(SystemExit) as err:
                diag.main(['--report',str(Path(directory)/'x.json'),'--repetitions','11'])
            self.assertEqual(err.exception.code,2)


if __name__=='__main__':
    unittest.main()
