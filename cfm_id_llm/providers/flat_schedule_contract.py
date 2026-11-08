"""Expose existing decision-dependent constraints; never repair model output."""
import json

VERSION = "flat-schedule-explicit-contract-v0.42.1"
TABLE_FIELDS = ("node_order", "world_a_default_outcomes", "world_a_overrides",
                "world_b_default_outcomes", "world_b_overrides")
RULES = """
字段类型按 decision 分支选择，output_schema.oneOf 明确列出两种互斥情形。
PROPOSE_COUNTEREXAMPLE 时：unresolved_reason 必须 null；五个结果表字段全部必须是数组，不能是 null。
特别是某个世界没有任何覆盖项时，其 overrides 必须写空数组 []，不能写 null。
UNDETERMINED 时：五个结果表字段全部必须 null，unresolved_reason 是至少5个字符的原因。
这些只是既有输出格式要求，不改变数学条件。不要因格式要求新增或修改任何假设或业务目标。
"""

def explicit_request(system_prompt, user_prompt):
    data = json.loads(user_prompt)
    schema = data["output_schema"]
    if schema["properties"]["schema_version"].get("const") != "structured-witness-flat-v0.39.1":
        raise ValueError("Unexpected output contract")
    schema["oneOf"] = [
        dict(properties={"decision":{"const":"PROPOSE_COUNTEREXAMPLE"},
                         "unresolved_reason":{"type":"null"},
                         **{k:{"type":"array"} for k in TABLE_FIELDS}},
             required=["decision","unresolved_reason",*TABLE_FIELDS]),
        dict(properties={"decision":{"const":"UNDETERMINED"},
                         "unresolved_reason":{"type":"string","minLength":5},
                         **{k:{"type":"null"} for k in TABLE_FIELDS}},
             required=["decision","unresolved_reason",*TABLE_FIELDS]),
    ]
    for field in ("world_a_overrides", "world_b_overrides"):
        schema["properties"][field]["description"] = (
            "构造反例时必须为数组，没有覆盖项写[]；只有UNDETERMINED时写null。")
    return system_prompt + RULES, json.dumps(data,ensure_ascii=False,separators=(",",":"))

class ExplicitFlatScheduleProviderV0421:
    """Opt-in prompt adapter. Returned content is untouched; old validators run."""
    def __init__(self,provider):
        self.provider=provider
        self.name=provider.name
        self.prompt_version=VERSION
    def generate_json(self,*,system_prompt,user_prompt):
        system,user=explicit_request(system_prompt,user_prompt)
        return self.provider.generate_json(system_prompt=system,user_prompt=user)

