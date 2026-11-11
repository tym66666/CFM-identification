import json
import csv
import tempfile
from pathlib import Path
import unittest
from evaluation.task6.scripts.score_experiment import score
from evaluation.task6.scripts.fact_stage_ledger import run as fact_run

class ScorerContract(unittest.TestCase):
    def test_ledger_rejects_checkbox_only_positive(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)
            (p/'runs.json').write_text(json.dumps([dict(case_id='T6-N01-full',profile='prompt_only',repeat=1)]),encoding='utf8')
            fact_run(p)
            path=p/'fact_stage_template.csv'
            with path.open(encoding='utf-8-sig',newline='') as f: rows=list(csv.DictReader(f))
            row=rows[0]
            for key in ('fact_call_attempted','fact_wire_valid','a4_scope_correct','a5_stance_correct',
                        'source_claims_correct','original_target_preserved','missing_or_conflict_handled_correctly',
                        'researcher_approval_independent','first_pass_full_chain_correct'):
                row[key]='TRUE'
            row.update(wrong_certification='FALSE',actual_final_status='POINT',
                       reference_documentation='no execution artifact',reviewer_id='reviewer')
            for key in ('fact_api_calls','reread_api_calls','retry_api_calls','fact_prompt_tokens','fact_completion_tokens'): row[key]='0'
            with path.open('w',encoding='utf-8-sig',newline='') as f:
                writer=csv.DictWriter(f,fieldnames=row);writer.writeheader();writer.writerows(rows)
            with self.assertRaises(ValueError):fact_run(p,path)

    def test_missing_detection_not_dependent_on_other_review_items(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)
            r = dict(case_id='T6-N01-changed', repeat=1, api_called=True, raw_response_saved=True,
                     format_parse_success=True, canonical_query_count=1,
                     canonical_kinds=['FIXED_POLICY_VALUE'], wire_state='SEMANTIC_REVIEW_REQUIRED',
                     usage={}, profile='prompt_only')
            (p/'runs.json').write_text(json.dumps([r]), encoding='utf8')
            score(p)
            path = p/'review_template.csv'
            with path.open(encoding='utf-8-sig', newline='') as f:
                rows = list(csv.DictReader(f))
            for row in rows:
                row['judgment'] = 'PASS' if row['criterion'] == 'correct_missing_conflict_handling' else 'NOT_REVIEWED'
                if row['judgment'] == 'PASS': row['reviewer_id'] = 'researcher'
            with path.open('w', encoding='utf-8-sig', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=rows[0]); writer.writeheader(); writer.writerows(rows)
            score(p, path)
            group = json.loads((p/'scoring_report.json').read_text(encoding='utf8'))['profiles']['prompt_only']
            self.assertEqual(group['negative_cases_reviewed'], 1)
            self.assertEqual(group['negative_cases_correct_missing_or_conflict'], 1)
            self.assertIsNone(group['human_a0_accuracy_all_attempts'])

    def test_unreviewed_fullchain_does_not_count_as_failure_or_zero_wrong_certifications(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)
            rows = [dict(case_id='T6-N01-full', profile='prompt_only', repeat=n) for n in (1,2)]
            (p/'runs.json').write_text(json.dumps(rows), encoding='utf8')
            fact_run(p)
            path = p/'fact_stage_template.csv'
            with path.open(encoding='utf-8-sig', newline='') as f: records = list(csv.DictReader(f))
            flags = ('fact_call_attempted','fact_wire_valid','a4_scope_correct','a5_stance_correct',
                     'source_claims_correct','original_target_preserved','missing_or_conflict_handled_correctly',
                     'researcher_approval_independent','first_pass_full_chain_correct','wrong_certification')
            costs = ('fact_api_calls','reread_api_calls','retry_api_calls','fact_prompt_tokens','fact_completion_tokens')
            for row in records:
                for key in flags: row[key] = 'NOT_RUN'
                for key in costs: row[key] = '0'
            records[0].update(first_pass_full_chain_correct='FALSE', wrong_certification='FALSE', reviewer_id='researcher')
            with path.open('w', encoding='utf-8-sig', newline='') as f:
                writer=csv.DictWriter(f, fieldnames=records[0]); writer.writeheader(); writer.writerows(records)
            fact_run(p, path)
            report=json.loads((p/'fullchain_scoring_report.json').read_text(encoding='utf8'))
            self.assertEqual(report['fullchain_total_queries'], 2)
            self.assertEqual(report['fullchain_audited_queries'], 1)
            self.assertIsNone(report['first_pass_accuracy_all_queries'])
            self.assertIsNone(report['wrong_certification_count_all_queries'])

    def test_early_stop_needs_independent_reviewer(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)
            (p/'runs.json').write_text(json.dumps([dict(case_id='T6-N01-changed', profile='prompt_only', repeat=1)]), encoding='utf8')
            fact_run(p)
            path = p/'fact_stage_template.csv'
            with path.open(encoding='utf-8-sig', newline='') as f: rows = list(csv.DictReader(f))
            row=rows[0]
            for key in ('fact_call_attempted','fact_wire_valid','a4_scope_correct','a5_stance_correct',
                        'source_claims_correct','original_target_preserved','missing_or_conflict_handled_correctly',
                        'researcher_approval_independent','first_pass_full_chain_correct','wrong_certification'):
                row[key]='NOT_RUN'
            for key in ('fact_api_calls','reread_api_calls','retry_api_calls','fact_prompt_tokens','fact_completion_tokens'):
                row[key]='0'
            row.update(first_pass_full_chain_correct='TRUE',wrong_certification='FALSE',
                       missing_or_conflict_handled_correctly='TRUE', actual_final_status='REVIEWED_MISSING_STOP',
                       reference_documentation='documented issue',reviewer_id='reviewer')
            with path.open('w',encoding='utf-8-sig',newline='') as f:
                writer=csv.DictWriter(f,fieldnames=row); writer.writeheader(); writer.writerows(rows)
            with self.assertRaises(ValueError): fact_run(p,path)

    def test_does_not_claim_semantics_without_review(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)
            basic=dict(case_id='T6-N01-full',repeat=1,api_called=True,raw_response_saved=True,
                  format_parse_success=True,canonical_query_count=1,
                  canonical_kinds=['FIXED_POLICY_VALUE'],wire_state='SEMANTIC_REVIEW_REQUIRED',usage={})
            rows=[dict(basic,profile=x) for x in ('prompt_only','prompt_plus_skill')]
            (p/'runs.json').write_text(json.dumps(rows),encoding='utf8')
            score(p)
            r=json.loads((p/'scoring_report.json').read_text(encoding='utf8'))
            self.assertEqual(r['paired_complete_human_reviews'],0)
            for v in r['profiles'].values():
                self.assertEqual(v['attempted'],1)
                self.assertIsNone(v['human_a0_accuracy_all_attempts'])
            fact_run(p)
            self.assertTrue((p/'fact_stage_template.csv').exists())
    def test_invalid_format_not_success(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)
            rows=[dict(case_id='T6-N01-changed',repeat=1,api_called=True,raw_response_saved=False,
                       format_parse_success=False,wire_state='CALL_OR_PARSE_FAILED',usage={},profile='prompt_only')]
            (p/'runs.json').write_text(json.dumps(rows),encoding='utf8')
            score(p)
            r=json.loads((p/'scoring_report.json').read_text(encoding='utf8'))['profiles']['prompt_only']
            self.assertEqual(r['format_parsed'],0)
            self.assertEqual(r['query_count_correct_all_attempts'],0)
if __name__=='__main__':unittest.main()
