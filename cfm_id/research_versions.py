"""Controlled condition-version comparisons over independently reviewed sessions.

This module never approves conditions, edits a native model, or accepts a saved
LLM/result JSON as proof. Inclusion is checked only for an unchanged finite
model and target, wider/narrower same-kind bounds and added/deleted mean orders.
"""
from copy import deepcopy
from fractions import Fraction
from cfm_id_bridge.scientific_binding import canonical_data, sha
from . import research_session as work, session_routes as routes, session_policy_routes as policies

SUPPORTED = (routes.MEAN_ORDER, *policies.BOUNDED)
VERSION = 'research-condition-comparison-1'


def fork_version(session, *, label, reason, bundle=None):
    """Keep the parent intact. No approval is inherited by the new session ID."""
    parent = work._checked(session)
    if (type(label) is not str or not label.strip() or type(reason) is not str or len(reason.strip()) < 3):
        raise work.SessionError('VERSION_LABEL_AND_REASON_REQUIRED')
    child = work.start(parent.lane, parent.bundle if bundle is None else bundle)
    same_materials = sha(child.bundle) == sha(parent.bundle)
    origin = dict(action='CONDITION_VERSION_CREATED', label=label, reason=reason,
        parent_session_id=parent.session_id, parent_binding_sha256=work.binding(parent),
        parent_checkpoint_sha256=sha(parent.model_dump()),
        parent_native_submission_sha256=parent.review.native_submission_sha256 if parent.review else None,
        reading_reused_from_identical_request=same_materials and parent.candidate is not None,
        approvals_inherited=False)
    return work._checked(child.model_copy(update={
        'candidate': deepcopy(parent.candidate) if same_materials else None,
        'history': [*deepcopy(parent.history), origin]}))


def _record(session, native):
    return dict(session_id=session.session_id, revision=session.revision, lane=session.lane,
        binding_sha256=work.binding(session), checkpoint_sha256=sha(session.model_dump()),
        native_submission_sha256=routes.submission_digest(session.lane, native))


def _bounds(rows):
    value = {r['node']: [r['lower'], r['upper']] for r in rows}
    if len(value) != len(rows):
        raise ValueError('UNIQUE_CONDITION_BOUNDS_REQUIRED')
    return dict(sorted(value.items()))


def _describe(session, native):
    """Validated declarations, not a mathematical result or scientific grant."""
    lane = session.lane
    if lane == routes.MEAN_ORDER:
        from .workflows.mean_order import inspect_candidate
        from .mean_order_contract import MeanOrderProblem
        view = inspect_candidate(session.bundle, session.candidate, science=native['science'])
        if view['state'] != 'REVIEW_REQUIRED':
            raise ValueError('COMPLETE_CURRENT_MODEL_REQUIRED')
        model = MeanOrderProblem.model_validate(view['result']['proposed_model']).model_dump()
        target_keys = ('node_order', 'first', 'second', 'weights', 'operation', 'context',
                       'treatment_definition', 'outcome_definition', 'outcome_kind', 'outcome_unit', 'outcome_period')
        fixed = {k: v for k, v in model.items() if k not in
                 ('bounds', 'node_orders', 'bounds_provenance', 'scientific_provenance')}
        fixed['values'] = sorted(fixed['values'], key=lambda r: (r['node'], r['own'], r['exposure']))
        orders = sorted((row['node'], axis) for row in model['node_orders'] for axis in ('OWN','PEERS')
                        if row['mode'] in (axis, 'BOTH'))
        return canonical_data(dict(target={k:model[k] for k in target_keys}, fixed_model=fixed,
            bounds_kind=model['bounds_kind'], bounds=_bounds(model['bounds']), orders=orders,
            provenance={k:model[k] for k in ('bounds_provenance','scientific_provenance')}))
    if lane not in policies.BOUNDED:
        raise ValueError('CONDITION_COMPARISON_NOT_ADAPTED')
    from .bounded_policy_contract import validate_model
    from .bounded_contrast_contract import validate_pair, target_coordinates
    qid = native['query_id']
    if set(session.bundle['question_slots']) != {qid}:
        raise ValueError('EXACT_CONDITION_COMPARISON_QUERY_REQUIRED')
    if lane == policies.BOUNDED_POLICY:
        inquiry = native['context'].core_port.bindings[qid].inquiry
        validate_model(inquiry, native['information'])
        inputs = canonical_data(inquiry)
        info = native['information'].model_dump()
        target = canonical_data(inquiry.target)
    else:
        inquiries = {s: native['context'][s].core_port.bindings[qid].inquiry for s in policies.SIDES}
        validate_pair(inquiries, native['information'])
        inputs = canonical_data(inquiries)
        info = native['information']['first'].model_dump()
        target = target_coordinates(inquiries)
    fixed_info = {k:v for k,v in info.items() if k not in ('bounds','bounds_provenance')}
    fixed_info['values'] = sorted(fixed_info['values'], key=lambda r:(r['node'],r['own'],r['exposure']))
    return canonical_data(dict(target=target, fixed_model=dict(inquiries=inputs, information=fixed_info),
        bounds_kind=info['bounds_kind'], bounds=_bounds(info['bounds']), orders=[],
        provenance=dict(bounds_provenance=info['bounds_provenance'])))


def _changes(before, after, path=''):
    """Exact content differences, including type differences; no semantic repair."""
    if sha(before) == sha(after):
        return []
    if type(before) is dict and type(after) is dict and set(before) == set(after):
        return [row for key in sorted(before) for row in _changes(before[key], after[key], path + '/' + key)]
    return [dict(path=path or '/', before=deepcopy(before), after=deepcopy(after))]


def _relation(before, after):
    if sha(before['target']) != sha(after['target']):
        return dict(relation='NOT_COMPARABLE', reason_code='MATHEMATICAL_TARGET_CHANGED',
                    fixed_field_changes=_changes(before['target'],after['target']))
    if before['bounds_kind'] != after['bounds_kind']:
        return dict(relation='NOT_COMPARABLE', reason_code='BOUND_SEMANTIC_LEVEL_CHANGED',
                    fixed_field_changes=_changes(before['bounds_kind'],after['bounds_kind']))
    if sha(before['fixed_model']) != sha(after['fixed_model']):
        return dict(relation='NOT_COMPARABLE', reason_code='A4_OR_FIXED_MODEL_CHANGED',
                    fixed_field_changes=_changes(before['fixed_model'],after['fixed_model']))
    if set(before['bounds']) != set(after['bounds']):
        raise ValueError('COMMON_MODEL_BOUND_COORDINATES_REQUIRED')
    old_orders, new_orders = ({tuple(row) for row in v['orders']} for v in (before,after))
    weaker = new_orders <= old_orders
    stronger = old_orders <= new_orders
    changed_bounds = []
    for node, old in before['bounds'].items():
        new = after['bounds'][node]
        lo0, hi0 = map(Fraction, old)
        lo1, hi1 = map(Fraction, new)
        if lo0 > hi0 or lo1 > hi1:
            raise ValueError('NONEMPTY_DECLARED_BOUND_REQUIRED')
        weaker &= lo1 <= lo0 and hi0 <= hi1
        stronger &= lo0 <= lo1 and hi1 <= hi0
        if old != new:
            changed_bounds.append(dict(node=node,before=old,after=new))
    relation = ('SAME_DECLARED_CONSTRAINTS' if weaker and stronger else 'WEAKENING' if weaker
                else 'STRENGTHENING' if stronger else 'NON_NESTED_DECLARATIONS')
    return dict(relation=relation, reason_code=None, fixed_field_changes=[],
        changed_bounds=changed_bounds, removed_orders=sorted(old_orders-new_orders),
        added_orders=sorted(new_orders-old_orders),
        unchanged_target_sha256=sha(before['target']), unchanged_fixed_model_sha256=sha(before['fixed_model']),
        strict_model_inclusion_claimed=False)


def plan_comparison(before, after, *, before_submission, after_submission):
    """Preview explicit differences; this plan grants neither review nor proof."""
    before, after = work._checked(before), work._checked(after)
    if before.session_id == after.session_id:
        raise work.SessionError('DISTINCT_CONDITION_VERSION_SESSIONS_REQUIRED')
    out = dict(version=VERSION, before=_record(before,before_submission), after=_record(after,after_submission),
        material_changes=_changes(before.bundle['documents'],after.bundle['documents']),
        relation='NOT_COMPARABLE', reason_code=None, scientific_approval=False,
        mathematical_conclusion=None, backend_called=False)
    if before.lane != after.lane:
        out['reason_code']='CROSS_ROUTE_RELATION_NOT_ADAPTED'
    elif before.lane not in SUPPORTED:
        out['reason_code']='CONDITION_COMPARISON_NOT_ADAPTED'
    elif sha(before.bundle['question_slots']) != sha(after.bundle['question_slots']):
        out['reason_code']='BUSINESS_QUESTION_CHANGED'
    else:
        try:
            left, right = _describe(before,before_submission), _describe(after,after_submission)
            out.update(_relation(left,right), before_conditions=left, after_conditions=right)
        except (ValueError, TypeError, KeyError, AttributeError):
            out.update(relation='NOT_COMPARABLE', reason_code='COMPLETE_VALID_CONDITION_MODELS_REQUIRED')
    out['plan_sha256']=sha(out)
    return canonical_data(out)


def _compact(result):
    return deepcopy({k:result[k] for k in ('session_id','revision','lane','binding_sha256','state','reason_code',
        'mathematical_claim','certificate','independent_replay','backend_called',
        'production_admission','estimation_handoff_allowed')})


def _interval(result):
    claim = result['mathematical_claim']
    if (result['state'] not in ('POINT','PARTIAL') or result['independent_replay'] is not True
            or type(claim) is not dict or claim.get('representation') != 'EXACT_IDENTIFIED_INTERVAL'
            or claim.get('sharp') is not True or result['certificate'] is None):
        return None
    values = claim['interval']
    if type(values) is not list or len(values)!=2 or any(type(v) is not str for v in values):
        raise ValueError('EXACT_INTERVAL_REQUIRED')
    lo,hi = map(Fraction,values)
    if lo>hi or any(str(Fraction(v))!=v for v in values):
        raise ValueError('CANONICAL_NONEMPTY_INTERVAL_REQUIRED')
    if (lo==hi) != (result['state']=='POINT'):
        raise ValueError('POINT_INTERVAL_STATUS_MISMATCH')
    return lo,hi


def compare_versions(before, after, *, plan, before_submission, after_submission,
                     research_protocol_selected=False):
    """Execute both independently; saved result dictionaries are not accepted."""
    current = plan_comparison(before,after,before_submission=before_submission,after_submission=after_submission)
    if type(plan) is not dict or sha(plan)!=sha(current):
        raise work.SessionError('STALE_OR_CHANGED_COMPARISON_PLAN')
    out = dict(version=VERSION, plan=deepcopy(current), state='NOT_COMPARABLE', reason_code=current['reason_code'],
        results={}, conclusion=None, both_results_independently_replayed=False, backend_called=False,
        production_admission=False, estimation_handoff_allowed=False)
    if current['relation']=='NOT_COMPARABLE':
        return out
    if research_protocol_selected is not True:
        return dict(out,state='REVIEW_REQUIRED',reason_code='EXPLICIT_COMPARISON_RESEARCH_PROTOCOL_REQUIRED')
    # Independent item review is mandatory for these new controlled comparisons.
    # Existing single-session legacy approvals remain compatible at their own API.
    if any(s.item_review is None or s.review is None for s in (before,after)):
        return dict(out,state='REVIEW_REQUIRED',reason_code='BOTH_VERSIONS_REQUIRE_ITEM_REVIEW')
    left = work.execute(before,native_submission=before_submission,research_protocol_selected=True)
    right = work.execute(after,native_submission=after_submission,research_protocol_selected=True)
    fresh = plan_comparison(before,after,before_submission=before_submission,after_submission=after_submission)
    if sha(fresh)!=sha(current):
        raise work.SessionError('CONDITION_VERSION_CHANGED_DURING_COMPARISON')
    out.update(results=dict(before=_compact(left),after=_compact(right)),
        backend_called=left['backend_called'] or right['backend_called'],
        both_results_independently_replayed=left['independent_replay'] is True and right['independent_replay'] is True)
    try:
        a,b = _interval(left),_interval(right)
    except (ValueError, TypeError, KeyError, AttributeError, ZeroDivisionError):
        return dict(out,state='CHECK_BLOCKED',reason_code='INVALID_PUBLIC_INTERVAL_FOR_COMPARISON')
    if a is None or b is None:
        return dict(out,state='COMPARISON_BLOCKED',reason_code='BOTH_VERIFIED_NONEMPTY_IDENTIFIED_INTERVALS_REQUIRED')
    before_subset = b[0]<=a[0] and a[1]<=b[1]
    after_subset = a[0]<=b[0] and b[1]<=a[1]
    relation = current['relation']
    expected = (before_subset if relation=='WEAKENING' else after_subset if relation=='STRENGTHENING'
                else before_subset and after_subset if relation=='SAME_DECLARED_CONSTRAINTS' else True)
    if not expected:
        return dict(out,state='CHECK_BLOCKED',reason_code='VERIFIED_INTERVALS_VIOLATE_DECLARED_NESTING')
    ordered = relation != 'NON_NESTED_DECLARATIONS'
    out.update(state='COMPARED' if ordered else 'COMPARED_UNORDERED',reason_code=None,
        both_results_independently_replayed=True,
        conclusion=dict(scope='UNCHANGED_BASE_MODEL_A4_AND_TARGET',
            declaration_relation=relation, model_inclusion_checked=ordered,
            model_inclusion=('BEFORE_SUBSET_OF_AFTER' if relation=='WEAKENING' else
                'AFTER_SUBSET_OF_BEFORE' if relation=='STRENGTHENING' else
                'EQUAL_CONSTRAINT_SETS' if relation=='SAME_DECLARED_CONSTRAINTS' else None),
            before_interval=[str(v) for v in a],after_interval=[str(v) for v in b],
            before_interval_subset_of_after=before_subset,after_interval_subset_of_before=after_subset,
            intervals_equal=a==b, strict_model_inclusion_claimed=False,
            interval_evidence='EACH_VERSION_NATIVE_CERTIFICATE_INDEPENDENTLY_REPLAYED',
            inclusion_evidence='EXACT_SAME_KIND_BOUND_AND_DECLARED_ORDER_SUBSET_CHECK' if ordered else None))
    return out
