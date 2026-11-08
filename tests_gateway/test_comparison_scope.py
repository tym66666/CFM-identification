"""Explicit question scope with original provenance and unchanged Core checks."""
from copy import deepcopy
from unittest.mock import patch
import unittest
from pydantic import ValidationError
import cfm_id_bridge.bridge as bridge
import pfn_pipeline.identification_business as core
from cfm_id import fixed_comparison as comparison
from cfm_id.intent_submission import submit
from cfm_id_bridge.scientific_binding import sha
from examples.fixed_comparison_fixture import public_bundle,reference,reviews,declared_targets,independent_oracle,CONTRACT


class ComparisonScopeTests(unittest.TestCase):
    def setUp(self):
        self.b=public_bundle();self.raw=reference(self.b)

    def call(self, options=None, raw=None):
        raw=self.raw if raw is None else raw
        options=reviews(self.b,raw,query_ids=['q2','q4']) if options is None else options
        with patch.object(bridge,'identify_network_business_query',wraps=bridge.identify_network_business_query) as bs,patch.object(core,'identify_network_business_query',wraps=core.identify_network_business_query) as ds:
            out=submit(self.b,raw,'FIXED_COMPARISON',contract=CONTRACT,**options)
        return out,(bs.call_count,ds.call_count)

    def assert_blocked(self,options,raw=None):
        out,counts=self.call(options,raw)
        self.assertEqual(counts,(0,0));self.assertFalse(out['core_called'])
        self.assertEqual(out['state'],'CHECK_BLOCKED')

    def test_wrong_complete_unreviewed_query_does_not_block_correct_queries(self):
        self.raw['reading']['questions']['q1']['first'].update(A=1,C=0)
        b0=deepcopy(self.b);r0=deepcopy(self.raw)
        out,counts=self.call()
        self.assertEqual(counts,(4,4));self.assertEqual(self.b,b0);self.assertEqual(self.raw,r0)
        self.assertEqual(out['reading_candidate'],r0)
        v={v['query_id']:v for v in out['query_views']}
        self.assertEqual([x['state'] for x in v.values()],['REVIEW_REQUIRED','CORE_POINT','NEEDS_INPUT','UNSUPPORTED','NEEDS_INPUT'])
        self.assertEqual(v['q1']['reason_code'],'COMPARISON_NOT_IN_REVIEW_SCOPE')
        self.assertEqual([x['query_id'] for x in out['identification']['results']],['q2','q4'])
        for q in ('q1','q3','q5'):
            self.assertFalse(v[q]['core_called']);self.assertNotIn('composition',v[q])
        self.assertTrue(independent_oracle(declared_targets(self.b)['q2'],v['q2']['composition'])['passed'])
        self.assertTrue(v['q2']['composition_replayed']);self.assertTrue(v['q2']['certificate_replayed'])
        self.assertEqual(v['q4']['endpoints']['second']['state'],'CORE_POINT')
        self.assertFalse(v['q4']['nonidentification_proved']);self.assertNotIn('composition',v['q4'])
        scope=out['comparison_review_scope']
        self.assertEqual(scope['full_bundle_sha256'],sha(b0));self.assertEqual(scope['full_reading_sha256'],sha(r0))

    def test_omission_does_not_claim_that_query_is_wrong(self):
        out,_=self.call()
        self.assertEqual(out['query_views'][0]['state'],'REVIEW_REQUIRED')
        self.assertNotIn('semantic_correct',out['query_views'][0])

    def test_each_singleton_is_independently_submittable(self):
        for q,expected in [('q1','CORE_POINT'),('q2','CORE_POINT'),('q4','UNSUPPORTED')]:
            with self.subTest(q=q):
                options=reviews(self.b,self.raw,query_ids=[q]);out,counts=self.call(options)
                self.assertEqual(counts,(2,2))
                self.assertEqual([(x['query_id'],x['state']) for x in out['identification']['results']],[(q,expected)])
                self.assertEqual([v['query_id'] for v in out['query_views'] if v['core_called']],[q])

    def test_including_wrong_target_still_blocks_selected_set_before_core(self):
        self.raw['reading']['questions']['q1']['first'].update(A=1,C=0)
        self.assert_blocked(reviews(self.b,self.raw,query_ids=['q1','q2']))

    def test_old_all_ready_review_keeps_old_behavior(self):
        out,counts=self.call(reviews(self.b,self.raw))
        self.assertEqual(counts,(6,6));self.assertNotIn('comparison_review_scope',out)
        self.raw['reading']['questions']['q1']['first'].update(A=1,C=0)
        self.assert_blocked(reviews(self.b,self.raw))

    def test_all_ready_explicit_scope_is_allowed(self):
        out,counts=self.call(reviews(self.b,self.raw,query_ids=['q1','q2','q4']))
        self.assertEqual(counts,(6,6))
        self.assertEqual(out['comparison_review_scope']['unreviewed_query_ids'],[])

    def test_scope_cannot_select_missing_unknown_duplicate_or_reordered_questions(self):
        opts=reviews(self.b,self.raw,query_ids=['q2','q4'])
        for ids in ([],['q3'],['q5'],['unknown'],['q2','q2'],['q4','q2'],['q2',1],('q2',)):
            with self.subTest(ids=ids),self.assertRaises((ValueError,TypeError)):
                comparison.scoped_worksheet(self.b,self.raw,opts['packet'],opts['context'],reviewed_query_ids=ids)

    def test_modified_scope_cannot_reuse_old_review(self):
        for ids in (['q1','q2','q4'],['q2'],['q3'],['q4','q2']):
            opts=reviews(self.b,self.raw,query_ids=['q2','q4'])
            opts['submission_review']=opts['submission_review'].model_copy(update={'reviewed_query_ids':ids})
            self.assert_blocked(opts)

    def test_unselected_reading_edit_invalidates_review(self):
        for q in ('q1','q3','q5'):
            opts=reviews(self.b,self.raw,query_ids=['q2','q4']);raw=deepcopy(self.raw)
            raw['reading']['questions'][q]['first']['F']=1
            self.assert_blocked(opts,raw)

    def test_changed_material_invalidates_review(self):
        opts=reviews(self.b,self.raw,query_ids=['q2','q4'])
        self.b['documents']['study.txt']+='\n附加材料。'
        self.assert_blocked(opts)

    def test_fresh_outer_approval_cannot_replace_independent_target_review(self):
        for kind in ('assignment','direction','population'):
            raw=deepcopy(self.raw);q=raw['reading']['questions']['q2']
            if kind=='assignment':q['first']['F']=1
            elif kind=='direction':q['first'],q['second']=q['second'],q['first']
            else:q['population']=['B']
            self.assert_blocked(reviews(self.b,raw,query_ids=['q2','q4']),raw)

    def test_broader_or_narrower_endpoint_context_cannot_be_reused(self):
        for side in comparison.SIDES:
            for ids in (['q1','q2','q4'],['q2']):
                opts=reviews(self.b,self.raw,query_ids=['q2','q4'])
                other=reviews(self.b,self.raw,query_ids=ids)
                for key in ('packet','context','assignment_review'):opts[key][side]=other[key][side]
                # Even a fresh outer fingerprint cannot expand the admitted set.
                sheet=comparison.scoped_worksheet(self.b,self.raw,opts['packet'],opts['context'],reviewed_query_ids=['q2','q4'])
                opts['submission_review']=opts['submission_review'].model_copy(update=sheet)
                self.assert_blocked(opts)

    def test_packet_crosswalk_and_facts_are_required_for_both_selected_endpoints(self):
        for side in comparison.SIDES:
            for key in ('packet','context','assignment_review'):
                opts=reviews(self.b,self.raw,query_ids=['q2','q4']);del opts[key][side]
                self.assert_blocked(opts)
            for kind in ('packet_extra','crosswalk_extra','a4','a5','study'):
                opts=reviews(self.b,self.raw,query_ids=['q2','q4'])
                if kind=='packet_extra':opts['packet'][side]['queries']['q1']=deepcopy(opts['packet'][side]['queries']['q2'])
                elif kind=='crosswalk_extra':opts['context'][side].core_port.crosswalks['q1']=opts['context'][side].core_port.crosswalks['q2']
                else:opts['packet'][side]['queries']['q2'][{'a4':'a4_sources_sha256','a5':'a5_licenses_sha256','study':'study_sha256'}[kind]]='0'*64
                sheet=comparison.scoped_worksheet(self.b,self.raw,opts['packet'],opts['context'],reviewed_query_ids=['q2','q4'])
                opts['submission_review']=opts['submission_review'].model_copy(update=sheet)
                self.assert_blocked(opts)

    def test_missing_reviews_or_opt_in_never_call_core(self):
        for key in ('packet','context','assignment_review','submission_review','synthetic_protocol_selected'):
            opts=reviews(self.b,self.raw,query_ids=['q2','q4']);opts[key]=False if key=='synthetic_protocol_selected' else None
            out,counts=self.call(opts);self.assertEqual(counts,(0,0));self.assertFalse(out['core_called'])

    def test_dictionary_from_model_is_not_review(self):
        opts=reviews(self.b,self.raw,query_ids=['q2','q4'])
        opts['submission_review']=opts['submission_review'].model_dump()
        self.assert_blocked(opts)

    def test_scoped_worksheet_contains_no_approval(self):
        opts=reviews(self.b,self.raw,query_ids=['q2','q4'])
        sheet=comparison.scoped_worksheet(self.b,self.raw,opts['packet'],opts['context'],reviewed_query_ids=['q2','q4'])
        self.assertFalse({'reviewer','evidence','synthetic_fixture','reviewed_comparison_direction_and_population'} & set(sheet))
        with self.assertRaises(ValidationError):comparison.ReviewedComparisonScope(**sheet)

    def test_strict_record_rejects_coercions_extra_fields_and_duplicate_ids(self):
        data=reviews(self.b,self.raw,query_ids=['q2','q4'])['submission_review'].model_dump()
        for name in ('synthetic_fixture','reviewed_comparison_direction_and_population'):
            for value in (False,1,'true'):
                with self.assertRaises(ValidationError):comparison.ReviewedComparisonScope.model_validate(dict(data,**{name:value}))
        for ids in ([],['q2','q2'],[''],[' q2'],[2],('q2',)):
            with self.assertRaises(ValidationError):comparison.ReviewedComparisonScope.model_validate(dict(data,reviewed_query_ids=ids))
        with self.assertRaises(ValidationError):comparison.ReviewedComparisonScope.model_validate(dict(data,automatic_approval=True))

    def test_original_assignment_facts_are_still_global(self):
        for name,value in (('reported_conflict',True),('uniform_subset_declared',None)):
            opts=reviews(self.b,self.raw,query_ids=['q2','q4']);raw=deepcopy(self.raw)
            raw['reported_assignment'][name]=value
            out,counts=self.call(opts,raw);self.assertEqual(counts,(0,0));self.assertEqual(out['state'],'NEEDS_INPUT')


if __name__=='__main__':unittest.main()
