"""Separate question intent from missing coordinates in one model response.

This is a reading contract, not a new identification route. Intent labels are
projected mechanically to the existing operation enum; no coordinates are filled.
"""
from copy import deepcopy
import json
from . import business_frozen_reading as previous

from cfm_id.workflows.legacy_network.question_intent_base import VERSION
from cfm_id.workflows.legacy_network.question_intent_base import OPERATIONS
from cfm_id.workflows.legacy_network.question_intent_base import INSTRUCTION


from cfm_id.workflows.legacy_network.question_intent_base import make_request


from cfm_id.workflows.legacy_network.question_intent_base import project_intents


from cfm_id.workflows.legacy_network.question_intent_base import identify


def normalize(bundle, provider, entry, envelope=None):
    system, user = make_request(bundle, entry, envelope)
    return identify(bundle, provider.generate_json(system_prompt=system, user_prompt=user), entry, envelope)
