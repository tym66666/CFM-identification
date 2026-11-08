"""Safe JSON recipes: each registered route has positive core replay + negative tamper.
A0 business meaning and scientific A4/A5 are separately approved in integration
benchmark; here the scoped science data are hypothetical typed test fixtures.
"""
from __future__ import annotations
import json
import unittest
from dataclasses import asdict,replace
from itertools import product
from fractions import Fraction

from cfm_id_bridge.bridge import ScientificAdmissionV29,formal_target_fingerprint_v29
from cfm_id_bridge.typed_packets import ReviewedTypedInquiryPacketV291,construct_reviewed_typed_binding_v291
from pfn_pipeline.identification_business import identify_network_business_query,replay_verified_business_outcome
from examples.llm_core_fixture import reviewed_case,bindings,scientist,d1_arm_packet,demo_study
from pfn_pipeline._internal.identification.schemas import Assumption
from pfn_pipeline.identification_policy_r2 import declare_policy_signature
from pfn_pipeline.identification_observational_r3 import declare_observational_population_v23


def st_recipe(st):
    return dict(network_id=st.network_id,node_order=list(st.node_order),
      undirected_edges=[list(x) for x in st.undirected_edges],
      treatment_variable=st.treatment_variable,outcome_variable=st.outcome_variable,
      outcome_kind=st.outcome_kind,context_reference=st.context_reference,
      observation_regime=st.observation_regime,
      assignment_design=json.loads(st.assignment_design_json) if st.assignment_design_json else None,
      protocol_provenance=st.protocol_provenance,network_provenance=st.network_provenance,
      graph_timing_claim=st.graph_timing_claim)


def source_recipe(src):
    base={k:getattr(src,k) for k in ('source_id','operator','provenance','admission','availability','outcome_nodes')}
    if hasattr(src,'assignment_cells') and src.operator=='ASSIGNMENT_NODE_MEANS':
        base['assignment_cells']=[list(x) for x in src.assignment_cells]
    return base


def obs_study():
    from pfn_pipeline.network_inquiry_shadow import declare_network_study
    return declare_network_study(network_id='SYNTH_OBS_V291',node_order=('A','B','C'),
       undirected_edges=(('A','B'),('A','C')),
       treatment_variable='ai_access',outcome_variable='sales_amount',
       outcome_kind='continuous',context_reference='W',observation_regime='observational',
       assignment_design=None,protocol_provenance='independent synthetic observed selection',
       network_provenance='synthetic fixed pretreatment network',
       graph_timing_claim='DECLARED_PRETREATMENT_FIXED')


def obs_source_recipe():
    return dict(source_id='OBS_SYNTHETIC_FULL_LAW',
       provenance='SYNTHETIC POPULATION LAW NOT SAMPLE OBSERVATIONS',
       assignment_masses=[(list(t),'1/8') for t in product((0,1),repeat=3)],
       outcome_nodes=['A','B','C'],admission='ADMITTED',
       availability='SYMBOLIC_POPULATION_OPERATOR')


def assumptions(names):
    return [Assumption(name=n,source='demo_specification',confirmed=True,
              evidence=['hypothetical scoped A5 reviewer accepted']).model_dump(mode='json')
           for n in names]


class JSONPacketRegression(unittest.TestCase):
    def setUp(self):
        self.case,self.reviewed=reviewed_case()
        self.arm,self.policy=bindings(self.case,self.reviewed)
        self.st=self.policy.inquiry.study
        self.r1bsrc=source_recipe(self.policy.inquiry.r1b_sources[0])
        self.r1ass=[x.model_dump(mode='json') for x in self.policy.inquiry.assumptions]
        self.expsource=obs_source_recipe()
        self.obsa5=assumptions(('full_vector_conditional_exchangeability','consistency',
             'fixed_pretreatment_network','finite_conditional_first_moments'))
        self.basic=assumptions(('consistency','fixed_pretreatment_network',
             'finite_conditional_first_moments'))

    def _packet(self,f,recipe):
        # This stage checks construction and actual core replay, not Gateway
        # authorization. Final v2.9.1 POINT requires an independently supplied
        # exact scientific approval separately tested in integration tests.
        science=self.policy.admission.model_copy(update={
            'formal_family':f,'formal_target_fingerprint':'0'*64,
            'approved_scientific_binding':None})
        packet=ReviewedTypedInquiryPacketV291(scientific_admission=science,formal_family=f,
                                              recipe=json.loads(json.dumps(recipe,default=str)))
        # Compute the correct *proposed* scientific target fingerprint separately.
        try:
            construct_reviewed_typed_binding_v291(packet)
        except ValueError as e:
            # The previous v2.9 A1 fingerprint remains a mandatory gate.
            self.assertIn('scientific target fingerprint',str(e))
        # Actual fresh typed inquiry constructed in adapter; for test use a
        # temporary bypass only to get a proposed worksheet coordinate.
        from unittest.mock import patch
        from cfm_id_bridge.bridge import FormalQueryBindingV29
        with patch.object(FormalQueryBindingV29,'__post_init__',lambda self:None):
            tmp=construct_reviewed_typed_binding_v291(packet)
        fixed=science.model_copy(update={
            'formal_target_fingerprint':formal_target_fingerprint_v29(tmp.inquiry)})
        packet=packet.model_copy(update={'scientific_admission':fixed})
        converted=construct_reviewed_typed_binding_v291(packet)
        return converted,packet

    def _assert_real_core_and_replay(self,f,recipe):
        b,packet=self._packet(f,recipe)
        result=identify_network_business_query(b.inquiry)
        self.assertEqual(result.status,'POINT',msg=(f,result.reason_code))
        self.assertTrue(replay_verified_business_outcome(result))
        payload=packet.model_dump(mode='json')
        payload['malicious_class']='os.system'
        from pydantic import ValidationError
        with self.assertRaises(ValidationError):
            ReviewedTypedInquiryPacketV291.model_validate(payload)
        return b,packet,result

    def _integrated_approved_route(self,f,recipe):
        from cfm_id_llm.schemas import (BusinessCase,SemanticClaim,EvidenceQuote,
            TargetDraft,TargetKind,DraftProblemSpec,UnitsVariablesDraft,
            StructureDraft,InformationDesignDraft,AssignmentFamily,PopulationInformationLevel)
        from cfm_id_llm.multiquery import (MultiQueryDraftV09,BusinessInquiryV09,
            HumanMultiQueryReviewV09,approve_multiquery)
        from cfm_id_llm.multiquery_formulator import MultiQueryFormulatorV09
        from cfm_id_llm.providers.mock import MockProvider
        from cfm_id_llm.orchestration_schemas import canonical_sha256
        from cfm_id_bridge.bridge import run_verified_multiquery_v29,FormalQueryBindingV29
        from cfm_id_bridge.scientific_binding import (
            sha,proposed_binding_snapshot_v291,ApprovedScienceBindingV291)
        from unittest.mock import patch
        is_obs=f.startswith('R3_')
        treatment='员工使用AI'
        outcome='销售额'
        net='员工A与B、C有处理前固定合作关系'
        exposure='邻居使用AI达到严格多数称为高暴露，否则低暴露'
        law=('员工自主选择AI' if is_obs else '公司独立随机给员工开放AI')
        if f=='R1A_ARM':
            goal='员工A不使用AI且同事低暴露时的平均销售额'
            kind=TargetKind.NETWORK_DESIGN_STANDARDIZED_ARM_MEAN
        elif f in ('R1B_FIXED_POLICY','R2_FIXED_POLICY','R3_POLICY'):
            goal='三名员工全部使用AI时的平均销售额';kind=TargetKind.FIXED_POLICY_VALUE
        elif f=='R1B_FINITE_POLICY':
            goal='以各一半机会执行全员AI政策或只让A与C用AI的平均销售额'
            kind=TargetKind.STOCHASTIC_POLICY_VALUE
        else:
            goal='员工A在同事低AI暴露下有AI与无AI的平均销售额差'
            kind=TargetKind.DIRECT_EFFECT
        question='。'.join((net,treatment,outcome,exposure,law,goal))+'。'
        def cl(text):
            return SemanticClaim(value=text,basis='EXPLICIT_TEXT',
                evidence=[EvidenceQuote(source_id='business_question',quote=text)])
        case=BusinessCase(case_id='V291_'+f,business_question=question)
        target=TargetDraft(kind=kind,description=cl(goal))
        shared=DraftProblemSpec(target=target,
            units_variables=UnitsVariablesDraft(analysis_unit=cl(net),
                treatment=cl(treatment),outcome=cl(outcome)),
            structure=StructureDraft(unit_network=cl(net),
                network_pretreatment_status=cl(net),exposure_mapping=cl(exposure)),
            information_design=InformationDesignDraft(
                assignment_family=AssignmentFamily.OBSERVATIONAL if is_obs else AssignmentFamily.INDEPENDENT_BERNOULLI,
                assignment_law=cl(law),
                population_information_level=PopulationInformationLevel.FINITE_SAMPLE_DESCRIPTION,
                sample_data_description=cl('销售额')))
        draft=MultiQueryDraftV09(primary_query_id='q1',shared_draft=shared,
            queries=[BusinessInquiryV09(query_id='q1',target=target,business_goal=cl(goal))])
        report=MultiQueryFormulatorV09(MockProvider(draft.model_dump(mode='json'))).formulate(case)
        reviewer=HumanMultiQueryReviewV09(case_id=case.case_id,input_sha256=report.input_sha256,
            draft_sha256=report.draft_sha256,confirmed_query_ids=['q1'],
            reviewed_by='Independent synthetic business reviewer',decision='CONFIRMED',
            review_note='Independently checked this synthetic goal and exact query meaning')
        reviewed=approve_multiquery(case,report,reviewer)
        old=self.policy.admission
        science=old.model_copy(update={
            'case_id':case.case_id,'input_sha256':report.input_sha256,
            'draft_sha256':report.draft_sha256,'query_id':'q1',
            'target_sha256':canonical_sha256(target),'formal_family':f,
            'formal_target_fingerprint':'0'*64,'approved_scientific_binding':None})
        packet=ReviewedTypedInquiryPacketV291(scientific_admission=science,
            formal_family=f,recipe=recipe)
        with patch.object(FormalQueryBindingV29,'__post_init__',lambda self:None):
            typed=construct_reviewed_typed_binding_v291(packet).inquiry
        fingerprint=formal_target_fingerprint_v29(typed)
        expected={'R1A_ARM':'R1A_RANDOMIZED_ARM','R1A_EFFECT':'R1A_COMPOSITION',
            'R1B_FIXED_POLICY':'R1B_FULL_ASSIGNMENT','R2_FIXED_POLICY':'R2_MEAN_SIGNATURE',
            'R1B_FINITE_POLICY':'R1B_FINITE_POLICY','R3_POLICY':'R3_FULL_ASSIGNMENT',
            'R3_P_STANDARDIZED':'R3_P_STANDARDIZED_EFFECTS',
            'R3_EXPOSURE_ADJUSTED':'R3_EXPOSURE_ADJUSTED_EFFECTS',
            'R3_NODEWISE_ADJUSTED':'R3_NODEWISE_EXPOSURE_ADJUSTED_EFFECTS'}[f]
        # The following is the separate scientific REVIEW in a labelled
        # synthetic fixture. Production must not infer this from Gateway.
        worksheet=proposed_binding_snapshot_v291(typed,
            business_review_sha256=sha(reviewer),
            target_sha256=canonical_sha256(target),business_quote=goal,
            a4_reference=science.a4_population_operator_reference,
            a5_reference=science.a5_assumption_reference,
            theorem_route=expected,reviewer=science.scientific_reviewer,
            evidence=science.evidence_reference)
        admitted=ApprovedScienceBindingV291.model_validate({**worksheet,
            'reviewer_confirmed_exact_coordinates':True,
            'reviewer_confirmed_sources_and_licenses':True})
        science=science.model_copy(update={'formal_target_fingerprint':fingerprint,
              'approved_scientific_binding':admitted})
        packet=packet.model_copy(update={'scientific_admission':science})
        binding=construct_reviewed_typed_binding_v291(packet)
        from dataclasses import replace
        from examples.llm_core_fixture import independently_confirm_business_intent_v292
        # Explicit synthetic BUSINESS truth assertions, not a science worksheet.
        if f=='R1A_ARM':
            coordinates=dict(classification='RANDOMIZED_ARM',node_order=['A','B','C'],
                             node_id='A',own_treatment=0,exposure_state=0)
        elif f in ('R1B_FIXED_POLICY','R2_FIXED_POLICY','R3_POLICY'):
            coordinates=dict(classification='FIXED_POLICY',node_order=['A','B','C'],
                             assignment=[1,1,1],unit_weights=['1/3']*3)
        elif f=='R1B_FINITE_POLICY':
            coordinates=dict(classification='FINITE_POLICY',probabilities=['1/2','1/2'],
                component_target_digests=[x.target_fingerprint for x in binding.inquiry.components])
        else:
            from cfm_id_bridge.scientific_binding import scientific_target_coordinates
            actual=scientific_target_coordinates(binding.inquiry)
            coordinates=dict(classification=type(binding.inquiry).__name__,kind='DIRECT',
                node_weights=[['A','1']],reference_exposure=0,
                comparison_exposure=0,spillover_own_treatment=actual['spillover_own_treatment'])
        intent=independently_confirm_business_intent_v292(reviewed,'q1',coordinates,
             evidence='Explicit synthetic business goal reviewed independently before scientific input')
        from examples.llm_core_fixture import independently_review_evidence_v292
        binding=replace(binding,business_intent=intent,
                        evidence_manifest=independently_review_evidence_v292(science,binding.inquiry))
        decision=run_verified_multiquery_v29(case,reviewed,(binding,)).results[0]
        self.assertEqual((decision.status,decision.route,decision.verification_level),
            ('POINT',expected,'CORE_REPLAY_VERIFIED'),msg=f)
        # Wrong A4 reference, even if some other typed source supports it,
        # cannot leave the original scientific approval untouched.
        altered=science.model_copy(update={'a4_population_operator_reference':
               'SYNTHETIC_UNAPPROVED_REPLACEMENT_A4_SOURCE'})
        bad=FormalQueryBindingV29(altered,binding.inquiry)
        blocked=run_verified_multiquery_v29(case,reviewed,(bad,)).results[0]
        self.assertEqual(blocked.status,'INCOMPATIBLE',msg=f)
        wrong_a5=science.model_copy(update={'a5_assumption_reference':
                     'A5_DIFFERENT_UNREVIEWED_LICENSE'})
        denied=run_verified_multiquery_v29(case,reviewed,
                 (FormalQueryBindingV29(wrong_a5,binding.inquiry),)).results[0]
        self.assertEqual(denied.status,'INCOMPATIBLE',msg=f)
        route_changed=('R3_MEAN_SIGNATURE' if f=='R3_POLICY' else 'R3_FULL_ASSIGNMENT')
        scope=admitted.model_copy(update={'approved_theorem_route':route_changed})
        wrong_route=science.model_copy(update={'approved_scientific_binding':scope})
        denied_route=run_verified_multiquery_v29(case,reviewed,
                 (FormalQueryBindingV29(wrong_route,binding.inquiry),)).results[0]
        self.assertEqual(denied_route.status,'INCOMPATIBLE',msg=f)
        if not hasattr(self,'integrated_packet_by_route'):
            self.integrated_packet_by_route={}
        self.integrated_packet_by_route[f]=(case,report,reviewer,packet,
            binding.business_intent,binding.evidence_manifest)
        return [
          dict(route=f,scenario='ADMITTED_FORMAL_TARGET',expected='POINT',actual=decision.status,
               replay=decision.verification_level),
          dict(route=f,scenario='A4_SOURCE_MISMATCH',expected='INCOMPATIBLE',actual=blocked.status),
          dict(route=f,scenario='A5_LICENSE_MISMATCH',expected='INCOMPATIBLE',actual=denied.status),
          dict(route=f,scenario='ROUTE_APPROVAL_MISMATCH',expected='INCOMPATIBLE',actual=denied_route.status),
        ]

    def test_json_a4_must_explicitly_declare_admission_and_availability(self):
        """No A4 science permission or population granularity is manufactured."""
        from cfm_id_bridge.typed_packets import _observational_source, _keys
        for missing in ('admission','availability'):
            source = dict(self.expsource)
            source.pop(missing)
            with self.subTest(operator='finite_observational', missing=missing):
                with self.assertRaises(ValueError):
                    _observational_source(obs_study(),source)
            for cls in ('stratified','nodewise'):
                mandatory = ('source_id','provenance',
                    'adjustment_variable','strata','covered_cells','admission','availability') if cls=='stratified' else (
                    'source_id','provenance','feature_name','profiles','covered_cells','admission','availability')
                payload={x: 'synthetic' for x in mandatory if x != missing}
                with self.subTest(operator=cls, missing=missing):
                    with self.assertRaises(ValueError):
                        _keys(payload,mandatory)

    def test_all_nine_routes_and_negative_injection(self):
        # Original D1 arm: explicit D1 packet is also accepted by the safe
        # generic reviewed route adapter; no simulated outcome numbers.
        d1=d1_arm_packet(self.case,self.reviewed)
        v=d1.model_dump(mode='json');v.pop('schema_version');v.pop('scientific_admission')
        cases=[('R1A_ARM',{'d1':v})]
        cases.append(('R1A_EFFECT',dict(d1=v,
          effect=dict(kind='DIRECT',node_weights=[['A','1']],
                      reference_exposure=0,comparison_exposure=0),
          a4_source=dict(source_id='R1A_FULL_POPULATION',operator='NODE_FULL_LAW',
                         provenance='synthetic full node population law',admission='ADMITTED',
                         availability='SYMBOLIC_POPULATION_OPERATOR',outcome_nodes=['A','B','C']))))
        cases.append(('R1B_FIXED_POLICY',dict(study=st_recipe(self.st),
          assumptions=self.r1ass,policy={'assignment':[1,1,1]},a4_source=self.r1bsrc)))
        cases.append(('R1B_FINITE_POLICY',dict(study=st_recipe(self.st),
          assumptions=self.r1ass,a4_source=self.r1bsrc,
          components=[{'policy':{'assignment':[1,1,1]}},
                      {'policy':{'assignment':[1,0,1]}}],probabilities=['1/2','1/2'])))
        # R2: use a full-support policy with separately accepted signature
        # sufficiency. Its A5 still cannot be inferred from the presence of E1.
        r2_source=dict(source_id='R2_SYNTH_A4',operator='NODE_FULL_LAW',
          provenance='synthetic population means',admission='ADMITTED',
          availability='SYMBOLIC_POPULATION_OPERATOR',outcome_nodes=['A','B','C'])
        cases.append(('R2_FIXED_POLICY',dict(study=st_recipe(self.st),
          assumptions=self.r1ass,policy={'assignment':[1,1,1]},
          signature={'grouping':'strict_majority_ties_low'},
          sufficiency={'covered_nodes':['A','B','C'],
            'assumption':assumptions(('mean_signature_sufficiency',))[0]},
          a4_sources=[r2_source])))
        obs=st_recipe(obs_study())
        cases.append(('R3_POLICY',dict(study=obs,assumptions=self.obsa5,
          policy={'assignment':[1,1,1]},a4_source=self.expsource)))
        effect=dict(kind='DIRECT',node_weights=[['A','1']],
                    reference_exposure=0,comparison_exposure=0)
        cases.append(('R3_P_STANDARDIZED',dict(study=obs,assumptions=self.obsa5,
          signature={'grouping':'strict_majority_ties_low'},effect=effect,
          a4_source=self.expsource)))
        strata=dict(source_id='STRATIFIED_SYNTH',provenance='synthetic conditional population',
          adjustment_variable='pretreatment_B',admission='ADMITTED',
          availability='SYMBOLIC_POPULATION_OPERATOR',
          strata=[['s0','1/2',['1/2','1/2','1/2']],['s1','1/2',['1/2','1/2','1/2']]],
          covered_cells=[[b,'A',t,0] for b in ['s0','s1'] for t in (0,1)])
        lic=dict(covered_nodes=['A'],
          potential_outcome_exposure_sufficiency=assumptions(('potential_outcome_exposure_sufficiency',))[0],
          exposure_level_conditional_exchangeability=assumptions(('exposure_level_conditional_exchangeability',))[0])
        cases.append(('R3_EXPOSURE_ADJUSTED',dict(study=obs,assumptions=self.basic,
          signature={'grouping':'strict_majority_ties_low'},effect=effect,
          a4_source=strata,license=lic)))
        nodewise=dict(source_id='NODEWISE_SYNTH',provenance='synthetic P(X),P(T|X),E[Y|C,T,S]',
          feature_name='pre_AI_skill',admission='ADMITTED',
          availability='SYMBOLIC_POPULATION_OPERATOR',profiles=[['p0','1',[0,1,0],['1/2','1/2','1/2']]],
          covered_cells=[['A',0,1,t,0] for t in (0,1)])
        nlic=dict(feature_name='pre_AI_skill',covered_nodes=['A'],
          potential_outcome_exposure_sufficiency=assumptions(('potential_outcome_exposure_sufficiency',))[0],
          local_covariate_exposure_mean_exchangeability=assumptions(('local_covariate_exposure_mean_exchangeability',))[0])
        cases.append(('R3_NODEWISE_ADJUSTED',dict(study=obs,assumptions=self.basic,
          signature={'grouping':'strict_majority_ties_low'},effect=effect,
          a4_source=nodewise,license=nlic)))
        failures=[]
        for f,r in cases:
            with self.subTest(route=f):
                try:self._assert_real_core_and_replay(f,r)
                except Exception as e:failures.append(f'{f}: {e!r}')
        if failures:self.fail('; '.join(failures))
        # Second, run all routes through real A0 review -> explicitly approved
        # business/science crosswalk -> true Core -> independent replay.
        self.formal_benchmark_results=[]
        for f,r in cases:
            with self.subTest(integrated_route=f):
                self.formal_benchmark_results.extend(self._integrated_approved_route(f,r))

if __name__=='__main__':unittest.main()
