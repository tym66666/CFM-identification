"""Independent synthetic acceptance protocol; never sent to the reading LLM.

Only public_bundle is public. Review helpers are explicit hypothetical test
assertions. They cannot approve real enterprise data or repair a model reply.
"""
from fractions import Fraction as F
from itertools import product

from examples import intent_routes_fixture as f
from cfm_id.question_bound_assignment import question_catalog, resolve_reading, CONTRACT
from cfm_id.source_locations import build_catalog
from cfm_id.assignment_review import assignment_worksheet, ReviewedQuestionBoundAssignmentFacts
from cfm_id.bounded_policy_contract import BoundedMeanInformation, ReviewedBoundedPolicy, VERSION
from cfm_id.bounded_policy import worksheet


def specification(name='star7', population=None):
    if name == 'star7':
        nodes = tuple(['H'] + ['L'+str(i) for i in range(1, 7)])
        edges, quota = tuple(('H', n) for n in nodes[1:]), 3
    elif name == 'chain4':
        nodes = tuple('ABCD'); edges, quota = (('A','B'), ('B','C'), ('C','D')), 2
    elif name == 'star5':
        nodes = tuple(['H'] + ['L'+str(i) for i in range(1, 5)])
        edges, quota = tuple(('H', n) for n in nodes[1:]), 4
    else:
        raise ValueError('UNKNOWN_SYNTHETIC_CASE')
    pop = list(nodes) if population is None else list(population)
    if not pop or len(set(pop)) != len(pop) or not set(pop) <= set(nodes):
        raise ValueError('INVALID_FIXTURE_POPULATION')
    return nodes, edges, quota, pop


def public_bundle(name='star7', population=None):
    nodes, edges, quota, pop = specification(name, population)
    lines = [
        '有'+str(len(nodes))+'个服务小组，编号为'+'、'.join(nodes)+'。我们研究使用AI助手与每日任务是否按时完成。',
        '处理前冻结的无向合作边是'+'、'.join(a+'—'+b for a,b in edges)+'，没有其他边。',
        f'原试点每轮从{len(nodes)}个小组中均匀随机抽取恰好{quota}个使用AI助手，其余不用；所有同人数名单等概率。',
        '合作邻居中严格超过一半使用助手记为高暴露，否则为低；这个定义本身不排除其他安排的影响。',
        '这里只提供合成业务说明，没有把有限样本记录声明成精确总体信息。按时完成记1，否则记0。',
    ]
    goal = '问题1：如果所有小组都使用AI助手，只评价'+'、'.join(pop)+'，每组权重相同，他们平均的按时完成率是多少？'
    return dict(case_id='BOUNDED_'+name+'_'+'_'.join(pop), node_order=list(nodes),
        documents={'study.txt':'\n'.join(lines),'goal.txt':goal}, question_slots={'q1':goal})


def reference(name='star7', population=None):
    """Mock only: label it as such; never replace a real model answer with it."""
    b = public_bundle(name, population)
    nodes, _, quota, pop = specification(name, population)
    sid = [s for s,r in build_catalog(b['documents']).items() if r['doc_id']=='study.txt'
        and r['text'].rstrip('\r\n') == b['documents']['study.txt'].splitlines()[2]]
    return dict(reading=dict(intents={'q1':dict(kind='水平',question_id=question_catalog(b)['q1']['question_id'])},
        questions={'q1':dict(first={n:1 for n in nodes},second=None,population=pop,aggregation='等权平均')}),
        reported_assignment=dict(mechanism='FIXED_QUOTA_RANDOM',fixed_count=quota,maximum_count=None,
            uniform_subset_declared=True,reported_conflict=False,source_ids=sid))


def model(name='star7', population=None):
    nodes, edges, quota, pop = specification(name, population)
    st = f.declare_network_study(network_id='BOUNDED_'+name, node_order=nodes,
        undirected_edges=edges, treatment_variable='AI',outcome_variable='on_time',outcome_kind='binary',
        context_reference='W_same_day_protocol',observation_regime='experimental',
        assignment_design={'kind':'complete_randomization_binary_v1','m':quota},
        protocol_provenance='Hypothetical uniform quota experiment; independently stipulated',
        network_provenance='Hypothetical fixed undirected network',graph_timing_claim='DECLARED_PRETREATMENT_FIXED')
    target = f.fixed_policy_target_from_context(st, (1,)*len(nodes), authority='TRUSTED_FIXTURE',
        unit_weights=tuple(str(F(1,len(pop))) if n in pop else '0' for n in nodes))
    sig = f.declare_policy_signature(st,grouping='strict_majority_ties_low')
    suff = f.admit_mean_signature_sufficiency(st,sig,covered_nodes=nodes,
        assumption=f.Assumption(name='mean_signature_sufficiency',source='demo_specification',
            confirmed=True,status='ADMITTED',evidence=['Hypothetically reviewed for ALL binary arrangements and ALL study nodes']))
    neighbors = {n: {v if u==n else u for u,v in edges if n in (u,v)} for n in nodes}
    supported = set()
    for z in product((0,1),repeat=len(nodes)):
        if sum(z) != quota: continue
        p = dict(zip(nodes,z))
        supported.update((n,p[n],int(2*sum(p[j] for j in neighbors[n])>len(neighbors[n]))) for n in nodes)
    cells = tuple(sorted(supported))
    source = f.declare_signature_population_source(st,sig,source_id='EXACT_SYNTHETIC_MEANS',
        operator='NODE_SIGNATURE_MEANS',outcome_nodes=nodes,signature_cells=cells,
        admission='ADMITTED',availability='EXACT_POPULATION_VALUE',
        provenance='Explicit hypothetical population means, each equal to one half; no sample estimation')
    inquiry = f.FixedPolicyInquiryV21(st,target,f._assumptions(),r2_signature=sig,
        r2_sufficiency=suff,r2_sources=(source,))
    info = BoundedMeanInformation(version=VERSION,inquiry_sha256=f.sha(inquiry),source_id=source.source_id,
        source_sha256=f.sha(source),information_scope='EXACT_LISTED_SIGNATURE_MEANS_ONLY',
        model_scope='SIGNATURE_MEANS_AND_NODE_BOUNDS_ONLY',availability='EXACT_POPULATION_VALUE',
        values=[dict(node=n,own=a,exposure=e,value='1/2') for n,a,e in cells],
        bounds=[dict(node=n,lower='0',upper='1') for n in nodes],bounds_kind='ALMOST_SURE_OUTCOME',
        bounds_scope='ALL_BINARY_ASSIGNMENTS_CONDITIONAL_ON_STUDY_CONTEXT',
        outcome_definition='Each group completes its specified daily task on time (one) or not (zero)',
        outcome_unit='Binary daily completion indicator',outcome_period='The same fixed day protocol W',
        a4_provenance='Synthetic protocol: all and only the enumerated signature population means are known',
        bounds_provenance='Binary outcome definition applies to every intervention; this is a stipulated synthetic protocol')
    return inquiry, info


def reviews(name='star7', population=None, *, raw=None):
    b=public_bundle(name,population); raw=reference(name,population) if raw is None else raw
    resolved,_=resolve_reading(b,raw); typed,info=model(name,population)
    coords=dict(classification='FIXED_POLICY',node_order=list(typed.study.node_order),
        assignment=list(typed.target.policy_assignment),unit_weights=list(typed.target.unit_weights))
    if f.project(b,resolved['reading'])[0] != {'q1':coords}:
        raise ValueError('READING_DIFFERS_FROM_INDEPENDENT_FIXTURE')
    text='\n'.join(b['documents'].values()); goal=b['question_slots']['q1']; lines=b['documents']['study.txt'].splitlines()
    case=f.BusinessCase(case_id=b['case_id'],business_question=text)
    def cl(q):
        if q not in text: raise ValueError('FIXTURE_QUOTE_NOT_FOUND')
        return f.SemanticClaim(value=q,basis='EXPLICIT_TEXT',evidence=[f.EvidenceQuote(source_id='business_question',quote=q)])
    target=f.TargetDraft(kind=f.TargetKind.FIXED_POLICY_VALUE,description=cl(goal))
    shared=f.DraftProblemSpec(target=target,
        units_variables=f.UnitsVariablesDraft(analysis_unit=cl(lines[0]),treatment=cl('使用AI助手'),outcome=cl('每日任务是否按时完成')),
        structure=f.StructureDraft(unit_network=cl(lines[1]),network_pretreatment_status=cl(lines[1]),exposure_mapping=cl(lines[3])),
        information_design=f.InformationDesignDraft(assignment_family=f.AssignmentFamily.COMPLETE_RANDOMIZATION,
            assignment_law=cl(lines[2]),population_information_level=f.PopulationInformationLevel.FINITE_SAMPLE_DESCRIPTION,
            sample_data_description=cl(lines[4])))
    query=f.BusinessInquiryV010(query_id='q1',target=target,business_goal=cl(goal),semantics=f.QuerySemanticsV010(
        target_population=cl(goal),intervention=cl(goal),aggregation=cl(goal),policy_assignment=cl(goal)))
    quality=f.audit_business_quality(case,f.MultiQueryDraftV010(shared_draft=shared,primary_query_id='q1',queries=[query]),
        provider='INDEPENDENT_SYNTHETIC_REVIEW',prompt_version='bounded-policy-fixture')
    review=f.BusinessQueryReviewV011(case_id=case.case_id,input_sha256=quality.input_sha256,draft_sha256=quality.draft_sha256,
        confirmed_query_ids=['q1'],reviewed_by='Independent synthetic reviewer',decision='CONFIRMED',
        review_note='Frozen policy and evaluation population; hypothetical fixture only')
    reviewed=f.approve_multiquery(case,quality.legacy_audit,f.v29_review_from_v011(review,legacy_draft_sha256=quality.legacy_audit.draft_sha256))
    science=f.ScientificAdmissionV29(case_id=case.case_id,input_sha256=quality.input_sha256,
        draft_sha256=quality.legacy_audit.draft_sha256,query_id='q1',target_sha256=f.canonical_sha256(target),
        formal_family='R2_FIXED_POLICY',formal_target_fingerprint=f.formal_target_fingerprint_v29(typed),
        math_target_description=goal,math_target_crosswalk_confirmed=True,scientific_reviewer='Independent synthetic scientist',
        evidence_reference='BOUNDED_SYNTHETIC_PROTOCOL',a4_population_operator_reference='EXACT_SYNTHETIC_MEANS',
        a4_scientifically_admitted=True,a5_assumption_reference='EXPLICIT_SYNTHETIC_A5',a5_scientifically_admitted=True,
        scientific_review_note='Mean information and full-arrangement mean sufficiency stipulated separately; no model approval',is_synthetic_fixture=True)
    science=f.independently_review_fixture(science,typed,reviewed,'q1','R2_MEAN_SIGNATURE')
    intent=f.independently_confirm_business_intent_v292(reviewed,'q1',coords,evidence='Predeclared full intervention and equal evaluation population')
    binding=f.FormalQueryBindingV29(science,typed,intent,f.independently_review_evidence_v292(science,typed))
    sheet=f.unapproved_crosswalk_worksheet_v012(case=case,quality=quality,business_review=review,query_id='q1',
        formal_binding=binding,reviewer='Independent synthetic scientist',evidence='Exact fixed target and complete hypothetical A4/A5 reviewed')
    sheet.update(reviewer_confirmed_business_to_math=True,reviewer_confirmed_a4_a5_and_route=True)
    port=f.RealCoreCoveragePortV012(bindings={'q1':binding},crosswalks={'q1':f.ApprovedBusinessMathCrosswalkV012.model_validate(sheet)})
    packet=dict(mode='SYNTHETIC_BENCHMARK_ONLY',bundle_sha256=f.canonical_hash(b),queries={'q1':dict(
        study_sha256=f.sha(typed.study),a4_sources_sha256=f.sha(f.actual_scientific_sources(typed)),
        a5_licenses_sha256=f.sha(f.actual_scientific_licenses(typed)),a4_reference=science.a4_population_operator_reference,
        a5_reference=science.a5_assumption_reference)})
    approval=f.MaterialsCandidateApprovalV035(bundle_sha256=f.canonical_hash(b),model_draft_sha256=f.canonical_hash(resolved['reading']),
        science_packet_sha256=f.canonical_hash(packet),gateway_case_sha256=f.canonical_sha256(case),
        gateway_quality_sha256=f.canonical_sha256(quality),gateway_review_sha256=review.fingerprint(),reviewed_query_ids=['q1'],
        reviewed_a4_levels={},reviewer='Independent synthetic materials reviewer',review_evidence='Actual response checked against frozen target',
        reviewed_materials_to_gateway=True,synthetic_fixture=True)
    context=f.ReviewedMaterialsContextV035(case,quality,review,port,approval)
    outer=f.reviewed_submission(b,resolved['reading'],'FIXED_POLICY',packet,context)
    facts=ReviewedQuestionBoundAssignmentFacts(**assignment_worksheet(b,raw,packet,context,contract=CONTRACT),
        reviewer='Independent synthetic assignment reviewer',evidence='Original uniform fixed quota and full sources explicitly checked',
        reviewed_original_assignment_and_sources=True,synthetic_fixture=True)
    bound=ReviewedBoundedPolicy(**worksheet(b,raw,query_id='q1',packet=packet,context=context,information=info),
        reviewer='Independent synthetic bound reviewer',evidence='Only these A4 means; binary bound, all-arrangement A5 and no extra couplings',
        reviewed_complete_a4_information=True,reviewed_scientific_bounds_and_scope=True,
        reviewed_no_additional_coupling_constraints=True,synthetic_fixture=True)
    return dict(query_id='q1',packet=packet,context=context,information=info,bounded_review=bound,
        submission_review=outer,assignment_review=facts,synthetic_protocol_selected=True)


if __name__ == '__main__':
    import json
    from cfm_id.bounded_policy import submit
    for name in ('star7','chain4','star5'):
        result=submit(public_bundle(name),reference(name),**reviews(name))
        print(json.dumps(dict(case=name,state=result['state'],replayed=result['bounded_certificate_replayed'],
            interval=[result.get('bounded_result',{}).get(k) for k in ('lower','upper')]),ensure_ascii=False))
