"""Test-only comparisons of configured readers before native compilation.

These assertions justify running native proofs on representative protocols.
They do not equate review receipts or certify arbitrary future inputs.
"""
from copy import deepcopy
import json
from jsonschema import Draft202012Validator


NATIVE_PROFILES = (None, 'network-source-selections-alignment-1')

def current_fixture(entry, candidate):
    """Author current-wire fixtures; never used for live model answers."""
    from cfm_id_llm import shared_fact_definitions as shared
    raw=deepcopy(candidate)
    if entry.get('network_fact_contract')==shared.PROFILE:
        raw['study']['network_source_ids']=list(raw['study']['source_ids'])
        reverse={v:k for k,v in shared.LAW_NAMES.items()}
        for info in raw['information']:info['operator']=reverse.get(info['operator'],info['operator'])
    return raw


def validate_candidate(entry, candidate):
    body = json.JSONDecoder().raw_decode(entry['request']['user'])[0]
    Draft202012Validator(body['output_schema']).validate(candidate)


def method_contracts(plan):
    assert plan['state'] == 'REVIEW_REQUIRED' and not plan['backend_called']
    return [dict(method=row['method'], source_indices=row['source_indices'],
                 reading_decisions=row['reading_worksheet']['decisions'],
                 science_decisions=row['science_worksheet']['decisions'])
            for row in plan['methods']]


def policy_inputs(plan, reference_context):
    facts = deepcopy(plan['facts'])
    # This is request identity, not mathematics: check it locally before
    # excluding this one named field from cross-request comparisons.
    assert facts.pop('reference_context') == reference_context
    return dict(facts=facts, target=plan['proposed_target'],
                a4=plan.get('a4_projection'), methods=method_contracts(plan))


def contrast_inputs(plan, reference_context):
    return dict(target=plan['proposed_target'], methods=method_contracts(plan),
                endpoints={side: policy_inputs(plan['endpoint_plans'][side], reference_context)
                           for side in ('first', 'second')})
