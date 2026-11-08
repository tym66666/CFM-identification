"""Causal-IDFM v2.9: audited business-to-typed-identification integration.

Mathematics: unchanged v2.8 postrelease P1.1. LLM: unchanged Gateway 0.9.
Scientific approval and explicit formal bindings remain separate from LLM.
"""
__version__ = "2.9.2"

from .bridge import (
    ScientificAdmissionV29, FormalQueryBindingV29, QueryBridgeResultV29,
    IntegrationReportV29, run_verified_multiquery_v29,
)

from .scientific_binding import (ApprovedScienceBindingV291,
    scientific_target_coordinates, proposed_binding_snapshot_v291)
from .typed_packets import (ReviewedTypedInquiryPacketV291,
    construct_reviewed_typed_binding_v291)

from .business_intent import ApprovedBusinessIntentV292, verify_business_intent_v292
from .evidence import ReviewedScientificEvidenceV292, verify_science_evidence_v292
