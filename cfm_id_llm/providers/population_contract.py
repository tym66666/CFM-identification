"""Request-only conditional population constraints; never edits model output."""
import json
from copy import deepcopy
def annotate_population_contract(system_prompt,user_prompt):
    m=json.loads(user_prompt);schema=m.get("output_schema",{});study=schema.get("properties",{}).get("study",{})
    if "global_quota" not in study.get("properties",{}):return system_prompt,user_prompt
    q=schema.get("$defs",{}).get("Question",{})
    if q.get("properties",{}).get("population",{}).get("$ref")!="#/$defs/Selection":return system_prompt,user_prompt
    nodes=m.get("data_catalog",{}).get("nodes")
    if not isinstance(nodes,list) or not nodes or any(not isinstance(x,str) for x in nodes) or len(nodes)!=len(set(nodes)):
        raise ValueError("VALID_PUBLIC_NODE_CATALOG_REQUIRED")
    original=schema["$defs"].get("Selection",{})
    if original.get("properties",{}).get("selection",{}).get("enum") is None:
        raise ValueError("EXPECTED_SELECTION_CONTRACT_REQUIRED")
    def option(label,ids):
        return dict(type="object",additionalProperties=False,required=["selection","ids"],properties=dict(selection=dict(type="string",const=label),ids=ids))
    schema["$defs"]["Selection"]={"oneOf":[
        option("指定",dict(type="array",minItems=1,uniqueItems=True,items=dict(type="string",enum=nodes))),
        option("全体",dict(type="array",maxItems=0,items=dict(type="string"))),
        option("不明确",dict(type="array",maxItems=0,items=dict(type="string")))],
        "description":"population中的指定必须有原文明示编号；没有编号的某站点用不明确且ids=[]。全体也用ids=[]由程序展开；不可为了满足非空要求猜编号。"}
    system_prompt+="\npopulation是有条件的二元合同：明确编号才用指定且ids非空；某个未指明站点必须selection=不明确且ids=[]。不要输出指定+空名单，也不要猜编号。这是编码约束，不增加业务事实。\n"
    return system_prompt,json.dumps(m,ensure_ascii=False)
class ExplicitPopulationSelectionProviderV0461:
    def __init__(self,provider):self.provider=provider;self.name=getattr(provider,"name","wrapped")
    def generate_json(self,*,system_prompt,user_prompt):
        s,u=annotate_population_contract(system_prompt,user_prompt)
        return self.provider.generate_json(system_prompt=s,user_prompt=u)

