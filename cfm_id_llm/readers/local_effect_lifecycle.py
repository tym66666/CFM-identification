"""Pair existing local-effect readers; no prompt, model or approval changes."""
from .. import network_effect_reading as legacy, role_effect_reading as role
from .. import owned_effect_reading as owned, scoped_effect_reading as scoped
from .. import network_source_dependencies as dependencies, reading_alignment_contract as alignment
from ..compact_response_contract import evidence_contract

reference_catalog = legacy.reference_catalog


def variants():
    return ((None,legacy,legacy.NetworkEffectReading),
            (legacy.VERSION,legacy,legacy.NetworkEffectReading),
            (role.VERSION,role,role.RoleReading),
            (owned.VERSION,owned,owned.Reading),
            (scoped.VERSION,scoped,scoped.Reading))


def make_request(bundle, *, binding, assignment_semantics=None, network_fact_contract=None):
    request=legacy.make_request(bundle,binding=binding,assignment_semantics=assignment_semantics)
    if network_fact_contract==alignment.NETWORK_CONTRACT:return alignment.apply(request)
    if network_fact_contract==dependencies.CONTRACT:return dependencies.apply(request)
    return request


def parse(entry, raw):
    version=entry.get('effect_fact_contract')
    module=next((module for profile,module,_ in variants() if profile==version),None)
    if module is None:raise ValueError('UNKNOWN_EFFECT_FACT_CONTRACT')
    options=dict(binding=entry['fact_binding_sha256'])
    if module is not legacy:
        reviewed=entry['reviewed_local_request']
        if module is scoped:
            if getattr(evidence_contract(reviewed['contract']),'FACT_VERSION',None)!=scoped.VERSION:
                raise ValueError('REVIEWED_ROLE_CONTRACT_REQUIRED')
        else:
            from ..local_role_ownership import CONTRACT as OWNED
            from ..role_coordinate_contract import CONTRACT as ROLE
            if reviewed['contract']!=(OWNED if module is owned else ROLE):
                raise ValueError('REVIEWED_ROLE_CONTRACT_REQUIRED')
        options['reviewed_query']=reviewed['raw_query']
    return module.parse(entry['bundle'],raw,**options)


def field_constraints(entry, paths):
    from .. import network_effect_conditioning
    rows = _field_constraints(entry, paths)
    if network_effect_conditioning.has_explicit_context(entry.get('reviewed_target_context')):
        rows += network_effect_conditioning.field_constraints(paths)
    return rows


def _field_constraints(entry, paths):
    if entry.get('effect_fact_contract')==scoped.VERSION:
        local=entry.get('reviewed_local_request')
        if local:
            adapter=evidence_contract(local['contract'])
            if getattr(adapter,'FACT_VERSION',None)==scoped.VERSION:
                return adapter.fact_constraints(paths)
        return scoped.field_constraints(paths)
    if entry.get('effect_fact_contract')==owned.VERSION:
        return owned.field_constraints(paths)
    rows=[]
    profile=entry.get('network_fact_contract')
    if profile==alignment.NETWORK_CONTRACT:
        rows=alignment.field_constraints(paths,request=entry['request'])
    elif profile==dependencies.CONTRACT:
        rows=dependencies.field_constraints(paths,request=entry['request'])
    if entry.get('reviewed_local_request'):
        rows+=evidence_contract(entry['reviewed_local_request']['contract']).fact_constraints(paths)
    return rows
