"""Frozen network compatibility implementation extracted from evaluation.

Explicit inputs and independent reviews remain required. No default benchmark
selection, fixture approval, or candidate-model continuation is provided here.
See README.md before extending this historical protocol.
"""
from copy import deepcopy
import json
import cfm_id.workflows.legacy_network.materials_compact_json as previous
from cfm_id.workflows.legacy_network.materials_target_precedence import output_schema as prior_schema
from cfm_id.workflows.legacy_network.materials_base import bundle_value
from cfm_id.serialization import canonical_hash


VERSION='business-materials-v0.24.2'


SYSTEM=previous.SYSTEM.replace(
    '组内固定名额=每组均匀无放回抽指定人数，填quota；整组开关=全组一起采用或不采用，填probability；另一参数null。',
    '组内固定名额=每组均匀无放回抽指定人数，逐组填quota、probability=null。整组开关=全组一起采用或不采用。若data_catalog.cluster_rates完整列出了各组概率，group_parameters填null，由程序直接绑定原表；若没有该表，才逐组填probability、quota=null。不能把表中概率当作抽签独立声明。')


def output_schema(bundle):
    schema=prior_schema(bundle)
    if bundle['structure']['cluster_rates']:
        properties=schema['properties']['study']['properties']
        properties['group_parameters']={'anyOf':[properties['group_parameters'],{'type':'null'}],
            'description':'整组开关且cluster_rates完整时填null，程序绑定原概率表；其他情况逐组摘录参数，不猜测。'}
    return schema


def make_request(value):
    _,user=previous.make_request(value); message=json.loads(user)
    message['output_schema']=output_schema(bundle_value(value))
    return SYSTEM,json.dumps(message,ensure_ascii=False)


def expand(value,raw):
    bundle=bundle_value(value); copied=deepcopy(raw); binding=None
    if isinstance(copied,dict) and isinstance(copied.get('study'),dict):
        study=copied['study']
        if 'group_parameters' in study and study['group_parameters'] is None:
            rates=bundle['structure']['cluster_rates']; groups=bundle['structure']['groups']
            if study.get('design')!='整组开关' or not rates or set(rates)!=set(groups):
                raise ValueError('COMPLETE_CLUSTER_PROBABILITY_TABLE_REQUIRED')
            study['group_parameters']=[dict(group_id=g,quota=None,probability=rates[g]) for g in sorted(groups)]
            binding=dict(source='cluster_randomization.csv',file_sha256=bundle['file_inventory']['cluster_randomization.csv']['sha256'],
                         parameters=deepcopy(study['group_parameters']),independence_inferred=False)
    return copied,binding


def project(value,raw):
    expanded,_=expand(value,raw)
    return previous.project(value,expanded)


def evaluate_draft(value,raw,packet,*,synthetic_protocol_selected=False):
    try: expanded,binding=expand(value,raw)
    except ValueError as exc:
        return dict(version=VERSION,status='REJECTED',reason_code=str(exc),results=[],production_admission=False,
            semantic_correctness_verified=False,candidate_generator_called=False,estimation_called=False,
            policy_called=False,nonidentification_proven=False,model_draft_sha256=canonical_hash(raw))
    result=previous.evaluate_draft(value,expanded,packet,synthetic_protocol_selected=synthetic_protocol_selected)
    result.update(version=VERSION,model_draft_sha256=canonical_hash(raw),local_design_table_binding=binding)
    return result
