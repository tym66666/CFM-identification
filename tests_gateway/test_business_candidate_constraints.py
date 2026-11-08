import json
import unittest
from copy import deepcopy
from pydantic import ValidationError
from cfm_id_llm.candidate_queries import CandidateProposalV011
from examples.materials_candidate_fixture import load_case, synthetic_context
from tests_gateway.test_business_candidate_base import RecordingMock
from evaluation import business_candidate_constraints as current


class CrossFieldSchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        item = load_case()
        provider = RecordingMock()
        result = current.evaluate_with_candidates(item["bundle"], item["raw"], item["packet"],
            context=synthetic_context(item), provider=provider, enable_candidates=True,
            synthetic_protocol_selected=True)
        schema, _ = json.JSONDecoder().raw_decode(provider.calls[0][1].split(current.SCHEMA_MARKER, 1)[1])
        cls.schema = schema
        cls.rules = schema["$defs"]["CandidateDraftV03"]["allOf"]
        cls.valid = result["candidate_results"][0]["candidate"]

    def test_valid_unknown_still_admitted(self):
        CandidateProposalV011.model_validate(self.valid)

    def test_request_schema_exposes_notpoint_formula_rule(self):
        value = deepcopy(self.valid)
        value["proposal"].update(claimed_identification="NOT_POINT", candidate_expression="target formula",
            nonidentification_witness=dict(world_a="world one",world_b="world two",
                why_observables_match="same observable law",why_targets_differ="different targets"))
        self.assertEqual(self.rules[0]["if"]["properties"]["claimed_identification"]["enum"], ["NOT_POINT", "UNDETERMINED"])
        self.assertEqual(self.rules[0]["then"]["properties"]["candidate_expression"], {"type": "null"})
        with self.assertRaises(ValidationError): CandidateProposalV011.model_validate(value)

    def test_unknown_cannot_carry_witness(self):
        value = deepcopy(self.valid)
        value["proposal"]["nonidentification_witness"] = dict(world_a="world one",world_b="world two",
            why_observables_match="same observable law",why_targets_differ="different targets")
        self.assertEqual(self.rules[2]["then"]["properties"]["nonidentification_witness"], {"type": "null"})
        with self.assertRaises(ValidationError): CandidateProposalV011.model_validate(value)

    def test_conditional_needs_requirement(self):
        value = deepcopy(self.valid)
        value["proposal"]["scope"] = "IF_ADDITIONAL_REQUIREMENTS"
        self.assertEqual(self.rules[5]["then"]["properties"]["additional_requirements"], {"minItems": 1})
        with self.assertRaises(ValidationError): CandidateProposalV011.model_validate(value)

    def test_point_needs_expression(self):
        value = deepcopy(self.valid)
        value["proposal"].update(claimed_identification="POINT", a4_used=dict(
            source="REVIEWED_OPERATOR",operator="NODE_FULL_LAW",level="NODE_FULL_LAW"))
        self.assertEqual(self.rules[3]["then"]["properties"]["candidate_expression"], {"type": "string", "minLength": 1})
        with self.assertRaises(ValidationError): CandidateProposalV011.model_validate(value)

    def test_unresolved_a4_cannot_claim_notpoint_as_reviewed(self):
        value = deepcopy(self.valid)
        value["proposal"].update(claimed_identification="NOT_POINT",nonidentification_witness=dict(
            world_a="world one",world_b="world two",why_observables_match="same law forever",why_targets_differ="different targets"))
        rule = self.rules[7]
        self.assertIn("NOT_POINT", rule["if"]["properties"]["claimed_identification"]["enum"])
        self.assertEqual(rule["then"]["properties"]["scope"], {"const": "IF_ADDITIONAL_REQUIREMENTS"})
        self.assertEqual(rule["then"]["properties"]["additional_requirements"]["contains"]["properties"]["kind"], {"const": "A4_INFORMATION"})


if __name__ == "__main__":
    unittest.main()
