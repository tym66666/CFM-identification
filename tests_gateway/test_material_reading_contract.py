import json
import unittest
from copy import deepcopy
from cfm_id.business_entry import prepare_request, preview
from cfm_id.intent_submission import submit
from cfm_id.material_reading_contract import clarify_request
from examples import nbib_d1_fixture as fixture
from evaluation.business_materials_intake import sources


class MaterialReadingContractTests(unittest.TestCase):
    def setUp(self):
        item=deepcopy(fixture.load_case());self.bundle=item['bundle'];self.raw=item['raw']
        self.raw['intents']={qid:dict(kind='比较',quote=q) for qid,q in self.bundle['question_slots'].items()}
        for qid,q in self.raw['questions'].items():
            q.pop('operation');q['peer_evidence']={side:self.bundle['question_slots'][qid] for side in ('first','second')}

    def test_public_materials_and_semantic_choices_unchanged(self):
        request=prepare_request(self.bundle,'D1_EFFECTS');before=deepcopy(request)
        revised=clarify_request(request)
        self.assertEqual(request,before)
        old,new=json.loads(before['user']),json.loads(revised['user'])
        self.assertEqual({k:v for k,v in old.items() if k!='output_schema'}, {k:v for k,v in new.items() if k!='output_schema'})
        self.assertEqual(old['output_schema']['$defs']['Local'],new['output_schema']['$defs']['Local'])
        self.assertEqual(revised,clarify_request(revised))

    def test_source_choices_are_all_eligible_public_locations_not_answers(self):
        schema=json.loads(clarify_request(prepare_request(self.bundle,'D1_EFFECTS'))['user'])['output_schema']
        target=[k for k in sources(self.bundle) if k.startswith(self.bundle['active_goal_document']+':')]
        question=schema['$defs']['Question']['properties']
        self.assertEqual(question['remaining_source']['anyOf'][0]['enum'],target)
        self.assertEqual(schema['properties']['study']['properties']['independence_source']['anyOf'][0]['enum'],list(sources(self.bundle)))
        self.assertNotIn('default',schema['properties']['study']['properties']['declared_independent'])

    def test_recording_true_never_grants_science(self):
        out=submit(self.bundle,self.raw,'D1_EFFECTS')
        self.assertEqual(out['state'],'REVIEW_REQUIRED')
        self.assertFalse(out['core_called'])
        self.assertFalse(out['production_admission'])

    def test_model_omission_stays_omitted(self):
        self.raw['study'].update(declared_independent=None,independence_source=None)
        out=preview(self.bundle,self.raw,'D1_EFFECTS')
        self.assertEqual(out['state'],'NEEDS_INPUT')
        self.assertIsNone(out['draft']['study']['declared_independent'])
        self.assertFalse(out['core_called'])

    def test_negative_declaration_cannot_enter_core(self):
        self.bundle['documents']['study_protocol.md']=self.bundle['documents']['study_protocol.md'].replace('所有经理独立抽签','所有经理的抽签存在相关性，不相互独立')
        self.raw['study'].update(declared_independent=False,independence_source='study_protocol.md:L3')
        out=preview(self.bundle,self.raw,'D1_EFFECTS')
        self.assertEqual(out['state'],'NEEDS_INPUT')
        self.assertFalse(out['core_called'])

    def test_literal_text_in_locator_remains_invalid(self):
        for q in self.raw['questions'].values():q['remaining_source']=q['remaining_evidence_span']
        out=preview(self.bundle,self.raw,'D1_EFFECTS')
        self.assertEqual(out['state'],'DRAFT_INVALID')
        self.assertFalse(out['core_called'])


if __name__=='__main__':unittest.main()
