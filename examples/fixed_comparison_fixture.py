"""Predeclared synthetic science and language fixtures, never a review service.

Only public_bundle enters model requests. Endpoint targets and A4/A5 below are
independent hypothetical references, not conditions inferred from a reply.
"""
from copy import deepcopy
from fractions import Fraction as F
from itertools import product
from examples import intent_routes_fixture as f
from cfm_id.question_bound_assignment import question_catalog, resolve_reading, CONTRACT
from cfm_id.source_locations import build_catalog
from cfm_id.assignment_review import assignment_worksheet, ReviewedQuestionBoundAssignmentFacts
from cfm_id.fixed_comparison import worksheet, ReviewedComparison

NODES = tuple('ABCDEF')
BC = dict(zip(NODES, (0,1,1,0,0,0)))
AD = dict(zip(NODES, (1,0,0,1,0,0)))
LINES = [
    '有A、B、C、D、E、F六个维修班组，研究故障诊断助手与每天完成维修的台数。',
    '处理前冻结的无向协作边为A—B、B—C、C—D、D—E、E—F，没有其他边。',
    '原试点每轮从六个班组均匀随机选两个使用助手，其余四个不用，全部十五份两组名单等概率。',
    '合作对象中至少一个使用助手记为高暴露，否则为低；此分组不排除其他班组的影响。',
    '只有有限样本业务记录，未声称已经掌握精确总体均值。',
]
GOALS = {
 'plain': [
    '问题1：方案甲让B、C用助手，A、D、E、F不用；方案乙让A、D用，B、C、E、F不用。只看B、D且二者各占一半，甲比乙的每天平均维修台数多多少？',
    '问题2：同样只看B、D且各占一半，想知道乙比甲的每天平均维修台数多多少。这里乙是A、D用而B、C、E、F不用；甲是B、C用而A、D、E、F不用。',
    '问题3：只看B、D且二者各占一半，比较甲减乙的每天平均维修台数。甲为B、C用，A、D、E、F不用；乙为A、D用，B、C、E不用，但F是否使用还没定。',
    '问题4：甲让B、C、F用助手，A、D、E不用；乙让A、D用，B、C、E、F不用。只看B、D且各占一半，甲比乙的每天平均维修台数多多少？',
    '问题5：甲让B、C用，A、D、E、F不用；乙让A、D用，B、C、E、F不用。我想看甲比乙的每天平均维修台数多多少，只评价其中一些班组、各组权重相同，但具体名单还没定。',
 ],
 'natural': [
    '问题1：我们只关心B和D，两个班组一人一半。如果从A和D开助手、BCEF关掉，换成B和C开、ADEF关掉，他们平均每天会多完成多少台维修？',
    '问题2：反过来，只算B和D的简单平均。如果从B和C使用、ADEF不用，改成A和D使用、BCEF不用，平均每天维修台数会增加多少？',
    '问题3：B和D各算一半。想问BC用而ADEF不用，比AD用、BCE不用、F尚未决定的安排，平均每天多修几台？',
    '问题4：只算B和D，权重相同。如果把AD使用且BCEF不使用，改成BCF使用且ADE不使用，他们每天平均维修台数增加多少？',
    '问题5：想比较BC开助手、ADEF不开，相对AD开、BCEF不开，平均每天多修多少台。只关心部分班组，每组同等重要，但评价哪些班组还没有决定。',
 ]}


def specifications():
    pairs = [(BC, AD, ['B','D']), (AD, BC, ['B','D']),
             (BC, dict(AD,F=None), ['B','D']), (dict(BC,F=1), AD, ['B','D']), (BC,AD,None)]
    return {'q'+str(i+1): dict(first=deepcopy(a),second=deepcopy(b),population=p,aggregation='等权平均')
            for i,(a,b,p) in enumerate(pairs)}


def public_bundle(style='plain', only=None):
    qs = {'q'+str(i+1): text for i,text in enumerate(GOALS[style])}
    if only is not None: qs={q:qs[q] for q in only}
    return dict(case_id='FIXED_COMPARISON_'+style, node_order=list(NODES),
        documents={'study.txt':'\n'.join(LINES),'goal.txt':'\n'.join(qs.values())},question_slots=qs)


def reference(bundle):
    catalog=question_catalog(bundle)
    sid=[sid for sid,r in build_catalog(bundle['documents']).items() if r['doc_id']=='study.txt' and r['text'].rstrip('\r\n')==LINES[2]]
    assert len(sid)==1
    return dict(reading=dict(intents={q:dict(kind='比较',question_id=r['question_id']) for q,r in catalog.items()},
        questions={q:specifications()[q] for q in catalog}),reported_assignment=dict(mechanism='FIXED_QUOTA_RANDOM',
        fixed_count=2,maximum_count=None,uniform_subset_declared=True,reported_conflict=False,source_ids=sid))


def study(bundle):
    return f.declare_network_study(network_id=bundle['case_id'],node_order=NODES,undirected_edges=tuple(zip(NODES[:-1],NODES[1:])),
        treatment_variable='assistant',outcome_variable='repairs_per_day',outcome_kind='continuous',context_reference='W',
        observation_regime='experimental',assignment_design={'kind':'complete_randomization_binary_v1','m':2},
        protocol_provenance=LINES[2],network_provenance=LINES[1],graph_timing_claim='DECLARED_PRETREATMENT_FIXED')


def declared_targets(bundle):
    targets={}
    for q in bundle['question_slots']:
        v=specifications()[q]
        if v['population'] is None or any(x is None for side in ('first','second') for x in v[side].values()):continue
        targets[q]=dict(node_order=list(NODES),first=[v['first'][n] for n in NODES],second=[v['second'][n] for n in NODES],
            unit_weights=[str(F(1,len(v['population']))) if n in v['population'] else '0' for n in NODES],operation='first_minus_second')
    return targets


def endpoint_context(bundle, raw, side, *, query_ids=None):
    resolved,_=resolve_reading(bundle,raw)
    targets=declared_targets(bundle)
    if query_ids is not None:
        # Explicit fixture selection, never inferred from a model answer.
        if (type(query_ids) is not list or not query_ids or len(set(query_ids)) != len(query_ids)
                or query_ids != [q for q in targets if q in query_ids]):
            raise ValueError('PREDECLARED_FIXTURE_QUERY_SCOPE_REQUIRED')
        targets={q:targets[q] for q in query_ids}
    qs=list(targets);st=study(bundle)
    typed={q:f.FixedPolicyInquiryV21(st,f.fixed_policy_target_from_context(st,tuple(t[side]),
        authority='TRUSTED_FIXTURE',unit_weights=tuple(t['unit_weights'])),f._assumptions(),r1b_sources=(f._full_source(st),)) for q,t in targets.items()}
    text='\n'.join(bundle['documents'].values());case=f.BusinessCase(case_id=bundle['case_id'],business_question=text)
    def claim(value):
        assert value in text
        return f.SemanticClaim(value=value,basis='EXPLICIT_TEXT',evidence=[f.EvidenceQuote(source_id='business_question',quote=value)])
    drafts={q:f.TargetDraft(kind=f.TargetKind.FIXED_POLICY_VALUE,description=claim(bundle['question_slots'][q])) for q in qs}
    shared=f.DraftProblemSpec(target=drafts[qs[0]],
        units_variables=f.UnitsVariablesDraft(analysis_unit=claim(LINES[0]),treatment=claim('故障诊断助手'),outcome=claim('每天完成维修的台数')),
        structure=f.StructureDraft(unit_network=claim(LINES[1]),network_pretreatment_status=claim(LINES[1]),exposure_mapping=claim(LINES[3])),
        information_design=f.InformationDesignDraft(assignment_family=f.AssignmentFamily.COMPLETE_RANDOMIZATION,assignment_law=claim(LINES[2]),
            population_information_level=f.PopulationInformationLevel.FINITE_SAMPLE_DESCRIPTION,sample_data_description=claim(LINES[4])))
    queries=[f.BusinessInquiryV010(query_id=q,target=drafts[q],business_goal=claim(bundle['question_slots'][q]),
        semantics=f.QuerySemanticsV010(target_population=claim(bundle['question_slots'][q]),intervention=claim(bundle['question_slots'][q]),
            aggregation=claim(bundle['question_slots'][q]),policy_assignment=claim(bundle['question_slots'][q]))) for q in qs]
    quality=f.audit_business_quality(case,f.MultiQueryDraftV010(shared_draft=shared,primary_query_id=qs[0],queries=queries),
        provider='INDEPENDENT_SYNTHETIC_ENDPOINT_REVIEW',prompt_version='fixed-comparison-fixture')
    review=f.BusinessQueryReviewV011(case_id=case.case_id,input_sha256=quality.input_sha256,draft_sha256=quality.draft_sha256,
        confirmed_query_ids=qs,reviewed_by='Independent synthetic reviewer',decision='CONFIRMED',
        review_note='Review of the '+side+' endpoint of an ordered comparison; other endpoint requires its own binding.')
    reviewed=f.approve_multiquery(case,quality.legacy_audit,f.v29_review_from_v011(review,legacy_draft_sha256=quality.legacy_audit.draft_sha256))
    bindings={};crosswalks={};packet=dict(mode='SYNTHETIC_BENCHMARK_ONLY',bundle_sha256=f.canonical_hash(bundle),queries={})
    for q in qs:
        inquiry=typed[q];t=targets[q];goal=bundle['question_slots'][q]
        science=f.ScientificAdmissionV29(case_id=case.case_id,input_sha256=quality.input_sha256,draft_sha256=quality.legacy_audit.draft_sha256,
            query_id=q,target_sha256=f.canonical_sha256(drafts[q]),formal_family='R1B_FIXED_POLICY',
            formal_target_fingerprint=f.formal_target_fingerprint_v29(inquiry),math_target_description=side+' endpoint: '+goal,
            math_target_crosswalk_confirmed=True,scientific_reviewer='Independent synthetic scientist',evidence_reference='COMPARISON_PROTOCOL',
            a4_population_operator_reference='COMPARISON_A4_FULL_LAW',a4_scientifically_admitted=True,
            a5_assumption_reference='COMPARISON_A5_RANDOMIZATION_CONSISTENCY',a5_scientifically_admitted=True,
            scientific_review_note='Hypothetical common full population law and explicit assumptions, no model approval.',is_synthetic_fixture=True)
        science=f.independently_review_fixture(science,inquiry,reviewed,q,'R1B_FULL_ASSIGNMENT')
        coords=dict(classification='FIXED_POLICY',node_order=t['node_order'],assignment=t[side],unit_weights=t['unit_weights'])
        intent=f.independently_confirm_business_intent_v292(reviewed,q,coords,evidence='Predeclared '+side+' endpoint and common equal evaluation population')
        binding=f.FormalQueryBindingV29(science,inquiry,intent,f.independently_review_evidence_v292(science,inquiry))
        sheet=f.unapproved_crosswalk_worksheet_v012(case=case,quality=quality,business_review=review,query_id=q,formal_binding=binding,
            reviewer='Independent synthetic reviewer',evidence='Separate ordered endpoint, original study, full-law information and named assumptions')
        sheet.update(reviewer_confirmed_business_to_math=True,reviewer_confirmed_a4_a5_and_route=True)
        bindings[q]=binding;crosswalks[q]=f.ApprovedBusinessMathCrosswalkV012.model_validate(sheet)
        packet['queries'][q]=dict(study_sha256=f.sha(inquiry.study),a4_sources_sha256=f.sha(f.actual_scientific_sources(inquiry)),
            a5_licenses_sha256=f.sha(f.actual_scientific_licenses(inquiry)),a4_reference=science.a4_population_operator_reference,a5_reference=science.a5_assumption_reference)
    port=f.RealCoreCoveragePortV012(bindings=bindings,crosswalks=crosswalks,
        comparison_endpoint_sources={q:dict(bundle=bundle,raw=raw,query_id=q,side=side) for q in qs})
    approval=f.MaterialsCandidateApprovalV035(bundle_sha256=f.canonical_hash(bundle),model_draft_sha256=f.canonical_hash(resolved['reading']),
        science_packet_sha256=f.canonical_hash(packet),gateway_case_sha256=f.canonical_sha256(case),gateway_quality_sha256=f.canonical_sha256(quality),
        gateway_review_sha256=review.fingerprint(),reviewed_query_ids=qs,reviewed_a4_levels={},reviewer='Independent synthetic materials reviewer',
        review_evidence='Actual candidate recorded, endpoint meaning checked against independent reference',reviewed_materials_to_gateway=True,synthetic_fixture=True)
    return packet,f.ReviewedMaterialsContextV035(case,quality,review,port,approval)


def reviews(bundle, raw, *, query_ids=None):
    packets={};contexts={};facts={}
    for side in ('first','second'):
        packets[side],contexts[side]=endpoint_context(bundle,raw,side,query_ids=query_ids)
        facts[side]=ReviewedQuestionBoundAssignmentFacts(**assignment_worksheet(bundle,raw,packets[side],contexts[side],contract=CONTRACT),
            reviewer='Independent synthetic fact reviewer',evidence='Frozen original uniform quota rule and full scientific study checked separately.',
            reviewed_original_assignment_and_sources=True,synthetic_fixture=True)
    if query_ids is None:
        review_type=ReviewedComparison;sheet=worksheet(bundle,raw,packets,contexts)
    else:
        from cfm_id.fixed_comparison import ReviewedComparisonScope,scoped_worksheet
        review_type=ReviewedComparisonScope
        sheet=scoped_worksheet(bundle,raw,packets,contexts,reviewed_query_ids=query_ids)
    paired=review_type(**sheet,reviewer='Independent synthetic comparison reviewer',
        evidence='Direction is first minus second; both endpoints evaluate the identical predeclared equal-weight population.',
        reviewed_comparison_direction_and_population=True,synthetic_fixture=True)
    return dict(packet=packets,context=contexts,assignment_review=facts,submission_review=paired,synthetic_protocol_selected=True)


def independent_oracle(target, receipt):
    """Full-vector finite rational schedules, independent of Core formula builder."""
    support=[v for v in product((0,1),repeat=len(NODES)) if sum(v)==2]
    masses={s:F(tuple(target[s]) in support,len(support)) for s in ('first','second')}
    if not all(masses.values()):return dict(passed=receipt is None,support={s:str(v) for s,v in masses.items()})
    values=[]
    for k in (1,2):
        def y(i,z):return F(i+2)+F((i+1)*k,3)*z[i]+sum(F(j+k,7)*a for j,a in enumerate(z))+F(z[0]*z[-1],11)
        causal=sum(F(w)*(y(i,target['first'])-y(i,target['second'])) for i,w in enumerate(target['unit_weights']))
        obs=F(0)
        for term in receipt['terms']:
            z=tuple(term['assignment']);i=NODES.index(term['node'])
            conditional=sum(F(1,len(support))*y(i,v) for v in support if v==z)/masses[term['side']]
            obs+=F(term['coefficient'])*conditional
        assert causal==obs
        values.append(dict(causal=str(causal),observable=str(obs)))
    return dict(passed=True,support={s:str(v) for s,v in masses.items()},schedules=values)
