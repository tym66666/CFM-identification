from copy import deepcopy
import json
import unittest
from unittest.mock import patch
from evaluation.business_groups_cases import fixtures
from evaluation.business_groups import make_request, evaluate_draft


class ScopeProvenanceTests(unittest.TestCase):
    def test_missing_scope_source_is_still_blocked(self):
        c = fixtures()[1]
        raw = deepcopy(c["reading_reference"])
        next(iter(raw["questions"].values()))["population_source"] = None
        with patch("pfn_pipeline.identification_business.identify_network_business_query") as core:
            r = evaluate_draft(c["business_question"], raw, c["packet"], synthetic_protocol_selected=True)
            self.assertEqual(r["results"][0]["reason_code"], "POPULATION_AND_AGGREGATION_REQUIRED")
            core.assert_not_called()

    def test_schema_explains_scope_and_restricts_source_ids(self):
        c = fixtures()[1]
        system, user = make_request(c["business_question"])
        data = json.loads(user)
        props = data["output_schema"]["$defs"]["Question"]["properties"]
        self.assertIn("不是总体", props["population_source"]["description"])
        self.assertEqual(props["population_source"]["anyOf"][0]["enum"], list(data["source_catalog"]))
        self.assertIn("单个对象也有平均结果", system)

    def test_correct_reference_still_replays_and_unknown_scope_does_not_default(self):
        c = fixtures()[1]
        r = evaluate_draft(c["business_question"], c["reading_reference"], c["packet"], synthetic_protocol_selected=True)
        self.assertTrue(r["results"][0]["certificate_replay"])
        raw = deepcopy(c["reading_reference"])
        next(iter(raw["questions"].values()))["population"] = dict(selection="不明确", ids=[])
        r = evaluate_draft(c["business_question"], raw, c["packet"], synthetic_protocol_selected=True)
        self.assertFalse(r["results"][0]["core_called"])
        self.assertEqual(r["results"][0]["status"], "NEEDS_INPUT")


if __name__ == "__main__":
    unittest.main()
