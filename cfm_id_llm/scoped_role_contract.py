"""Same A0 ownership contract, explicit reviewed-kind and information-scope facts."""
from . import local_role_ownership as previous, scoped_effect_reading as facts

CONTRACT = 'local-role-ownership-2'
FACT_VERSION = facts.VERSION
project = previous.project
apply_gate = previous.apply_gate
omitted_semantics = previous.omitted_semantics
EXTRA_STATE_RULES = previous.EXTRA_STATE_RULES
review_items = previous.review_items
review_definition = previous.review_definition
review_semantics = previous.review_semantics
describe = previous.describe
system_prompt = previous.system_prompt
recheck_field_roles = previous.recheck_field_roles
clarify_fact_request = facts.transform_request
fact_constraints = facts.field_constraints


def fact_focus(raw_query, *, query_id, binding):
    focus = previous.fact_focus(raw_query, query_id=query_id, binding=binding)
    focus['reviewed_business_roles']['contract'] = CONTRACT
    return focus
