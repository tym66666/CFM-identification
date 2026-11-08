"""Question-local evidence for peer predicates, shared by typed reading entries.

This is a conservative lexical admission check, NOT an entailment prover. It
does not infer a target, approve science, or correct an LLM output. Unsupported
wording requires reading review. Role binding and contrast orientation still
require independent semantic review, even when this check succeeds.
"""
from copy import deepcopy
import json
import re

from cfm_id.workflows.legacy_network.condition_evidence_base import VERSION
from cfm_id.workflows.legacy_network.condition_evidence_base import INSTRUCTION

from cfm_id.workflows.legacy_network.condition_evidence_base import _NUMBER
from cfm_id.workflows.legacy_network.condition_evidence_base import _EXACT
from cfm_id.workflows.legacy_network.condition_evidence_base import _PATTERNS
from cfm_id.workflows.legacy_network.condition_evidence_base import _UNSET
from cfm_id.workflows.legacy_network.condition_evidence_base import _SPLIT


from cfm_id.workflows.legacy_network.condition_evidence_base import augment_request


from cfm_id.workflows.legacy_network.condition_evidence_base import _integer


from cfm_id.workflows.legacy_network.condition_evidence_base import _literal_support


from cfm_id.workflows.legacy_network.condition_evidence_base import project_evidence


from cfm_id.workflows.legacy_network.condition_evidence_base import guarded_dispatch


def normalize(bundle, provider, request, consumer):
    system, user = augment_request(*request)
    raw = provider.generate_json(system_prompt=system, user_prompt=user)
    return guarded_dispatch(bundle, raw, consumer)
