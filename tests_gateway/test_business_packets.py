"""Realistic business packets are synthetic, with *authored mock answers*."""
from __future__ import annotations
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from evaluation.business_packet_eval import FIXTURE_DIR, evaluate_packets, render_html
from cfm_id_llm.material_integrity import create_grounded_intake, review_grounded_intake
from cfm_id_llm.multisource_intake_cli import _load_manifest
from cfm_id_llm.formulator import ProblemFormulator
from cfm_id_llm.providers import MockProvider

ROOT=Path(__file__).resolve().parents[1]


class BusinessPacketTestsV08(unittest.TestCase):
    def test_eight_complete_packets(self):
        report=evaluate_packets()
        self.assertEqual(report['cases'],8)
        self.assertEqual(report['software_checks_pass'],8)
        self.assertEqual(report['evidence_kind'],'AUTHORED_MOCK_FIXTURES_NOT_ONLINE_LLM_ACCURACY')
        self.assertEqual(report['real_llm_calls'],0)
        self.assertEqual(report['mathematical_certificates'],0)

    def test_covers_multiple_industries(self):
        names={p.name for p in FIXTURE_DIR.iterdir() if p.is_dir()}
        self.assertTrue({'retail','platform','health','education','manufacturing'}<=names)

    def test_natural_business_questions_are_not_one_liners(self):
        for folder in FIXTURE_DIR.iterdir():
            if (folder/'case.json').exists():
                d=json.loads((folder/'case.json').read_text(encoding='utf-8'))
                if folder.name in {'retail','platform','health','education','manufacturing'}:
                    self.assertGreater(len(d['business_question']),90)
                self.assertGreaterEqual(len(d['attachments']),2)

    def test_benchmark_cannot_claim_mathematical_certification(self):
        report=evaluate_packets()
        for row in report['rows']:
            self.assertFalse(row['online_llm_called'])
            self.assertFalse(row['math_verified'])
        html=render_html(report)
        self.assertIn('不是在线 LLM 正确率',html)
        self.assertIn('数学识别证书',html)

    def test_all_mock_quotes_bind_to_actual_excerpts(self):
        for p in FIXTURE_DIR.iterdir():
            if not (p/'case.json').exists():
                continue
            cid, question, lang, files=_load_manifest(p/'case.json')
            intake=create_grounded_intake(case_id=cid,business_question=question,
                                         response_language=lang,attachments=files)
            raw=json.loads((p/'mock_draft.json').read_text(encoding='utf-8'))
            f=ProblemFormulator(MockProvider(raw)).formulate(intake.case)
            r=review_grounded_intake(intake,f)
            self.assertEqual(r.base.intake.case.case_id,cid)
            self.assertFalse(r.estimation_handoff_allowed)
            self.assertEqual(r.mathematical_verification,'NOT_PERFORMED')

    def test_expected_quality_warnings(self):
        report=evaluate_packets()
        records={r['industry']:r for r in report['rows']}
        self.assertIn('POTENTIAL_ASSIGNMENT_CONFLICT', records['protocol_conflict']['actual_quality_codes'])
        self.assertIn('POTENTIAL_NETWORK_TIMING_CONFLICT', records['network_timing_conflict']['actual_quality_codes'])
        self.assertIn('UNTRUSTED_DOCUMENT_INSTRUCTION', records['injected_attachment']['actual_quality_codes'])

    def test_benchmark_cli_writes_json_and_sanitized_html(self):
        with tempfile.TemporaryDirectory() as d:
            output=Path(d)/'result.json';page=Path(d)/'report.html'
            cmd=[sys.executable,'-m','evaluation.business_packet_eval',
                 '--output',str(output),'--html',str(page)]
            proc=subprocess.run(cmd,cwd=ROOT,timeout=45,text=True,capture_output=True)
            self.assertEqual(proc.returncode,0,proc.stderr)
            self.assertEqual(json.loads(output.read_text(encoding='utf-8'))['software_checks_pass'],8)
            page_content=page.read_text(encoding='utf-8')
            self.assertIn('真实 LLM 调用：<strong>0',page_content)

    def test_real_api_key_never_needed_for_fixture_benchmark(self):
        report=evaluate_packets()
        self.assertTrue(all(r['format_and_gate_pass'] for r in report['rows']))


if __name__=='__main__':
    unittest.main()
