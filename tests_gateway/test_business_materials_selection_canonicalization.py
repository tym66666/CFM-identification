from copy import deepcopy
import unittest
from evaluation.business_materials_cases import fixtures
from evaluation.business_materials_selection_canonicalization import evaluate_draft, project
from tests_gateway.test_business_materials_remaining_declaration import reference


class RedundantScopeTests(unittest.TestCase):
    def test_full_valid_list_equals_implicit_all_without_mutating_raw(self):
        c = fixtures()[5]; raw = reference(c); expected = project(c["bundle"], raw)
        for q in raw["questions"].values():
            q["population"]["ids"] = list(reversed(c["bundle"]["structure"]["nodes"]))
        before = deepcopy(raw)
        self.assertEqual(project(c["bundle"], raw), expected)
        r = evaluate_draft(c["bundle"], raw, c["packet"], synthetic_protocol_selected=True)
        self.assertTrue(all(q["certificate_replay"] for q in r["results"]))
        self.assertEqual(len(r["redundant_scope_normalizations"]), 2)
        self.assertEqual(raw, before)

    def test_partial_extra_duplicate_lists_are_not_silently_discarded(self):
        c = fixtures()[5]; nodes = c["bundle"]["structure"]["nodes"]
        for ids in (nodes[:-1], nodes + ["extra"], nodes + [nodes[0]], [None]):
            raw = reference(c); raw["questions"]["q1"]["population"]["ids"] = ids
            r = evaluate_draft(c["bundle"], raw, c["packet"], synthetic_protocol_selected=True)
            self.assertEqual(r["status"], "REJECTED")
            self.assertEqual(r["results"], [])

    def test_explicit_cross_scope_list_must_match_all_precomputed_members(self):
        c = fixtures()[-1]; raw = reference(c); expected = project(c["bundle"], raw)
        members = c["bundle"]["structure"]["units_with_cross_group_neighbors"]
        raw["questions"]["q1"]["population"]["ids"] = members
        self.assertEqual(project(c["bundle"], raw), expected)
        raw["questions"]["q1"]["population"]["ids"] = members[:-1]
        r = evaluate_draft(c["bundle"], raw, c["packet"], synthetic_protocol_selected=True)
        self.assertEqual(r["reason_code"], "REDUNDANT_SCOPE_IDS_CONFLICT")

    def test_all_existing_coordinates_and_decisions_unchanged(self):
        from evaluation.business_materials_remaining_declaration import evaluate_draft as old
        for c in fixtures():
            a = evaluate_draft(c["bundle"], reference(c), c["packet"], synthetic_protocol_selected=True)
            b = old(c["bundle"], reference(c), c["packet"], synthetic_protocol_selected=True)
            self.assertEqual(a["results"], b["results"])


if __name__ == "__main__":
    unittest.main()
