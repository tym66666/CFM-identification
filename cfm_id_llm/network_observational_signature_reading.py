"""Opt-in R3 signature fields, sharing the historical reader's lifecycle.

This is a wire contract, not a theorem selector or scientific approval. The
original observational profile and its requests remain unchanged.
"""
import json
from typing import Literal
from pydantic import Field, model_validator
from . import network_observational_policy_reading as base
from .network_policy_reading import Exposure, Sufficiency
from .network_design_reading import EXPOSURE_GUIDANCE
from .source_reference_wire import catalog
from .fact_source_contract import public_contract

PROFILE = 'mean-signature'
Profile = Literal['mean-signature', 'mean-signature-definitions'] | None
VERSION = 'network-observational-signature-reading-1'
SUFFICIENCY_DESCRIPTION = (
    '额外科学条件：在conditioning所述同一固定处理前W下，对covered_nodes中每个对象、'
    '所有完整二元安排，其潜在结果条件均值只依赖自身处理与exposure定义的同伴状态。'
    '明确采用或拟采用为true，明确不采用为false，未说明或尚未决定为null；不是科学批准。'
    '仅定义暴露不产生此条件；只在观测支持内成立用OTHER。实际声明的范围及名单须引用。'
    '不采用或未知时不要求补出未声明的作用域、名单或暴露。')


class ConditionalMeanSufficiency(Sufficiency):
    @model_validator(mode='after')
    def sources(self):
        if (self.value is not None or self.scope != 'UNKNOWN' or self.covered_nodes) and not self.source_ids:
            raise ValueError('CONDITIONAL_SUFFICIENCY_SOURCE_REQUIRED')
        return self


class ObservationalSignatureReading(base.ObservationalPolicyReading):
    version: Literal['network-observational-signature-reading-1']
    exposure: Exposure = Field(description=EXPOSURE_GUIDANCE)
    mean_sufficiency: ConditionalMeanSufficiency = Field(description=SUFFICIENCY_DESCRIPTION)

    @model_validator(mode='after')
    def coordinates(self):
        nodes = self.study.nodes
        sf, exp = self.mean_sufficiency, self.exposure
        if len(set(sf.covered_nodes)) != len(sf.covered_nodes) or not set(sf.covered_nodes) <= set(nodes):
            raise ValueError('CONDITIONAL_SUFFICIENCY_NODE_SCOPE_INVALID')
        if (exp.kind not in ('UNKNOWN','NONE') or exp.core_collaborators is not None) and not exp.source_ids:
            raise ValueError('EXPOSURE_DEFINITION_SOURCE_REQUIRED')
        if exp.core_collaborators is not None:
            if exp.kind != 'PRETREATMENT_CORE_COLLABORATOR_MAJORITY':
                raise ValueError('CORE_MAP_WITH_OTHER_EXPOSURE')
            neighbors = {n:{v if u==n else u for u,v in self.study.edges if n in (u,v)} for n in nodes}
            if not set(exp.core_collaborators) <= set(nodes):
                raise ValueError('UNKNOWN_CORE_MAP_NODE')
            if any(not core or len(set(core))!=len(core) or not set(core)<=neighbors[n]
                   for n,core in exp.core_collaborators.items()):
                raise ValueError('NONEMPTY_PRETREATMENT_NEIGHBOR_SUBSET_REQUIRED')
        return self


def reference_catalog(bundle, *, binding):
    return catalog(bundle, base.documents(bundle), binding=binding, version=VERSION)


def make_request(bundle, *, binding):
    request = base.request_for_model(bundle, reference_catalog(bundle,binding=binding), ObservationalSignatureReading)
    body = json.loads(request['user'])
    paths = ['/'+name for name in ObservationalSignatureReading.model_fields
             if name not in ('version','reference_context')]
    paths.append('/information/*/assignment_masses/*')
    body['source_review_contract'] = public_contract(paths)
    # This wire uses direct citations only. The public rule does not grant an
    # undeclared definition_refs extension or implicit parent inheritance.
    body['source_review_contract']['definition_refs_supported'] = False
    request['system'] = base.READING_SYSTEM + '\n字段职责与引用要求见source_review_contract，科学条件的具体含义见Schema；它们是读取规则，不是原文证据或科学批准。'
    request['user'] = json.dumps(body,ensure_ascii=False)
    return request


def parse(bundle, raw, *, binding):
    return base.parse_for_model(raw, reference_catalog(bundle,binding=binding), ObservationalSignatureReading)


def field_constraints(paths, *, request=None):
    # Rechecks reuse the actual first-request rules, not case-specific answers.
    def intersects(path):
        return any(not p or all(a==b or a=='*' or b=='*'
            for a,b in zip(p.split('/'),path.split('/'))) for p in paths)
    rows = [dict(field_path=path, description=description) for path,description in
            (('/exposure',EXPOSURE_GUIDANCE),('/mean_sufficiency',SUFFICIENCY_DESCRIPTION))
            if intersects(path)]
    if request is not None:
        body = json.JSONDecoder().raw_decode(request['user'])[0]
        contract = body.get('source_review_contract',{})
        rows += [dict(field_path=path, description=role,
                      evidence_rule=contract['evidence_rule'])
                 for path,role in contract.get('field_roles',{}).items() if intersects(path)]
    return rows
