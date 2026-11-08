import unittest
from evaluation.business_materials_cases import fixtures
from evaluation.business_materials_plan_references import evaluate_draft, project
from tests_gateway.test_business_materials_remaining_declaration import reference as old_reference


def reference(c):
    raw = old_reference(c)
    for q in raw["questions"].values():
        for w in (q["first"], q["second"]):
            if isinstance(w, dict) and w["setting"] == "完整安排":
                s = w["treated"]; values = s.pop("ids")
                field = {"政策名单": "policy_id", "指定分组": "group_ids", "指定": "node_ids"}.get(s["selection"])
                if field:
                    s[field] = values[0] if field == "policy_id" else values
    return raw


class TypedPlanReferenceTests(unittest.TestCase):
    def test_no_empty_enum_when_materials_have_no_policy_table(self):
        from evaluation.business_materials_plan_references import output_schema
        def walk(value):
            if isinstance(value, dict):
                if "enum" in value:
                    self.assertTrue(value["enum"])
                for child in value.values():
                    walk(child)
            elif isinstance(value, list):
                for child in value:
                    walk(child)
        for c in fixtures():
            walk(output_schema(c["bundle"]))

    def test_typed_plan_references_preserve_every_existing_target(self):
        from evaluation.business_materials_selection_canonicalization import project as old
        for c in fixtures():
            self.assertEqual(project(c["bundle"], reference(c)), old(c["bundle"], old_reference(c)))

    def test_node_list_is_not_accepted_as_policy_identifier(self):
        c = fixtures()[4]; raw = reference(c)
        raw["questions"]["q1"]["first"]["treated"]["policy_id"] = ["unit_000"]
        r = evaluate_draft(c["bundle"], raw, c["packet"], synthetic_protocol_selected=True)
        self.assertEqual(r["reason_code"], "POLICY_ID_REQUIRED")
        raw = reference(c)
        raw["questions"]["q1"]["first"]["treated"] = dict(selection="政策名单", node_ids=["unit_000"])
        r = evaluate_draft(c["bundle"], raw, c["packet"], synthetic_protocol_selected=True)
        self.assertEqual(r["reason_code"], "PLAN_SELECTION_FIELDS_INVALID")

    def test_known_policy_remains_unsupported_and_whole_groups_replay(self):
        cases = fixtures()
        a = evaluate_draft(cases[4]["bundle"], reference(cases[4]), cases[4]["packet"], synthetic_protocol_selected=True)
        b = evaluate_draft(cases[7]["bundle"], reference(cases[7]), cases[7]["packet"], synthetic_protocol_selected=True)
        self.assertEqual(a["results"][0]["status"], "UNSUPPORTED")
        self.assertEqual(b["results"][0]["status"], "POINT")
        self.assertTrue(b["results"][0]["certificate_replay"])


if __name__ == "__main__":
    unittest.main()
