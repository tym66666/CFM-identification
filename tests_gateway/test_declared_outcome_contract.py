import copy,json,unittest
from cfm_id_llm.providers.declared_outcome_contract import annotate_outcome_contract,DeclaredOutcomeContractProviderV0441
from evaluation.nbib_acceptance import material_input,registry,public_path,check_public
from evaluation.business_materials import make_request
class DeclaredOutcomeContractTests(unittest.TestCase):
    def setUp(self):self.s,self.u=make_request(material_input("NBIB-003-single-store"))
    def test_public_identifier_only(self):
        s,u=annotate_outcome_contract(self.s,self.u);m=json.loads(u);old=json.loads(self.u)
        p=m["output_schema"]["properties"]["study"]["properties"]["outcome"]
        self.assertEqual(p["enum"],["store_revenue"])
        self.assertIn("data_dictionary.md:L3",p["description"])
        del p["enum"];p.pop("description")
        self.assertEqual(m,old);self.assertTrue(s.startswith(self.s))
    def test_wrapper_returns_original_object_even_if_wrong(self):
        raw={"study":{"outcome":"metric_after"}}
        class P:
            def generate_json(inner,**kw):
                self.assertIn("enum",json.loads(kw["user_prompt"])["output_schema"]["properties"]["study"]["properties"]["outcome"])
                return raw
        self.assertIs(DeclaredOutcomeContractProviderV0441(P()).generate_json(system_prompt=self.s,user_prompt=self.u),raw)
    def test_no_declaration_no_guess(self):
        m=json.loads(self.u);m["source_catalog"]={}
        u=json.dumps(m);self.assertEqual(annotate_outcome_contract(self.s,u),(self.s,u))
    def test_conflicting_declarations_not_resolved_by_guess(self):
        m=json.loads(self.u);m["source_catalog"]["data_dictionary.md:L99"]="- 本案例主要结果指标：`profit`，单位为元。"
        u=json.dumps(m);self.assertEqual(annotate_outcome_contract(self.s,u),(self.s,u))
    def test_other_document_does_not_define_dictionary_identifier(self):
        m=json.loads(self.u);m["source_catalog"]={"business_question.md:L1":"- 本案例主要结果指标：`hidden_gold`，单位为元。"}
        u=json.dumps(m);self.assertEqual(annotate_outcome_contract(self.s,u),(self.s,u))
    def test_conflicting_prior_enum_is_rejected(self):
        m=json.loads(self.u);m["output_schema"]["properties"]["study"]["properties"]["outcome"]["enum"]=["different"]
        with self.assertRaisesRegex(ValueError,"CONFLICTING_PUBLIC"):annotate_outcome_contract(self.s,json.dumps(m))
    def test_original21_dictionary_metadata_only(self):
        for entry in registry()["entries"]:
            if entry["track"]!="NBIB_RAW":continue
            check_public(entry)
            path=public_path(entry["public_directory"])/"data_dictionary.md"
            catalog={f"data_dictionary.md:L{i}":line for i,line in enumerate(path.read_text(encoding="utf8").splitlines(),1)}
            # Tests dictionary extraction only: some raw cases have no fixed
            # network and are intentionally outside the D3/D4 material adapter.
            m={"source_catalog":catalog,"output_schema":{"properties":{"study":{"properties":{"outcome":{"type":"string"}}}}}}
            _,v=annotate_outcome_contract("",json.dumps(m))
            field=json.loads(v)["output_schema"]["properties"]["study"]["properties"]["outcome"]
            self.assertEqual(len(field["enum"]),1,entry["id"])
            self.assertNotIn(field["enum"][0],["metric_before","metric_after"])
    def test_unrecognized_declaration_is_not_transformed(self):
        m=json.loads(self.u);m["source_catalog"]={"data_dictionary.md:L3":"结果可能是营业额、利润或其他字段，尚未决定。"}
        u=json.dumps(m);self.assertEqual(annotate_outcome_contract(self.s,u),(self.s,u))
if __name__=="__main__":unittest.main()

