"""One source for target/operator compatibility; no target inference or repair."""
EFFECTS = frozenset({'DIRECT_EFFECT', 'SPILLOVER_EFFECT', 'LOCAL_TOTAL_EFFECT', 'TOTAL_EFFECT', 'ATE', 'CATE', 'LATE'})
LEVELS = frozenset({'NETWORK_DESIGN_STANDARDIZED_ARM_MEAN', 'FIXED_POLICY_VALUE',
    'STOCHASTIC_POLICY_VALUE', 'POLICY_OPTIMIZATION', 'INTERVENTIONAL_DISTRIBUTION'})
DIFFERENCES = ('INTERVENTION_MINUS_COMPARATOR', 'COMPARATOR_MINUS_INTERVENTION')
GROUPS = ((EFFECTS, (*DIFFERENCES, 'UNSPECIFIED')),
          (LEVELS, ('NOT_APPLICABLE',)),
          (frozenset({'OTHER', 'UNRESOLVED'}), ('UNSPECIFIED', 'NOT_APPLICABLE')))


def allowed_operations(kind):
    for kinds, operations in GROUPS:
        if kind in kinds:
            return operations
    return ('UNSPECIFIED', 'NOT_APPLICABLE')  # Unknown kind still fails TargetKind validation.


def describe(schema):
    """Encode the existing runtime rule, without choosing any business value."""
    query = schema['$defs']['CompactQuery']
    query.setdefault('allOf', []).extend({
        'if': {'properties': {'kind': {'enum': sorted(kinds)}}, 'required': ['kind']},
        'then': {'properties': {'comparison_order': {'properties': {
            'operation': {'enum': list(operations)}}}}},
    } for kinds, operations in GROUPS)


def guidance():
    rows = '\n'.join('、'.join(sorted(kinds)) + ' → ' + '、'.join(operations)
                     for kinds, operations in GROUPS)
    return ('目标类别与comparison_order.operation使用同一组合规则：\n' + rows +
        '\n选择一项政策不是求两个已指定政策的差值。即使预算、目标或最优名单尚未确定，'
        'POLICY_OPTIMIZATION的comparison_order也用NOT_APPLICABLE；其缺项保留在相应目标字段。'
        '不能因为还不知道选哪份名单而填UNSPECIFIED，不能另造基准。'
        '若原问其实要求两政策的差值，应依原文重新核对目标类别，不为通过格式改类。')


def conflict_issue(index, kind):
    return dict(code='TARGET_OPERATOR_CONFLICT',
        path=['queries', index, 'comparison_order', 'operation'],
        allowed_values=list(allowed_operations(kind)))
