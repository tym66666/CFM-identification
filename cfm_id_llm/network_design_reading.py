"""Shared D1-D6/E1-E5 field rules, without inference or scientific approval.

Only declared values are checked. Missing parameters stay missing; this module
does not estimate a design, complete groups or select a target from prose.
"""
from fractions import Fraction


DESIGN_FIELDS = {
    'INDEPENDENT_BERNOULLI': ('probabilities',),
    'UNIFORM_FIXED_QUOTA': ('fixed_count',),
    'TWO_GROUP_FIXED_QUOTA': ('groups', 'treated_quotas'),
    'CLUSTER_BERNOULLI': ('clusters', 'cluster_probabilities'),
    'MULTI_GROUP_FIXED_QUOTA': ('groups', 'treated_quotas'),
    'TWO_STAGE_QUOTA_MIXTURE': ('groups', 'quota_profiles', 'profile_probabilities'),
}
ASSIGNMENT_FIELDS = tuple(dict.fromkeys(k for fields in DESIGN_FIELDS.values() for k in fields))
PROBABILITIES_DESCRIPTION = (
    '仅INDEPENDENT_BERNOULLI使用：各对象独立抽签的启用概率，约分分数字符串。'
    '该设计的明确概率规则应完整读取；缺少规则保持null。'
    '固定名额、分组、簇或两阶段设计使用各自专门参数，本字段必须为null；'
    '不能把这些设计可推导的边际启用概率填到此处，也不能因此判定材料缺少概率。')
EXPOSURE_GROUPS = {
    'STRICT_MAJORITY_TIES_LOW': 'strict_majority_ties_low',
    'THREE_LEVEL_TREATED_NEIGHBOR_FRACTION': 'three_level_treated_neighbor_fraction',
    'PRETREATMENT_CORE_COLLABORATOR_MAJORITY': 'pretreatment_core_collaborator_majority',
    'EXACT_TREATED_NEIGHBOR_COUNT': 'exact_treated_neighbor_count',
    'ANY_TREATED_NEIGHBOR': 'any_treated_neighbor',
}
D6_CONDITION = 'first_stage_profile_no_direct_outcome_effect'
CORE_EXPOSURE = 'PRETREATMENT_CORE_COLLABORATOR_MAJORITY'


def assignment_schema(schema):
    """Publish the same mutually exclusive fields enforced by validation.

    Missing active parameters remain nullable and require clarification. Only
    inactive parameters are restricted to null; no design is inferred here.
    """
    props=schema.get('properties',{})
    schema['allOf']=[
        {'if':{'properties':{'kind':{'const':kind}},'required':['kind']},
         'then':{'properties':{name:{'type':'null'} for name in ASSIGNMENT_FIELDS
                               if name not in allowed and name in props}}}
        for kind,allowed in DESIGN_FIELDS.items()]


def validate_assignment_ownership(assignment):
    allowed=DESIGN_FIELDS.get(assignment.kind)
    if allowed is not None and any(getattr(assignment,k) is not None
            for k in ASSIGNMENT_FIELDS if k not in allowed):
        raise ValueError('CONFLICTING_DESIGN_FIELDS')

ASSIGNMENT_GUIDANCE = '''assignment只读原试点的完整分配规则，不是未来政策。INDEPENDENT_BERNOULLI为逐对象独立抽签，probabilities按对象记录已知概率；UNIFORM_FIXED_QUOTA为均匀固定总名额，fixed_count记录名额。TWO_GROUP_FIXED_QUOTA为两个不交组各自均匀抽固定名额，MULTI_GROUP_FIXED_QUOTA为多个组的同类设计，groups与treated_quotas按相同顺序填写，各组抽取独立。CLUSTER_BERNOULLI为固定簇内对象一起处理、不同簇独立抽签，clusters与cluster_probabilities按相同顺序记录。TWO_STAGE_QUOTA_MIXTURE先按已知联合概率抽一个各组名额向量，再在各组均匀抽取且给定向量后各组独立；groups、quota_profiles、profile_probabilities保留原顺序与全部方案，不能用平均名额或组边际概率替代联合方案。分组或簇必须是原文明示的完整不交划分；无法对应的规则用OTHER，未说明用UNKNOWN；缺少必要参数保留null，不估计或补造。不属于所选设计的参数为null。assignment.source_ids覆盖设计、划分、名额或概率全部实际填写的事实。'''
EXPOSURE_GUIDANCE = '''exposure只读原文明示的定义，不批准暴露充分性。STRICT_MAJORITY_TIES_LOW：处理邻居严格过半为1，平票及孤立点为0。THREE_LEVEL_TREATED_NEIGHBOR_FRACTION：比例小于1/3为0，至少1/3但小于2/3为1，至少2/3为2；孤立点未定义。PRETREATMENT_CORE_COLLABORATOR_MAJORITY：对原文指定的处理前核心同伴作严格多数分组，core_collaborators按每个对象列出非空邻居子集，不能自行选人。EXACT_TREATED_NEIGHBOR_COUNT：暴露值为使用的邻居人数。ANY_TREATED_NEIGHBOR：至少一名邻居使用为1，否则0。其他定义用OTHER，未说明用UNKNOWN；除核心同伴定义外core_collaborators=null。exposure.source_ids须覆盖定义及实际核心名单。LocalArm和总体均值格子的exposure使用该定义的真实状态，不一律限制成0/1；格子范围仅由原文提供的信息决定。'''
STAGE_GUIDANCE = '''first_stage_exclusion独立记录原文是否采用“在最终完整处理名单相同的情况下，第一阶段抽到哪个配额方案不再直接影响结果”。它不是完整分配规律或随机化声明。D6需要这项条件；按原文填写ADOPTED/PROPOSED/NOT_ADOPTED/UNDECIDED/NOT_STATED/CONFLICTING及source_ids，不能由两阶段抽签本身推定。非D6且未提该条件时用null。读取状态不是科学批准，后续必须独立审核。'''


def missing_assignment(assignment, nodes):
    fields = DESIGN_FIELDS.get(assignment.kind, ())
    missing = [f'assignment.{k}' for k in fields if getattr(assignment, k) is None]
    if assignment.kind == 'UNKNOWN':
        missing.append('assignment.kind')
    if assignment.kind == 'INDEPENDENT_BERNOULLI' and assignment.probabilities is not None:
        if set(assignment.probabilities) != set(nodes):
            missing.append('assignment.probabilities:complete_node_scope')
    return missing


def missing_exposure(exposure, nodes):
    if exposure.kind == 'UNKNOWN':
        return ['exposure.kind']
    if exposure.kind == CORE_EXPOSURE:
        if exposure.core_collaborators is None or set(exposure.core_collaborators) != set(nodes):
            return ['exposure.core_collaborators:complete_pretreatment_map']
    return []


def validate_components(assignment, exposure, nodes, edges):
    """Reject contradictions in supplied values without filling absent values."""
    validate_assignment_ownership(assignment)
    if assignment.probabilities is not None and (not set(assignment.probabilities) <= set(nodes)
            or any(not 0 <= Fraction(v) <= 1 for v in assignment.probabilities.values())):
        raise ValueError('INVALID_DESIGN_PROBABILITIES')
    if assignment.fixed_count is not None and not 0 <= assignment.fixed_count <= len(nodes):
        raise ValueError('INVALID_FIXED_QUOTA')
    for name in ('groups', 'clusters'):
        parts = getattr(assignment, name)
        if parts is None:
            continue
        flat = [n for group in parts for n in group]
        if not parts or any(not g for g in parts) or len(set(flat)) != len(flat) or set(flat) != set(nodes):
            raise ValueError('COMPLETE_DISJOINT_DESIGN_PARTITION_REQUIRED')
        if name == 'groups' and assignment.kind == 'TWO_GROUP_FIXED_QUOTA' and len(parts) != 2:
            raise ValueError('TWO_GROUP_DESIGN_REQUIRES_TWO_GROUPS')
        if name == 'groups' and assignment.kind == 'MULTI_GROUP_FIXED_QUOTA' and not 3 <= len(parts) <= 64:
            raise ValueError('MULTI_GROUP_NATIVE_DOMAIN_REQUIRES_3_TO_64_GROUPS')
        if name == 'groups' and assignment.kind == 'TWO_STAGE_QUOTA_MIXTURE' and not 2 <= len(parts) <= 64:
            raise ValueError('TWO_STAGE_NATIVE_DOMAIN_REQUIRES_2_TO_64_GROUPS')
    groups = assignment.groups
    if assignment.treated_quotas is not None:
        q = assignment.treated_quotas
        if any(v < 0 for v in q) or (groups is not None and
                (len(q) != len(groups) or any(v > len(g) for v,g in zip(q,groups)))):
            raise ValueError('INVALID_GROUP_QUOTAS')
    if assignment.cluster_probabilities is not None:
        p = assignment.cluster_probabilities
        if any(not 0 <= Fraction(v) <= 1 for v in p) or (assignment.clusters is not None and len(p) != len(assignment.clusters)):
            raise ValueError('INVALID_CLUSTER_PROBABILITIES')
    if assignment.quota_profiles is not None:
        profiles = assignment.quota_profiles
        if not 1 <= len(profiles) <= 64 or len({tuple(q) for q in profiles}) != len(profiles):
            raise ValueError('DISTINCT_NONEMPTY_QUOTA_PROFILES_REQUIRED')
        for q in profiles:
            if any(v < 0 for v in q) or (groups is not None and
                    (len(q) != len(groups) or any(v > len(g) for v,g in zip(q,groups)))):
                raise ValueError('INVALID_QUOTA_PROFILE')
    if assignment.profile_probabilities is not None:
        probabilities = [Fraction(v) for v in assignment.profile_probabilities]
        if not probabilities or any(v <= 0 for v in probabilities) or sum(probabilities) != 1:
            raise ValueError('EXACT_NORMALIZED_PROFILE_PROBABILITIES_REQUIRED')
        if assignment.quota_profiles is not None and len(probabilities) != len(assignment.quota_profiles):
            raise ValueError('QUOTA_PROFILE_PROBABILITY_ALIGNMENT_REQUIRED')
    if exposure.core_collaborators is not None:
        if exposure.kind != CORE_EXPOSURE:
            raise ValueError('CORE_MAP_WITH_OTHER_EXPOSURE')
        neighbors = {n:set() for n in nodes}
        for u,v in edges:
            neighbors[u].add(v); neighbors[v].add(u)
        if not set(exposure.core_collaborators) <= set(nodes):
            raise ValueError('UNKNOWN_CORE_MAP_NODE')
        for n,core in exposure.core_collaborators.items():
            if not core or len(set(core)) != len(core) or not set(core) <= neighbors[n]:
                raise ValueError('NONEMPTY_PRETREATMENT_NEIGHBOR_SUBSET_REQUIRED')


def validate_exposure_coordinate(exposure, node, value, edges):
    """Coordinate legality only, never assignment support or sufficiency."""
    if exposure.kind not in EXPOSURE_GROUPS:
        return
    degree = sum(node in edge for edge in edges)
    if value < 0 or (exposure.kind == 'EXACT_TREATED_NEIGHBOR_COUNT' and value > degree):
        raise ValueError('EXPOSURE_COORDINATE_OUTSIDE_DECLARED_MAPPING')
    if exposure.kind == 'THREE_LEVEL_TREATED_NEIGHBOR_FRACTION':
        if degree == 0 or value not in (0,1,2):
            raise ValueError('EXPOSURE_COORDINATE_OUTSIDE_DECLARED_MAPPING')
    elif exposure.kind != 'EXACT_TREATED_NEIGHBOR_COUNT' and value not in (0,1):
        raise ValueError('EXPOSURE_COORDINATE_OUTSIDE_DECLARED_MAPPING')
