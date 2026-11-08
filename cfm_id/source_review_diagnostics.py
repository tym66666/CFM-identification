"""Explain rejected source reviews; never change their disposition or gate.

A citation-only rejection is not a proof of harmlessness. In particular, the
current study record mixes definitions with context that enters the target.
"""


def describe(worksheet, review):
    issues = []
    for path, decision in review.decisions.items():
        failed = [k for k in ('field_role', 'value_state', 'source_coverage')
                  if getattr(decision, k) == 'REJECTED']
        if not failed:
            continue
        citation_only = failed == ['source_coverage']
        root = path.split('/')[1] if path else ''
        use = ('WHOLE_READING_COMPLETENESS' if not path else
               'MIXED_STUDY_RECORD_CONTEXT_ENTERS_TARGET' if root == 'study' else
               'READING_NOTE_REQUIRES_SEPARATE_REVIEW' if root == 'unresolved' else
               'IDENTIFICATION_INPUT_OR_ADMISSION')
        issues.append(dict(field_path=path, rejected_dimensions=failed,
            category='CITATION_COVERAGE_ONLY' if citation_only else 'MEANING_OR_FIELD_ROLE',
            use=use, blocks_current_review=True,
            impact='NOT_ESTABLISHED_BY_RECORD_LEVEL_REVIEW' if citation_only else 'REQUIRES_READING_CORRECTION',
            ownership_check=worksheet['fields'][path].get('ownership_check')))
    return dict(version='source-review-diagnostics-1', issues=issues,
        citation_only_count=sum(i['category']=='CITATION_COVERAGE_ONLY' for i in issues),
        meaning_or_role_count=sum(i['category']=='MEANING_OR_FIELD_ROLE' for i in issues),
        explanation_only_waiver_granted=False, scientific_approval=False,
        note='记录级引用失败不能证明数学目标错误，也不能自动证明只是无关说明；原审核仍阻断。')
