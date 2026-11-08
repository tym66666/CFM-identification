"""A *proposal* to a future core adapter, not a runnable IdentificationSpec.

Only query intents reviewed by a human are exported; no assumed A4 or A5 license
and no theorem, support computation, certificate or estimation is produced here.
"""
from __future__ import annotations
from typing import Literal
from pydantic import Field, model_validator
from .schemas import StrictModel, TargetDraft
from .multiquery import ReviewedMultiQueryV09
from .orchestration_schemas import canonical_sha256


class ReviewedQueryPreviewV09(StrictModel):
    query_id: str
    target: TargetDraft
    business_goal: str
    shared_draft_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    target_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    formal_core_spec_generated: Literal[False] = False
    identification_status: Literal["NOT_PERFORMED"] = "NOT_PERFORMED"


class CoreHandoffPreviewV09(StrictModel):
    schema_version: Literal["cfm-id-core-handoff-preview-v0.9"] = "cfm-id-core-handoff-preview-v0.9"
    case_id: str
    input_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    reviewed_draft_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    reviewer: str
    reviewed_queries: list[ReviewedQueryPreviewV09] = Field(min_length=1, max_length=8)
    core_adapter_state: Literal["NOT_CONNECTED"] = "NOT_CONNECTED"
    mathematical_verification: Literal["NOT_PERFORMED"] = "NOT_PERFORMED"
    estimation_handoff_allowed: Literal[False] = False

    @model_validator(mode="after")
    def validate_unique(self):
        ids = [q.query_id for q in self.reviewed_queries]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate query preview")
        return self


def prepare_core_handoff_preview(reviewed: ReviewedMultiQueryV09) -> CoreHandoffPreviewV09:
    report, human = reviewed.report, reviewed.human_review
    mapping = {q.query_id: q for q in report.draft.queries}
    shared_sha = canonical_sha256(report.draft.shared_draft)
    return CoreHandoffPreviewV09(
        case_id=report.case_id, input_sha256=report.input_sha256,
        reviewed_draft_sha256=report.draft_sha256, reviewer=human.reviewed_by,
        reviewed_queries=[ReviewedQueryPreviewV09(
            query_id=qid, target=mapping[qid].target,
            business_goal=mapping[qid].business_goal.value or "",
            shared_draft_sha256=shared_sha,
            target_sha256=canonical_sha256(mapping[qid].target),
        ) for qid in human.confirmed_query_ids],
    )
