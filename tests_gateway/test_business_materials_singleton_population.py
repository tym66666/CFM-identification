from copy import deepcopy
import unittest
from evaluation.business_materials_cases import fixtures
from evaluation.business_materials_singleton_population import evaluate_draft, project
from tests_gateway.test_business_materials_independence import reference


class SingletonAliasTests(unittest.TestCase):
    def test_valid_singleton_alias_preserves_exact_target_and_raw(self):
        c = fixtures()[8]; canonical = reference(c); raw = deepcopy(canonical)
        raw["questions"]["q1"]["population"]["selection"] = "单个"
        before = deepcopy(raw)
        self.assertEqual(project(c["bundle"], raw), project(c["bundle"], canonical))
        r = evaluate_draft(c["bundle"], raw, c["packet"], synthetic_protocol_selected=True)
        self.assertTrue(r["results"][0]["certificate_replay"])
        self.assertEqual(len(r["equivalent_format_normalizations"]), 1)
        self.assertEqual(raw, before)

    def test_singleton_alias_does_not_hide_multiple_or_missing_ids(self):
        c = fixtures()[8]
        for ids in ([], ["unit_031", "unit_032"], "unit_031", None):
            raw = reference(c)
            raw["questions"]["q1"]["population"] = dict(selection="单个", ids=ids)
            r = evaluate_draft(c["bundle"], raw, c["packet"], synthetic_protocol_selected=True)
            self.assertEqual(r["reason_code"], "SINGLETON_SCOPE_REQUIRES_ONE_ID")

    def test_singleton_alias_never_invents_unit(self):
        c = fixtures()[8]; raw = reference(c)
        raw["questions"]["q1"]["population"] = dict(selection="单个", ids=["unknown"])
        r = evaluate_draft(c["bundle"], raw, c["packet"], synthetic_protocol_selected=True)
        self.assertEqual(r["reason_code"], "UNKNOWN_NODE_ID")


if __name__ == "__main__":
    unittest.main()
