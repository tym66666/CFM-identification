"""v3.0 independent integration and presentation invariants, no PFN training."""
import base64
from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest
from pydantic import ValidationError

from cfm_id_llm.candidate_queries import CandidateSafetyError
from cfm_id.local_demo import intake_request, UnsafeIntake
from examples.build_supervisor import build_payload, render, STEM, COVER
from examples.run_candidate_real_core import synthetic_env, run_example

class V30TrustedGatewayCore(unittest.TestCase):
    def test_proven_point_and_gap_control_candidate(self):
        for off in (True,False):
            _,_,_,r,calls,lookups,real=run_example(off_support=off)
            self.assertEqual(lookups,['q1','q2'])
            self.assertEqual(real['q1']['status'],'POINT')
            self.assertEqual(real['q1']['verification_level'],'CORE_REPLAY_VERIFIED')
            self.assertEqual(real['q2']['status'],'UNSUPPORTED' if off else 'POINT')
            self.assertEqual(calls,1 if off else 0)
            self.assertTrue(all(x.mathematical_certificate is None for x in r.results))
            self.assertFalse(r.estimation_handoff_allowed)
    def test_no_independent_business_approval_blocks_before_theorem(self):
        case,q,review,port=synthetic_env(off_support=False)
        b=port.bindings['q2'];port.bindings['q2']=replace(b,business_intent=None)
        with self.assertRaises(CandidateSafetyError):port.lookup(case=case,quality=q,review=review,query_id='q2')
        self.assertEqual(port.calls,[])
    def test_no_evidence_manifest_blocks_before_theorem(self):
        case,q,review,port=synthetic_env(off_support=False)
        b=port.bindings['q2'];port.bindings['q2']=replace(b,evidence_manifest=None)
        with self.assertRaises(CandidateSafetyError):port.lookup(case=case,quality=q,review=review,query_id='q2')
        self.assertEqual(port.calls,[])
    def test_inconsistent_business_coordinates_cannot_be_reapproved_by_scientist(self):
        case,q,review,port=synthetic_env(off_support=False)
        b=port.bindings['q2'];intent=b.business_intent
        changed=intent.model_copy(update={'binding_coordinates':{**intent.binding_coordinates,'assignment':[1,0,0]}})
        port.bindings['q2']=replace(b,business_intent=changed)
        with self.assertRaises(CandidateSafetyError):port.lookup(case=case,quality=q,review=review,query_id='q2')
        self.assertEqual(port.calls,[])
    def test_stale_a4_evidence_rejected(self):
        case,q,review,port=synthetic_env(off_support=False)
        b=port.bindings['q1'];bad=b.evidence_manifest.model_copy(update={'a4_typed_sources_digest':'0'*64})
        port.bindings['q1']=replace(b,evidence_manifest=bad)
        with self.assertRaises(CandidateSafetyError):port.lookup(case=case,quality=q,review=review,query_id='q1')
        self.assertEqual(port.calls,[])

class V30SafeUserIntake(unittest.TestCase):
    def case(self,files=None):return {'business_question':'这次团队 AI 试验是否影响同事销售表现？','requirements':'先审查研究设计','attachments':files or []}
    def upload(self,name,content):return {'filename':name,'data_base64':base64.b64encode(content).decode()}
    def test_text_intake_returns_no_certification(self):
        res=intake_request(self.case([self.upload('说明.txt','固定合作网络'.encode())]))
        self.assertFalse(res['llm_called']);self.assertFalse(res['core_called']);self.assertFalse(res['point_certified'])
        self.assertEqual(res['status'],'REVIEW_REQUIRED_NO_IDENTIFICATION')
        self.assertEqual(len(res['attachments']),1)
    def test_csv_is_schema_only(self):
        res=intake_request(self.case([self.upload('data.csv',b'user_id,treatment,y\n1,1,500\n')]))
        self.assertEqual(res['attachments'][0]['mode'],'SCHEMA_ONLY')
        self.assertFalse(res['point_certified'])
    def test_invalid_suffix_rejected(self):
        with self.assertRaises(UnsafeIntake):intake_request(self.case([self.upload('bad.exe',b'something')]))
    def test_path_traversal_filename_rejected(self):
        with self.assertRaises(UnsafeIntake):intake_request(self.case([self.upload('../bad.txt',b'x')]))
    def test_result_status_cannot_be_uploaded_as_verified(self):
        with self.assertRaises(UnsafeIntake):intake_request({**self.case(),'POINT':True})
    def test_unsafe_base64_refused(self):
        with self.assertRaises(UnsafeIntake):intake_request(self.case([{'filename':'notes.txt','data_base64':'@@@'}]))

class V30Display(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.data=build_payload()
    def test_case_count_and_core_invariants(self):
        d=self.data;self.assertEqual(len(d['core_cases']),27)
        self.assertEqual(d['summary'],{'POINT':9,'NEEDS_INPUT':10,'UNSUPPORTED':8})
        self.assertTrue(all(x['proof']['replay_verified'] for x in d['core_cases'] if x['identification']['status']=='POINT'))
        self.assertFalse(d['candidate_demo']['online_llm_called'])
        self.assertEqual(d['candidate_demo']['off_support_model_calls'],1)
        self.assertEqual(d['candidate_demo']['supported_model_calls'],0)
    def test_partial_only_research(self):
        self.assertFalse(self.data['research_partial']['proof']['replay_verified'])
        self.assertEqual(self.data['research_partial']['identification']['sharp_width'],'1/7')
    def test_coverage_map_kept_and_no_claim_of_majority(self):
        d=self.data['coverage'];self.assertEqual(len(d['designs']),6)
        self.assertEqual(len(d['exposures']),5);self.assertEqual(len(d['topologies']),9)
        self.assertEqual(len(d['scenarios']),16)
    def test_deterministic_rebuild_html_and_json(self):
        with tempfile.TemporaryDirectory() as a,tempfile.TemporaryDirectory() as b:
            a=render(Path(a));b=render(Path(b));self.assertEqual([p.read_bytes() for p in a],[p.read_bytes() for p in b])
            html=a[1].read_text(encoding='utf-8')
            self.assertIn('可以确定',html);self.assertIn('业务问题',html)
            self.assertIn('为什么得到这个结果',html)
            self.assertNotIn('https://cdn.',html)
            self.assertNotIn('</script><script>alert',html)

if __name__=='__main__':unittest.main()
