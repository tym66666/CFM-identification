"""Explicit definition ownership including the scope of mean sufficiency.

Uses the existing source-review and definition resolver. Kept as a distinct wire
so saved requests and reviews from all prior contracts remain replayable.
No source selection, scientific adoption, target inference or mathematical work.
"""
from typing import Literal
from pydantic import Field
from . import policy_evidence_dependencies as definitions
from . import network_statement_reading as statements, reading_alignment_contract as alignment

CONTRACT = 'network-policy-record-definitions-1'
ADDITIONAL_RECORDS = (('mean_sufficiency', ('covered_nodes',)),)


class DefinedMeanSufficiency(statements.SelectedMeanSufficiency):
    definition_refs: list[Literal['study']] = Field(description=definitions.RULE)


class Reading(definitions.Reading):
    version: Literal['network-policy-record-definitions-1']
    mean_sufficiency: DefinedMeanSufficiency


def _request(request, model):
    return definitions._request(request, model, contract=CONTRACT,
        extra_required={'mean_sufficiency': 'study when covered_nodes is nonempty; the scope and adoption status still require their own direct claim sources'},
        schema_aliases={'DefinedMeanSufficiency': 'SelectedMeanSufficiency'})


def make_request(bundle, *, binding, assignment_semantics=None):
    return _request(alignment.make_request(bundle, binding=binding,
        assignment_semantics=assignment_semantics), Reading)


def make_contrast_request(bundle, *, binding, assignment_semantics=None):
    from . import network_contrast_reading as contrast
    return _request(contrast.make_request(bundle, binding=binding,
        assignment_semantics=assignment_semantics, profile=alignment.NETWORK_CONTRACT),
        contrast.reading_model(CONTRACT))


def parse(bundle, raw, *, binding):
    return definitions.parse_defined(bundle, raw, binding=binding, model=Reading,
        contract=CONTRACT, additional_records=ADDITIONAL_RECORDS)


def parse_contrast(bundle, raw, *, binding):
    return definitions.parse_defined_contrast(bundle, raw, binding=binding,
        mean_parser=parse, contract=CONTRACT, additional_records=ADDITIONAL_RECORDS)


def field_constraints(paths, *, request):
    return definitions.field_constraints(paths, request=request, contract=CONTRACT)
