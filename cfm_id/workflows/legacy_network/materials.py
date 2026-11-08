"""Frozen network compatibility implementation extracted from evaluation.

Explicit inputs and independent reviews remain required. No default benchmark
selection, fixture approval, or candidate-model continuation is provided here.
See README.md before extending this historical protocol.
"""
import json
import cfm_id.workflows.legacy_network.materials_whole_clause_evidence as previous
from cfm_id.workflows.legacy_network.materials_base import bundle_value
from cfm_id.materials import sources


VERSION='business-materials-v0.24.6'


def allowed_design_sources(value):
    bundle=bundle_value(value)
    return list(sources(bundle))+(['cluster_randomization.csv'] if 'cluster_randomization.csv' in bundle['tables'] else [])


def make_request(value):
    system,user=previous.make_request(value)
    message=json.loads(user)
    prop=message['output_schema']['properties']['study']['properties']['design_sources']
    prop.update(minItems=1,items=dict(type='string',enum=allowed_design_sources(value)),
        description='说明抽签规则、参数或独立性的原句编号，或实际存在的cluster_randomization.csv；名册与网络已由程序绑定，不填在这里。')
    system+='\nstudy.design_sources只从该字段的enum中选择。units.csv和network_edges.csv是已绑定的结构文件，不是该字段允许的抽签设计来源。不要复制所有文件名。\n'
    return system,json.dumps(message,ensure_ascii=False)


project=previous.project


def evaluate_draft(value,raw,packet,*,synthetic_protocol_selected=False):
    result=previous.evaluate_draft(value,raw,packet,synthetic_protocol_selected=synthetic_protocol_selected)
    result['version']=VERSION
    return result
