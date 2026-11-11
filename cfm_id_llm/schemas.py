"""Gateway-owned interchange contracts; never import a particular ID-Library release.

A DraftProblemSpec is *not* an IdentificationSpec, not an admitted assumption,
not a certificate, and never grants permission to estimate a causal quantity.
"""
from __future__ import annotations

from enum import Enum
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator, model_serializer


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class SourceKind(str, Enum):
    BUSINESS_NARRATIVE = "BUSINESS_NARRATIVE"
    STUDY_PROTOCOL = "STUDY_PROTOCOL"
    DATA_DICTIONARY = "DATA_DICTIONARY"
    DOMAIN_KNOWLEDGE = "DOMAIN_KNOWLEDGE"
    OTHER = "OTHER"


class SourceDocument(StrictModel):
    """Caller-provided content. Kind describes claimed origin, not verified authenticity."""
    source_id: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z][A-Za-z0-9_.-]*$")
    kind: SourceKind = SourceKind.OTHER
    text: str = Field(min_length=1, max_length=30000)
    label: str | None = Field(default=None, max_length=200)


class BusinessCase(StrictModel):
    case_id: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
    business_question: str = Field(min_length=3, max_length=12000)
    sources: list[SourceDocument] = Field(default_factory=list, max_length=20)
    response_language: Literal["zh", "en"] = "zh"

    @model_validator(mode="after")
    def valid_sources(self):
        ids = [x.source_id for x in self.sources]
        if "business_question" in ids or len(set(ids)) != len(ids):
            raise ValueError("Duplicate source_id or reserved business_question source_id")
        return self

    def source_map(self) -> dict[str, str]:
        return {"business_question": self.business_question, **{x.source_id: x.text for x in self.sources}}


class EvidenceQuote(StrictModel):
    source_id: str = Field(min_length=1, max_length=80)
    quote: str = Field(min_length=2, max_length=2000)


ClaimBasis = Literal["EXPLICIT_TEXT", "INTERPRETATION", "UNRESOLVED"]

# Capacity for source-backed business summaries, not scientific permissions.
# Shared with the compact reader so expansion never truncates valid references.
MAX_CLAIM_EVIDENCE = 64


class SemanticClaim(StrictModel):
    """Evidence-backed proposal. Even EXPLICIT_TEXT is not scientific certification."""
    value: str | None = Field(default=None, max_length=2500)
    basis: ClaimBasis = "UNRESOLVED"
    evidence: list[EvidenceQuote] = Field(default_factory=list, max_length=MAX_CLAIM_EVIDENCE)

    @model_validator(mode="after")
    def coherent(self):
        if self.basis == "UNRESOLVED":
            if self.value is not None or self.evidence:
                raise ValueError("UNRESOLVED claims must have null value and no evidence")
        else:
            if not self.value or not self.evidence:
                raise ValueError("Non-unresolved claims require a value and supporting quotes")
        return self


class TargetKind(str, Enum):
    NETWORK_DESIGN_STANDARDIZED_ARM_MEAN = "NETWORK_DESIGN_STANDARDIZED_ARM_MEAN"
    DIRECT_EFFECT = "DIRECT_EFFECT"
    SPILLOVER_EFFECT = "SPILLOVER_EFFECT"
    LOCAL_TOTAL_EFFECT = "LOCAL_TOTAL_EFFECT"
    TOTAL_EFFECT = "TOTAL_EFFECT"
    LATE = "LATE"
    ATE = "ATE"
    CATE = "CATE"
    FIXED_POLICY_VALUE = "FIXED_POLICY_VALUE"
    STOCHASTIC_POLICY_VALUE = "STOCHASTIC_POLICY_VALUE"
    POLICY_OPTIMIZATION = "POLICY_OPTIMIZATION"
    INTERVENTIONAL_DISTRIBUTION = "INTERVENTIONAL_DISTRIBUTION"
    OTHER = "OTHER"
    UNRESOLVED = "UNRESOLVED"


class TargetDraft(StrictModel):
    kind: TargetKind = TargetKind.UNRESOLVED
    description: SemanticClaim = Field(default_factory=SemanticClaim)
    alternatives: list[TargetKind] = Field(default_factory=list, max_length=5)

    @model_validator(mode="after")
    def kind_needs_description(self):
        if self.kind != TargetKind.UNRESOLVED and self.description.basis == "UNRESOLVED":
            raise ValueError("A concrete target kind requires a described, evidenced target")
        return self


class UnitsVariablesDraft(StrictModel):
    analysis_unit: SemanticClaim = Field(default_factory=SemanticClaim)
    treatment: SemanticClaim = Field(default_factory=SemanticClaim)
    outcome: SemanticClaim = Field(default_factory=SemanticClaim)
    covariates: list[SemanticClaim] = Field(default_factory=list, max_length=20)
    temporal_structure: SemanticClaim = Field(default_factory=SemanticClaim)


class StructureDraft(StrictModel):
    unit_network: SemanticClaim = Field(default_factory=SemanticClaim)
    variable_causal_graph: SemanticClaim = Field(default_factory=SemanticClaim)
    exposure_mapping: SemanticClaim = Field(default_factory=SemanticClaim)
    network_pretreatment_status: SemanticClaim = Field(default_factory=SemanticClaim)


class AssignmentFamily(str, Enum):
    INDEPENDENT_BERNOULLI = "INDEPENDENT_BERNOULLI"
    COMPLETE_RANDOMIZATION = "COMPLETE_RANDOMIZATION"
    STRATIFIED_FIXED_QUOTAS = "STRATIFIED_FIXED_QUOTAS"
    CLUSTER_RANDOMIZATION = "CLUSTER_RANDOMIZATION"
    OBSERVATIONAL = "OBSERVATIONAL"
    OTHER = "OTHER"
    UNRESOLVED = "UNRESOLVED"


class PopulationInformationLevel(str, Enum):
    FULL_JOINT_LAW = "FULL_JOINT_LAW"
    NODE_FULL_LAW = "NODE_FULL_LAW"
    NODE_ARM_CONDITIONAL_MEANS = "NODE_ARM_CONDITIONAL_MEANS"
    SIGNATURE_CONDITIONAL_MEANS = "SIGNATURE_CONDITIONAL_MEANS"
    ASSIGNMENT_CONDITIONAL_MEANS = "ASSIGNMENT_CONDITIONAL_MEANS"
    FINITE_SAMPLE_DESCRIPTION = "FINITE_SAMPLE_DESCRIPTION"
    OTHER = "OTHER"
    UNRESOLVED = "UNRESOLVED"


class InformationDesignDraft(StrictModel):
    assignment_family: AssignmentFamily = AssignmentFamily.UNRESOLVED
    assignment_law: SemanticClaim = Field(default_factory=SemanticClaim)
    assignment_law_gap: SemanticClaim | None = Field(default=None, description=(
        'Source-backed statement that the assignment law is incomplete or unavailable. '
        'This is a gap description, never a known law, parameter value or scientific permission.'))
    population_information_level: PopulationInformationLevel = PopulationInformationLevel.UNRESOLVED
    population_observable_operator: SemanticClaim = Field(default_factory=SemanticClaim)
    sample_data_description: SemanticClaim = Field(default_factory=SemanticClaim)

    @model_validator(mode="after")
    def typed_fields_need_evidence(self):
        if self.assignment_law_gap is not None:
            if self.assignment_law_gap.basis != "EXPLICIT_TEXT" or self.assignment_law.basis != "UNRESOLVED":
                raise ValueError("Assignment-law gap requires explicit evidence and an unresolved law")
        # OBSERVATIONAL labels a proposed study regime; it does not assert a
        # known assignment distribution. DAG identification can use an observed
        # joint law without knowing that distribution. Keep the law unresolved
        # and require downstream evidence/review for every actual condition.
        if (self.assignment_family not in (AssignmentFamily.UNRESOLVED, AssignmentFamily.OBSERVATIONAL)
                and self.assignment_law.basis == "UNRESOLVED" and self.assignment_law_gap is None):
            raise ValueError("Concrete assignment_family requires evidenced assignment_law")
        operator_levels = {
            PopulationInformationLevel.FULL_JOINT_LAW,
            PopulationInformationLevel.NODE_FULL_LAW,
            PopulationInformationLevel.NODE_ARM_CONDITIONAL_MEANS,
            PopulationInformationLevel.SIGNATURE_CONDITIONAL_MEANS,
            PopulationInformationLevel.ASSIGNMENT_CONDITIONAL_MEANS,
        }
        if self.population_information_level in operator_levels and self.population_observable_operator.basis == "UNRESOLVED":
            raise ValueError("Declared population-law level requires an evidenced operator")
        return self

    @model_serializer(mode="wrap")
    def preserve_existing_records(self, handler):
        value = handler(self)
        if self.assignment_law_gap is None:
            value.pop('assignment_law_gap', None)
        return value


class AssumptionProposal(StrictModel):
    """Every LLM-authored assumption remains PROPOSED or UNRESOLVED."""
    name: str = Field(min_length=2, max_length=200)
    statement: str = Field(min_length=3, max_length=2500)
    status: Literal["PROPOSED", "UNRESOLVED"] = "PROPOSED"
    basis: Literal["REPORTED_BY_SOURCE", "LLM_SUGGESTION", "MISSING"]
    evidence: list[EvidenceQuote] = Field(default_factory=list, max_length=8)

    @model_validator(mode="after")
    def validate_assumption(self):
        if self.basis == "REPORTED_BY_SOURCE" and not self.evidence:
            raise ValueError("Source-reported assumption requires evidence")
        if self.basis == "MISSING" and self.status != "UNRESOLVED":
            raise ValueError("Missing assumptions cannot be PROPOSED as if present")
        return self


class ValidityDraft(StrictModel):
    support_or_positivity: SemanticClaim = Field(default_factory=SemanticClaim)
    query_domain: SemanticClaim = Field(default_factory=SemanticClaim)
    other_conditions: list[SemanticClaim] = Field(default_factory=list, max_length=12)


class Ambiguity(StrictModel):
    field_path: str = Field(min_length=3, max_length=150)
    alternatives: list[str] = Field(min_length=2, max_length=8)
    description: str = Field(min_length=5, max_length=1500)


class ClarificationQuestion(StrictModel):
    field_path: str = Field(min_length=3, max_length=150)
    question: str = Field(min_length=5, max_length=1000)
    reason: str = Field(min_length=5, max_length=1200)
    priority: Literal["HIGH", "MEDIUM", "LOW"] = "HIGH"


class DraftProblemSpec(StrictModel):
    """A0-A6 proposal, *not* a core library TaskSpec or IdentificationResult."""
    schema_version: Literal["cfm-id-draft-v0.1"] = "cfm-id-draft-v0.1"
    target: TargetDraft = Field(default_factory=TargetDraft)                 # A1
    units_variables: UnitsVariablesDraft = Field(default_factory=UnitsVariablesDraft)  # A2
    structure: StructureDraft = Field(default_factory=StructureDraft)       # A3
    information_design: InformationDesignDraft = Field(default_factory=InformationDesignDraft)  # A4
    assumptions: list[AssumptionProposal] = Field(default_factory=list, max_length=30)  # A5
    validity: ValidityDraft = Field(default_factory=ValidityDraft)         # A6
    ambiguities: list[Ambiguity] = Field(default_factory=list, max_length=20)
    clarifying_questions: list[ClarificationQuestion] = Field(default_factory=list, max_length=20)
    normalization_notes: list[str] = Field(default_factory=list, max_length=20)


class AuditIssue(StrictModel):
    code: str
    field_path: str
    detail: str
    severity: Literal["BLOCKING", "WARNING"]


class FormulationReport(StrictModel):
    gateway_version: Literal["0.1.0"] = "0.1.0"
    schema_version: Literal["cfm-id-draft-v0.1"] = "cfm-id-draft-v0.1"
    prompt_version: str
    case_id: str
    input_sha256: str
    provider: str
    draft: DraftProblemSpec
    review_status: Literal["NEEDS_CLARIFICATION", "DRAFT_READY_FOR_HUMAN_REVIEW"]
    issues: list[AuditIssue] = Field(default_factory=list)
    suggested_questions: list[ClarificationQuestion] = Field(default_factory=list)
    # Hard safety invariants: a v0.1 report cannot convey certification or estimation permission.
    mathematical_verification: Literal["NOT_PERFORMED"] = "NOT_PERFORMED"
    estimation_handoff_allowed: Literal[False] = False


# Keep the source/quote audit independent of the LLM provider.
EVIDENCE_MARKER_FIELDS = ("source_id", "quote")
