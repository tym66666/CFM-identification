import unittest
from unittest.mock import patch
from cfm_id import business_intake,project
from cfm_id_llm import target_first_skill_guarded
from evaluation.task6.scripts.pilot_fullchain import case


class BoundProfileTests(unittest.TestCase):
    def test_opt_in_profile_in_request_and_stale_prompt_rejected(self):
        config=project.reading_config().model_dump(mode='json')
        self.assertEqual(config['a0_response_contract'],'target-first-skill-1')
        config['a0_response_contract']='target-first-skill-guarded-1'
        session=business_intake.start_configured(case('point'),config)
        request=business_intake.prepare_request(session)
        self.assertIn(target_first_skill_guarded.ADDITION,request['system_prompt'])
        self.assertEqual(session.request_sha256,request['request_sha256'])
        with patch.object(target_first_skill_guarded,'ADDITION','temporarily changed'):
            with self.assertRaises(business_intake.IntakeError):
                business_intake.prepare_request(session)

    def test_same_response_schema_and_parser_as_baseline(self):
        from cfm_id_llm.compact_response_contract import evidence_contract
        base=evidence_contract('target-first-skill-1')
        revised=evidence_contract('target-first-skill-guarded-1')
        self.assertIs(base.describe,revised.describe)
        self.assertIs(base.render_request,revised.render_request)
        self.assertIs(base.project,revised.project)


if __name__=='__main__':unittest.main()
