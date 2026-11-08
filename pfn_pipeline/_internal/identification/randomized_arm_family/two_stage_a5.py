"""D6-specific scientific A5 admission, shared without collapsing into design proof."""
from __future__ import annotations
from ..schemas import Assumption, AssumptionStatus

D6_EXCLUSION = 'first_stage_profile_no_direct_outcome_effect'


def admitted_no_direct_profile_effect(assumptions) -> bool:
    """Only an explicit reviewed scientific admission, not metadata or LLM guesses.

    A profile can be announced, independently influencing the result even with
    the same final assignment. The current Y_i(t) theorem is invalid then.
    """
    records = [a for a in assumptions if isinstance(a,Assumption) and a.name==D6_EXCLUSION]
    if len(records)!=1:return False
    a=records[0]
    try:
        restored=Assumption.model_validate(a.model_dump(mode='json'))
    except (ValueError,TypeError):
        return False
    return (a.model_dump(mode='json')==restored.model_dump(mode='json')
            and a.confirmed and a.status in {AssumptionStatus.ADMITTED,AssumptionStatus.CERTIFIED}
            and a.source in {'human_confirmation','domain_knowledge','demo_specification'}
            and any(isinstance(e,str) and e.strip() for e in a.evidence))


def profile_exclusion_reason(assumptions) -> str | None:
    """A5 verdict, distinguishing absent/unreviewed from explicit repudiation.

    Both states forbid POINT. Only absent or pending scientific input is labelled
    NEEDS_INPUT by the business layer; explicit contradiction stays UNSUPPORTED.
    """
    if admitted_no_direct_profile_effect(assumptions):
        return None
    denied = any(isinstance(a, Assumption) and a.name == D6_EXCLUSION
                 and a.status in {AssumptionStatus.NOT_ADMITTED,
                                  AssumptionStatus.CONTRADICTED}
                 for a in assumptions)
    return ('D6_FIRST_STAGE_PROFILE_EXCLUSION_CONTRADICTED' if denied
            else 'D6_FIRST_STAGE_PROFILE_EXCLUSION_NOT_ADMITTED')
