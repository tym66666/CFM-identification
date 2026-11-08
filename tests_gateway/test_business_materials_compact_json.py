import json
import sys
import time
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch
from evaluation import business_materials_target_precedence as old, business_materials_compact_json as new
from evaluation.business_materials_cases import fixtures
from tests_gateway.test_business_materials_plan_references import reference
from evaluation.budgeted_process_base import bounded_process, run_slot

class CompactContractTests(unittest.TestCase):
    def test_payload_schema_and_business_materials_unchanged(self):
        for c in fixtures():
            old_s,old_u=old.make_request(c['bundle']); new_s,new_u=new.make_request(c['bundle'])
            self.assertEqual(old_u,new_u)
            self.assertTrue(new_s.startswith(old_s))
            self.assertIn('所有必需字段仍必须保留',new_s)

    def test_target_coordinates_and_decisions_unchanged(self):
        for c in fixtures():
            raw=reference(c)
            self.assertEqual(old.project(c['bundle'],raw),new.project(c['bundle'],raw))
            a=old.evaluate_draft(c['bundle'],raw,c['packet'],synthetic_protocol_selected=True)
            b=new.evaluate_draft(c['bundle'],raw,c['packet'],synthetic_protocol_selected=True)
            a.pop('version'); b.pop('version'); self.assertEqual(a,b)

class ProcessDeadlineTests(unittest.TestCase):
    def fake_reserved_slot(self,root):
        out=root/'experiment'; out.mkdir()
        ledger_dir=root/'online_round2_20261019'; ledger_dir.mkdir()
        artifact=ledger_dir/'attempt2'; artifact.mkdir()
        prior={'attempt':1,'status':'COMPLETED','run_id':'earlier'}
        current={'attempt':2,'status':'IN_FLIGHT','run_id':'experiment_case','artifact_directory':'attempt2'}
        (ledger_dir/'REQUEST_LEDGER.json').write_text(json.dumps({'requests':[prior,current]}))
        (out/'EXPERIMENT_PLAN.json').write_text(json.dumps({'slots':{'case':{'case':'C','key':'key1','phase':'validation','stream':True}}}))
        for p in (out/'RUNNING.lock',ledger_dir/'RUNNING.lock'): p.write_text('')
        return out,ledger_dir,artifact,prior

    def test_timeout_preserves_budget_history_and_clears_only_own_locks(self):
        with tempfile.TemporaryDirectory() as t:
            out,ld,artifact,prior=self.fake_reserved_slot(Path(t))
            with patch('evaluation.budgeted_process_base.bounded_process',return_value=(None,True)):
                self.assertEqual(run_slot(out,'case',300).returncode,0)
            rows=json.loads((ld/'REQUEST_LEDGER.json').read_text())['requests']
            self.assertEqual(len(rows),2); self.assertEqual(rows[0],prior)
            self.assertEqual(rows[1]['error_code'],'PROCESS_WALL_DEADLINE')
            self.assertTrue((out/'case_pointer.json').exists())
            self.assertFalse((out/'RUNNING.lock').exists()); self.assertFalse((ld/'RUNNING.lock').exists())
            self.assertFalse(json.loads((artifact/'result.json').read_text())['core_called'])

    def test_complete_saved_result_survives_exit_time_race(self):
        with tempfile.TemporaryDirectory() as t:
            out,ld,artifact,prior=self.fake_reserved_slot(Path(t))
            (out/'case_pointer.json').write_text(json.dumps({'folder':str(artifact)}))
            ledger=json.loads((ld/'REQUEST_LEDGER.json').read_text()); ledger['requests'][1]['status']='COMPLETED'
            (ld/'REQUEST_LEDGER.json').write_text(json.dumps(ledger))
            (artifact/'result.json').write_text(json.dumps({'status':'COMPLETED'}))
            before=(ld/'REQUEST_LEDGER.json').read_bytes()
            with patch('evaluation.budgeted_process_base.bounded_process',return_value=(None,True)):
                self.assertEqual(run_slot(out,'case',300).returncode,0)
            self.assertEqual((ld/'REQUEST_LEDGER.json').read_bytes(),before)
            self.assertFalse((out/'RUNNING.lock').exists()); self.assertFalse((ld/'RUNNING.lock').exists())

    def test_hung_child_is_bounded(self):
        started=time.monotonic()
        result,expired=bounded_process([sys.executable,'-c','import time; time.sleep(20)'],0.3)
        self.assertTrue(expired); self.assertIsNone(result)
        self.assertLess(time.monotonic()-started,5)

    def test_completed_process_not_marked_timeout(self):
        result,expired=bounded_process([sys.executable,'-c','pass'],5)
        self.assertFalse(expired); self.assertEqual(result.returncode,0)

if __name__=='__main__': unittest.main()
