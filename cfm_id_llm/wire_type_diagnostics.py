"""Advisory type errors from fixed reader models; never repair a candidate.

This is not complete request JSON Schema validation, source entailment, scientific
review or mathematical verification. No provider, solver or dynamic model import.
"""
from pydantic import ValidationError


def _model(entry):
    # Preserve this import surface; selection has one runtime owner shared with
    # source review. A missing/unknown contract remains advisory, not approval.
    from .fact_wire_models import model_for
    try:
        return model_for(entry)
    except (ValueError, TypeError):
        return None


def _definition_source_diagnostics(value):
    """Locate the resolver's existing dependency/direct-source invariant.

    Advisory only: schemas accept list shapes independently; the native reader
    still owns acceptance. No reference is removed, inherited or manufactured.
    """
    rows = []
    def walk(record, path=''):
        if isinstance(record, dict):
            if record.get('definition_refs') and 'source_ids' in record and not record['source_ids']:
                rows.append(dict(field_path=path, error_code='DIRECT_CLAIM_SOURCE_REQUIRED',
                    field_rule=dict(trigger_field='definition_refs', trigger='nonempty',
                        required_field='source_ids', required_value='nonempty'),
                    constraint='定义依赖不能替代直接主张来源。未声明的科学条件不得补为已采用；须核对当前记录是否实际存在需引用的定义依赖。'))
            for key, child in record.items():
                walk(child, path+'/'+key.replace('~','~0').replace('/','~1'))
        elif isinstance(record, list):
            for index, child in enumerate(record):walk(child, path+'/'+str(index))
    walk(value)
    return rows[:50]


def diagnose(entry, candidate):
    """Return bounded diagnostics, without raw values or free-text validator errors."""
    model = _model(entry)
    if model is None:
        return []
    try:
        parsed = model.model_validate(candidate)
    except ValidationError as exc:
        rows = []
        for error in exc.errors(include_input=False, include_url=False)[:50]:
            # Custom value_error messages can contain arbitrary candidate data;
            # only type codes and model-owned Literal alternatives are public.
            row = dict(field_path=''.join('/'+str(p).replace('~','~0').replace('/','~1')
                                          for p in error['loc']), error_code=error['type'])
            if error['type'] == 'literal_error':
                expected = error.get('ctx', {}).get('expected')
                if type(expected) is str and len(expected) <= 4000:
                    row['allowed_literals'] = expected
            if entry.get('network_fact_contract') == 'network-policy-scopes-1':
                from .policy_scope_reading import validation_diagnostic
                row.update(validation_diagnostic(error))
            if entry.get('network_fact_contract') == 'network-policy-scopes-2':
                from .policy_assumption_dependencies import validation_diagnostic
                row.update(validation_diagnostic(error))
            if entry.get('network_fact_contract') in ('network-source-selections-mean-orders-1', 'network-source-selections-mean-orders-2', 'network-shared-definitions-1'):
                from .mean_order_field_contract import validation_diagnostic
                row.update(validation_diagnostic(error))
            if entry.get('observational_fact_profile') == 'mean-signature-definitions':
                from .network_observational_definitions import validation_diagnostic
                row.update(validation_diagnostic(error))
            rows.append(row)
        return rows
    except (ValueError, TypeError, ArithmeticError):
        # Advisory diagnostics must not disable the pre-existing source recheck
        # when an old custom validator raises an unwrapped arithmetic error.
        return []
    if entry.get('reader_id') in ('NETWORK_FIXED_POLICY_FACTS', 'NETWORK_POLICY_CONTRAST_FACTS'):
        dependency_rows = _definition_source_diagnostics(parsed.model_dump(mode='json'))
        if dependency_rows:return dependency_rows
    if entry.get('reader_id') == 'NETWORK_RANDOMIZED_EFFECT_FACTS':
        from .effect_information_rules import diagnose as effect_diagnostics
        return effect_diagnostics(parsed.information)
    if entry.get('network_fact_contract') in ('network-source-selections-information-1', 'network-source-selections-information-2') and entry.get('reader_id') in ('NETWORK_FIXED_POLICY_FACTS', 'NETWORK_POLICY_CONTRAST_FACTS'):
        from .information_field_rules import diagnose as information_diagnostics
        return information_diagnostics(parsed.information)
    return []
