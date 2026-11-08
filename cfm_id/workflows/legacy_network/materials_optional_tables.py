"""Frozen network compatibility implementation extracted from evaluation.

Explicit inputs and independent reviews remain required. No default benchmark
selection, fixture approval, or candidate-model continuation is provided here.
See README.md before extending this historical protocol.
"""
import json
import cfm_id.workflows.legacy_network.materials_compact_json as without_table
import cfm_id.workflows.legacy_network.materials_probability_tables as with_table
from cfm_id.workflows.legacy_network.materials_base import bundle_value


VERSION='business-materials-v0.24.3'


def make_request(value):
    bundle=bundle_value(value)
    rates=bundle['structure']['cluster_rates']
    if not rates:
        # The observed null-quota regression came from exposing an irrelevant
        # shortcut. Restore the exact previously validated no-table request.
        return without_table.make_request(value)
    system,user=with_table.make_request(value);message=json.loads(user)
    message['available_local_design_binding']=dict(
        applies_only_to_design='整组开关',source='cluster_randomization.csv',
        groups=sorted(rates),parameters_field_when_applied=None,
        independence_or_causal_license_implied=False)
    return system,json.dumps(message,ensure_ascii=False)


def project(value,raw):
    return with_table.project(value,raw)


def evaluate_draft(value,raw,packet,*,synthetic_protocol_selected=False):
    result=with_table.evaluate_draft(value,raw,packet,synthetic_protocol_selected=synthetic_protocol_selected)
    result['version']=VERSION
    return result
