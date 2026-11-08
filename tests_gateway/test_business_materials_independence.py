from copy import deepcopy
import unittest
from evaluation.business_materials_cases import fixtures
from evaluation.business_materials_intake import sources
from evaluation.business_materials_independence import evaluate_draft
from tests_gateway.test_business_materials_file_roles import reference as parent_reference


def reference(c):
    r = parent_reference(c)
    refs = [k for k in r["study"]["design_sources"] if "独立" in sources(c["bundle"]).get(k, "")]
    r["study"]["independence_source"] = refs[0] if r["study"]["declared_independent"] else None
    return r


class DeclarationEvidenceTests(unittest.TestCase):
    def test_probability_only_does_not_support_independence(self):
        c = fixtures()[1]
        r = reference(c)
        r["study"]["declared_independent"] = True
        r["study"]["independence_source"] = "study_protocol.md:L3"
        result = evaluate_draft(c["bundle"], r, c["packet"], synthetic_protocol_selected=True)
        self.assertEqual(result["reason_code"], "EXPLICIT_INDEPENDENCE_DECLARATION_REQUIRED")
        self.assertEqual(result["results"], [])

    def test_unknown_independence_preserves_need_for_input(self):
        c = fixtures()[1]
        result = evaluate_draft(c["bundle"], reference(c), c["packet"], synthetic_protocol_selected=True)
        self.assertEqual(result["reason_code"], "INDEPENDENT_GROUP_DRAWS_NOT_DECLARED")

    def test_explicit_declarations_do_not_approve_original_science(self):
        c = fixtures()[0]
        result = evaluate_draft(c["bundle"], reference(c), c["packet"], synthetic_protocol_selected=True)
        self.assertFalse(any(q["core_called"] for q in result["results"]))

    def test_all_clarified_fixtures_keep_core_results(self):
        from evaluation.business_materials_base import evaluate_draft as old
        for c in fixtures()[3:]:
            a = old(c["bundle"], c["reading_reference"], c["packet"], synthetic_protocol_selected=True)
            b = evaluate_draft(c["bundle"], reference(c), c["packet"], synthetic_protocol_selected=True)
            self.assertEqual(a["results"], b["results"])


if __name__ == "__main__":
    unittest.main()
