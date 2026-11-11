"""Closed lifecycle bindings for the registered business reader families.

This registry pairs existing reading components. It does not select a causal
method, interpret text, grant reviews, load caller-provided code, or change a
wire contract. Other reader families retain their existing compatibility paths.
"""
from copy import deepcopy
from dataclasses import dataclass
from functools import partial
from typing import Callable, get_args
from pydantic import BaseModel


class ReadingContractError(ValueError):
    """Invalid wiring or metadata, never a mathematical coverage conclusion."""


@dataclass(frozen=True)
class TargetContextHandoff:
    clarify_request: Callable
    field_constraints: Callable
    decision: str
    description: str

    def review_item(self, reviewed_context, fact_conditioning):
        # Merely display both claims; equality of prose is not an approval.
        return dict(requirement=self.description, reviewed_query=deepcopy(reviewed_context),
                    fact_conditioning=deepcopy(fact_conditioning), decision=self.decision,
                    is_approval=False)


@dataclass(frozen=True)
class FactReadingContract:
    reader_id: str
    reference_format: str
    version_field: str | None
    wire_version: str
    make_request: Callable
    parse: Callable
    reference_catalog: Callable
    model: type[BaseModel]
    documents: Callable
    target_context: TargetContextHandoff | None
    profile_field: str | None = None
    profile: str | None = None
    uses_assignment_semantics: bool = False
    field_constraints: Callable | None = None
    clarify_comparison: Callable | None = None
    contextual_parse: Callable | None = None
    contextual_constraints: Callable | None = None
    uses_network_profile: bool = False
    facts_model: type[BaseModel] | None = None

    def __post_init__(self):
        if (not all(type(x) is str and x.strip() for x in
                    (self.reader_id, self.reference_format, self.wire_version))
                or not all(callable(f) for f in
                           (self.make_request, self.parse, self.reference_catalog, self.documents))
                or not isinstance(self.model, type) or not issubclass(self.model, BaseModel)):
            raise ReadingContractError('INCOMPLETE_FACT_READING_CONTRACT')
        if (not all(v is None or (type(v) is str and v.strip()) for v in
                    (self.version_field, self.profile_field, self.profile))
                or not (self.version_field or self.profile_field)
                or (self.profile is not None and self.profile_field is None)
                or (self.version_field is not None and self.version_field == self.profile_field)
                or type(self.uses_assignment_semantics) is not bool
                or (self.field_constraints is not None and not callable(self.field_constraints))
                or (self.clarify_comparison is not None and not callable(self.clarify_comparison))):
            raise ReadingContractError('INVALID_FACT_READING_SELECTOR')
        if any(f is not None and not callable(f) for f in (self.contextual_parse,self.contextual_constraints)):
            raise ReadingContractError('INVALID_FACT_READING_CONTEXT_HANDLER')
        if self.facts_model is not None and (not isinstance(self.facts_model,type) or not issubclass(self.facts_model,BaseModel)):
            raise ReadingContractError('INVALID_PROJECTED_FACTS_MODEL')
        version = self.model.model_fields.get('version')
        if version is None or get_args(version.annotation) != (self.wire_version,):
            raise ReadingContractError('INCOMPLETE_FACT_READING_CONTRACT')
        context = self.target_context
        if context is not None and (not isinstance(context, TargetContextHandoff)
                or not callable(context.clarify_request) or not callable(context.field_constraints)
                or not all(type(x) is str and x.strip() for x in (context.decision,context.description))):
            raise ReadingContractError('INCOMPLETE_TARGET_CONTEXT_HANDOFF')

    def check_entry(self, entry):
        if (entry.get('reader_id') != self.reader_id
                or entry.get('reference_format') != self.reference_format
                or (self.version_field is not None and self.version_field in entry
                    and entry[self.version_field] != self.wire_version)
                or (self.profile_field is not None and entry.get(self.profile_field) != self.profile)):
            raise ReadingContractError('FACT_READING_CONTRACT_MISMATCH')
        # Old minimal callers may omit the version metadata. An explicitly
        # supplied foreign/unknown version must never select this parser.

    def entry_metadata(self):
        """Preserve old receipts: omitted default profile stays omitted."""
        metadata = {self.version_field: self.wire_version} if self.version_field else {}
        if self.profile_field and self.profile is not None:
            metadata[self.profile_field] = self.profile
        return metadata

    def request(self, bundle, *, binding, assignment_semantics=None, signed_comparison=False, network_fact_contract=None):
        options = dict(binding=binding)
        if self.uses_assignment_semantics:
            options['assignment_semantics'] = assignment_semantics
        if self.uses_network_profile:
            options['network_fact_contract'] = network_fact_contract
        request = self.make_request(bundle, **options)
        if signed_comparison and self.clarify_comparison is not None:
            request = self.clarify_comparison(request)
        return request

    def parse_candidate(self, entry, raw):
        self.check_entry(entry)
        if self.contextual_parse is not None:
            return self.contextual_parse(entry, raw)
        return self.parse(entry['bundle'], raw, binding=entry['fact_binding_sha256'])

    def public_constraints(self, entry, paths):
        self.check_entry(entry)
        extra = []
        if self.reader_id == 'NETWORK_RANDOMIZED_EFFECT_FACTS':
            from .assumption_choices import field_constraints
            extra = field_constraints(paths)
        if self.reader_id in ('NETWORK_RANDOMIZED_EFFECT_FACTS','NETWORK_RANDOMIZED_ARM_FACTS'):
            from .network_population_contract import field_constraints
            extra += field_constraints(paths)
        if self.contextual_constraints is not None:
            rows = self.contextual_constraints(entry, paths)
            if entry.get('reviewed_intent') is None:
                return rows + extra
        else:
            rows = self.field_constraints(paths, request=entry['request']) if self.field_constraints else []
        if self.target_context is not None and entry.get('reviewed_target_context'):
            rows += self.target_context.field_constraints(paths)
        if entry.get('reviewed_intent') is not None:
            from .reviewed_intent_handoff import field_constraints
            rows += field_constraints(paths)
        return rows + extra


def registrations():
    # Static source-owned pairing; no user data controls imports. Construct on
    # access so request factories and type diagnostics consume the same owner.
    from . import network_observational_policy_reading as reading
    from . import network_observational_signature_reading as signature
    from . import network_observational_definitions as definitions
    from . import query_conditioning_contract as conditioning
    from . import network_policy_reading as policy
    from . import network_contrast_reading as contrast
    from .compact_evidence_contract import clarify_fact_order
    from .network_fact_protocols import network_fact_profiles, network_fact_protocol
    r3 = FactReadingContract(
        reader_id='NETWORK_OBSERVATIONAL_POLICY_FACTS', reference_format='short_refs',
        version_field='observational_fact_contract', wire_version=reading.VERSION,
        profile_field='observational_fact_profile',
        make_request=reading.make_request, parse=reading.parse,
        reference_catalog=reading.reference_catalog, model=reading.ObservationalPolicyReading,
        documents=reading.documents,
        target_context=TargetContextHandoff(conditioning.clarify_conditioning_request,
            conditioning.conditioning_constraints, conditioning.MATCH_DECISION, conditioning.DESCRIPTION))
    r3_signature = FactReadingContract(
        reader_id=r3.reader_id, reference_format=r3.reference_format,
        version_field=r3.version_field, wire_version=signature.VERSION,
        profile_field=r3.profile_field, profile=signature.PROFILE,
        make_request=signature.make_request, parse=signature.parse,
        reference_catalog=signature.reference_catalog, model=signature.ObservationalSignatureReading,
        documents=reading.documents, target_context=r3.target_context,
        field_constraints=signature.field_constraints)
    r3_definitions = FactReadingContract(
        reader_id=r3.reader_id, reference_format=r3.reference_format,
        version_field=r3.version_field, wire_version=definitions.VERSION,
        profile_field=r3.profile_field, profile=definitions.PROFILE,
        make_request=definitions.make_request, parse=definitions.parse,
        reference_catalog=definitions.reference_catalog, model=definitions.Reading,
        facts_model=signature.ObservationalSignatureReading,
        documents=reading.documents, target_context=r3.target_context,
        field_constraints=definitions.field_constraints)
    # Keep configuration -> request/parser/model ownership in the existing table.
    # Several request profiles share a wire version; these are distinct selectors.
    policies, contrasts = [], []
    for profile in network_fact_profiles():
        protocol = network_fact_protocol(profile)
        policies.append(FactReadingContract(
            reader_id='NETWORK_FIXED_POLICY_FACTS', reference_format='short_refs',
            version_field=None, wire_version=protocol.wire_version,
            make_request=protocol.make_request, parse=protocol.parse,
            reference_catalog=policy.reference_catalog, model=protocol.model,
            documents=policy.documents, target_context=TargetContextHandoff(
                conditioning.preserve_contrast_request, conditioning.contrast_conditioning_constraints,
                conditioning.MATCH_DECISION, conditioning.CONTRAST_DESCRIPTION),
            profile_field='network_fact_contract', profile=profile,
            uses_assignment_semantics=True, field_constraints=protocol.public_constraints))
        contrasts.append(FactReadingContract(
            reader_id='NETWORK_POLICY_CONTRAST_FACTS', reference_format='short_refs',
            version_field=None, wire_version=contrast.VERSION,
            make_request=partial(contrast.make_request, profile=profile),
            parse=partial(contrast.parse, profile=profile),
            reference_catalog=contrast.reference_catalog, model=contrast.reading_model(profile),
            documents=policy.documents, target_context=TargetContextHandoff(
                conditioning.preserve_contrast_request, conditioning.contrast_conditioning_constraints,
                conditioning.MATCH_DECISION, conditioning.CONTRAST_DESCRIPTION),
            profile_field='network_fact_contract', profile=profile,
            uses_assignment_semantics=True, field_constraints=partial(contrast.field_constraints, profile=profile),
            clarify_comparison=clarify_fact_order))
    from . import dag_query_reading as dag
    from .dag_reading import documents as dag_documents
    dag_contract = FactReadingContract(
        reader_id='VARIABLE_DAG_FACTS', reference_format='short_refs', version_field=None,
        profile_field='dag_fact_contract', wire_version=dag.VERSION,
        make_request=dag.make_request, parse=dag.parse, reference_catalog=dag.reference_catalog,
        model=dag.DagQueryReading, documents=dag_documents, target_context=None)
    from .readers import local_effect_lifecycle as effects
    local = tuple(FactReadingContract(
        reader_id='NETWORK_RANDOMIZED_EFFECT_FACTS', reference_format='short_refs',
        version_field=None, profile_field='effect_fact_contract', profile=profile,
        wire_version=module.VERSION, make_request=effects.make_request, parse=module.parse,
        reference_catalog=effects.reference_catalog, model=model, documents=policy.documents,
        target_context=None, uses_assignment_semantics=True, uses_network_profile=True,
        contextual_parse=effects.parse, contextual_constraints=effects.field_constraints)
        for profile,module,model in effects.variants())
    from .network_extended_reading import contracts as extended_contracts
    from . import iv_fact_reading as iv
    iv_contract = FactReadingContract(reader_id=iv.FAMILY, reference_format='short_refs',
        version_field='iv_fact_contract', wire_version=iv.VERSION, make_request=iv.make_request,
        parse=iv.parse, reference_catalog=iv.reference_catalog, model=iv.IVFactReading,
        documents=iv.documents, target_context=None)
    return (r3, r3_signature, r3_definitions, *policies, *contrasts, dag_contract, *local, *extended_contracts(), iv_contract)


def _family(reader_id):
    if type(reader_id) is not str:
        raise ReadingContractError('FACT_READER_ID_REQUIRED')
    rows = registrations()
    if len({(row.reader_id, row.profile) for row in rows}) != len(rows):
        raise ReadingContractError('DUPLICATE_FACT_READING_CONTRACT')
    family = tuple(row for row in rows if row.reader_id == reader_id)
    if len({row.profile_field for row in family}) > 1:
        raise ReadingContractError('AMBIGUOUS_FACT_PROFILE_SELECTOR')
    return family


def registered_contract(reader_id, *, profile=None):
    """Unknown family keeps its legacy owner; unknown registered profile fails."""
    family = _family(reader_id)
    if not family:
        return None
    if profile is not None and type(profile) is not str:
        raise ReadingContractError('UNKNOWN_FACT_READING_PROFILE')
    contract = next((row for row in family if row.profile == profile), None)
    if contract is None:
        raise ReadingContractError('UNKNOWN_FACT_READING_PROFILE')
    return contract


def contract_for_entry(entry):
    # Retain the historical hash-based DAG adapter. The common business wire
    # is short_refs; this compatibility API has no short-reference worksheet.
    if entry.get('reader_id') == 'VARIABLE_DAG_FACTS' and entry.get('reference_format') == 'source_hash':
        return None
    family = _family(entry.get('reader_id'))
    if not family:
        return None
    selector = family[0].profile_field
    contract = registered_contract(entry['reader_id'], profile=entry.get(selector) if selector else None)
    if contract is not None:
        contract.check_entry(entry)
    return contract
