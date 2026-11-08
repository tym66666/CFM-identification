"""Offline before/after clarification demonstration (prepared mock replies).

Does NOT certify randomization, any population operator, POINT, or estimators.
"""
from __future__ import annotations

import json
from pathlib import Path

from cfm_id_llm.formulator import ProblemFormulator
from cfm_id_llm.normalization_prompts import BUSINESS_SYSTEM_PROMPT_V06, PROMPT_VERSION_V06
from cfm_id_llm.normalization import (
    ClarificationAnswerV06, append_clarification, build_normalization_review,
)
from cfm_id_llm.providers import MockProvider
from cfm_id_llm.schemas import BusinessCase, SemanticClaim, EvidenceQuote, AssignmentFamily

ROOT = Path(__file__).resolve().parents[1]


def execute() -> dict:
    case = BusinessCase.model_validate_json((Path(__file__).resolve().parent/'normalization_fixtures/sales_ambiguous.json').read_text(encoding='utf-8'))
    initial_draft = json.loads((Path(__file__).resolve().parent/'normalization_fixtures/sales_ambiguous_mock_response.json').read_text(encoding='utf-8'))
    first_form = ProblemFormulator(MockProvider(initial_draft),
                                   system_prompt=BUSINESS_SYSTEM_PROMPT_V06,
                                   prompt_version=PROMPT_VERSION_V06).formulate(case)
    first_review = build_normalization_review(case, first_form)
    question = next(q for q in first_review.business_questions
                    if q.field_path == 'information_design.assignment_family')
    reply = ClarificationAnswerV06(
        question_id=question.question_id, input_sha256=first_review.input_sha256,
        draft_sha256=first_review.draft_sha256,
        answer='我们是从全部300名销售员中随机抽取恰好150名开通AI，而不是每人独立抛硬币。',
    )
    updated_case = append_clarification(case, first_review, reply)
    added_source = updated_case.sources[-1]
    # A new LLM call would be required in production. Here the next mock reply
    # is deliberately prepared to illustrate the intended schema/provenance.
    second_draft = json.loads((Path(__file__).resolve().parent/'normalization_fixtures/sales_ambiguous_mock_response.json').read_text(encoding='utf-8'))
    second_draft['information_design']['assignment_family'] = 'COMPLETE_RANDOMIZATION'
    second_draft['ambiguities'] = [a for a in second_draft['ambiguities'] if a['field_path'] != 'information_design.assignment_family']
    second_draft['clarifying_questions'] = [q for q in second_draft['clarifying_questions'] if q['field_path'] != 'information_design.assignment_family']
    second_draft['information_design']['assignment_law'] = SemanticClaim(
        value='用户报告：恰好150名从300名销售员中随机选出（待核对实验协议）',
        basis='EXPLICIT_TEXT',
        evidence=[EvidenceQuote(source_id=added_source.source_id,
                                quote='随机抽取恰好150名开通AI')],
    ).model_dump(mode='json')
    second_form = ProblemFormulator(MockProvider(second_draft),
                                    system_prompt=BUSINESS_SYSTEM_PROMPT_V06,
                                    prompt_version=PROMPT_VERSION_V06).formulate(updated_case)
    second_review = build_normalization_review(updated_case, second_form)
    assert first_review.formulation.draft.information_design.assignment_family == AssignmentFamily.UNRESOLVED
    assert second_review.formulation.draft.information_design.assignment_family == AssignmentFamily.COMPLETE_RANDOMIZATION
    return {
        'case_id': case.case_id,
        'demo_kind': 'PREPARED_MOCK_BEFORE_AFTER_NO_LIVE_LLM',
        'initial_assignment': first_review.formulation.draft.information_design.assignment_family.value,
        'user_question': question.question,
        'user_answer': reply.answer,
        'revised_assignment': second_review.formulation.draft.information_design.assignment_family.value,
        'revised_assignment_is_user_report_not_causal_certification': True,
        'original_case_sha256': first_review.input_sha256,
        'revised_case_sha256': second_review.input_sha256,
        'population_information_level': second_review.formulation.draft.information_design.population_information_level.value,
        'pending_business_questions': [q.question for q in second_review.business_questions],
        'revised_formulation_report': second_review.model_dump(mode='json'),
        'core_formal_spec_generated': False,
        'math_verification': 'NOT_PERFORMED',
        'estimation_handoff_allowed': False,
    }


def main(argv: list[str] | None = None):
    import argparse
    p=argparse.ArgumentParser(description='Mock before/after clarification, never mathematical identification')
    p.add_argument('--output')
    args=p.parse_args(argv)
    content=json.dumps(execute(), ensure_ascii=False, indent=2)+'\n'
    if args.output:
        Path(args.output).write_text(content, encoding='utf-8')
    else:
        print(content)


if __name__ == '__main__':
    main()
