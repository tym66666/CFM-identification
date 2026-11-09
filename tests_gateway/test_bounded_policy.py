"""Finite mean-box mathematics, review gates and adversarial replay; no APIs."""
from copy import deepcopy
from dataclasses import replace
from fractions import Fraction as F
from itertools import product, combinations
import json
import subprocess
import sys
import unittest
from unittest.mock import Mock, patch

from pydantic import ValidationError
from cfm_id_bridge.scientific_binding import sha
from cfm_id import bounded_policy as entry
from cfm_id.bounded_policy_contract import (
    BoundedMeanInformation, ReviewedBoundedPolicy, BoundedPolicyUnavailable, validate_model,
)
from cfm_id.bounded_policy_solver import solve
from cfm_id.bounded_policy_verify import replay
from cfm_id.business_entry import read_once, prepare_request
from cfm_id.intent_submission import submit as point_submit
from examples.bounded_policy_fixture import public_bundle, reference, model, reviews, CONTRACT
from examples import intent_routes_fixture as fixture
from pfn_pipeline.identification_policy_r2 import declare_signature_population_source
from pfn_pipeline._internal.identification.schemas import Assumption
from pfn_pipeline._internal.identification.randomized_arm_family import SupportEngine


def rebind(inquiry, info):
    return info.model_copy(update={'inquiry_sha256':sha(inquiry),
        'source_sha256':sha(inquiry.r2_sources[0]),'source_id':inquiry.r2_sources[0].source_id})


def rehash(cert):
    cert.pop('certificate_sha256',None); cert['certificate_sha256']=sha(cert)
    return cert


class BoundedMathematicsTests(unittest.TestCase):
    def setUp(self):
        self.q,self.info=model()

    def unavailable(self, inquiry, info, state, reason):
        with self.assertRaises(BoundedPolicyUnavailable) as cm: solve(inquiry,info)
        self.assertEqual((cm.exception.state,cm.exception.reason),(state,reason))

    def test_known_star_chain_point_and_single_population_results(self):
        cases=[('star7',None,['3/7','4/7'],'PARTIAL'),('chain4',None,['1/4','3/4'],'PARTIAL'),
            ('star5',None,['1/2','1/2'],'POINT'),('star7',['H'],['0','1'],'PARTIAL'),
            ('star7',['L1'],['1/2','1/2'],'POINT'),('chain4',['A','B'],['1/4','3/4'],'PARTIAL')]
        for name,pop,expected,status in cases:
            with self.subTest(name=name,pop=pop):
                q,info=model(name,pop); cert=solve(q,info)
                self.assertEqual([cert['lower'],cert['upper']],expected)
                self.assertEqual(cert['status'],status); self.assertTrue(replay(cert,inquiry=q,information=info))
                self.assertEqual(cert['realization'],'BERNOULLI_PER_NODE_SIGNATURE')
                if pop==['H']:self.assertFalse(cert['informative']);self.assertTrue(cert['sharp'])

    def test_replay_does_not_call_solver_support_engine_or_classifier(self):
        cert=solve(self.q,self.info)
        with patch('cfm_id.bounded_policy_solver.solve',side_effect=AssertionError('producer called')),\
             patch.object(SupportEngine,'evaluate',side_effect=AssertionError('support engine called')),\
             patch('pfn_pipeline.identification_policy_r2.ExposureSpec.classify',side_effect=AssertionError('classifier called')):
            self.assertTrue(replay(cert,inquiry=self.q,information=self.info))

    def test_nonuniform_weights_use_the_same_math(self):
        q=replace(self.q,target=replace(self.q.target,unit_weights=('1/2',)+('1/12',)*6,target_digest=''))
        info=rebind(q,self.info);cert=solve(q,info)
        self.assertEqual([cert['lower'],cert['upper']],['1/4','3/4'])
        self.assertTrue(replay(cert,inquiry=q,information=info))

    def test_bound_degenerate_unknown_cell_is_point(self):
        bounds=[v.model_copy(update={'lower':'1/2','upper':'1/2'}) if v.node=='H' else v for v in self.info.bounds]
        info=self.info.model_copy(update={'bounds':bounds,'bounds_kind':'CONDITIONAL_MEAN'});cert=solve(self.q,info)
        self.assertEqual((cert['status'],cert['lower'],cert['upper']),('POINT','1/2','1/2'))
        self.assertTrue(replay(cert,inquiry=self.q,information=info))

    def test_all_a4_means_checked_even_zero_weight_or_non_target(self):
        q,info=model('star7',['L1']);values=list(info.values)
        i=next(i for i,v in enumerate(values) if v.node=='H' and v.own==0)
        values[i]=values[i].model_copy(update={'value':'2'})
        self.unavailable(q,info.model_copy(update={'values':values}),'INCOMPATIBLE','A4_MEAN_OUTSIDE_SCIENTIFIC_BOUNDS')

    def test_inconsistent_and_binary_logical_bounds(self):
        for lo,hi in [('3/4','1/4'),('2','3')]:
            bounds=[v.model_copy(update={'lower':lo,'upper':hi}) if v.node=='H' else v for v in self.info.bounds]
            self.unavailable(self.q,self.info.model_copy(update={'bounds':bounds,'bounds_kind':'CONDITIONAL_MEAN'}),
                'INCOMPATIBLE','EMPTY_BOUND_RANGE')
        bounds=[v.model_copy(update={'lower':'-1','upper':'2'}) for v in self.info.bounds]
        info=self.info.model_copy(update={'bounds':bounds});cert=solve(self.q,info)
        self.assertEqual([cert['lower'],cert['upper']],['3/7','4/7'])
        self.assertTrue(replay(cert,inquiry=self.q,information=info))

    def test_binary_almost_sure_bounds_are_not_mean_bounds(self):
        data=self.info.model_dump()
        data['bounds'][0].update(lower='1/4',upper='3/4')
        info=BoundedMeanInformation.model_validate(data)
        self.unavailable(self.q,info,'INCOMPATIBLE','EMPTY_BINARY_OUTCOME_SUPPORT')
        mean_info=info.model_copy(update={'bounds_kind':'CONDITIONAL_MEAN'})
        cert=solve(self.q,mean_info)
        self.assertEqual([cert['lower'],cert['upper']],['13/28','15/28'])
        self.assertTrue(replay(cert,inquiry=self.q,information=mean_info))
        # Y<=3/4 for a binary outcome forces zero; known mean 1/2 is inconsistent.
        data['bounds'][0].update(lower='0',upper='3/4')
        self.unavailable(self.q,BoundedMeanInformation.model_validate(data),
            'INCOMPATIBLE','A4_MEAN_OUTSIDE_SCIENTIFIC_BOUNDS')

    def test_missing_numeric_value_and_missing_positive_target_remain_needs_input(self):
        values=[v for v in self.info.values if (v.node,v.own,v.exposure)!=('L1',1,1)]
        self.unavailable(self.q,self.info.model_copy(update={'values':values}),
            'NEEDS_INPUT','COMPLETE_EXACT_A4_VALUE_LIST_REQUIRED')
        source=replace(self.q.r2_sources[0],signature_cells=tuple((v.node,v.own,v.exposure) for v in values))
        q=replace(self.q,r2_sources=(source,));info=rebind(q,self.info).model_copy(update={'values':values})
        self.unavailable(q,info,'NEEDS_INPUT','SUPPORTED_TARGET_A4_MEAN_MISSING')

    def test_zero_probability_conditional_a4_is_rejected(self):
        source=replace(self.q.r2_sources[0],signature_cells=self.q.r2_sources[0].signature_cells+(('H',1,1),))
        q=replace(self.q,r2_sources=(source,));data=rebind(q,self.info).model_dump()
        data['values'].append(dict(node='H',own=1,exposure=1,value='1/2'))
        self.unavailable(q,BoundedMeanInformation.model_validate(data),'INCOMPATIBLE','A4_CONDITIONAL_EVENT_HAS_ZERO_PROBABILITY')

    def test_missing_bounds_no_default(self):
        self.unavailable(self.q,self.info.model_copy(update={'bounds':self.info.bounds[1:]}),
            'NEEDS_INPUT','EXPLICIT_ALL_NODE_BOUNDS_REQUIRED')

    def test_full_law_and_extra_a5_never_silently_dropped(self):
        source=declare_signature_population_source(self.q.study,self.q.r2_signature,source_id='FULL_JOINT',
            operator='FULL_JOINT_LAW',outcome_nodes=self.q.study.node_order,admission='ADMITTED',
            availability='EXACT_POPULATION_VALUE',provenance='A stronger complete law cannot be replaced by means')
        q=replace(self.q,r2_sources=(source,))
        self.unavailable(q,rebind(q,self.info),'UNSUPPORTED','FULL_LAW_CANNOT_BE_DOWNGRADED_TO_MEAN_BOX')
        extra=Assumption(name='monotonicity',source='demo_specification',status='ADMITTED',confirmed=True,evidence=['Extra constraint'])
        q=replace(self.q,assumptions=self.q.assumptions+(extra,))
        self.unavailable(q,rebind(q,self.info),'UNSUPPORTED','ADDITIONAL_A5_REQUIRES_JOINT_CONSTRAINT_SOLVER')

    def test_sufficiency_and_randomization_not_inferred(self):
        for name in ('full_vector_randomization','consistency'):
            q=replace(self.q,assumptions=tuple(a for a in self.q.assumptions if a.name!=name))
            self.unavailable(q,rebind(q,self.info),'NEEDS_INPUT','NEEDS_INPUT')
        assumption=Assumption(name='mean_signature_sufficiency',source='llm_candidate',confirmed=False,
            status='PROPOSED',evidence=['Candidate speculation is not a license'])
        q=replace(self.q,r2_sufficiency=replace(self.q.r2_sufficiency,assumption=assumption))
        self.unavailable(q,rebind(q,self.info),'NEEDS_INPUT','NEEDS_INPUT')

    def test_sample_and_symbolic_values_not_misused_as_exact_numbers(self):
        for availability in ('FINITE_SAMPLE_ESTIMATE','SYMBOLIC_POPULATION_OPERATOR'):
            q=replace(self.q,r2_sources=(replace(self.q.r2_sources[0],availability=availability),))
            self.unavailable(q,rebind(q,self.info),'NEEDS_INPUT','REVIEWED_EXACT_POPULATION_MEANS_REQUIRED')

    def test_nonuniform_study_other_exposure_and_unknown_scope_rejected(self):
        from pfn_pipeline.identification_policy_r2 import declare_policy_signature,admit_mean_signature_sufficiency
        sig=declare_policy_signature(self.q.study,grouping='any_treated_neighbor')
        suff=admit_mean_signature_sufficiency(self.q.study,sig,assumption=self.q.r2_sufficiency.assumption,covered_nodes=self.q.study.node_order)
        q=replace(self.q,r2_signature=sig,r2_sufficiency=suff)
        self.unavailable(q,rebind(q,self.info),'UNSUPPORTED','BOUNDED_D2_E1_FINITE_DOMAIN_REQUIRED')

    def test_six_graph_families_54_exact_vertex_oracles(self):
        # New mathematical cases, not model benchmark samples. Includes isolates,
        # ties, degenerate quotas, negative outcome ranges, nonuniform weights,
        # unequal A4 means and both supported/off-support policies.
        nodes=tuple('ABCD')
        graphs=[(),(('A','B'),('B','C'),('C','D')),
            (('A','B'),('B','C'),('C','D'),('D','A')),
            (('A','B'),('A','C'),('A','D')),tuple(combinations(nodes,2)),(('A','B'),('C','D'))]
        policies=[(0,0,0,0),(1,0,1,0),(1,1,1,1)]
        for gi,edges in enumerate(graphs):
            for quota in (0,2,4):
                for policy in policies:
                    with self.subTest(graph=gi,quota=quota,policy=policy):
                        st=fixture.declare_network_study(network_id='ORACLE_'+str(gi),node_order=nodes,
                            undirected_edges=edges,treatment_variable='AI',outcome_variable='score',outcome_kind='continuous',
                            context_reference='W',observation_regime='experimental',
                            assignment_design={'kind':'complete_randomization_binary_v1','m':quota},
                            protocol_provenance='Independent synthetic vertex oracle',network_provenance='Explicit small graph',
                            graph_timing_claim='DECLARED_PRETREATMENT_FIXED')
                        target=fixture.fixed_policy_target_from_context(st,policy,authority='TRUSTED_FIXTURE',
                            unit_weights=('1/2','0','1/3','1/6'))
                        sig=fixture.declare_policy_signature(st,grouping='strict_majority_ties_low')
                        suff=fixture.admit_mean_signature_sufficiency(st,sig,covered_nodes=nodes,
                            assumption=self.q.r2_sufficiency.assumption)
                        def coord(i,z):
                            neighbors=[nodes.index(b if a==nodes[i] else a) for a,b in edges if nodes[i] in (a,b)]
                            return nodes[i],z[i],int(2*sum(z[j] for j in neighbors)>len(neighbors))
                        support=[z for z in product((0,1),repeat=4) if sum(z)==quota]
                        cells=sorted({coord(i,z) for z in support for i in range(4)})
                        ranges={n:(F(-i-1),F(i+2)) for i,n in enumerate(nodes)}
                        known={c:ranges[c[0]][0]+(ranges[c[0]][1]-ranges[c[0]][0])*F(1+c[1]+2*c[2],5) for c in cells}
                        source=fixture.declare_signature_population_source(st,sig,source_id='ORACLE_MEANS',
                            operator='NODE_SIGNATURE_MEANS',outcome_nodes=nodes,signature_cells=tuple(cells),
                            admission='ADMITTED',availability='EXACT_POPULATION_VALUE',provenance='Known oracle cell means')
                        q=fixture.FixedPolicyInquiryV21(st,target,fixture._assumptions(),r2_signature=sig,r2_sufficiency=suff,r2_sources=(source,))
                        data=self.info.model_dump();data.update(inquiry_sha256=sha(q),source_id=source.source_id,source_sha256=sha(source),
                            values=[dict(node=c[0],own=c[1],exposure=c[2],value=str(v)) for c,v in known.items()],
                            bounds=[dict(node=n,lower=str(ranges[n][0]),upper=str(ranges[n][1])) for n in nodes],
                            bounds_kind='CONDITIONAL_MEAN',outcome_definition='Finite continuous score with signed range',
                            outcome_unit='Continuous score units')
                        info=BoundedMeanInformation.model_validate(data);cert=solve(q,info)
                        corners=product(*[(known[coord(i,policy)],) if coord(i,policy) in known else ranges[n] for i,n in enumerate(nodes)])
                        values=[sum(F(w)*v for w,v in zip(target.unit_weights,corner)) for corner in corners]
                        self.assertEqual([cert['lower'],cert['upper']],list(map(str,[min(values),max(values)])))
                        self.assertTrue(replay(cert,inquiry=q,information=info))
                        self.assertEqual(cert['realization'],'DETERMINISTIC_PER_NODE_SIGNATURE')

    def test_software_domain_does_not_silently_enumerate_a_large_network(self):
        # A stricter current budget is safe; test that the explicit guard is live.
        with patch('cfm_id.bounded_policy_contract.MAX_N',6):
            self.unavailable(self.q,self.info,'UNSUPPORTED','BOUNDED_D2_E1_FINITE_DOMAIN_REQUIRED')

    def test_information_model_scope_must_be_explicit(self):
        # Legitimate Chinese units/periods need not have three characters.
        data=self.info.model_dump();data.update(outcome_unit='比例',outcome_period='日')
        self.assertEqual(BoundedMeanInformation.model_validate(data).outcome_unit,'比例')
        for key,value in [('model_scope','MEANS_AND_MONOTONICITY'),('information_scope','FULL_LAW'),
                          ('bounds_scope','OBSERVED_ASSIGNMENTS_ONLY'),('bounds_provenance','   '),('outcome_unit',' ')]:
            data=self.info.model_dump();data[key]=value
            with self.assertRaises(ValidationError):BoundedMeanInformation.model_validate(data)

    def test_immutable_external_target_and_info_binding(self):
        cert=solve(self.q,self.info)
        q=replace(self.q,target=replace(self.q.target,policy_assignment=(0,)*7,target_digest=''))
        self.assertFalse(replay(cert,inquiry=q,information=rebind(q,self.info)))
        info=self.info.model_copy(update={'bounds_provenance':'A different provenance requires new binding'})
        self.assertFalse(replay(cert,inquiry=self.q,information=info))

    def test_certificate_forgery_rejected_even_with_recomputed_hash(self):
        original=solve(self.q,self.info)
        mutations=[lambda c:c.update(lower='0'),lambda c:c.update(upper='1'),lambda c:c.update(width='0'),
            lambda c:c.update(status='POINT'),lambda c:c.update(sharp=False),lambda c:c.update(informative=False),
            lambda c:c.update(logical_range=['1/4','3/4']),lambda c:c.update(realization='DETERMINISTIC_PER_NODE_SIGNATURE'),
            lambda c:c.update(production_admission=True),lambda c:c.update(ignored='extra'),
            lambda c:c['bound_terms'][0].update(coefficient='0'),lambda c:c['bound_terms'][0].update(basis='A4_EQUALITY'),
            lambda c:c['cells'][0].update(support='0'),lambda c:c['cells'][0].update(lower_world='3/4'),
            lambda c:c['cells'].append(deepcopy(c['cells'][0])),lambda c:c['cells'].pop(),
            lambda c:c['cells'][0]['cell'].__setitem__(1,True)]
        # A wider valid outer interval with internally consistent width is still not sharp.
        mutations.append(lambda c:c.update(lower='0',upper='1',width='1'))
        # Corrupt an unsupported target witness without touching the reported interval.
        mutations.append(lambda c:next(r for r in c['cells'] if r['cell']==['H',1,1]).update(upper_world='1/2'))
        for mutate in mutations:
            cert=deepcopy(original);mutate(cert)
            with self.subTest(cert=mutations.index(mutate)):
                self.assertFalse(replay(rehash(cert),inquiry=self.q,information=self.info))
    def test_feasible_world_missing_claimed_lower_bound_is_rejected(self):
        inquiry, information = model("star7", None)
        original = solve(inquiry, information)
        self.assertEqual(F(original["lower"]), F(3, 7))
        self.assertTrue(replay(original, inquiry=inquiry, information=information))

        changed = deepcopy(original)
        center = next(row for row in changed["cells"] if row["cell"] == ["H", 1, 1])
        self.assertIsNone(center["a4_value"])
        self.assertEqual(F(center["lower_world"]), 0)
        center["lower_world"] = "1/2"

        # Recompute the digest so replay must check the witness itself.
        changed.pop("certificate_sha256")
        changed["certificate_sha256"] = sha(changed)

        target_rows = [
            row for row in changed["cells"] if row["cell"][1:] == [1, 1]
        ]
        self.assertEqual(len(target_rows), 7)
        changed_value = sum(F(row["lower_world"]) for row in target_rows) / 7
        self.assertEqual(changed_value, F(1, 2))
        self.assertNotEqual(changed_value, F(changed["lower"]))
        self.assertFalse(replay(changed, inquiry=inquiry, information=information))

    def test_invalid_rational_and_coercion_do_not_enter_contract(self):
        for value in (0.5,True,'nan','inf','1/0','2/4',' 1/2',None):
            data=self.info.model_dump();data['values'][0]['value']=value
            with self.subTest(value=value),self.assertRaises(ValidationError):BoundedMeanInformation.model_validate(data)
        for value in (True,'1',0.0):
            data=self.info.model_dump();data['values'][0]['own']=value
            with self.assertRaises(ValidationError):BoundedMeanInformation.model_validate(data)

    def test_proof_checks_survive_python_optimization(self):
        script='''from examples.bounded_policy_fixture import model
from cfm_id.bounded_policy_solver import solve
from cfm_id.bounded_policy_verify import replay
from cfm_id_bridge.scientific_binding import sha
q,info=model();c=solve(q,info);valid=replay(c,inquiry=q,information=info)
c['lower']='0';c.pop('certificate_sha256');c['certificate_sha256']=sha(c)
print(valid,replay(c,inquiry=q,information=info))'''
        run=subprocess.run([sys.executable,'-B','-O','-c',script],capture_output=True,text=True,check=True)
        self.assertEqual(run.stdout.strip(),'True False')


class BoundedEntryTests(unittest.TestCase):
    def setUp(self):
        self.b=public_bundle();self.raw=reference();self.options=reviews()

    def call(self,options=None,raw=None):
        return entry.submit(self.b,self.raw if raw is None else raw,**(self.options if options is None else options))

    def test_mock_reading_to_reviewed_partial_preserves_original_core_outcome(self):
        provider=Mock();provider.generate_json.return_value=self.raw
        preview=read_once(self.b,provider,'FIXED_POLICY',contract=CONTRACT)
        self.assertEqual(preview['state'],'REVIEW_REQUIRED');self.assertFalse(preview['core_called'])
        provider.generate_json.assert_called_once()
        original=deepcopy(self.raw);out=self.call()
        self.assertEqual(out['state'],'PARTIAL');self.assertTrue(out['bounded_certificate_replayed'])
        self.assertEqual(self.raw,original);self.assertEqual(out['reading_candidate'],original)
        self.assertEqual(out['point_assessment']['state'],'UNSUPPORTED')
        self.assertEqual(out['point_assessment']['query_views'][0]['reason_code'],'ZERO_POLICY_SIGNATURE_SUPPORT')
        self.assertEqual(out['identification']['results'][0]['status'],'PARTIAL')
        self.assertEqual(out['point_assessment']['identification']['results'][0]['status'],'UNSUPPORTED')
        self.assertTrue(out['core_called']);self.assertFalse(out['estimation_called']);self.assertFalse(out['policy_called'])
        self.assertFalse(out['production_admission']);self.assertFalse(out['estimation_handoff_allowed'])

    def test_three_business_cases_full_chain(self):
        for name,state in [('star7','PARTIAL'),('chain4','PARTIAL'),('star5','POINT')]:
            with self.subTest(name=name):
                out=entry.submit(public_bundle(name),reference(name),**reviews(name))
                self.assertEqual(out['state'],state);self.assertTrue(out['bounded_certificate_replayed'])

    def test_original_entry_does_not_auto_fallback(self):
        opts={k:v for k,v in self.options.items() if k not in ('query_id','information','bounded_review')}
        out=point_submit(self.b,self.raw,'FIXED_POLICY',contract=CONTRACT,**opts)
        self.assertEqual(out['state'],'UNSUPPORTED');self.assertNotIn('bounded_result',out)

    def test_no_science_or_bound_reference_leaks_into_reading_prompt(self):
        prompt=prepare_request(self.b,'FIXED_POLICY',contract=CONTRACT)
        text=prompt['system']+prompt['user']
        for term in ('EXACT_SYNTHETIC_MEANS','FINITE_SIGNATURE_MEAN_BOX','3/7','reviewed_scientific_bounds'):
            self.assertNotIn(term,text)

    def test_missing_reviews_or_information_cannot_call_new_backend(self):
        for key in ('packet','context','information','bounded_review','submission_review','assignment_review','synthetic_protocol_selected'):
            opts=dict(self.options);opts[key]=False if key=='synthetic_protocol_selected' else None
            with self.subTest(key=key),patch.object(entry,'solve',side_effect=AssertionError('backend called')):
                out=self.call(opts);self.assertFalse(out['bounded_backend_called']);self.assertFalse(out['core_called'])
                self.assertNotIn('bounded_result',out)
        for invalid in (1,'true'):
            opts=dict(self.options,synthetic_protocol_selected=invalid)
            out=self.call(opts);self.assertFalse(out['core_called']);self.assertFalse(out['bounded_backend_called'])

    def test_missing_policy_population_or_design_remains_blocked(self):
        for kind in ('policy','population','quota','uniform','conflict'):
            raw=deepcopy(self.raw)
            if kind=='policy':raw['reading']['questions']['q1']['first']['H']=None
            elif kind=='population':raw['reading']['questions']['q1']['population']=None
            elif kind=='quota':raw['reported_assignment']['fixed_count']=None
            elif kind=='uniform':raw['reported_assignment']['uniform_subset_declared']=None
            else:raw['reported_assignment']['reported_conflict']=True
            out=self.call(raw=raw)
            self.assertEqual(out['state'],'NEEDS_INPUT');self.assertFalse(out['bounded_backend_called'])

    def test_review_cannot_be_model_dictionary_or_stale_record(self):
        for kind in ('dict','reading','source','bound'):
            opts=dict(self.options);raw=deepcopy(self.raw)
            if kind=='dict':opts['bounded_review']=opts['bounded_review'].model_dump()
            elif kind=='reading':raw['reading']['questions']['q1']['first']['H']=0
            elif kind=='source':opts['information']=opts['information'].model_copy(update={'source_sha256':'0'*64})
            else:opts['information']=opts['information'].model_copy(update={'bounds_provenance':'Changed scientific statement'})
            out=self.call(opts,raw);self.assertEqual(out['state'],'CHECK_BLOCKED');self.assertFalse(out['bounded_backend_called'])

    def test_new_outer_hash_does_not_bypass_existing_review(self):
        raw=deepcopy(self.raw);raw['reading']['questions']['q1']['population']=['H']
        opts=dict(self.options)
        opts['bounded_review']=opts['bounded_review'].model_copy(update=entry.worksheet(self.b,raw,query_id='q1',
            packet=opts['packet'],context=opts['context'],information=opts['information']))
        out=self.call(opts,raw)
        self.assertEqual(out['state'],'CHECK_BLOCKED');self.assertFalse(out['bounded_backend_called'])

    def test_outer_review_is_explicit_and_not_a_signature(self):
        sheet=entry.worksheet(self.b,self.raw,query_id='q1',packet=self.options['packet'],
            context=self.options['context'],information=self.options['information'])
        self.assertNotIn('reviewer',sheet)
        with self.assertRaises(ValidationError):ReviewedBoundedPolicy(**sheet)
        data=self.options['bounded_review'].model_dump()
        for key in ('reviewed_complete_a4_information','reviewed_scientific_bounds_and_scope',
                    'reviewed_no_additional_coupling_constraints','synthetic_fixture'):
            for value in (False,1,'true'):
                with self.assertRaises(ValidationError):ReviewedBoundedPolicy.model_validate(dict(data,**{key:value}))

    def test_independent_replay_failure_never_publishes_interval(self):
        with patch.object(entry,'replay',return_value=False):out=self.call()
        self.assertEqual(out['state'],'CHECK_BLOCKED');self.assertFalse(out['bounded_certificate_replayed'])
        self.assertNotIn('bounded_result',out)


if __name__=='__main__':unittest.main()
