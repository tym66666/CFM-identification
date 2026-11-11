"""Small regressions for observed Task2 false passes and frozen-input writes."""
from copy import deepcopy
import base64
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from evaluation.literature_cases.tools.public_input import load_public, PUBLIC
from evaluation.literature_cases.tools.score_benchmark import classify, read_jsonl
from evaluation.literature_cases.tools import reference_fixture
from cfm_id_llm.document_intake import create_intake, AttachmentRequestV07, AttachmentError, MAX_ATTACHMENTS
from cfm_id_llm.network_files import load_network, NetworkFileError


class LiteratureExecutionEvidenceTest(unittest.TestCase):
    def reference(self, state="PARTIAL", count=1):
        return dict(expected_runtime_state=state, expected_query_count=count,
                    input_sha256={"business_question.md": "frozen"},
                    expected_interval=["1/5", "1"])

    def row(self):
        return dict(transport_complete=True, contract_passed=True, query_count=1,
                    semantic_passed=True, expected_decision_passed=True,
                    point_present=False, point_replay_passed=True,
                    input_sha256={"business_question.md": "frozen"},
                    semantic_review=dict(reviewer="test reviewer", evidence="checked frozen source",
                                         input_sha256={"business_question.md": "frozen"},
                                         query_ids=["q1"], candidate_repaired=False),
                    query_results=[dict(query_id="q1", result={})])

    def test_legacy_flags_cannot_pass_missing_or_wrong_evidence(self):
        row=self.row()
        self.assertEqual(classify(row,self.reference()),"MATHEMATICAL_EVIDENCE_FAILURE")
        self.assertEqual(classify(row,self.reference("POINT",3)),"QUERY_COVERAGE_FAILURE")
        row["query_results"][0]["result"]={"state":"NEEDS_INPUT"}
        self.assertEqual(classify(row,self.reference("POINT")),"MATHEMATICAL_EVIDENCE_FAILURE")

    def test_recorded_partial_requires_intact_certificate_and_reference_interval(self):
        folder=PUBLIC.parents[0]/"research_only/LIT-NET-04/structured_runs/original"
        outcome=json.loads((folder/"result.json").read_text("utf8"))
        row=self.row();row["query_results"][0]["result"]=outcome
        # The student's compact historical file dropped backend_called. It is
        # incomplete evidence and must fail. The next line makes a test double,
        # not a correction of the archived run or a real accuracy observation.
        self.assertEqual(classify(row,self.reference()),"MATHEMATICAL_EVIDENCE_FAILURE")
        outcome["backend_called"]=True
        self.assertEqual(classify(row,self.reference()),"PASS_RECORDED_EVIDENCE")
        for part in ("certificate","independent_replay"):
            bad=deepcopy(row);bad["query_results"][0]["result"].pop(part)
            self.assertEqual(classify(bad,self.reference()),"MATHEMATICAL_EVIDENCE_FAILURE")
        wrong=self.reference();wrong["expected_interval"]=["0","1"]
        self.assertEqual(classify(row,wrong),"MATHEMATICAL_EVIDENCE_FAILURE")

    def test_same_status_alone_does_not_validate_correct_stop(self):
        row=self.row();q=row["query_results"][0];q["result"]={"state":"NEEDS_INPUT"}
        self.assertEqual(classify(row,self.reference("NEEDS_INPUT")),"STOP_REASON_NOT_SCORED")
        q.update(stop_reason_reviewed=True,stop_reason_evidence="peer order explicitly undecided")
        self.assertEqual(classify(row,self.reference("NEEDS_INPUT")),"PASS_RECORDED_EVIDENCE")
        q["result"]["backend_called"]=True
        self.assertEqual(classify(row,self.reference("NEEDS_INPUT")),"STOP_INCORRECTLY_CERTIFIED")

    def test_two_dag_values_need_semantic_coverage_not_just_query_count(self):
        row=self.row();q=row["query_results"][0]
        q.update(result={"state":"NEEDS_INPUT"},stop_reason_reviewed=True,stop_reason_evidence="missing graph")
        ref=self.reference("NEEDS_INPUT");ref.update(allowed_query_counts=[1,2],required_target_ids=["do_0","do_1"])
        row["semantic_review"]["target_coverage"]={"q1":["do_1"]}
        self.assertEqual(classify(row,ref),"QUERY_COVERAGE_FAILURE")
        row["semantic_review"]["target_coverage"]={"q1":["do_0","do_1"]}
        self.assertEqual(classify(row,ref),"PASS_RECORDED_EVIDENCE")

    def test_corrupt_jsonl_stays_in_denominator(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/"attempts.jsonl";p.write_text('{}\n{broken\n[]\n',"utf8")
            rows=read_jsonl(p)
            self.assertEqual(len(rows),3)
            self.assertEqual(rows[1],{"parse_error_line":2})
            self.assertEqual(classify(rows[1],{}),"INVALID_JSON_RECORD")

    def test_malformed_nested_evidence_is_rejected(self):
        row=self.row();row["semantic_review"]="not a review"
        self.assertEqual(classify(row,self.reference()),"SEMANTICS_NOT_SCORED")
        row=self.row();row["query_results"][0]["result"]="not an outcome"
        self.assertEqual(classify(row,self.reference()),"QUERY_EVIDENCE_MISSING")
        row=self.row();row["semantic_review"]["target_coverage"]={"q1":[{}]}
        ref=self.reference();ref["required_target_ids"]=["do_0","do_1"]
        self.assertEqual(classify(row,ref),"QUERY_COVERAGE_NOT_SCORED")

    def test_loader_uses_changed_public_text_without_mutating_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);folder=root/"LIT-NET-04/original"
            shutil.copytree(PUBLIC/"LIT-NET-04/original",folder)
            p=folder/"business_question.md";p.write_text("另一个明确的业务问题。","utf8")
            before={x.name:hashlib.sha256(x.read_bytes()).hexdigest() for x in folder.iterdir()}
            loaded=load_public("LIT-NET-04","original",public_root=root)
            self.assertEqual(loaded["payload"]["question"],p.read_text("utf8"))
            self.assertEqual(loaded["input_sha256"]["business_question.md"],before[p.name])
            after={x.name:hashlib.sha256(x.read_bytes()).hexdigest() for x in folder.iterdir()}
            self.assertEqual(before,after)
            with self.assertRaises(ValueError):load_public("../outside","original",public_root=root)

    def test_ten_real_attachments_accepted_eleven_rejected(self):
        self.assertEqual(MAX_ATTACHMENTS,10)
        with tempfile.TemporaryDirectory() as tmp:
            requests=[]
            for i in range(11):
                p=Path(tmp)/f"note{i}.txt";p.write_text(f"第{i}份研究材料。","utf8")
                requests.append(AttachmentRequestV07(path=str(p),label=p.name))
            self.assertTrue(create_intake(case_id="ten-files",business_question="研究问题是什么？",attachments=requests[:10]))
            with self.assertRaises(AttachmentError):
                create_intake(case_id="eleven-files",business_question="研究问题是什么？",attachments=requests)

    def test_student_network_headers_preserve_declared_structure(self):
        folder=PUBLIC/"LIT-NET-04/original"
        declaration=json.loads((folder/"submission_manifest.json").read_text("utf8"))["network_upload"]["declaration"]
        network=load_network(folder/"units.csv",folder/"network_edges.csv",declaration)
        self.assertEqual(len(network.nodes),4);self.assertEqual(len(network.edges),6)
        with self.assertRaises(NetworkFileError):load_network(folder/"units.csv",folder/"network_edges.csv",None)

    def test_fixture_output_cannot_overwrite_source_or_history(self):
        from types import SimpleNamespace
        with self.assertRaises(ValueError):
            reference_fixture.output(SimpleNamespace(reference_fixture=True,output=PUBLIC),PUBLIC.parents[2])


if __name__=="__main__":
    unittest.main()
