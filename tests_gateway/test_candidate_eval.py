"""Offline software probes and uns cored expert mathematical review checks."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from evaluation.candidate_reasoning_eval import (
    run_offline_probes,run_probe,expert_worksheet,score_expert_worksheet,FROZEN,
)

ROOT=Path(__file__).resolve().parents[1]

class CandidateEvaluationV011Tests(unittest.TestCase):
    def test_19_separate_safety_probes(self):
        x=run_offline_probes()
        self.assertEqual(x['probes_total'],19)
        self.assertEqual(x['probes_passed'],19)
        self.assertEqual(x['online_api_calls'],0)
        self.assertFalse(x['actual_math_core_called'])
        self.assertEqual(x['mathematical_candidate_formula_verification'],'NOT_PERFORMED')

    def test_oracle_is_not_proof_of_llm_candidate(self):
        x=run_offline_probes()
        self.assertEqual(x['mathematical_oracle_sanity_checks'],8)
        self.assertEqual(x['mathematical_oracle_sanity_passed'],8)
        self.assertTrue(x['reference_oracles_are_not_candidate_proof'])

    def test_expert_template_is_unscored(self):
        report,_=run_probe()
        w=expert_worksheet(report.model_dump(mode='json'))
        self.assertEqual(w['mathematical_certification'],'NOT_PERFORMED')
        self.assertEqual(len(w['entries']),1)
        self.assertTrue(all(v is None for v in w['entries'][0]['ratings'].values()))
        summary=score_expert_worksheet(w)
        self.assertTrue(all(x['positive_rate'] is None for x in summary['scores'].values()))

    def test_expert_worksheet_only_real_boolean(self):
        report,_=run_probe()
        w=expert_worksheet(report.model_dump(mode='json'))
        key='formula_is_mathematically_valid_under_stated_conditions'
        w['entries'][0]['ratings'][key]=True
        summary=score_expert_worksheet(w)
        self.assertEqual(summary['scores'][key]['reviewed'],1)
        self.assertEqual(summary['scores'][key]['positive_rate'],1)
        w['entries'][0]['ratings'][key]='True'
        with self.assertRaises(ValueError):score_expert_worksheet(w)

    def test_bad_scoring_template_rejected(self):
        with self.assertRaises(ValueError):score_expert_worksheet({'kind':'FAKE','entries':[]})

    def test_fixtures_are_part_of_evaluation_package(self):
        self.assertTrue((FROZEN/'a0_quality_report.json').exists())
        self.assertTrue((FROZEN/'mock_candidate_q2.json').exists())

    def test_cli_offline_evaluation(self):
        with tempfile.TemporaryDirectory() as d:
            output=Path(d)/'report.json';worksheet=Path(d)/'human.json'
            cmd=[sys.executable,'-m','evaluation.candidate_reasoning_eval',
                 '--output',str(output),'--worksheet',str(worksheet)]
            p=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True)
            self.assertEqual(p.returncode,0,p.stderr)
            x=json.loads(output.read_text(encoding='utf-8'))
            self.assertEqual(x['probes_passed'],19)
            self.assertTrue(worksheet.exists())

if __name__=='__main__':unittest.main()
