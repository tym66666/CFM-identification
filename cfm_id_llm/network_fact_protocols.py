"""Closed request/parser pairs for network facts, not identification routes.

Only developer-selected wire contracts live here. No arbitrary import paths,
source rewriting, scientific permissions or mathematical dispatch.
"""
from dataclasses import dataclass
from functools import lru_cache
from types import MappingProxyType
from typing import Callable, Literal

NetworkFactProfile = Literal[
    'network-source-statements-1', 'network-source-selections-1',
    'network-source-selections-a4-1', 'network-source-selections-roles-1',
    'network-source-selections-information-1', 'network-source-selections-information-2', 'network-source-selections-information-3', 'network-source-selections-information-4',
    'network-source-selections-outcome-1',
    'network-source-selections-remainder-1',
    'network-source-selections-dependencies-1',
    'network-source-selections-alignment-1',
    'network-source-selections-mean-orders-1',
    'network-source-selections-mean-orders-2',
    'network-policy-definition-refs-1',
    'network-policy-record-definitions-1',
    'network-policy-scopes-1',
    'network-policy-scopes-2',
    'network-shared-definitions-1',
] | None


@dataclass(frozen=True)
class NetworkFactProtocol:
    make_request: Callable
    parse: Callable
    model: type
    wire_version: str
    field_constraints: Callable | None = None
    request_field_constraints: Callable | None = None

    def public_constraints(self, paths, *, request):
        """Public reread guidance, paired with this profile's original request."""
        if self.request_field_constraints is not None:
            return self.request_field_constraints(paths, request=request)
        return self.field_constraints(paths) if self.field_constraints is not None else []


@lru_cache(maxsize=1)
def _protocols():
    from . import network_policy_reading as legacy
    from . import network_statement_reading as statements
    from . import network_reading_contract as roles
    from . import network_information_contract as information
    from . import network_model_scope_contract as model_scope
    from . import network_field_contract as field_contract
    from . import network_outcome_contract as outcome_contract
    from . import network_remainder_contract as remainder_contract
    from . import network_source_dependencies as dependencies
    from . import reading_alignment_contract as alignment
    from .network_mean_order_reading import PROFILE as mean_orders
    from .mean_order_ownership import PROFILE as owned_orders
    from . import policy_evidence_dependencies as explicit
    from . import policy_record_definitions as records, policy_scope_reading as scopes
    from . import policy_assumption_dependencies as assumption_dependencies
    from . import shared_fact_definitions as shared
    return MappingProxyType({
        shared.PROFILE: NetworkFactProtocol(shared.make_request, shared.parse, shared.Reading, statements.SELECTION_VERSION,request_field_constraints=shared.field_constraints),
        None: NetworkFactProtocol(legacy.make_request, legacy.parse, legacy.NetworkPolicyReading, legacy.VERSION),
        statements.VERSION: NetworkFactProtocol(statements.make_request, statements.parse, statements.StatementReading, statements.VERSION),
        statements.SELECTION_VERSION: NetworkFactProtocol(statements.make_selection_request, statements.parse_selection, statements.SelectionReading, statements.SELECTION_VERSION),
        statements.INFORMATION_SCOPE_CONTRACT: NetworkFactProtocol(statements.make_information_request, statements.parse_selection, statements.SelectionReading, statements.SELECTION_VERSION),
        roles.CONTRACT: NetworkFactProtocol(roles.make_request, statements.parse_selection, statements.SelectionReading, statements.SELECTION_VERSION),
        information.CONTRACT: NetworkFactProtocol(information.make_request, statements.parse_selection, statements.SelectionReading, statements.SELECTION_VERSION),
        model_scope.CONTRACT: NetworkFactProtocol(model_scope.make_request, statements.parse_selection, statements.SelectionReading, statements.SELECTION_VERSION),
        model_scope.LOCAL_CONTRACT: NetworkFactProtocol(model_scope.make_local_request, statements.parse_selection, statements.SelectionReading, statements.SELECTION_VERSION),
        field_contract.CONTRACT: NetworkFactProtocol(field_contract.make_request, statements.parse_selection, statements.SelectionReading, statements.SELECTION_VERSION,field_contract.field_constraints),
        outcome_contract.CONTRACT: NetworkFactProtocol(outcome_contract.make_request, statements.parse_selection, statements.SelectionReading, statements.SELECTION_VERSION,outcome_contract.field_constraints),
        remainder_contract.CONTRACT: NetworkFactProtocol(remainder_contract.make_request, statements.parse_selection, statements.SelectionReading, statements.SELECTION_VERSION,remainder_contract.field_constraints),
        alignment.NETWORK_CONTRACT: NetworkFactProtocol(alignment.make_request, statements.parse_selection, statements.SelectionReading, statements.SELECTION_VERSION,request_field_constraints=alignment.field_constraints),
        mean_orders: NetworkFactProtocol(alignment.make_request, statements.parse_selection, statements.SelectionReading, statements.SELECTION_VERSION,request_field_constraints=alignment.field_constraints),
        owned_orders: NetworkFactProtocol(alignment.make_request, statements.parse_selection, statements.SelectionReading, statements.SELECTION_VERSION,request_field_constraints=alignment.field_constraints),
        dependencies.CONTRACT: NetworkFactProtocol(dependencies.make_request, statements.parse_selection, statements.SelectionReading, statements.SELECTION_VERSION,request_field_constraints=dependencies.field_constraints),
        explicit.CONTRACT: NetworkFactProtocol(explicit.make_request, explicit.parse, explicit.Reading, explicit.CONTRACT,request_field_constraints=explicit.field_constraints),
        scopes.CONTRACT: NetworkFactProtocol(scopes.make_request, scopes.parse, scopes.Reading, scopes.CONTRACT,request_field_constraints=scopes.field_constraints),
        assumption_dependencies.CONTRACT: NetworkFactProtocol(assumption_dependencies.make_request, assumption_dependencies.parse, assumption_dependencies.Reading, assumption_dependencies.CONTRACT,request_field_constraints=assumption_dependencies.field_constraints),
        records.CONTRACT: NetworkFactProtocol(records.make_request, records.parse, records.Reading, records.CONTRACT,request_field_constraints=records.field_constraints),
    })


def network_fact_profiles():
    return tuple(_protocols())


def network_fact_protocol(profile: NetworkFactProfile):
    if profile is not None and type(profile) is not str:
        raise ValueError('UNKNOWN_NETWORK_FACT_CONTRACT')
    try:
        return _protocols()[profile]
    except KeyError:
        raise ValueError('UNKNOWN_NETWORK_FACT_CONTRACT') from None
