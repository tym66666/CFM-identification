"""Intent split with explicit partial states; never drop known coordinates."""
from copy import deepcopy
import json
from . import business_question_intent_base as base

from cfm_id.workflows.legacy_network.question_intent import VERSION


from cfm_id.workflows.legacy_network.question_intent import make_request


from cfm_id.workflows.legacy_network.question_intent import project_intents


from cfm_id.workflows.legacy_network.question_intent import identify


def normalize(bundle,provider,entry,envelope=None):
    system,user=make_request(bundle,entry,envelope)
    return identify(bundle,provider.generate_json(system_prompt=system,user_prompt=user),entry,envelope)
