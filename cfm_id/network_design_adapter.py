"""Reviewed business D/E records -> existing native constructors.

No design inference, theorem implementation, support calculation or automatic
scientific admission. Call constructors only after the dispatch reviews pass.
"""
from cfm_id_llm import network_design_reading as fields


NATIVE_DESIGNS = {
    'INDEPENDENT_BERNOULLI': 'heterogeneous_bernoulli_binary_v1',
    'UNIFORM_FIXED_QUOTA': 'complete_randomization_binary_v1',
    'TWO_GROUP_FIXED_QUOTA': 'two_group_fixed_quota_binary_v1',
    'CLUSTER_BERNOULLI': 'cluster_bernoulli_binary_v2_4',
    'MULTI_GROUP_FIXED_QUOTA': 'multi_group_fixed_quota_binary_v2_5',
    'TWO_STAGE_QUOTA_MIXTURE': 'two_stage_quota_mixture_binary_v2_7',
}


def design_payload(assignment):
    if assignment.kind not in NATIVE_DESIGNS or any(
            getattr(assignment, name) is None for name in fields.DESIGN_FIELDS[assignment.kind]):
        raise ValueError('COMPLETE_SUPPORTED_DESIGN_REQUIRED')
    result = dict(kind=NATIVE_DESIGNS[assignment.kind])
    aliases = {'probabilities':'propensities', 'fixed_count':'m'}
    for name in fields.DESIGN_FIELDS[assignment.kind]:
        value = getattr(assignment, name)
        if isinstance(value, list):
            value = tuple(tuple(v) if isinstance(v,list) else v for v in value)
        result[aliases.get(name,name)] = value
    return result


def exposure_payload(exposure):
    grouping = fields.EXPOSURE_GROUPS[exposure.kind]
    cores = exposure.core_collaborators
    return dict(grouping=grouping, core_collaborators=None if cores is None else {n:tuple(v) for n,v in cores.items()})


def component_gaps(c, *, local_effect=False):
    """Return material gaps and explicit exclusions; never approve conditions."""
    missing = fields.missing_assignment(c.assignment, c.study.nodes)
    excluded = []
    statement = c.first_stage_exclusion
    if c.assignment.kind == 'TWO_STAGE_QUOTA_MIXTURE':
        if statement is None or statement.status in ('NOT_STATED','UNDECIDED'):
            missing.append('first_stage_exclusion')
        elif statement.status == 'NOT_ADOPTED':
            excluded.append('DECLARED_MODEL_EXCLUDES:'+fields.D6_CONDITION)
        elif statement.status == 'CONFLICTING':
            excluded.append('CONFLICTING_FIRST_STAGE_EXCLUSION')
    elif statement is not None and statement.status != 'NOT_STATED':
        excluded.append('FIRST_STAGE_CONDITION_REQUIRES_D6_DESIGN')
    if local_effect:
        missing += fields.missing_exposure(c.exposure, c.study.nodes)
    return missing, excluded


def assignment_availability_question(declaration):
    """Unavailable design information is a gap, not a rejected causal premise.

    Keep false/null unchanged. Concrete parameters, source review and scientific
    admission are still checked separately; this helper never infers a law.
    """
    if declaration.value is not True:
        return '请核对并补充完整历史分配规则及其参数；规则资料不完整不等于当前数学方法未覆盖。'
    return None


def extra_science(c):
    return (fields.D6_CONDITION,) if c.assignment.kind == 'TWO_STAGE_QUOTA_MIXTURE' else ()


def make_arm(c, network, *, source, evidence, authority='SYNTHETIC_TEST'):
    if authority not in ('SYNTHETIC_TEST', 'EXTERNAL_RESEARCH_REVIEW'):
        raise ValueError('EXPLICIT_RESEARCH_AUTHORITY_REQUIRED')
    synthetic = authority == 'SYNTHETIC_TEST'
    from pfn_pipeline import identification as native
    makers = {
        'INDEPENDENT_BERNOULLI': native.make_heterogeneous_bernoulli_arm_task,
        'UNIFORM_FIXED_QUOTA': native.make_complete_randomization_arm_task,
        'TWO_GROUP_FIXED_QUOTA': native.make_two_group_quota_arm_task,
        'CLUSTER_BERNOULLI': native.make_cluster_bernoulli_arm_task,
        'MULTI_GROUP_FIXED_QUOTA': native.make_multi_group_quota_arm_task,
        'TWO_STAGE_QUOTA_MIXTURE': native.make_two_stage_quota_arm_task,
    }
    design = design_payload(c.assignment); design.pop('kind')
    signature = exposure_payload(c.exposure)
    grouping = signature.pop('grouping')
    if c.assignment.kind == 'TWO_STAGE_QUOTA_MIXTURE':
        if c.first_stage_exclusion is None or c.first_stage_exclusion.status not in ('ADOPTED','PROPOSED'):
            raise ValueError('REVIEWABLE_D6_EXCLUSION_REQUIRED')
        # The caller has independently checked the D6-specific science decision.
        design['profile_exclusion_admitted'] = True
    return makers[c.assignment.kind](network, **design, **signature,
        node_id=c.target.population[0], own_treatment_value=c.target.first.own,
        exposure_value=c.target.first.exposure,
        exposure_definition='strict_majority' if grouping=='strict_majority_ties_low' else grouping,
        source=source, evidence=evidence, admitted=True, synthetic=synthetic,
        query_authority='TRUSTED_FIXTURE' if synthetic else 'HUMAN_CONFIRMED',
        outcome_kind='continuous' if c.study.outcome_kind=='COUNT' else c.study.outcome_kind.lower())
