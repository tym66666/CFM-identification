"""Opt-in end-to-end role contract. A0 wire stays unchanged; facts retain roles."""
from copy import deepcopy
from . import requested_change_contract as previous
from . import role_effect_reading as facts

CONTRACT='local-change-quantity-2'
FACT_VERSION=facts.VERSION
project=previous.project
apply_gate=previous.apply_gate
omitted_semantics=previous.omitted_semantics
EXTRA_STATE_RULES=previous.EXTRA_STATE_RULES
review_items=previous.review_items
review_definition=previous.review_definition
review_semantics=previous.review_semantics
describe=previous.describe
system_prompt=previous.system_prompt
recheck_field_roles=previous.recheck_field_roles
clarify_fact_request=facts.transform_request


def fact_focus(raw_query,*,query_id,binding):
    request=raw_query['comparison_request']
    if request['quantity'] not in previous.QUANTITIES[:-1]:
        raise ValueError('REVIEWED_DIRECTED_QUANTITY_REQUIRED')
    def content(v):
        return {k:deepcopy(x) for k,x in v.items() if k!='refs'} if type(v) is dict else deepcopy(v)
    return dict(query_id=query_id,business_goal=content(raw_query['goal']),
        reviewed_business_roles=dict(binding_sha256=binding,contract=CONTRACT,kind=raw_query['kind'],
            reference=content(request['reference']),evaluated=content(request['evaluated']),
            conditions={k:content(v) for k,v in raw_query['semantics'].items()},
            scientific_approval=False,is_citable_source=False))


def fact_constraints(paths):
    return previous.fact_constraints(paths)+facts.field_constraints(paths)
