import unittest,json
from copy import deepcopy
from examples.nbib_d2_fixture import load_case
from evaluation.business_d2_submission import make_request,preview_submission
from cfm_id_llm.providers.population_contract import annotate_population_contract,ExplicitPopulationSelectionProviderV0461
class PopulationContractTests(unittest.TestCase):
 def setUp(self):self.i=load_case("NBIB-002");self.s,self.u=make_request(self.i["bundle"])
 def test_specified_requires_public_nonempty_ids(self):
  _,u=annotate_population_contract(self.s,self.u);d=json.loads(u)["output_schema"]["$defs"]["Selection"]["oneOf"][0]
  self.assertEqual(d["properties"]["ids"]["minItems"],1);self.assertEqual(d["properties"]["ids"]["items"]["enum"],self.i["bundle"]["structure"]["nodes"])
 def test_unknown_requires_empty_ids(self):
  _,u=annotate_population_contract(self.s,self.u);o=json.loads(u)["output_schema"]["$defs"]["Selection"]["oneOf"]
  self.assertEqual(o[2]["properties"]["selection"]["const"],"不明确");self.assertEqual(o[2]["properties"]["ids"]["maxItems"],0)
 def test_public_documents_unchanged(self):
  _,u=annotate_population_contract(self.s,self.u);a,b=json.loads(self.u),json.loads(u)
  for k in ("documents","source_catalog","data_catalog","question_slots","file_inventory"):self.assertEqual(a[k],b[k])
 def test_output_not_repaired(self):
  raw=deepcopy(self.i["raw"]);raw["questions"]["q1"]["population"]["selection"]="指定"
  class Provider:
   calls=0
   def generate_json(p,**kw):p.calls+=1;return raw
  p=Provider();out=ExplicitPopulationSelectionProviderV0461(p).generate_json(system_prompt=self.s,user_prompt=self.u)
  self.assertIs(out,raw);self.assertEqual(p.calls,1);self.assertEqual(preview_submission(self.i["bundle"],out)["state"],"DRAFT_INVALID")
 def test_other_entry_unchanged(self):
  u=json.dumps({"output_schema":{"properties":{"study":{"properties":{}}}}})
  self.assertEqual(annotate_population_contract("s",u),("s",u))
 def test_no_public_ids_rejected(self):
  m=json.loads(self.u);m["data_catalog"]["nodes"]=[]
  with self.assertRaises(ValueError):annotate_population_contract(self.s,json.dumps(m))
if __name__=="__main__":unittest.main()

