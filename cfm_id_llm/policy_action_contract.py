"""One declared primary action, with an explicit legacy policy view.

No text inference or answer repair. The new wire forbids duplicate policy input;
the original action, its state and citations own both legacy consumer positions.
"""
from copy import deepcopy
from . import query_conditioning_contract as previous
from .quality_formulator import A0QualityValidationError

CONTRACT = 'single-action-target-1'
KINDS = ('FIXED_POLICY_VALUE', 'TOTAL_EFFECT')
ACTION = ('本问被评价的主安排，只填写一次，保留完整名单或原文已知部分及未知状态。'
          '比较时仅写主方案，基准放comparator，方向放comparison_order；不能混入基准名单。'
          '本字段与自己的引用同时供行动和政策视图使用，不从goal、名册或其他字段补值。')
FACT_VERSION = previous.FACT_VERSION
BIND_POPULATION_INFORMATION = previous.BIND_POPULATION_INFORMATION
EXTRA_STATE_RULES = previous.EXTRA_STATE_RULES
review_definition = previous.review_definition
review_items = previous.review_items
clarify_fact_request = previous.clarify_fact_request
fact_constraints = previous.fact_constraints
fact_focus = previous.fact_focus
target_context = previous.target_context
admission = previous.admission
recheck_field_roles = previous.recheck_field_roles


def omitted_semantics(query):
    return ('policy_assignment',) if query.get('kind') in KINDS else previous.omitted_semantics(query)


def review_semantics(query, rule):
    result = previous.review_semantics(query, rule)
    if query.get('kind') in KINDS and rule.name == 'intervention':
        result = dict(result, meaning=ACTION, excludes='', wire_description=ACTION)
    return result


def describe(schema):
    previous.describe(schema)
    defs = schema['$defs']
    query = deepcopy(defs['NonlocalQuery'])
    query['properties']['kind']['enum'] = list(KINDS)
    query['properties']['semantics'] = {'$ref': '#/$defs/PolicyActionSemantics'}
    semantics = deepcopy(defs['CompactSemantics'])
    semantics['properties'].pop('policy_assignment')
    semantics['properties']['intervention']['description'] = ACTION
    semantics['required'] = list(dict.fromkeys([
        *[k for k in semantics.get('required', []) if k != 'policy_assignment'], 'intervention']))
    defs['PolicyActionSemantics'] = semantics
    defs['PolicyActionQuery'] = query
    defs['NonlocalQuery']['properties']['kind']['enum'] = [
        k for k in defs['NonlocalQuery']['properties']['kind']['enum'] if k not in KINDS]
    schema['properties']['queries']['items']['oneOf'].append({'$ref': '#/$defs/PolicyActionQuery'})
    return ''


def system_prompt(**kwargs):
    # Replace the superseded owner rule; do not append a conflicting override.
    system = previous.system_prompt(**kwargs)
    old = '完整政策的主方案放policy_assignment；选择政策时保留约束，不代求最优名单。'
    if system.count(old) != 1:
        raise ValueError('POLICY_ACTION_BASE_OWNER_RULE_CHANGED')
    return system.replace(old,
        'FIXED_POLICY_VALUE与TOTAL_EFFECT使用PolicyActionQuery：semantics.intervention是唯一主安排，'
        '不输出policy_assignment；comparator与comparison_order仍独立填写。'
        '其他政策类别按各自Schema保留字段；选择政策时保留约束，不代求最优名单。')


def project(raw, catalog):
    output = deepcopy(raw); mappings = []
    for index, query in enumerate(output.get('queries', []) if type(output) is dict else []):
        if type(query) is not dict or query.get('kind') not in KINDS:
            continue
        sem = query.get('semantics')
        code = ('POLICY_ACTION_OBJECT_REQUIRED' if type(sem) is not dict else
                'POLICY_DUPLICATE_OWNER_FORBIDDEN' if 'policy_assignment' in sem else
                'missing' if 'intervention' not in sem else None)
        if code:
            name = 'policy_assignment' if code == 'POLICY_DUPLICATE_OWNER_FORBIDDEN' else 'intervention'
            raise A0QualityValidationError('Primary action wire rejected', code='A0_POLICY_ACTION_REJECTED',
                diagnostics=dict(issues=[dict(code=code, path=['queries', index, 'semantics', name])]))
        sem['policy_assignment'] = deepcopy(sem['intervention'])
        mappings.append(dict(query_id=f'q{index+1}', source_field='semantics.intervention',
                             compatibility_field='semantics.policy_assignment', inferred=False))
    projected, details = previous.project(output, catalog)
    details['policy_action_projection'] = dict(contract=CONTRACT, mappings=mappings,
        raw_candidate_modified=False, scientific_approval=False)
    return projected, details


def apply_gate(gate, details):
    previous.apply_gate(gate, details)
    gate['policy_action_projection'] = deepcopy(details['policy_action_projection'])
    aliases = {m['query_id'] for m in details['policy_action_projection']['mappings']}
    gate['proposed_business_questions'] = [q for q in gate['proposed_business_questions']
        if not (q.get('query_id') in aliases and q.get('field') == 'policy_assignment')]
