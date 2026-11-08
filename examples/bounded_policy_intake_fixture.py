"""Parameter-generated OFFLINE examples and explicit synthetic review assertions.

No case-name dispatch, API calls, actual reviewers or production authorization.
The mock coordinates and population truth are supplied independently of the
reader. Never use these review helpers to approve a real enterprise question.
"""
from fractions import Fraction as F
from itertools import product

from examples import intent_routes_fixture as f
from cfm_id import bounded_policy_intake as intake
from cfm_id.bounded_policy_contract import ReviewedBoundedPolicy
from cfm_id.bounded_policy import worksheet
from cfm_id.question_bound_assignment import question_catalog, resolve_reading, CONTRACT
from cfm_id.source_locations import build_catalog
from cfm_id.assignment_review import assignment_worksheet, ReviewedQuestionBoundAssignmentFacts


STATEMENTS = {
    'known_assignment_law':'原设计在所有恰好 m 个处理的完整名单上均匀，分配律作为已知科学输入。',
    'full_vector_randomization':'给定研究背景，完整处理向量独立于全部对象在全部安排下的潜在结果。',
    'consistency':'每个对象的观测结果等于该对象在实际完整处理安排下的潜在结果。',
    'fixed_pretreatment_network':'声明的无向网络在处理前固定，政策不会改变网络定义和对象名单。',
    'finite_conditional_first_moments':'给定研究背景，全部对象在全部二元安排下的潜在结果有有限一阶矩。',
    'mean_signature_sufficiency':'对于全部研究对象和全部二元安排，同一对象自身处理与邻居多数暴露相同时，其条件潜在结果均值相同。',
}


def make_case(nodes, edges, quota, policy, population, *, continuous=False, serial=0):
    """Generate data, not a theorem-specific expected interval or an LLM answer."""
    nodes, edges, policy, population = list(nodes), list(edges), list(policy), list(population)
    treatment, outcome = '使用辅助系统', '任务得分' if continuous else '是否按时完成任务'
    target = '、'.join(n for n,z in zip(nodes,policy) if z) or '没有任何小组'
    lines = [f'我们有{len(nodes)}个服务小组，编号是'+ '、'.join(nodes)+'。',
        '处理前固定的无向合作边是'+('、'.join(a+'—'+b for a,b in edges) or '空集')+'，没有其他合作边。',
        f'原试点每轮在全部{len(nodes)}个小组中均匀随机抽取恰好{quota}个使用辅助系统；所有同人数名单等概率，其余不用。',
        '合作邻居中严格超过一半使用辅助系统记高暴露，其余记低暴露；孤立小组为低暴露。',
        '业务结果是'+outcome+'。这里只提供合成业务说明，没有把样本均值声明为精确总体均值。']
    goal = '问题1：如果让'+target+'使用辅助系统，其余都不用，只评价'+'、'.join(population)+f'，每组权重相同，平均的{outcome}是多少？'
    bundle = dict(case_id='GENERATED_'+str(serial), node_order=nodes,
        documents={'study.txt':'\n'.join(lines),'goal.txt':goal}, question_slots={'q1':goal})
    catalog=build_catalog(bundle['documents'])
    raw=dict(reading=dict(intents={'q1':dict(kind='水平', question_id=question_catalog(bundle)['q1']['question_id'])},
        questions={'q1':dict(first=dict(zip(nodes,policy)),second=None,population=population,aggregation='等权平均')}),
        reported_assignment=dict(mechanism='FIXED_QUOTA_RANDOM',fixed_count=quota,maximum_count=None,
            uniform_subset_declared=True,reported_conflict=False,
            source_ids=[sid for sid,row in catalog.items() if row['doc_id']=='study.txt' and row['text'].strip()==lines[2]]))
    neighbors={n:{b if a==n else a for a,b in edges if n in (a,b)} for n in nodes}
    supported=set()
    for z in product((0,1),repeat=len(nodes)):
        if sum(z)!=quota:continue
        v=dict(zip(nodes,z))
        supported.update((n,v[n],int(2*sum(v[j] for j in neighbors[n])>len(neighbors[n]))) for n in nodes)
    ranges={n:(F(-i-1),F(i+2)) if continuous else (F(0),F(1)) for i,n in enumerate(nodes)}
    values=[]
    for n,a,e in sorted(supported):
        lo,hi=ranges[n]
        # Heterogeneous exact synthetic population values, never sample estimates.
        mean=lo+(hi-lo)*F(1+(nodes.index(n)+a+2*e+serial)%5,6)
        values.append(dict(node=n,own=a,exposure=e,value=str(mean)))
    declaration=dict(version=intake.INTAKE_VERSION, study=dict(
        network_id='GENERATED_GRAPH_'+str(serial), node_order=nodes, undirected_edges=[list(e) for e in edges],
        treatment_variable='auxiliary',outcome_variable='score' if continuous else 'on_time',
        outcome_kind='continuous' if continuous else 'binary',context_reference='Same_context_W',
        design='complete_randomization_binary_v1',fixed_count=quota,graph_timing='DECLARED_PRETREATMENT_FIXED',
        grouping='strict_majority_ties_low',protocol_provenance='Independent synthetic uniform fixed-quota protocol',
        network_provenance='Explicit synthetic fixed undirected graph'), information=dict(
        source_id='EXACT_SYNTHETIC_POPULATION',operator='NODE_SIGNATURE_MEANS',availability='EXACT_POPULATION_VALUE',
        information_scope='EXACT_LISTED_SIGNATURE_MEANS_ONLY',model_scope='SIGNATURE_MEANS_AND_NODE_BOUNDS_ONLY',
        values=values,bounds=[dict(node=n,lower=str(ranges[n][0]),upper=str(ranges[n][1])) for n in nodes],
        bounds_kind='CONDITIONAL_MEAN' if continuous else 'ALMOST_SURE_OUTCOME',
        bounds_scope='ALL_BINARY_ASSIGNMENTS_CONDITIONAL_ON_STUDY_CONTEXT',
        outcome_definition='固定任务的连续得分' if continuous else '固定任务按时完成为一，否则为零',
        outcome_unit='分' if continuous else '比例',outcome_period='日',
        a4_provenance='Independently stipulated exact cell population means; all and only this list is supplied',
        bounds_provenance='Separate synthetic scientific protocol for every node and all binary arrangements'),
        conditions=[dict(name=n,scope=intake.ALL_ARRANGEMENTS if n=='mean_signature_sufficiency' else 'STUDY_CONTEXT',
            statement=STATEMENTS[n],evidence='Independent hypothetical protocol explicitly posits: '+STATEMENTS[n])
            for n in sorted(intake.CONDITION_NAMES)],additional_constraints=[])
    claims=dict(analysis_unit=lines[0],treatment=treatment,outcome=outcome,network=lines[1],
        exposure=lines[3],assignment=lines[2],information=lines[4])
    expected=dict(classification='FIXED_POLICY',node_order=nodes,assignment=policy,
        unit_weights=[str(F(1,len(population))) if n in population else '0' for n in nodes])
    return bundle,raw,declaration,claims,expected


def declaration_review(bundle,raw,declaration,expected):
    """Test-only independent oracle; a bad model target is NOT corrected."""
    prepared=intake.prepare(bundle,raw,query_id='q1',declaration=declaration)
    if prepared.get('proposed_target') != expected:
        raise ValueError('ACTUAL_READING_DIFFERS_FROM_PREDECLARED_SYNTHETIC_TARGET')
    return intake.ReviewedBoundedDeclaration(**prepared['worksheet'],
        reviewer='Independent synthetic reviewer',evidence='Predeclared target and all explicit scientific declarations checked',
        condition_decisions={n:'ACCEPTED' for n in intake.CONDITION_NAMES},reviewed_business_target=True,
        reviewed_network_and_original_design=True,reviewed_exact_a4_information=True,
        reviewed_bounds_and_outcome_semantics=True,reviewed_complete_model_without_extra_constraints=True,
        synthetic_fixture=True)


def existing_reviews(bundle,raw,compiled,claims,expected):
    """Explicit hypothetical assertions through the unchanged old review chain."""
    resolved,_=resolve_reading(bundle,raw)
    if f.project(bundle,resolved['reading'])[0] != {'q1':expected}:
        raise ValueError('ACTUAL_READING_DIFFERS_FROM_PREDECLARED_SYNTHETIC_TARGET')
    typed,info=compiled.inquiry,compiled.information
    text='\n'.join(bundle['documents'].values());goal=bundle['question_slots']['q1']
    case=f.BusinessCase(case_id=bundle['case_id'],business_question=text)
    def cl(q):
        if q not in text:raise ValueError('INDEPENDENT_CLAIM_HAS_NO_PUBLIC_QUOTE')
        return f.SemanticClaim(value=q,basis='EXPLICIT_TEXT',evidence=[f.EvidenceQuote(source_id='business_question',quote=q)])
    target=f.TargetDraft(kind=f.TargetKind.FIXED_POLICY_VALUE,description=cl(goal))
    shared=f.DraftProblemSpec(target=target,
        units_variables=f.UnitsVariablesDraft(analysis_unit=cl(claims['analysis_unit']),
            treatment=cl(claims['treatment']),outcome=cl(claims['outcome'])),
        structure=f.StructureDraft(unit_network=cl(claims['network']),network_pretreatment_status=cl(claims['network']),
            exposure_mapping=cl(claims['exposure'])),
        information_design=f.InformationDesignDraft(assignment_family=f.AssignmentFamily.COMPLETE_RANDOMIZATION,
            assignment_law=cl(claims['assignment']),population_information_level=f.PopulationInformationLevel.FINITE_SAMPLE_DESCRIPTION,
            sample_data_description=cl(claims['information'])))
    query=f.BusinessInquiryV010(query_id='q1',target=target,business_goal=cl(goal),semantics=f.QuerySemanticsV010(
        target_population=cl(goal),intervention=cl(goal),aggregation=cl(goal),policy_assignment=cl(goal)))
    quality=f.audit_business_quality(case,f.MultiQueryDraftV010(shared_draft=shared,primary_query_id='q1',queries=[query]),
        provider='OFFLINE_INDEPENDENT_SYNTHETIC_REVIEW',prompt_version=intake.INTAKE_VERSION)
    review=f.BusinessQueryReviewV011(case_id=case.case_id,input_sha256=quality.input_sha256,draft_sha256=quality.draft_sha256,
        confirmed_query_ids=['q1'],reviewed_by='Independent synthetic business reviewer',decision='CONFIRMED',
        review_note='Actual mock reading compared with independently supplied target')
    reviewed=f.approve_multiquery(case,quality.legacy_audit,f.v29_review_from_v011(review,legacy_draft_sha256=quality.legacy_audit.draft_sha256))
    science=f.ScientificAdmissionV29(case_id=case.case_id,input_sha256=quality.input_sha256,
        draft_sha256=quality.legacy_audit.draft_sha256,query_id='q1',target_sha256=f.canonical_sha256(target),
        formal_family='R2_FIXED_POLICY',formal_target_fingerprint=f.formal_target_fingerprint_v29(typed),
        math_target_description=goal,math_target_crosswalk_confirmed=True,scientific_reviewer='Independent synthetic scientist',
        evidence_reference='PARAMETERIZED_SYNTHETIC_PROTOCOL',a4_population_operator_reference=info.source_id,
        a4_scientifically_admitted=True,a5_assumption_reference='EXPLICIT_ALL_ARRANGEMENT_A5',a5_scientifically_admitted=True,
        scientific_review_note='Only the separately declared and hypothetically accepted conditions and exact means apply',is_synthetic_fixture=True)
    science=f.independently_review_fixture(science,typed,reviewed,'q1','R2_MEAN_SIGNATURE')
    intent=f.independently_confirm_business_intent_v292(reviewed,'q1',expected,evidence='Independent synthetic policy and population checked')
    binding=f.FormalQueryBindingV29(science,typed,intent,f.independently_review_evidence_v292(science,typed))
    sheet=f.unapproved_crosswalk_worksheet_v012(case=case,quality=quality,business_review=review,query_id='q1',
        formal_binding=binding,reviewer='Independent synthetic scientist',evidence='Separate complete A4/A5 and target review')
    sheet.update(reviewer_confirmed_business_to_math=True,reviewer_confirmed_a4_a5_and_route=True)
    port=f.RealCoreCoveragePortV012(bindings={'q1':binding},crosswalks={'q1':f.ApprovedBusinessMathCrosswalkV012.model_validate(sheet)})
    packet=dict(mode='SYNTHETIC_BENCHMARK_ONLY',bundle_sha256=f.canonical_hash(bundle),queries={'q1':dict(
        study_sha256=f.sha(typed.study),a4_sources_sha256=f.sha(f.actual_scientific_sources(typed)),
        a5_licenses_sha256=f.sha(f.actual_scientific_licenses(typed)),a4_reference=science.a4_population_operator_reference,
        a5_reference=science.a5_assumption_reference)})
    approval=f.MaterialsCandidateApprovalV035(bundle_sha256=f.canonical_hash(bundle),model_draft_sha256=f.canonical_hash(resolved['reading']),
        science_packet_sha256=f.canonical_hash(packet),gateway_case_sha256=f.canonical_sha256(case),gateway_quality_sha256=f.canonical_sha256(quality),
        gateway_review_sha256=review.fingerprint(),reviewed_query_ids=['q1'],reviewed_a4_levels={},reviewer='Independent synthetic materials reviewer',
        review_evidence='Actual source and coordinates checked against explicit independent science',reviewed_materials_to_gateway=True,synthetic_fixture=True)
    context=f.ReviewedMaterialsContextV035(case,quality,review,port,approval)
    outer=f.reviewed_submission(bundle,resolved['reading'],'FIXED_POLICY',packet,context)
    facts=ReviewedQuestionBoundAssignmentFacts(**assignment_worksheet(bundle,raw,packet,context,contract=CONTRACT),
        reviewer='Independent synthetic assignment reviewer',evidence='Original uniform quota and exact public source checked',
        reviewed_original_assignment_and_sources=True,synthetic_fixture=True)
    bound=ReviewedBoundedPolicy(**worksheet(bundle,raw,query_id='q1',packet=packet,context=context,information=info),
        reviewer='Independent synthetic bounds reviewer',evidence='Exact means and all-arrangement bounds; no ignored constraints',
        reviewed_complete_a4_information=True,reviewed_scientific_bounds_and_scope=True,
        reviewed_no_additional_coupling_constraints=True,synthetic_fixture=True)
    return dict(packet=packet,context=context,bounded_review=bound,submission_review=outer,assignment_review=facts)
