"""Explicit evidence-to-typed-scientific-object reference for v2.9.2.

An evidence digest checks *record integrity*, never the truth of a causal
assumption. No cryptographic signer verification or external provenance fetch.
"""
from __future__ import annotations
from typing import Literal
from pydantic import Field, model_validator
from cfm_id_llm.schemas import StrictModel
from .scientific_binding import sha, actual_scientific_sources,actual_scientific_licenses

SHA_RE = r'^[0-9a-f]{64}$'
class ReviewedScientificEvidenceV292(StrictModel):
    schema_version: Literal['causal-idfm-scientific-evidence-v2.9.2']='causal-idfm-scientific-evidence-v2.9.2'
    case_id: str = Field(min_length=1)
    query_id: str = Field(pattern=r'^q[1-9][0-9]{0,2}$')
    a4_reference: str = Field(min_length=8)
    a5_reference: str = Field(min_length=8)
    a4_typed_sources_digest: str = Field(pattern=SHA_RE)
    a5_typed_licenses_digest: str = Field(pattern=SHA_RE)
    a4_evidence_record: str = Field(min_length=12)
    a5_evidence_record: str = Field(min_length=12)
    a4_evidence_digest: str = Field(pattern=SHA_RE)
    a5_evidence_digest: str = Field(pattern=SHA_RE)
    evidence_reviewer: str = Field(min_length=3)
    evidence_record_type: Literal['HYPOTHETICAL_SYNTHETIC','HUMAN_REVIEWED_DOCUMENT']
    reviewer_confirmed_evidence_link: Literal[True]  # explicit, never default True

    @model_validator(mode='after')
    def verify_internal_record_integrity(self):
        if (self.a4_evidence_digest != sha(self.a4_evidence_record) or
                self.a5_evidence_digest != sha(self.a5_evidence_record)):
            raise ValueError('V292_EVIDENCE_RECORD_DIGEST_MISMATCH')
        return self


def verify_science_evidence_v292(manifest, admission, inquiry):
    if manifest is None:
        raise ValueError('V292_TYPED_SCIENTIFIC_EVIDENCE_REQUIRED')
    if manifest.case_id!=admission.case_id or manifest.query_id!=admission.query_id:
        raise ValueError('V292_EVIDENCE_SCOPE_MISMATCH')
    if (manifest.a4_reference!=admission.a4_population_operator_reference or
            manifest.a5_reference!=admission.a5_assumption_reference):
        raise ValueError('V292_EVIDENCE_REFERENCE_MISMATCH')
    if (manifest.a4_typed_sources_digest!=sha(actual_scientific_sources(inquiry)) or
            manifest.a5_typed_licenses_digest!=sha(actual_scientific_licenses(inquiry))):
        raise ValueError('V292_EVIDENCE_TYPED_OBJECT_MISMATCH')
    if manifest.evidence_reviewer!=admission.scientific_reviewer:
        raise ValueError('V292_EVIDENCE_REVIEWER_MISMATCH')
    if admission.is_synthetic_fixture and manifest.evidence_record_type != 'HYPOTHETICAL_SYNTHETIC':
        raise ValueError('V292_HYPOTHETICAL_SOURCE_MISREPRESENTED')
    # For non-synthetic work, this is ONLY a human declaration that a document
    # was reviewed. Another trusted system must authenticate reviewer & record.
    if not admission.is_synthetic_fixture and manifest.evidence_record_type != 'HUMAN_REVIEWED_DOCUMENT':
        raise ValueError('V292_NO_REAL_DOCUMENT_EVIDENCE')
    return sha(manifest)
