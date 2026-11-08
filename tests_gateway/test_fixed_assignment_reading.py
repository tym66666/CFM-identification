"""Offline checks for source-bound assignment reading, never scientific admission."""
from copy import deepcopy
import json
import unittest

from pydantic import ValidationError
from cfm_id import fixed_assignment as contract
from cfm_id.business_entry import prepare_request, preview, read_once
from cfm_id.source_locations import build_catalog


NODES = ["A", "B", "C", "D", "E"]
GOAL = ("问题1：下一轮只让A和D启用提醒，B、C、E不启用。"
        "评价五个窗口的平均每日按时出餐份数，五个窗口权重相同。")
RULE = "原试点每轮从五个窗口中均匀随机选两个启用提醒，所有十种两窗口名单机会相同。"


def bundle(rule=RULE):
    return {
        "node_order": list(NODES),
        "documents": {
            "study.txt": "五个窗口使用电子提醒，观察按时出餐份数。\r\n" + rule + "\r\n",
            "goal.txt": GOAL,
        },
        "question_slots": {"q1": GOAL},
    }


def reading():
    return {
        "intents": {"q1": {"kind": "水平", "quote": GOAL}},
        "questions": {"q1": {
            "first": {"A": 1, "B": 0, "C": 0, "D": 1, "E": 0},
            "second": None, "population": list(NODES), "aggregation": "等权平均",
        }},
    }


def wrapper(b, *, mechanism="FIXED_QUOTA_RANDOM", count=2, cap=None,
            uniform=True, conflict=False):
    source_id = next(k for k, r in build_catalog(b["documents"]).items()
                     if r["doc_id"] == "study.txt" and r["start"] > 0)
    return {
        "reading": reading(),
        "reported_assignment": {
            "mechanism": mechanism,
            "fixed_count": count,
            "maximum_count": cap,
            "uniform_subset_declared": uniform,
            "reported_conflict": conflict,
            "source_ids": [source_id],
        },
    }


class FixedAssignmentReadingTests(unittest.TestCase):
    def assertNoAdmission(self, out):
        for field in ("core_called", "production_admission", "estimation_called",
                      "policy_called", "estimation_handoff_allowed"):
            self.assertFalse(out.get(field, False), field)
        self.assertEqual(out.get("candidate_model_calls", 0), 0)
        self.assertFalse(out["assignment_review"]["scientific_approval"])
        self.assertNotIn(out["state"], ("POINT", "CORE_POINT", "NONID"))

    def assertTargetRetained(self, out):
        self.assertEqual(out["target_reading_state"], "REVIEW_REQUIRED")
        self.assertEqual(out["proposed_targets"]["q1"]["assignment"], [1, 0, 0, 1, 0])
        self.assertEqual(out["proposed_targets"]["q1"]["unit_weights"], ["1/5"] * 5)

    def test_ready_reading_resolves_exact_original_location_but_never_certifies(self):
        b = bundle()
        raw = wrapper(b)
        before = deepcopy(raw)
        out = contract.preview(b, raw)
        self.assertEqual(out["state"], "REVIEW_REQUIRED")
        self.assertEqual(out["assignment_review"]["reason_code"],
                         "INDEPENDENT_ASSIGNMENT_REVIEW_REQUIRED")
        source = out["assignment_review"]["resolved_sources"][0]
        self.assertEqual(source["text"], RULE + "\r\n")
        self.assertEqual(b["documents"][source["doc_id"]][source["start"]:source["end"]],
                         source["text"])
        self.assertTargetRetained(out)
        self.assertNoAdmission(out)
        self.assertEqual(raw, before)

    def test_counts_reject_boolean_float_string_and_invalid_bounds(self):
        for field in ("fixed_count", "maximum_count"):
            for value in (True, False, 2.0, "2", -1, 6):
                with self.subTest(field=field, value=value):
                    b = bundle()
                    raw = wrapper(b)
                    raw["reported_assignment"][field] = value
                    out = contract.preview(b, raw)
                    self.assertEqual(out["state"], "CHECK_BLOCKED")
                    self.assertTargetRetained(out)
                    self.assertNoAdmission(out)

    def test_boolean_flags_are_strict(self):
        for field in ("uniform_subset_declared", "reported_conflict"):
            for value in (0, 1, "true", "false"):
                with self.subTest(field=field, value=value):
                    b = bundle()
                    raw = wrapper(b)
                    raw["reported_assignment"][field] = value
                    with self.assertRaises(ValidationError):
                        contract.AssignmentReading.model_validate(raw)
                    self.assertEqual(contract.preview(b, raw)["state"], "CHECK_BLOCKED")

    def test_extra_approval_or_freely_copied_evidence_fields_are_rejected(self):
        for container, field, value in (
            ("root", "scientific_approval", True),
            ("root", "route", "R1B_FULL_ASSIGNMENT"),
            ("facts", "a5_approved", True),
            ("facts", "evidence_quote", RULE),
            ("facts", "start", 0),
            ("facts", "sha256", "model_supplied"),
            ("facts", "clarifying_question", "请确认固定两处。"),
        ):
            with self.subTest(container=container, field=field):
                b = bundle()
                raw = wrapper(b)
                target = raw if container == "root" else raw["reported_assignment"]
                target[field] = value
                with self.assertRaises(ValidationError):
                    contract.AssignmentReading.model_validate(raw)
                out = contract.preview(b, raw)
                self.assertEqual(out["state"], "CHECK_BLOCKED")
                self.assertTargetRetained(out)
                self.assertNoAdmission(out)

    def test_missing_facts_does_not_clear_known_target(self):
        b = bundle()
        raw = {"reading": reading()}
        out = contract.preview(b, raw)
        self.assertEqual(out["state"], "CHECK_BLOCKED")
        self.assertTargetRetained(out)
        self.assertEqual(out["reading_candidate"], raw)
        self.assertNoAdmission(out)

    def test_unknown_facts_preserve_target_and_generate_neutral_questions(self):
        rule = "现有记录只表明过去平均每轮有两处启用；原试点如何选取、总人数是否固定都没有记录。"
        b = bundle(rule)
        raw = wrapper(b, mechanism="NOT_FULLY_SPECIFIED", count=None, uniform=None)
        out = contract.preview(b, raw)
        self.assertEqual(out["state"], "NEEDS_INPUT")
        self.assertIsNone(out["assignment_review"]["facts"]["fixed_count"])
        questions = "\n".join(out["assignment_review"]["questions"])
        self.assertIn("人数是否固定", questions)
        self.assertIn("若固定，人数是多少", questions)
        self.assertNotIn("2", questions)
        self.assertNotIn("两", questions)
        self.assertNotIn("独立", questions)
        self.assertTargetRetained(out)
        self.assertNoAdmission(out)

    def test_false_fixed_two_claim_cannot_be_rescued_by_average_source(self):
        b = bundle("记录只表明平均每轮启用两处；每轮人数是否固定、如何抽取没有说明。")
        raw = wrapper(b)
        out = contract.preview(b, raw)
        self.assertEqual(out["state"], "NEEDS_INPUT")
        self.assertEqual(out["assignment_review"]["reason_code"],
                         "SOURCE_DECLARATION_NOT_CONFIRMED")
        self.assertTargetRetained(out)
        self.assertNoAdmission(out)

    def test_known_upper_limit_is_preserved_without_independent_coin_suggestion(self):
        rule = "原试点每轮最多随机选两个窗口，也可能选一处或一处也不选；具体概率没有说明。"
        b = bundle(rule)
        raw = wrapper(b, mechanism="NOT_FULLY_SPECIFIED", count=None, cap=2, uniform=None)
        out = contract.preview(b, raw)
        facts = out["assignment_review"]["facts"]
        self.assertEqual(out["state"], "NEEDS_INPUT")
        self.assertEqual(facts["maximum_count"], 2)
        self.assertIsNone(facts["fixed_count"])
        questions = "\n".join(out["assignment_review"]["questions"])
        self.assertIn("不超过2", questions)
        self.assertIn("在这一上限内", questions)
        self.assertIn("各以什么概率", questions)
        self.assertIn("每种人数下的名单", questions)
        self.assertNotIn("独立", questions)
        self.assertNotIn("所有可能的子集", questions)
        self.assertTargetRetained(out)
        self.assertNoAdmission(out)

    def test_count_above_reported_cap_is_blocked(self):
        b = bundle()
        out = contract.preview(b, wrapper(b, count=2, cap=1))
        self.assertEqual(out["state"], "CHECK_BLOCKED")
        self.assertTargetRetained(out)
        self.assertNoAdmission(out)

    def test_future_proposal_is_not_a_source_for_original_design(self):
        b = bundle("原试点分配规则没有记录。未来想评估每轮随机选两个窗口的方案。")
        raw = wrapper(b, mechanism="NOT_FULLY_SPECIFIED", count=None, uniform=None)
        out = contract.preview(b, raw)
        self.assertEqual(out["state"], "NEEDS_INPUT")
        self.assertIsNone(out["assignment_review"]["facts"]["fixed_count"])
        self.assertIn("未来计划不能替代原试点规则",
                      "\n".join(out["assignment_review"]["questions"]))
        self.assertTargetRetained(out)
        self.assertNoAdmission(out)
        forged = wrapper(b)
        self.assertNotEqual(contract.preview(b, forged)["state"], "REVIEW_REQUIRED")

    def test_reported_conflict_stops_otherwise_complete_fields(self):
        b = bundle()
        out = contract.preview(b, wrapper(b, conflict=True))
        self.assertEqual(out["state"], "NEEDS_INPUT")
        self.assertEqual(out["assignment_review"]["reason_code"],
                         "CONFLICTING_ASSIGNMENT_MATERIALS")
        self.assertTrue(out["assignment_review"]["facts"]["reported_conflict"])
        self.assertIn("哪份是实际执行", out["assignment_review"]["questions"][0])
        self.assertTargetRetained(out)
        self.assertNoAdmission(out)

    def test_nonuniform_false_is_preserved_as_adapter_limit_not_nonidentification(self):
        b = bundle("原试点每轮随机选两处，不同两处名单的概率不同。")
        out = contract.preview(b, wrapper(b, uniform=False))
        facts = out["assignment_review"]
        self.assertEqual(out["state"], "CHECK_BLOCKED")
        self.assertIs(facts["facts"]["uniform_subset_declared"], False)
        self.assertEqual(facts["reason_code"], "NONUNIFORM_ASSIGNMENT_REQUIRES_ANOTHER_ADAPTER")
        self.assertIn("不是不可识别结论", facts["scope_note"])
        self.assertFalse(out.get("nonidentification_proven", False))
        self.assertTargetRetained(out)
        self.assertNoAdmission(out)

    def test_unknown_uniformity_asks_joint_list_probabilities_not_individual_marginals(self):
        b = bundle("原试点每轮随机选两处启用提醒。")
        out = contract.preview(b, wrapper(b, uniform=None))
        self.assertEqual(out["state"], "NEEDS_INPUT")
        self.assertEqual(out["assignment_review"]["facts"]["fixed_count"], 2)
        self.assertIn("同人数的不同名单各以什么概率",
                      "\n".join(out["assignment_review"]["questions"]))
        self.assertNoAdmission(out)

    def test_other_known_mechanisms_remain_known_but_need_another_adapter(self):
        for mechanism in ("INDEPENDENT_RANDOM", "OBSERVATIONAL"):
            with self.subTest(mechanism=mechanism):
                b = bundle("原试点采取题述另一机制。")
                out = contract.preview(b, wrapper(
                    b, mechanism=mechanism, count=None, uniform=None))
                self.assertEqual(out["state"], "CHECK_BLOCKED")
                self.assertEqual(out["assignment_review"]["facts"]["mechanism"], mechanism)
                self.assertIn("不是不可识别结论", out["assignment_review"]["scope_note"])
                self.assertTargetRetained(out)
                self.assertNoAdmission(out)

    def test_zero_and_roster_size_counts_are_valid_boundary_declarations(self):
        for count in (0, len(NODES)):
            with self.subTest(count=count):
                b = bundle(f"原试点每轮从五个窗口中均匀随机选{count}个窗口，所有同人数名单等概率。")
                out = contract.preview(b, wrapper(b, count=count))
                self.assertEqual(out["state"], "REVIEW_REQUIRED")
                self.assertEqual(out["assignment_review"]["facts"]["fixed_count"], count)
                self.assertNoAdmission(out)
        for cap in (0, len(NODES)):
            with self.subTest(cap=cap):
                b = bundle(f"原试点每轮启用人数不超过{cap}，规则还没有说明。")
                out = contract.preview(b, wrapper(
                    b, mechanism="NOT_FULLY_SPECIFIED", count=None, cap=cap, uniform=None))
                self.assertEqual(out["state"], "NEEDS_INPUT")
                self.assertEqual(out["assignment_review"]["facts"]["maximum_count"], cap)
                self.assertIn(f"不超过{cap}", "\n".join(out["assignment_review"]["questions"]))
                self.assertNoAdmission(out)

    def test_source_ids_reject_unknown_duplicates_nonlists_and_nonstring_items(self):
        b = bundle()
        valid = wrapper(b)["reported_assignment"]["source_ids"][0]
        for ids in ([valid, valid], ["missing"], [None], [1], valid, [valid] * 9):
            with self.subTest(ids=ids):
                raw = wrapper(b)
                raw["reported_assignment"]["source_ids"] = ids
                out = contract.preview(b, raw)
                self.assertEqual(out["state"], "CHECK_BLOCKED")
                self.assertTargetRetained(out)
                self.assertNoAdmission(out)

    def test_empty_sources_require_provenance_without_clearing_target(self):
        b = bundle()
        raw = wrapper(b)
        raw["reported_assignment"]["source_ids"] = []
        out = contract.preview(b, raw)
        self.assertEqual(out["state"], "NEEDS_INPUT")
        self.assertIn("材料来源", out["assignment_review"]["questions"][0])
        self.assertTargetRetained(out)
        self.assertNoAdmission(out)

    def test_stale_source_after_any_document_change_is_rejected(self):
        b = bundle()
        raw = wrapper(b)
        b["documents"]["study.txt"] += "\r\n"
        out = contract.preview(b, raw)
        self.assertEqual(out["state"], "CHECK_BLOCKED")
        self.assertTargetRetained(out)
        self.assertNoAdmission(out)

    def test_existing_but_irrelevant_source_cannot_prove_fixed_quota_declaration(self):
        b = bundle()
        raw = wrapper(b)
        goal_id = next(k for k, r in build_catalog(b["documents"]).items()
                       if r["doc_id"] == "goal.txt")
        raw["reported_assignment"]["source_ids"] = [goal_id]
        out = contract.preview(b, raw)
        self.assertEqual(out["state"], "NEEDS_INPUT")
        self.assertEqual(out["assignment_review"]["reason_code"], "SOURCE_DECLARATION_NOT_CONFIRMED")
        self.assertEqual(out["assignment_review"]["resolved_sources"][0]["text"], GOAL)
        self.assertTargetRetained(out)
        self.assertNoAdmission(out)

    def test_request_uses_only_source_ids_for_assignment_and_root_refs_resolve(self):
        b = bundle()
        system, user = contract.make_request(b)
        message = json.loads(user)
        schema = message["output_schema"]
        self.assertEqual(set(message), {"documents", "node_order", "question_slots",
                                        "output_schema", "source_catalog"})
        self.assertEqual(message["source_catalog"], build_catalog(b["documents"]))
        props = schema["properties"]["reported_assignment"]["properties"]
        self.assertEqual(set(props), {"mechanism", "fixed_count", "maximum_count",
                                     "uniform_subset_declared", "reported_conflict", "source_ids"})
        self.assertNotIn("evidence_quote", props)
        self.assertNotIn("clarifying_question", props)
        self.assertIn("quote", schema["$defs"]["Intent"]["properties"])
        self.assertIn("不要生成追问", system)
        self.assertIn("只复制ID，不复抄证据文字", system)
        references = []

        def visit(value):
            if isinstance(value, dict):
                if "$ref" in value:
                    references.append(value["$ref"])
                for child in value.values():
                    visit(child)
            elif isinstance(value, list):
                for child in value:
                    visit(child)
        visit(schema)
        self.assertTrue(references)
        for ref in references:
            self.assertTrue(ref.startswith("#/"))
            resolved = schema
            for part in ref[2:].split("/"):
                resolved = resolved[part.replace("~1", "/").replace("~0", "~")]
            self.assertIsInstance(resolved, dict)

    def test_new_request_does_not_mutate_old_contract_or_public_bundle(self):
        b = bundle()
        before = deepcopy(b)
        old = prepare_request(b, "FIXED_POLICY")
        first = contract.make_request(b)
        second = contract.make_request(b)
        self.assertEqual(first, second)
        self.assertEqual(prepare_request(b, "FIXED_POLICY"), old)
        self.assertEqual(b, before)
        old_message = json.loads(old["user"])
        self.assertNotIn("source_catalog", old_message)
        self.assertEqual(set(old_message["output_schema"]["properties"]), {"intents", "questions"})
        self.assertIn("Conditions", old_message["output_schema"]["$defs"])

    def test_unified_prepare_preview_and_single_mock_call(self):
        b = bundle()
        raw = wrapper(b)
        expected_system, expected_user = contract.make_request(b)
        self.assertEqual(prepare_request(b, "FIXED_POLICY", contract=contract.CONTRACT),
                         {"system": expected_system, "user": expected_user})
        out = preview(b, raw, "FIXED_POLICY", contract=contract.CONTRACT)
        self.assertEqual(out, contract.preview(b, raw))

        class LocalProvider:
            calls = 0

            def generate_json(self, *, system_prompt, user_prompt):
                self.calls += 1
                self.request = (system_prompt, user_prompt)
                return deepcopy(raw)

        provider = LocalProvider()
        result = read_once(b, provider, "FIXED_POLICY", contract=contract.CONTRACT)
        self.assertEqual(provider.calls, 1)
        self.assertEqual(provider.request, (expected_system, expected_user))
        self.assertEqual(result["state"], "REVIEW_REQUIRED")
        self.assertNoAdmission(result)

    def test_new_contract_rejects_unrelated_entry(self):
        b = bundle()
        for fn, args in ((prepare_request, (b, "D1_EFFECTS")),
                         (preview, (b, wrapper(b), "D1_EFFECTS"))):
            with self.subTest(function=fn.__name__):
                with self.assertRaisesRegex(ValueError, "REQUIRES_FIXED_POLICY"):
                    fn(*args, contract=contract.CONTRACT)


if __name__ == "__main__":
    unittest.main()

