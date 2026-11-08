"""Model-facing policy fields, separate from legacy client compatibility.

Only fixed-policy values and full-policy contrasts change their output view.
Other goals keep their own fields. Projection copies the declared owner and
its evidence; it never resolves two model answers or fills missing content.
"""
from . import guided_policy_reading as guided
from . import policy_action_contract as owner
from .guided_policy_reading import (
    KINDS, FACT_VERSION, BIND_POPULATION_INFORMATION, EXTRA_STATE_RULES,
    POLICY_FOCUS_READERS, review_definition, review_items, omitted_semantics,
    review_semantics, apply_gate, clarify_fact_request, fact_constraints,
    fact_focus, target_context, admission, recheck_field_roles, policy_focus,
)

CONTRACT = 'model-policy-output-1'


def _prune_unused_definitions(schema):
    """Keep only definitions referenced by the generated output branches."""
    defs = schema['$defs']; needed = set()

    def visit(value):
        if isinstance(value, dict):
            ref = value.get('$ref', '')
            if ref.startswith('#/$defs/'):
                name = ref.split('/')[2]
                if name not in needed:
                    needed.add(name)
                    visit(defs[name])
            for key, child in value.items():
                if key != '$defs':
                    visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(schema)
    schema['$defs'] = {k: v for k, v in defs.items() if k in needed}


def describe(schema):
    guided.describe(schema)
    # Old callers still use policy_action_compat. The model has no alias slot.
    schema['$defs']['PolicyActionSemantics']['properties'].pop('policy_assignment')
    _prune_unused_definitions(schema)
    return ''


def system_prompt(**kwargs):
    text = guided.system_prompt(**kwargs)
    old = '主政策字段及精确兼容别名以PolicyActionSemantics为准；无需生成兼容别名。'
    if text.count(old) != 1:
        raise ValueError('MODEL_POLICY_OWNER_GUIDANCE_CHANGED')
    return text.replace(old,
        '固定政策均值与两政策差值使用PolicyActionSemantics：主方案只填intervention；不输出policy_assignment。')


def project(raw, catalog):
    projected, details = owner.project(raw, catalog)
    receipt = details['policy_action_projection']
    receipt.update(contract=CONTRACT, compatibility_view_generated=True,
                   alias_accepted_from_model=False, citations_merged=False)
    return projected, details
