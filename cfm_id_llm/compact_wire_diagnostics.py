"""Advisory A0 format diagnostics from the existing parser, never repairs.

This is deliberately not complete Schema validation or semantic review. Some
extension/context errors have no field-level diagnostic and remain blocked by
the original parser. No error absence is an approval.
"""
from copy import deepcopy
import json
from pydantic import ValidationError
from .compact_formulator import CompactDraft, CompactCommon, CompactQuery, CompactSemantics, CompactClaim
from .compact_response_contract import validate_sections, evidence_contract, ROLE_REQUEST_PROFILES
from .compact_reference_contract import decode, canonical_catalog
from .quality_formulator import A0QualityValidationError
from . import business_field_contract as field_contract


def _inapplicable_state_diagnostics(wire):
    """Locate the existing field-specific prohibition after typed parsing.

    The shared CompactClaim accepts this enum, while ordinary request fields
    and audit_compact reject it. This adds a location for explicit rereading;
    it changes neither acceptance nor the response, and chooses no replacement.
    Whether comparator/policy_assignment are applicable remains semantic review.
    """
    rows = []
    for field in CompactCommon.model_fields:
        value = getattr(wire.common, field)
        values = enumerate(value) if isinstance(value, list) else [(None, value)]
        for index, claim in values:
            if isinstance(claim, CompactClaim) and claim.state == 'NOT_APPLICABLE':
                path = '/common/' + field + (f'/{index}' if index is not None else '')
                rows.append(dict(field_path=path, error_code='INVALID_NOT_APPLICABLE'))
    for index, query in enumerate(wire.queries):
        for field in CompactSemantics.model_fields:
            if (field not in field_contract.inapplicable_fields()
                    and getattr(query.semantics, field).state == 'NOT_APPLICABLE'):
                rows.append(dict(field_path=f'/queries/{index}/semantics/{field}',
                                 error_code='INVALID_NOT_APPLICABLE'))
    return rows[:20]


def diagnose(case, candidate, *, response_contract=None, reference_contract=None, expected_context=None):
    """Bounded, model-owned type codes/alternatives, without values/messages."""
    try:
        projected = decode(case, deepcopy(candidate), contract=reference_contract,
                           expected_context=expected_context)
        validate_sections(projected, response_contract)
        adapter = evidence_contract(response_contract)
        if adapter is not None:
            projected, _ = adapter.project(projected, canonical_catalog(case,reference_contract))
        wire = CompactDraft.model_validate(projected)
    except A0QualityValidationError as exc:
        rows = []
        ordered_codes = ('ORDERED_SCOPE_CONFLICT', 'ORDERED_LEGACY_FIELD_FORBIDDEN', 'ORDERED_OBJECT_REQUIRED',
                         'ORDERED_FORM_INVALID', 'ORDERED_SHAPE_INVALID', 'ORDERED_REFERENCES_INVALID', 'ORDERED_OPERAND_INVALID')
        for e in exc.diagnostics.get('issues', [])[:20]:
            if (e.get('code') not in ('missing', 'TARGET_OPERATOR_CONFLICT', 'REFERENCE_CONTEXT_MISMATCH') and
                    not (response_contract in ('ordered-local-comparison-1','ordered-local-comparison-2','local-change-quantity-1') and exc.code == 'A0_ORDERED_COMPARISON_REJECTED' and e.get('code') in ordered_codes) and
                    not (response_contract in ROLE_REQUEST_PROFILES and exc.code=='A0_CHANGE_REQUEST_REJECTED' and e.get('code') in ('CHANGE_SCOPE_CONFLICT','CHANGE_LEGACY_FIELD_FORBIDDEN','CHANGE_OBJECT_REQUIRED','CHANGE_QUANTITY_INVALID','CHANGE_SHAPE_INVALID')) and
                    not (exc.code=='A0_POLICY_ACTION_REJECTED' and e.get('code') in ('POLICY_ACTION_OBJECT_REQUIRED','POLICY_DUPLICATE_OWNER_FORBIDDEN','POLICY_ALIAS_CONFLICT')) and
                    not (exc.code=='A0_CONDITIONING_CONTEXT_REJECTED' and e.get('code') in ('CONDITIONING_REFERENCES_INVALID','CONDITIONING_CLAIM_INVALID'))):
                continue
            row = dict(field_path=''.join('/'+str(v) for v in e['path']), error_code=e['code'])
            if 'allowed_values' in e:
                row['allowed_literals'] = json.dumps(e['allowed_values'])
            rows.append(row)
        return rows
    except ValidationError as exc:
        fields = set().union(*(set(m.model_fields) for m in
                              (CompactDraft, CompactCommon, CompactQuery, CompactSemantics, CompactClaim)))
        rows = []
        for error in exc.errors(include_input=False, include_url=False)[:50]:
            path = []
            for part in error['loc']:
                if type(part) is int or part in fields:
                    path.append(str(part))
                else:
                    break  # Union branch names / untrusted extra keys are not JSON field paths.
            row = dict(field_path=''.join('/'+p.replace('~','~0').replace('/','~1') for p in path),
                       error_code=error['type'])
            if error['type'] in ('literal_error', 'enum'):
                expected = error.get('ctx', {}).get('expected')
                if type(expected) is str and len(expected) <= 4000:
                    row['allowed_literals'] = expected
            if row not in rows:
                rows.append(row)
        return rows
    except (ValueError, TypeError, ArithmeticError, KeyError, AttributeError):
        return []  # Advisory diagnostics never replace or disable original source recheck.
    return _inapplicable_state_diagnostics(wire)
