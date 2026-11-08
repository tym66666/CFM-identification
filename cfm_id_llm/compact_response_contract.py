"""Explicit compact response sections; unknown facts remain unknown.

This is a wire requirement, not a completeness/entailment or science decision.
Legacy requests and parsers keep their existing defaults unless opted in.
"""
from typing import Literal, get_args
from dataclasses import asdict

from .quality_formulator import A0QualityValidationError

CONTRACT = 'explicit-sections-1'
FIELD_ROLES = 'explicit-field-roles-1'
EVIDENCE_SLOTS = 'evidence-slots-1'
INLINE_EVIDENCE = 'inline-evidence-1'
TARGET_ROLES = 'inline-target-roles-1'
OUTPUT_GUIDE = 'inline-output-guide-1'
UNIFIED = 'inline-unified-contract-1'
UNIFIED_STRUCTURE = 'inline-unified-contract-2'
UNIFIED_INFORMATION = 'inline-unified-contract-3'
UNIFIED_WIRE_EVIDENCE = 'inline-unified-contract-4'
UNIFIED_LOCAL_STATE = 'inline-unified-contract-5'
UNIFIED_ENDPOINTS = 'inline-unified-contract-6'
UNIFIED_OPERATORS = 'inline-unified-contract-7'
UNIFIED_SOURCE_SCOPE = 'inline-unified-contract-8'
UNIFIED_STRUCTURE_SOURCE = 'inline-unified-contract-9'
UNIFIED_FOCUSED = 'inline-unified-contract-10'
UNIFIED_ALIGNMENT = 'inline-unified-contract-11'
ORDERED_LOCAL = 'ordered-local-comparison-1'
ORDERED_HANDOFF = 'ordered-local-comparison-2'
CHANGE_QUANTITY = 'local-change-quantity-1'
ROLE_COORDINATES = 'local-change-quantity-2'
ROLE_OWNERSHIP = 'local-role-ownership-1'
ROLE_SCOPE = 'local-role-ownership-2'
ROLE_POPULATION = 'local-role-ownership-3'
ROLE_FIELDS = 'local-role-ownership-4'
QUERY_CONDITIONING = 'query-conditioning-1'
ORGANIZED = 'organized-reading-1'
LiteralProfile = Literal['explicit-sections-1', 'explicit-field-roles-1', 'evidence-slots-1', 'inline-evidence-1', 'inline-target-roles-1', 'inline-output-guide-1', 'inline-unified-contract-1', 'inline-unified-contract-2', 'inline-unified-contract-3', 'inline-unified-contract-4', 'inline-unified-contract-5', 'inline-unified-contract-6', 'inline-unified-contract-7', 'inline-unified-contract-8', 'inline-unified-contract-9', 'inline-unified-contract-10', 'inline-unified-contract-11', 'ordered-local-comparison-1', 'ordered-local-comparison-2', 'local-change-quantity-1', 'local-change-quantity-2', 'local-role-ownership-1', 'local-role-ownership-2', 'local-role-ownership-3', 'local-role-ownership-4', 'query-conditioning-1', 'organized-reading-1', 'single-action-target-1', 'single-action-target-2', 'guided-policy-reading-1', 'model-policy-output-1', 'target-first-reading-1', 'target-first-operands-1', 'target-first-skill-1']
# One finite inventory owns the configuration enum, CLI choices and dispatch.
Profile = LiteralProfile | None
PROFILES = get_args(LiteralProfile)
UNIFIED_PROFILES = (UNIFIED, UNIFIED_STRUCTURE, UNIFIED_INFORMATION, UNIFIED_WIRE_EVIDENCE, UNIFIED_LOCAL_STATE, UNIFIED_ENDPOINTS, UNIFIED_OPERATORS, UNIFIED_SOURCE_SCOPE, UNIFIED_STRUCTURE_SOURCE, UNIFIED_FOCUSED, UNIFIED_ALIGNMENT)
# Closed, source-owned pairing. Consumers use these groups instead of copying
# protocol lists across request, review, diagnostics and dispatch modules.
# The historical LOCAL name denotes the response family; all these profiles
# also retain nonlocal targets. Query conditioning extends that same family.
LOCAL_PROFILE_MODULES = {
    'target-first-skill-1': 'target_first_skill',
    'target-first-operands-1': 'target_first_operands',
    'target-first-reading-1': 'target_first_reading',
    ORDERED_LOCAL: 'ordered_comparison_contract', ORDERED_HANDOFF: 'ordered_target_handoff',
    CHANGE_QUANTITY: 'requested_change_contract', ROLE_COORDINATES: 'role_coordinate_contract',
    ROLE_OWNERSHIP: 'local_role_ownership', ROLE_SCOPE: 'scoped_role_contract',
    ROLE_POPULATION: 'local_population_contract', ROLE_FIELDS: 'local_field_contract',
    QUERY_CONDITIONING: 'query_conditioning_contract', ORGANIZED: 'organized_reading_contract',
    'single-action-target-1': 'policy_action_contract',
    'single-action-target-2': 'policy_action_compat',
    'guided-policy-reading-1': 'guided_policy_reading',
    'model-policy-output-1': 'model_policy_output',
}
LOCAL_COMPARISON_PROFILES = tuple(LOCAL_PROFILE_MODULES)
REVIEWED_TARGET_PROFILES = tuple(p for p in LOCAL_COMPARISON_PROFILES if p not in (ORDERED_LOCAL, 'target-first-reading-1', 'target-first-operands-1', 'target-first-skill-1'))
ROLE_REQUEST_PROFILES = tuple(p for p in REVIEWED_TARGET_PROFILES if p != ORDERED_HANDOFF)
TARGET_CLARIFICATION_PROFILES = (UNIFIED_OPERATORS, UNIFIED_SOURCE_SCOPE, UNIFIED_STRUCTURE_SOURCE, UNIFIED_FOCUSED, UNIFIED_ALIGNMENT, *LOCAL_COMPARISON_PROFILES)
GUIDANCE = '''
本次响应必须显式包含顶层common和queries，以及每个query的semantics对象，不可省略这些区域。common提取原文已给出的共有事实；没有对应事实的字段仍用UNKNOWN或省略字段，不能为了填区域编造事实。semantics也保留未知，不猜目标。明确返回区域不等于事实完整，已知事实不得用空对象或UNKNOWN掩盖。'''

FIELD_GUIDANCE = '''
Schema中的字段职责来自独立审核使用的同一份定义。逐项判断材料是否回答了该字段的问题，不按出现相关词就填值；同一真句子放错字段也会误读。缺失、否定、尚未开始或未获批准的说明不是另一个字段的确定值，原文仍完整保留。
历史分配规则回答过去由谁、按什么办法决定行动；是否开展试点、未来计划如何安排，不能代替历史规则。网络时序回答对象关系是在行动之前还是之后形成、期间是否改变；研究起止时间或是否做试点不能代替它。原文确实给出规则或关系时序时应保留，不能一律UNKNOWN。
对象之间的合作/影响记录在unit_network；variable_causal_graph需要以变量为节点的明确因果陈述。两者可以同时存在，也可能都未明确，不能从对象影响自行画变量箭头。exposure_mapping需要原文明示如何把同伴的处理汇总；只说存在合作/影响还不是汇总定义。neighbor_exposure是本次目标明确要求的同伴状态或平均口径，不能用对象关系列表代填，也不能根据名单自行计算并标为STATED。
covariates逐项记录材料实际说明的背景变量及其可观测性，不因为有表格或日志就把处理、结果和整份资料列表一并放入；这里也不决定哪些变量可调整。有限记录仍是样本，不升级为总体信息。assignment_family和kind按Schema直接输出枚举字符串，其余已知claim才使用state/value/refs。所有未知与引用仍须独立审核；这些字段说明不是额外业务事实或科学许可。'''


def checked(contract):
    if contract is not None and contract not in PROFILES:
        raise ValueError('UNKNOWN_A0_RESPONSE_CONTRACT')
    return contract


def evidence_contract(contract):
    """Closed source-owned request/parser/review pairing, not route selection."""
    checked(contract)
    if contract in LOCAL_PROFILE_MODULES:
        from importlib import import_module
        return import_module('.' + LOCAL_PROFILE_MODULES[contract], package=__package__)
    if contract == EVIDENCE_SLOTS:
        from . import compact_evidence_contract
        return compact_evidence_contract
    if contract == INLINE_EVIDENCE:
        from . import compact_inline_evidence_contract
        return compact_inline_evidence_contract
    if contract == TARGET_ROLES:
        from . import compact_target_roles_contract
        return compact_target_roles_contract
    if contract == OUTPUT_GUIDE:
        from . import compact_output_guide
        return compact_output_guide
    if contract in UNIFIED_PROFILES:
        from . import compact_unified_contract
        return compact_unified_contract
    return None


def policy_focus_readers(contract):
    """Closed stage-handoff scope; preserve old requests for old profiles."""
    adapter = evidence_contract(contract)
    if adapter is None or not hasattr(adapter, 'policy_focus'):
        return ()
    return getattr(adapter, 'POLICY_FOCUS_READERS', (
        'NETWORK_FIXED_POLICY_FACTS', 'NETWORK_POLICY_CONTRAST_FACTS'))


def review_definition(rule, contract):
    """New profile shares its public role with the independent reviewer.

    Historical review identities remain unchanged for every older profile.
    """
    if contract in LOCAL_COMPARISON_PROFILES:
        return evidence_contract(contract).review_definition(rule)
    if contract in (UNIFIED_INFORMATION, UNIFIED_WIRE_EVIDENCE, UNIFIED_LOCAL_STATE, UNIFIED_ENDPOINTS, UNIFIED_OPERATORS, UNIFIED_SOURCE_SCOPE, UNIFIED_STRUCTURE_SOURCE, UNIFIED_FOCUSED, UNIFIED_ALIGNMENT):
        from .compact_unified_contract import field_definition, field_description
        return dict(field_definition(rule,contract),wire_description=field_description(rule,contract))
    return asdict(rule)


def describe(schema, contract=None):
    if checked(contract) is None:
        return ''
    schema['required'] = list(dict.fromkeys([*schema.get('required', []), 'common']))
    query = schema['$defs']['CompactQuery']
    query['required'] = list(dict.fromkeys([*query.get('required', []), 'semantics']))
    if contract in LOCAL_COMPARISON_PROFILES:
        return evidence_contract(contract).describe(schema)
    if contract in UNIFIED_PROFILES:
        return evidence_contract(contract).describe(schema, contract=contract)
    if contract in (FIELD_ROLES, EVIDENCE_SLOTS, INLINE_EVIDENCE, TARGET_ROLES, OUTPUT_GUIDE):
        from .business_field_contract import describe_field_roles
        describe_field_roles(schema)
        evidence = evidence_contract(contract)
        if evidence is not None:
            return GUIDANCE + FIELD_GUIDANCE + evidence.describe(schema)
        return GUIDANCE + FIELD_GUIDANCE
    return GUIDANCE


def scope_recheck_roles(roles, *, contract, user_prompt, candidate):
    """Use the issued nonlocal schema, not inherited local-effect guidance.

    The declared kind only selects public field help; it is not accepted as a
    correct reading. Values, citations and all independent reviews are unchanged.
    Local-effect and unrecognized fields retain their existing handling.
    """
    if contract not in LOCAL_COMPARISON_PROFILES or contract in ('target-first-reading-1','target-first-operands-1','target-first-skill-1'):
        return roles
    from .compact_reference_contract import split_user
    schema = split_user(user_prompt)[2]
    definitions = schema['$defs']
    query = definitions['NonlocalQuery']['properties']
    kinds = query['kind']['enum']
    semantics = definitions[query['semantics']['$ref'].rsplit('/', 1)[1]]['properties']
    queries = candidate.get('queries', [])
    result = []
    for row in roles:
        parts = [p.replace('~1', '/').replace('~0', '~') for p in row['field_path'].split('/')[1:]]
        description = None
        if (len(parts) >= 4 and parts[0] == 'queries' and parts[1].isdigit()
                and parts[2] == 'semantics' and isinstance(queries, list)):
            index = int(parts[1])
            if (index < len(queries) and isinstance(queries[index], dict)
                    and queries[index].get('kind') in kinds):
                description = semantics.get(parts[3], {}).get('description')
            if 'PolicyActionQuery' in definitions and index < len(queries) and isinstance(queries[index], dict):
                policy = definitions['PolicyActionQuery']['properties']
                if queries[index].get('kind') in policy['kind']['enum']:
                    props = definitions[policy['semantics']['$ref'].rsplit('/', 1)[1]]['properties']
                    description = props.get(parts[3], {}).get('description')
        result.append(dict(row, field_role=description) if description else row)
    return result


def validate_sections(raw, contract=None):
    """Check presence before Pydantic defaults; never insert missing sections."""
    if checked(contract) is None or type(raw) is not dict:
        return  # The existing schema parser handles incorrect container types.
    missing = [['common']] if 'common' not in raw else []
    queries = raw.get('queries')
    if type(queries) is list:
        missing.extend(['queries', i, 'semantics'] for i, q in enumerate(queries)
                       if type(q) is dict and 'semantics' not in q)
    if missing:
        raise A0QualityValidationError('Required compact response sections missing',
            code='A0_RESPONSE_SECTION_MISSING', diagnostics={
                'stage': 'compact_sections', 'issue_count': len(missing),
                'issues': [{'code': 'missing', 'path': p} for p in missing[:20]]})
