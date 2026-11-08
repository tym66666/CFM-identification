from copy import deepcopy
import json,tempfile,unittest
from pathlib import Path
from cfm_id_llm.schemas import BusinessCase
from cfm_id_llm.providers import MockProvider
from cfm_id_llm.evidence_refs import build_catalog
from cfm_id_llm.quality_formulator import A0QualityValidationError
from cfm_id_llm.source_fact_formulator import SourceFactFormulator,render_source_fact_html,PROMPT_VERSION,make_source_fact_request
from cfm_id_llm.source_fact_cli import main


class SourceFactTests(unittest.TestCase):
    def setUp(self):
        self.case=BusinessCase(case_id='HOLD-TEST',business_question='员工会交流客户问题。想知道AI助手对本人满意度的影响。还没确定对照、同伴状态、分配规则、汇总方式和时点。')
        self.ref=build_catalog(self.case)[0]['ref']
        self.c=lambda t,r='explicit':dict(text=t,refs=[self.ref],reading=r)
        self.raw={'facts':{'units':self.c('员工'),'action':self.c('AI助手'),'outcome':self.c('客户满意度')},
            'goals':[dict(form='comparison',focus='own',question=self.c('助手对本人的影响'),
                situation_a=dict(own_action=self.c('获得助手')),situation_b=dict(own_action=self.c('没有助手','interpretation')))]}

    def run_wire(self):
        p=MockProvider(self.raw);r=SourceFactFormulator(p).formulate(self.case);self.assertEqual(p.calls,1);return r

    def test_tentative_comparator_is_retained_but_not_projected(self):
        old=deepcopy(self.raw);r=self.run_wire();self.assertEqual(old,self.raw)
        self.assertIsNone(r['quality']['draft']['queries'][0]['semantics']['comparator']['value'])
        self.assertEqual(r['business_draft']['goals'][0]['situation_b']['own_action']['text'],'没有助手')
        self.assertEqual(r['held_interpretations'][0]['path'],'goals.q1.situation_b.own_action')
        self.assertEqual(r['quality']['prompt_version'],PROMPT_VERSION)
        self.assertFalse(r['core_called']);self.assertFalse(r['scientific_approval'])

    def test_declared_null_situation_is_empty_not_an_inferred_scenario(self):
        self.raw['goals'][0]['situation_b']=None;before=deepcopy(self.raw)
        r=self.run_wire();self.assertEqual(before,self.raw)
        self.assertIsNone(r['quality']['draft']['queries'][0]['semantics']['comparator']['value'])
        self.assertEqual(r['wire_normalizations'],[{'path':'goals.q1.situation_b','operation':'DECLARED_NULL_TO_EMPTY_SITUATION'}])
        _,user,_=make_source_fact_request(self.case);schema=json.loads(user.split('\n输出 Schema：\n')[1])
        self.assertIn({'type':'null'},schema['$defs']['Comparison']['properties']['situation_b']['anyOf'])

    def test_empty_group_handling_cannot_accept_undeclared_string_or_wrong_form(self):
        for value in ('UNKNOWN',[],42):
            self.raw['goals'][0]['situation_b']=value
            with self.subTest(value=value),self.assertRaises(A0QualityValidationError):self.run_wire()

    def test_shared_interpretation_cannot_declare_design_family(self):
        self.raw['facts'].update(historical_assignment=self.c('独立抽签','interpretation'),assignment_family='INDEPENDENT_BERNOULLI')
        r=self.run_wire();design=r['quality']['draft']['shared_draft']['information_design']
        self.assertEqual(design['assignment_family'],'UNRESOLVED');self.assertIsNone(design['assignment_law']['value'])
        self.assertEqual(r['business_draft']['facts']['assignment_family'],'INDEPENDENT_BERNOULLI')

    def test_known_coordinate_survives_when_other_coordinate_is_held(self):
        self.raw['goals'][0]['situation_b']['peers']=self.c('不超过一半使用')
        r=self.run_wire();value=r['quality']['draft']['queries'][0]['semantics']['comparator']['value']
        self.assertIn('不超过一半',value);self.assertNotIn('本人：',value)
        self.assertTrue(any(x['path'].endswith('situation_b.own_action') for x in r['missing_information_candidates']))

    def test_ambiguity_and_classification_contradiction_survive_withholding(self):
        q=self.raw['goals'][0];q['focus']='both';q['situation_a']['own_action']=self.c('没有助手')
        q['notes']=[self.c('比较尚未确定','interpretation')]
        r=self.run_wire();codes=[x['code'] for x in r['internal_recheck']]
        self.assertIn('FOCUS_CONTRADICTS_IDENTICAL_SCENARIOS',codes);self.assertIn('AMBIGUITY_OR_CONFLICT',codes)

    def test_question_interpretation_remains_a_proposed_goal_not_coordinate(self):
        self.raw['goals'][0]['question']['reading']='interpretation'
        r=self.run_wire();self.assertEqual(r['quality']['draft']['queries'][0]['target']['description']['basis'],'INTERPRETATION')
        self.assertFalse(r['identification_ready'])

    def test_bad_ref_cannot_hide_in_held_interpretation(self):
        self.raw['goals'][0]['situation_b']['own_action']['refs']=['foreign']
        with self.assertRaises(A0QualityValidationError):self.run_wire()

    def test_explicit_label_is_not_semantic_verification(self):
        self.raw['goals'][0]['when']=self.c('五十年后')
        r=self.run_wire();self.assertFalse(r['semantic_correctness_verified']);self.assertFalse(r['identification_ready'])

    def test_held_html_escapes_proposal(self):
        self.raw['goals'][0]['situation_b']['own_action']['text']='<script>猜测</script>'
        html=render_source_fact_html(self.case,self.run_wire())
        self.assertIn('待确认的解释',html);self.assertIn('&lt;script&gt;',html);self.assertNotIn('<script>',html)

    def test_cli_uses_single_call_source_fact_flow_and_plain_reply(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);fixture=p/'fixture.json';fixture.write_text(json.dumps(self.raw),encoding='utf8');out=p/'out'
            self.assertEqual(main(['--question',self.case.business_question,'--case-id',self.case.case_id,
                '--mock-response',str(fixture),'--output-dir',str(out)]),0)
            r=json.loads((out/'review_result.json').read_text(encoding='utf8'));self.assertEqual(r['prompt_version'],PROMPT_VERSION)
            self.assertIsNone(r['quality']['draft']['queries'][0]['semantics']['comparator']['value'])
            self.assertEqual(main(['--resume',str(out),'--reply','是的，比较本人获得和未获得助手，同伴仍未决定。','--preview','--output-dir',str(p/'reply')]),0)


if __name__=='__main__':unittest.main()
