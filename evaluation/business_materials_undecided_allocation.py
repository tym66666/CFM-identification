"""Withhold an allocation rule when its cited text explicitly leaves it undecided.

This is a conservative contradiction veto, not a natural-language entailment
proof. It never creates a positive declaration, scientific license, or target.
The v0.24.3 adapter remains available for replaying frozen historical results.
"""
from copy import deepcopy
import json
import re
from . import business_materials_optional_tables as previous
from .business_materials_base import bundle_value
from .business_materials_intake import sources
from .business_core_pilot_base import canonical_hash

VERSION = 'business-materials-v0.24.4'
from cfm_id.workflows.legacy_network.materials_undecided_allocation import REMAINING_INSTRUCTION

# These patterns only remove unsupported positive claims. They do not recognize
# every paraphrase, approve arbitrary remaining distributions, or read gold IDs.
from cfm_id.workflows.legacy_network.materials_undecided_allocation import _UNCERTAIN
from cfm_id.workflows.legacy_network.materials_undecided_allocation import _DENIED

from cfm_id.workflows.legacy_network.materials_undecided_allocation import make_request

def normalize(value,raw):
    copied=deepcopy(raw)
    actions=[]
    catalog=sources(bundle_value(value))
    if not isinstance(copied,dict) or not isinstance(copied.get('questions'),dict):
        return copied,actions
    for sid,q in copied['questions'].items():
        if not isinstance(q,dict):
            continue
        ref=q.get('remaining_source')
        if not isinstance(ref,str) or ref not in catalog:
            continue  # Earlier validators reject malformed/unavailable sources.
        text=catalog[ref]
        if _UNCERTAIN.search(text) or _DENIED.search(text):
            q['remaining_source']=None
            actions.append(dict(question_id=sid,field='remaining_source',source=ref,
                reason_code='REMAINING_SOURCE_EXPLICITLY_UNSET_OR_DENIED',withheld=True))
    return copied,actions

def project(value,raw):
    normalized,_=normalize(value,raw)
    return previous.project(value,normalized)

def evaluate_draft(value,raw,packet,*,synthetic_protocol_selected=False):
    normalized,actions=normalize(value,raw)
    result=previous.evaluate_draft(value,normalized,packet,synthetic_protocol_selected=synthetic_protocol_selected)
    result.update(version=VERSION,model_draft_sha256=canonical_hash(raw),
        remaining_evidence_vetoes=actions,
        remaining_evidence_gate='explicit_contradiction_veto_not_semantic_proof')
    return result
