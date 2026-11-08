"""Read-only network identification diagnostics; no solver or approval creation.

Execution records are reported, not authenticated or independently verified here.
This view must never be accepted as an admission, mathematical claim or certificate.
"""
from copy import deepcopy
from . import method_requirements as requirements
from . import business_dispatch as dispatch

VERSION = 'method-diagnostics-1'


def _review(sheet, record, authority, path):
    if sheet is None:
        return dict(state='NOT_PREPARED', conditions=[])
    decisions = {k: 'PENDING' for k in sheet['decisions']}
    state, code = 'PENDING', None
    if record is not None:
        try:
            try:
                checked = dispatch.checked_review(record, sheet)
                state = 'ACCEPTED'
            except dispatch.DispatchError as exc:
                if exc.reason not in ('DISPATCH_REVIEW_PENDING', 'DISPATCH_REVIEW_REJECTED'):
                    raise
                checked = dispatch.DispatchReview.model_validate(record)
                state = 'REJECTED' if exc.reason == 'DISPATCH_REVIEW_REJECTED' else 'PENDING'
            if checked.authority != authority:
                raise ValueError('REVIEW_AUTHORITY_MISMATCH')
            decisions = dict(checked.decisions)
        except (ValueError, TypeError, KeyError, dispatch.DispatchError):
            state, code = 'INVALID', 'INVALID_OR_STALE_REVIEW_RECORD'
            decisions = {k: 'UNKNOWN' for k in sheet['decisions']}
    return dict(state=state, reason_code=code, binding_sha256=sheet['binding_sha256'],
        conditions=[dict(key=k, label=requirements.condition_label(k), review_state=v,
            evidence_refs=[dict(origin='CURRENT_PLAN', json_pointer=path+'/decisions/'+k,
                                binding_sha256=sheet['binding_sha256'])], mathematical_check='NOT_CHECKED_HERE')
                    for k,v in decisions.items()])


def _execution(plan, result, method_ids):
    """Reject cross-plan/method/target records without claiming to replay them."""
    if result is None:
        return {}, {}
    if (not plan.get('plan_sha256') or result.get('plan_sha256') != plan['plan_sha256']
            or result.get('query_id') != plan.get('query_id')
            or result.get('fact_family') != plan.get('fact_family')):
        raise ValueError('DIAGNOSTIC_RESULT_PLAN_BINDING_MISMATCH')
    is_contrast = plan.get('fact_family') == requirements.contrast.FAMILY
    is_effect = plan.get('fact_family') == requirements.effects.FAMILY
    is_observational = plan.get('fact_family') == requirements.observational.FAMILY
    attempts, answers = {}, {}
    if is_contrast:
        from . import contrast_diagnostics
        attempts = contrast_diagnostics.attempts(result, method_ids)
    elif is_effect:
        from . import effect_diagnostics
        attempts = effect_diagnostics.attempts(plan, result, method_ids)
    elif is_observational:
        from . import observational_diagnostics
        attempts = observational_diagnostics.attempts(result, method_ids)
    else:
        for row in result.get('attempts', []):
            method = row.get('method')
            if method not in method_ids or method in attempts:
                raise ValueError('DIAGNOSTIC_UNEXPECTED_OR_DUPLICATE_ATTEMPT')
            attempts[method] = row
    for answer in result.get('answers', []):
        method = answer.get('method')
        claim = answer.get('mathematical_claim') or {}
        attempt = attempts.get(method, {})
        if (method not in method_ids or method in answers
                or result.get('backend_called') is not True or result.get('independent_replay') is not True
                or answer.get('independent_replay') is not True
                or claim.get('kind') not in ('POINT','PARTIAL')
                or result.get('state') != claim['kind']
                or claim.get('target') != plan.get('proposed_target')
                or not answer.get('certificate') or not answer.get('native_evidence')
                or not answer.get('reviewed_input_sha256')):
            raise ValueError('DIAGNOSTIC_INCOHERENT_EXECUTION_RECORD')
        if is_contrast:
            contrast_diagnostics.check_answer(plan, answer, attempt)
        elif is_effect:
            effect_diagnostics.check_answer(plan, answer, attempt)
        elif is_observational:
            observational_diagnostics.check_answer(plan, answer, attempt)
        elif attempt.get('independent_replay') is not True or attempt.get('state') != claim['kind']:
            raise ValueError('DIAGNOSTIC_INCOHERENT_EXECUTION_RECORD')
        answers[method] = answer
    if result.get('state') in ('POINT','PARTIAL') and (not answers or any(
            r.get('state') in ('POINT','PARTIAL') and m not in answers for m,r in attempts.items())):
        raise ValueError('DIAGNOSTIC_SUCCESS_WITHOUT_EVIDENCE')
    return attempts, answers


def describe(plan, *, plan_review=None, native_reviews=None, result=None):
    """Project native plan/review/result records. Does not change or execute them.

Randomized/observational policies, ordered differences and local effects share review reporting.
Uninspected families and upstream stops remain explicit; no method is inferred.
"""
    report = dict(version=VERSION, diagnostic_only=True, is_approval=False, is_certificate=False,
        backend_called=False, independent_replay=False, mathematical_claim=None,
        grants_execution=False, nonidentification_proved=False,
        source_plan_state=plan.get('state'), source_reason=requirements.reason(plan.get('reason_code')),
        query_id=plan.get('query_id'), plan_sha256=plan.get('plan_sha256'),
        target=deepcopy(plan.get('proposed_target')),
        clarification_questions=deepcopy(plan.get('clarification_questions', [])),
        unsupported_reasons=deepcopy(plan.get('unsupported_reasons', [])),
        execution_policy='ALL_PLANNED_REVIEWS_BEFORE_ANY_BACKEND',
        branches_independently_authorized=False, methods=[], next_actions=[],
        next_actions_are_ranked=False, minimum_or_weakest_conditions_claimed=False,
        common_outstanding_review_items=[])
    if report['source_reason']:
        report['next_actions'].append(dict(method=None,layer='COMMON',**report['source_reason']))
    family = plan.get('fact_family')
    if family not in requirements.DIAGNOSTIC_SCOPES:
        return dict(report, diagnostics_scope='UPSTREAM_OR_FAMILY_NOT_CONNECTED',
            scope_note='本诊断样板未检查该家族；不表示数学库未覆盖，也不代表任何方法不适用。')
    report['diagnostics_scope'] = requirements.DIAGNOSTIC_SCOPES[family]
    if family == requirements.contrast.FAMILY:
        from . import contrast_diagnostics
        report['comparison'] = contrast_diagnostics.comparison_view(plan)
    elif family == requirements.effects.FAMILY:
        from . import effect_diagnostics
        report['effect'] = effect_diagnostics.effect_view(plan)
    elif family == requirements.observational.FAMILY:
        from . import observational_diagnostics
        report['observational'] = observational_diagnostics.observational_view(plan)
    templates = {r['method']:r for r in requirements.catalog(family)}
    rows = plan.get('methods', [])
    planned = {r['method']:r for r in rows}
    exclusions = {r['method']:r for r in plan.get('exclusions', [])}
    if len(planned)!=len(rows) or not (set(planned)|set(exclusions))<=set(templates):
        raise ValueError('DIAGNOSTIC_CAPABILITY_REGISTRY_MISMATCH')
    if native_reviews is not None and (type(native_reviews) is not dict or set(native_reviews)!=set(planned)):
        raise ValueError('DIAGNOSTIC_EXACT_PLANNED_REVIEWS_REQUIRED')
    authority = plan.get('query_review', {}).get('authority')
    report['common_review'] = _review(plan.get('plan_worksheet'),plan_review,authority,'/plan_worksheet')
    attempts, answers = _execution(plan,result,set(planned))
    if result is not None:
        report['execution_record'] = dict(state=result.get('state'),reason=requirements.reason(result.get('reason_code')),
            plan_sha256=result['plan_sha256'],origin='EXISTING_EXECUTOR_RECORD',authenticated_here=False,
            independent_replay_performed_here=False)
    for method, template in templates.items():
        row=planned.get(method); exclusion=exclusions.get(method); attempt=attempts.get(method); answer=answers.get(method)
        item=dict(template=deepcopy(template),method=method,
            planning_state='PLANNED' if row else 'EXCLUDED_BY_NATIVE_INSPECTOR' if exclusion else 'NOT_PLANNED_FOR_CURRENT_INPUT',
            native_exclusion=deepcopy(exclusion), reason=requirements.reason(exclusion.get('reason_code')) if exclusion else None,
            reading_review=dict(state='NOT_PREPARED',conditions=[]),science_review=dict(state='NOT_PREPARED',conditions=[]),
            mathematical_applicability='NOT_CHECKED',execution='NOT_RUN',
            certificate=dict(state='NOT_REPORTED',verified_here=False),outstanding_review_items=[])
        if row:
            pair = native_reviews.get(method) if native_reviews is not None else None
            if pair is not None and (type(pair) is not dict or set(pair)!={'reading_review','science_review'}):
                raise ValueError('DIAGNOSTIC_EXACT_REVIEW_PAIR_REQUIRED')
            index=next(i for i,r in enumerate(rows) if r['method']==method)
            for stage in ('reading','science'):
                item[stage+'_review']=_review(row.get(stage+'_worksheet'),pair.get(stage+'_review') if pair else None,
                    authority,f'/methods/{index}/{stage}_worksheet')
                item['outstanding_review_items'] += [dict(stage=stage,**v) for v in item[stage+'_review']['conditions'] if v['review_state']!='ACCEPTED']
        if attempt:
            item['execution']='EXECUTOR_REPORTED_ATTEMPT'
            item['mathematical_applicability']=('NATIVE_NOT_APPLICABLE' if attempt['state']=='NOT_APPLICABLE' else 'NATIVE_RESULT_REPORTED' if answer else 'NOT_ESTABLISHED')
            item['native_attempt']=deepcopy(attempt)
            item['reason']=requirements.reason(attempt.get('reason_code'))
        if answer:
            claim=answer['mathematical_claim']
            if not attempt:
                item['execution']='EXECUTOR_REPORTED_RESULT'
            item['mathematical_applicability']='NATIVE_RESULT_REPORTED'
            item['certificate']=dict(state='REPLAY_REPORTED',verified_here=False,
                origin='EXISTING_EXECUTOR_RECORD',conclusion=claim['kind'],
                sharp=claim.get('sharp'),sharp_scope='CURRENT_REVIEWED_MODEL' if claim.get('sharp') else None,
                reviewed_input_sha256=answer['reviewed_input_sha256'],
                certificate_sha256=dispatch.sha(answer['certificate']))
        if family == requirements.contrast.FAMILY:
            contrast_diagnostics.decorate(item, plan, answer, result)
            for side, endpoint in item.get('native_attempt', {}).get('endpoint_attempts', {}).items():
                reason = requirements.reason(endpoint.get('reason_code'))
                if reason:
                    report['next_actions'].append(dict(method=method,endpoint=side,**reason))
        elif family == requirements.effects.FAMILY:
            effect_diagnostics.decorate(item, plan, answer, result)
        elif family == requirements.observational.FAMILY:
            observational_diagnostics.decorate(item, plan, answer, result)
        if item['reason']:
            report['next_actions'].append(dict(method=method,**item['reason']))
        elif item['outstanding_review_items']:
            report['next_actions'].append(dict(method=method,next_action='COMPLETE_OR_RESOLVE_EXISTING_REVIEW',
                condition_keys=[r['key'] for r in item['outstanding_review_items']],permission_granted=False))
        report['methods'].append(item)
    report['common_outstanding_review_items']=[r for r in report['common_review']['conditions'] if r['review_state']!='ACCEPTED']
    if report['common_outstanding_review_items']:
        report['next_actions'].insert(0,dict(method=None,layer='COMMON',next_action='RESOLVE_COMMON_REVIEW_FIRST',
            condition_keys=[r['key'] for r in report['common_outstanding_review_items']],permission_granted=False))
    if answers and (plan_review is not None or native_reviews is not None):
        if (report['common_review']['state']!='ACCEPTED' or any(
                m[stage+'_review']['state']!='ACCEPTED' for m in report['methods']
                if m['method'] in planned for stage in ('reading','science'))):
            raise ValueError('DIAGNOSTIC_REVIEW_RESULT_CONFLICT')
    report['scope_note']='登记说明不是条件已满足的证明；未列入计划的方法未被自动试算，尤其不会自动切换到有限 PARTIAL 模型。'
    return report


def inspect(intake, query_id, *, plan_review=None, native_reviews=None, **reading_options):
    """Read-only convenience entry; reuses normal reading/source/model gates."""
    plan=dispatch.inspect_methods(intake,query_id,**reading_options)
    return describe(plan,plan_review=plan_review,native_reviews=native_reviews)
