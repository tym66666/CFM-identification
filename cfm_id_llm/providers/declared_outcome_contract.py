"""Expose an explicit public outcome identifier; never repair model output.

The recognized declaration is the public NBIB data-dictionary convention, not
a research-only reference. Ambiguous or absent declarations remain unconstrained.
"""
import json,re

_DECLARATION=re.compile(r"^\s*-\s*本案例主要结果指标\s*[：:]\s*`([A-Za-z_][A-Za-z0-9_]*)`\s*[，,]")

def annotate_outcome_contract(system_prompt,user_prompt):
    message=json.loads(user_prompt)
    candidates={}
    for source,text in message.get("source_catalog",{}).items():
        if not source.startswith("data_dictionary.md:L") or not isinstance(text,str):
            continue
        match=_DECLARATION.match(text)
        if match:candidates[source]=match.group(1)
    identifiers=set(candidates.values())
    if len(identifiers)!=1:return system_prompt,user_prompt
    outcome=next(iter(identifiers))
    prop=message["output_schema"]["properties"]["study"]["properties"]["outcome"]
    # Preserve a narrower upstream contract rather than replacing disagreement.
    if "enum" in prop and outcome not in prop["enum"]:
        raise ValueError("CONFLICTING_PUBLIC_OUTCOME_CONTRACT")
    prop["enum"]=[outcome]
    prop["description"]="本案例主要结果指标的业务标识，来自"+", ".join(sorted(candidates))+"；CSV通用存储列名不是这个字段的业务标识。"
    system_prompt+="\nstudy.outcome填写数据字典明确声明的主要结果指标标识，并遵守该字段enum。metric_before/metric_after这类通用CSV列名不等于业务指标名；不能互相替换。该绑定不提供总体信息或科学许可。\n"
    return system_prompt,json.dumps(message,ensure_ascii=False)

class DeclaredOutcomeContractProviderV0441:
    def __init__(self,provider):
        self.provider=provider
        self.name=getattr(provider,"name","provider")+":declared-outcome-contract-v0441"
    def generate_json(self,*,system_prompt,user_prompt):
        system_prompt,user_prompt=annotate_outcome_contract(system_prompt,user_prompt)
        return self.provider.generate_json(system_prompt=system_prompt,user_prompt=user_prompt)

