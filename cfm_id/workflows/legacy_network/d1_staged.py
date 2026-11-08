"""Frozen network compatibility implementation extracted from evaluation.

Explicit inputs and independent reviews remain required. No default benchmark
selection, fixture approval, or candidate-model continuation is provided here.
See README.md before extending this historical protocol.
"""
from copy import deepcopy
import json
from typing import Literal
from cfm_id.workflows.legacy_network.target_model import Closed
from cfm_id.workflows.legacy_network.materials_base import bundle_value
from cfm_id.workflows.legacy_network.materials_target_provenance import target_sources
from cfm_id.workflows.legacy_network.materials_whole_clause_evidence import clause_choices
from cfm_id.workflows.legacy_network.materials_undecided_allocation import _UNCERTAIN
from cfm_id.workflows.legacy_network.materials_undecided_allocation import _DENIED


class Remaining(Closed):
    rule: Literal['原抽签条件平均', '未确定', '其他安排']
    source: str | None
    quote: str | None


def project_target_candidate(bundle, target_raw):
    """Validate typed evidence, then project it into the unchanged legacy schema.

    No inference from words to a rule is performed here. An explicit unknown
    projects to an unknown even when its uncertainty has a cited source.
    """
    if not isinstance(target_raw, dict) or set(target_raw) != {'questions'}:
        raise ValueError('TARGET_RESPONSE_ONLY')
    projected = deepcopy(target_raw)
    questions = projected['questions']
    if not isinstance(questions, dict):
        raise ValueError('QUESTIONS_OBJECT_REQUIRED')
    catalog = target_sources(bundle_value(bundle))
    evidence = {}
    for qid, q in questions.items():
        if not isinstance(q, dict) or 'remaining' not in q:
            raise ValueError('REMAINING_OBJECT_REQUIRED')
        if 'remaining_source' in q or 'remaining_evidence_span' in q:
            raise ValueError('MIXED_REMAINING_CONTRACTS')
        decision = Remaining.model_validate(q.pop('remaining'))
        source, quote = decision.source, decision.quote
        if (source is None) != (quote is None):
            raise ValueError('REMAINING_SOURCE_QUOTE_PAIR_REQUIRED')
        if source is not None:
            if source not in catalog:
                raise ValueError('TARGET_STATEMENT_SOURCE_REQUIRED')
            if quote not in clause_choices(catalog[source]):
                raise ValueError('REMAINING_COMPLETE_SOURCE_CLAUSE_REQUIRED')
        if decision.rule != '未确定' and source is None:
            raise ValueError('DECIDED_REMAINING_REQUIRES_EVIDENCE')
        if decision.rule == '原抽签条件平均' and (_UNCERTAIN.search(quote) or _DENIED.search(quote)):
            raise ValueError('DECLARED_REMAINING_CONTRADICTS_QUOTED_EVIDENCE')
        confirmed = decision.rule == '原抽签条件平均'
        q['remaining_source'] = source if confirmed else None
        q['remaining_evidence_span'] = quote if confirmed else None
        evidence[qid] = decision.model_dump()
    return projected, evidence
