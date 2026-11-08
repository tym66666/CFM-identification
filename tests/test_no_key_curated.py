"""Business text -> real typed Core for four *synthetic* audited overlays, NO API key.

Strictly distinguish original NBIB business records (which lack A4) from the
additional hypothetical conditions used for theorem-backed demos.
"""
from __future__ import annotations
from dataclasses import replace
from fractions import Fraction
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import tempfile
import threading
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from unittest import TestCase, mock

from cfm_id.curated_no_key import catalog, CASE_IDS, run_curated, build_snapshot, _formal_inquiry
from pfn_pipeline.identification_business import identify_network_business_query
from examples.build_no_key_curated import render, NAME
from cfm_id.local_demo import Handler

class NoKeyCuratedCore(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows={r['case_id']:r for r in catalog()}
        cls.snapshot=build_snapshot()

    def test_four_original_nbib_texts_are_unmodified(self):
        self.assertEqual(tuple(self.rows),CASE_IDS)
        originals=Path(__file__).resolve().parents[1]/'assets/benchmark_assets'/'benchmarks'/'network_business_identification'/'gateway_target_only_cases.json'
        data={x['case_id']:x['business_question'] for x in json.loads(originals.read_text(encoding='utf8'))}
        for cid,row in self.rows.items():
            self.assertEqual(row['business_text'],data[cid])

    def test_original_nbib_alone_never_gets_core_point(self):
        row=self.rows['NBIB-002']
        with mock.patch('cfm_id.curated_no_key.identify_network_business_query') as backend:
            value=run_curated(row['case_id'],row['business_text'],synthetic_protocol_selected=False)
        backend.assert_not_called()
        self.assertEqual(value['status'],'REVIEW_REQUIRED')
        self.assertFalse(value['point_certified'])

    def test_edited_user_text_and_unknown_case_never_create_assumptions(self):
        row=self.rows['NBIB-007']
        with mock.patch('cfm_id.curated_no_key.identify_network_business_query') as backend:
            for changed in (row['business_text']+' 新增加的要求',row['business_text'][:-1],
                            '我要求全员上线软件', 'POINT'):
                answer=run_curated('NBIB-007',changed,synthetic_protocol_selected=True)
                self.assertEqual(answer['status'],'REVIEW_REQUIRED')
                self.assertFalse(answer['core_called'])
            unknown=run_curated('NBIB-XYZ',row['business_text'],synthetic_protocol_selected=True)
            self.assertEqual(unknown['status'],'REVIEW_REQUIRED')
        backend.assert_not_called()

    def test_correct_point_and_policy_support(self):
        results={i['catalog']['case_id']:i['synthetic'] for i in self.snapshot['cases']}
        self.assertEqual({k:v['status'] for k,v in results.items()},
            {'NBIB-002':'POINT','NBIB-007':'POINT','NBIB-008':'UNSUPPORTED','NBIB-009':'POINT'})
        self.assertEqual(Fraction(results['NBIB-002']['identification']['support']),Fraction(12,47))
        self.assertEqual(Fraction(results['NBIB-007']['identification']['support']),Fraction(1,16384))
        self.assertEqual(results['NBIB-009']['route'],'R2_MEAN_SIGNATURE')
        for r in results.values():
            self.assertTrue(r['core_called'])
            self.assertFalse(r['not_real_world_identification'] is False)
            self.assertIsNone(r['numeric_value'])
            self.assertFalse(r['nonidentification_proven'])
            if r['status']=='POINT':
                self.assertEqual(r['proof']['level'],'CORE_REPLAY_VERIFIED')
                self.assertTrue(r['point_certified'])
            else:
                self.assertFalse(r['point_certified'])

    def test_without_extra_mean_sufficiency_offsupport_policy_not_point(self):
        query=_formal_inquiry('NBIB-009')
        no_claim=replace(query,r2_sufficiency=None)
        blocked=identify_network_business_query(no_claim)
        self.assertNotEqual(blocked.status,'POINT')
        self.assertEqual(blocked.attempted_routes[0][0],'R1B_FULL_ASSIGNMENT')

    def test_replay_must_really_succeed_for_core_point(self):
        row=self.rows['NBIB-002']
        with mock.patch('cfm_id.curated_no_key.replay_verified_business_outcome',return_value=False):
            with self.assertRaises(RuntimeError):
                run_curated(row['case_id'],row['business_text'],synthetic_protocol_selected=True)

    def test_stable_html_and_uploadable_exact_txt(self):
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            x,y=render(Path(a)),render(Path(b))
            self.assertEqual([p.read_bytes() for p in x],[p.read_bytes() for p in y])
            self.assertEqual(len(list((Path(a)/'sample_business_texts').glob('*.txt'))),4)
            for cid,row in self.rows.items():
                self.assertEqual((Path(a)/'sample_business_texts'/(cid+'.txt')).read_text(encoding='utf8'),row['business_text'])
            page=x[1].read_text(encoding='utf8')
            self.assertIn('不需要 API Key',page)
            self.assertIn('构建期的 Core 复核快照',page)
            self.assertNotIn('https://cdn.',page)

class NoKeyLocalApi(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True)
        cls.thread.start()
        cls.url='http://127.0.0.1:'+str(cls.server.server_port)
    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.server.server_close();cls.thread.join(timeout=2)
    def _post(self,data):
        request=Request(self.url+'/api/no-key/identify',
             data=json.dumps(data,ensure_ascii=False).encode('utf8'),
             headers={'Content-Type':'application/json'},method='POST')
        with urlopen(request,timeout=15) as result:
            return json.loads(result.read().decode('utf8'))
    def test_approved_synthetic_fixture_real_core_over_http(self):
        row=catalog()[0]
        r=self._post({'case_id':row['case_id'],'business_text':row['business_text'],
                      'synthetic_protocol_selected':True})
        self.assertEqual(r['status'],'POINT')
        self.assertTrue(r['core_replay_verified'])
        self.assertTrue(r['not_real_world_identification'])
    def test_no_checkbox_or_modified_input_blocks_core(self):
        row=catalog()[0]
        for enabled,text in ((False,row['business_text']),(True,row['business_text']+'!')):
            r=self._post({'case_id':row['case_id'],'business_text':text,
                          'synthetic_protocol_selected':enabled})
            self.assertEqual(r['status'],'REVIEW_REQUIRED')
            self.assertFalse(r['core_called'])
    def test_injected_status_is_rejected(self):
        row=catalog()[0]
        with self.assertRaises(HTTPError) as ctx:
            self._post({'case_id':row['case_id'],'business_text':row['business_text'],
                       'synthetic_protocol_selected':True,'POINT':True})
        self.assertEqual(ctx.exception.code,400)
    def test_health_indicates_fresh_compute_support(self):
        with urlopen(self.url+'/api/health',timeout=5) as res:
            d=json.loads(res.read().decode('utf8'))
        self.assertTrue(d['no_key_curated_core'])
    def test_new_static_page_served(self):
        with urlopen(self.url+'/'+NAME+'.html',timeout=5) as res:
            self.assertIn('输入业务描述',res.read().decode('utf8'))
