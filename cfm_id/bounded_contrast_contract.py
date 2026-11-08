"""Opt-in ordered contrast on ONE reviewed finite D2/E1 mean model.

Shares input validation only. No approval, support computation or solving here.
See docs/BOUNDED_CONTRAST_MATH_ZH.txt for the proof and literature boundaries.
"""
from cfm_id_bridge.scientific_binding import sha
from .bounded_policy_contract import validate_model, fail

VERSION = 'bounded-policy-contrast-1'
SIDES = ('first', 'second')


def validate_pair(inquiries, information):
    for mapping in (inquiries, information):
        if type(mapping) is not dict or set(mapping) != set(SIDES):
            fail('CHECK_BLOCKED', 'EXACT_TWO_ORDERED_MODELS_REQUIRED')
    validated = {s: validate_model(inquiries[s], information[s]) for s in SIDES}
    a, b = (inquiries[s] for s in SIDES)
    # All scientific structure is shared. Only the target may differ.
    for name in ('study', 'assumptions', 'r2_signature', 'r2_sufficiency', 'r2_sources'):
        if sha(getattr(a, name)) != sha(getattr(b, name)):
            fail('CHECK_BLOCKED', 'COMMON_CONTRAST_SCIENTIFIC_MODEL_REQUIRED')
    if (a.target.node_order != b.target.node_order
            or a.target.unit_weights != b.target.unit_weights):
        fail('CHECK_BLOCKED', 'COMMON_CONTRAST_POPULATION_AND_WEIGHTS_REQUIRED')
    contents = [information[s].model_dump(exclude={'inquiry_sha256'}) for s in SIDES]
    if sha(contents[0]) != sha(contents[1]):
        fail('CHECK_BLOCKED', 'COMMON_COMPLETE_NUMERIC_INFORMATION_REQUIRED')
    st, _, known, bounds = validated['first']
    return st, {s: validated[s][1] for s in SIDES}, known, bounds


def target_coordinates(inquiries):
    a, b = (inquiries[s].target for s in SIDES)
    return dict(node_order=list(a.node_order), first=list(a.policy_assignment),
                second=list(b.policy_assignment), unit_weights=list(a.unit_weights),
                operation='first_minus_second')


def input_digest(inquiries, information):
    return sha(dict(version=VERSION, inquiries=inquiries, information=information))
