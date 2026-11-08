"""Separate adjustment protocol; share only existing shape/support validation."""
from typing import Literal
from .dag_backdoor_contract import (BackdoorProblem,BackdoorReview,VERSION as CLASSICAL_VERSION,
    validate as validate_common,DECISIONS,Unavailable,fail)
from cfm_id_bridge.scientific_binding import sha

VERSION='dag-adjustment-1'
ROUTE='DAG_ADJUSTMENT'
THEOREM='DAG_ADJUSTMENT_SUFFICIENT'
CLAIM_SCOPE='SUFFICIENT_POINT_ONLY_FOR_DECLARED_BINARY_SCM'

class AdjustmentProblem(BackdoorProblem):
    version:Literal['dag-adjustment-1']

class AdjustmentReview(BackdoorReview):
    version:Literal['dag-adjustment-1']

def validate(problem):
    if type(problem) is not AdjustmentProblem:fail('CHECK_BLOCKED','TYPED_ADJUSTMENT_PROBLEM_REQUIRED')
    p=AdjustmentProblem.model_validate(problem.model_dump())
    # Old validation checks shape/support only, not the classical graphical rule.
    common=BackdoorProblem.model_validate({**p.model_dump(),'version':CLASSICAL_VERSION})
    validate_common(common)
    return p

def digest(problem):return sha(problem)

def check_review(problem,review):
    if review is None:fail('REVIEW_REQUIRED','EXTERNAL_REVIEW_REQUIRED')
    if type(review) is not AdjustmentReview:fail('CHECK_BLOCKED','TYPED_ADJUSTMENT_REVIEW_REQUIRED')
    r=AdjustmentReview.model_validate(review.model_dump())
    if r.problem_sha256!=digest(problem):fail('CHECK_BLOCKED','STALE_ADJUSTMENT_REVIEW')
    if set(r.decisions)!=set(DECISIONS):fail('CHECK_BLOCKED','EXACT_REVIEW_DECISIONS_REQUIRED')
    if 'REJECTED' in r.decisions.values():fail('CHECK_BLOCKED','SCIENTIFIC_CONDITION_REJECTED')
    if 'PENDING' in r.decisions.values():fail('REVIEW_REQUIRED','SCIENTIFIC_CONDITION_PENDING')
    return r

