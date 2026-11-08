"""Generic bounded-policy contract construction and unchanged admission chain."""
from copy import deepcopy
from dataclasses import replace
from fractions import Fraction as F
from itertools import product
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from pydantic import ValidationError
from cfm_id import bounded_policy_intake as intake
from cfm_id.bounded_policy_contract import BoundedPolicyUnavailable
from cfm_id.bounded_policy_solver import solve
from cfm_id.bounded_policy_verify import replay
from cfm_id.business_entry import prepare_request
from cfm_id.question_bound_assignment import question_catalog, CONTRACT
from cfm_id_bridge.scientific_binding import sha
from examples.bounded_policy_intake_fixture import make_case, declaration_review, existing_reviews


def compiled(case):
    b,raw,d,_,expected=case
    record=declaration_review(b,raw,d,expected)
    value=intake.compile_reviewed(b,raw,query_id='q1',declaration=d,review=record,synthetic_protocol_selected=True)
    return value,record


def vertex_oracle(declaration, coordinates):
    """Independent finite box corners; no producer, validator or support helper."""
    s,info=declaration['study'],declaration['information'];nodes=s['node_order'];n=len(nodes)
    index={node:i for i,node in enumerate(nodes)}
    adjacent=[[] for _ in nodes]
    for a,b in s['undirected_edges']:
        adjacent[index[a]].append(index[b]);adjacent[index[b]].append(index[a])
    def coord(i,z):return nodes[i],z[i],int(sum(z[j] for j in adjacent[i])*2>len(adjacent[i]))
    support=[z for z in product((0,1),repeat=n) if sum(z)==s['fixed_count']]
    supported={coord(i,z) for z in support for i in range(n)}
    known={(v['node'],v['own'],v['exposure']):F(v['value']) for v in info['values']}
    if not set(known)<=supported:raise ValueError('UNDEFINED_CONDITIONAL_MEAN')
    bounds={v['node']:(F(v['lower']),F(v['upper'])) for v in info['bounds']}
    if s['outcome_kind']=='binary':
        if info['bounds_kind']=='ALMOST_SURE_OUTCOME':
            possible={k:[F(x) for x in (0,1) if a<=x<=b] for k,(a,b) in bounds.items()}
            if any(not x for x in possible.values()):raise ValueError('EMPTY_BINARY_RANGE')
            bounds={k:(min(v),max(v)) for k,v in possible.items()}
        else:bounds={k:(max(a,F(0)),min(b,F(1))) for k,(a,b) in bounds.items()}
    if any(not bounds[c[0]][0]<=v<=bounds[c[0]][1] for c,v in known.items()):raise ValueError('INFEASIBLE_A4')
    corners=[]
    for i,node in enumerate(nodes):
        c=coord(i,coordinates['assignment']);weight=F(coordinates['unit_weights'][i])
        if weight>0 and c in supported and c not in known:raise ValueError('MISSING_SUPPORTED_TARGET_MEAN')
        corners.append((known[c],) if c in known else bounds[node])
    candidates=[sum((F(w)*v for w,v in zip(coordinates['unit_weights'],row)),F(0)) for row in product(*corners)]
    return min(candidates),max(candidates)


class IntakeTests(unittest.TestCase):
    def setUp(self):
        self.case=make_case(list('ABCD'),[('A','B'),('B','C'),('C','D')],2,[1]*4,list('ABCD'))
        self.b,self.raw,self.d,self.claims,self.expected=self.case

    def prepare(self,d=None,raw=None):
        return intake.prepare(self.b,self.raw if raw is None else raw,query_id='q1',declaration=self.d if d is None else d)

    def test_preparation_is_unapproved_and_does_not_solve(self):
        with patch.object(intake,'compile_reviewed',side_effect=AssertionError('compile called')),\
             patch('cfm_id.bounded_policy_solver.solve',side_effect=AssertionError('solver called')):
            view=self.prepare()
        self.assertEqual(view['state'],'REVIEW_REQUIRED')
        self.assertEqual(view['proposed_target'],self.expected)
        self.assertFalse(view['scientific_approval']);self.assertFalse(view['core_called'])
        self.assertFalse(any(k.startswith('reviewed_') for k in view['worksheet']))
        self.assertNotIn('condition_decisions',view['worksheet'])
        with self.assertRaises(ValidationError):intake.ReviewedBoundedDeclaration(**view['worksheet'])

    def test_public_prompt_does_not_receive_science_or_approval(self):
        request=prepare_request(self.b,'FIXED_POLICY',contract=CONTRACT)
        before=json.dumps(request,ensure_ascii=False)
        self.prepare()
        self.assertEqual(prepare_request(self.b,'FIXED_POLICY',contract=CONTRACT),request)
        for private in ('EXACT_SYNTHETIC_POPULATION','condition_decisions','Independent hypothetical protocol'):
            self.assertNotIn(private,before)

    def test_no_review_and_no_opt_in_cannot_compile(self):
        record=declaration_review(self.b,self.raw,self.d,self.expected)
        for kwargs in ({},{'review':record},{'synthetic_protocol_selected':True}):
            with self.subTest(kwargs=list(kwargs)),self.assertRaises(BoundedPolicyUnavailable):
                intake.compile_reviewed(self.b,self.raw,query_id='q1',declaration=self.d,**kwargs)

    def test_compile_keeps_actual_coordinates_and_has_no_identification_result(self):
        c,r=compiled(self.case)
        self.assertEqual(c.inquiry.target.policy_assignment,tuple(self.expected['assignment']))
        self.assertEqual(c.inquiry.target.unit_weights,tuple(self.expected['unit_weights']))
        self.assertFalse(c.review_receipt['identification_completed'])
        self.assertFalse(c.review_receipt['production_admission'])
        self.assertNotIn('lower',c.review_receipt)
        self.assertEqual(set(c.inquiry.r2_sufficiency.covered_nodes),set(self.b['node_order']))

    def test_missing_population_or_policy_is_not_filled_from_scientific_materials(self):
        for change in ('population','policy','aggregation'):
            raw=deepcopy(self.raw)
            if change=='population':raw['reading']['questions']['q1']['population']=None
            if change=='policy':raw['reading']['questions']['q1']['first']['A']=None
            if change=='aggregation':raw['reading']['questions']['q1']['aggregation']='不明确'
            before=deepcopy(raw);view=self.prepare(raw=raw)
            self.assertEqual(view['state'],'NEEDS_INPUT');self.assertEqual(raw,before)

    def test_wrong_complete_reading_requires_reviewer_not_gold_replacement(self):
        raw=deepcopy(self.raw);raw['reading']['questions']['q1']['first']['A']=0
        self.assertEqual(self.prepare(raw=raw)['state'],'REVIEW_REQUIRED')
        with self.assertRaises(ValueError):declaration_review(self.b,raw,self.d,self.expected)
        self.assertEqual(raw['reading']['questions']['q1']['first']['A'],0)

    def test_missing_or_extra_conditions_and_scope_are_blocked(self):
        for name in intake.CONDITION_NAMES:
            d=deepcopy(self.d);d['conditions']=[c for c in d['conditions'] if c['name']!=name]
            self.assertEqual(self.prepare(d)['state'],'NEEDS_INPUT')
        d=deepcopy(self.d);d['conditions'][0]['scope']='OBSERVED_ASSIGNMENTS_ONLY'
        self.assertEqual(self.prepare(d)['state'],'NEEDS_INPUT')
        d=deepcopy(self.d);d['conditions'].append(dict(name='monotonicity',scope='STUDY_CONTEXT',statement='额外单调性条件',evidence='单独科学信息来源'))
        self.assertEqual(self.prepare(d)['state'],'UNSUPPORTED')
        d=deepcopy(self.d);d['additional_constraints']=['全体总均值另有一条线性等式限制']
        self.assertEqual(self.prepare(d)['state'],'UNSUPPORTED')
        d=deepcopy(self.d);d['conditions'].append(deepcopy(d['conditions'][0]))
        self.assertEqual(self.prepare(d)['state'],'CHECK_BLOCKED')

    def test_pending_rejected_and_incomplete_decisions_never_grant_a5(self):
        _,r=compiled(self.case)
        for decision in ('PENDING','REJECTED',None):
            decisions=dict(r.condition_decisions)
            if decision is None:decisions.pop('mean_signature_sufficiency')
            else:decisions['mean_signature_sufficiency']=decision
            record=r.model_copy(update={'condition_decisions':decisions})
            with self.assertRaises(BoundedPolicyUnavailable):
                intake.compile_reviewed(self.b,self.raw,query_id='q1',declaration=self.d,review=record,synthetic_protocol_selected=True)

    def test_boolean_review_not_integer_or_mutated_construct(self):
        _,r=compiled(self.case)
        data=r.model_dump();data['reviewed_business_target']=1
        with self.assertRaises(ValidationError):intake.ReviewedBoundedDeclaration.model_validate(data)
        record=r.model_copy(update={'reviewed_exact_a4_information':False})
        with self.assertRaises(ValidationError):
            intake.compile_reviewed(self.b,self.raw,query_id='q1',declaration=self.d,review=record,synthetic_protocol_selected=True)

    def test_stale_review_binds_full_raw_bundle_and_declarations(self):
        _,r=compiled(self.case)
        variants=[]
        b=deepcopy(self.b);b['case_id']='changed';variants.append((b,self.raw,self.d))
        raw=deepcopy(self.raw);raw['reading']['questions']['q1']['population']=['A'];variants.append((self.b,raw,self.d))
        for field in ('a4_provenance','bounds_provenance','outcome_period'):
            d=deepcopy(self.d);d['information'][field]+=' revised';variants.append((self.b,self.raw,d))
        d=deepcopy(self.d);d['study']['undirected_edges']=[['A','D']];variants.append((self.b,self.raw,d))
        for b,raw,d in variants:
            with self.subTest(d=sha(d)),self.assertRaises(BoundedPolicyUnavailable):
                intake.compile_reviewed(b,raw,query_id='q1',declaration=d,review=r,synthetic_protocol_selected=True)

    def test_sample_full_law_and_wrong_bounds_scope_are_not_coerced(self):
        for field,value,state in [('availability','FINITE_SAMPLE_ESTIMATE','NEEDS_INPUT'),
            ('availability','SYMBOLIC_POPULATION_OPERATOR','NEEDS_INPUT'),('operator','FULL_JOINT_LAW','UNSUPPORTED'),
            ('information_scope','FULL_LAW','UNSUPPORTED'),('model_scope','MEANS_AND_MONOTONICITY','UNSUPPORTED'),
            ('bounds_scope','OBSERVED_ONLY','NEEDS_INPUT')]:
            d=deepcopy(self.d);d['information'][field]=value
            self.assertEqual(self.prepare(d)['state'],state)

    def test_invalid_graph_roster_quota_exposure_and_resource_limit(self):
        changes=[('undirected_edges',[['A','A']],'CHECK_BLOCKED'),('undirected_edges',[['A','B'],['B','A']],'CHECK_BLOCKED'),
            ('undirected_edges',[['A','Z']],'CHECK_BLOCKED'),('node_order',list('ABCE'),'CHECK_BLOCKED'),
            ('fixed_count',3,'CHECK_BLOCKED'),('fixed_count',True,'CHECK_BLOCKED'),
            ('design','bernoulli','UNSUPPORTED'),('grouping','any_treated_neighbor','UNSUPPORTED'),
            ('graph_timing','UNRESOLVED','NEEDS_INPUT')]
        for field,value,state in changes:
            d=deepcopy(self.d);d['study'][field]=value
            self.assertEqual(self.prepare(d)['state'],state)
        with patch.object(intake,'MAX_N',3):self.assertEqual(self.prepare()['state'],'UNSUPPORTED')

    def test_missing_bounds_duplicate_and_unknown_a4_cells(self):
        d=deepcopy(self.d);d['information']['bounds'].pop()
        self.assertEqual(self.prepare(d)['state'],'NEEDS_INPUT')
        d=deepcopy(self.d);d['information']['values'].append(deepcopy(d['information']['values'][0]))
        self.assertEqual(self.prepare(d)['state'],'NEEDS_INPUT')
        d=deepcopy(self.d);d['information']['values'][0]['node']='unknown'
        self.assertEqual(self.prepare(d)['state'],'NEEDS_INPUT')

    def test_numeric_values_remain_exact_and_binary_bounds_keep_mean_distinction(self):
        for value in (0.25,True,'2/4','nan','inf','1/0'):
            d=deepcopy(self.d);d['information']['values'][0]['value']=value
            self.assertEqual(self.prepare(d)['state'],'CHECK_BLOCKED')
        d=deepcopy(self.d);d['information']['bounds'][0].update(lower='1/4',upper='3/4')
        r=declaration_review(self.b,self.raw,d,self.expected)
        with self.assertRaises(BoundedPolicyUnavailable) as cm:
            intake.compile_reviewed(self.b,self.raw,query_id='q1',declaration=d,review=r,synthetic_protocol_selected=True)
        self.assertEqual(cm.exception.state,'INCOMPATIBLE')

    def test_supported_target_missing_mean_and_zero_mass_a4_remain_failures(self):
        for kind in ('missing','impossible'):
            d=deepcopy(self.d)
            if kind=='missing':d['information']['values']=[v for v in d['information']['values'] if (v['node'],v['own'],v['exposure'])!=('A',1,1)]
            else:d['information']['values'].append(dict(node='B',own=1,exposure=1,value='1/2'))
            c,r=compiled((self.b,self.raw,d,self.claims,self.expected))
            with self.assertRaises(BoundedPolicyUnavailable) as cm:solve(c.inquiry,c.information)
            self.assertEqual(cm.exception.state,'NEEDS_INPUT' if kind=='missing' else 'INCOMPATIBLE')

    def test_same_backend_varied_graphs_targets_populations_against_vertices(self):
        nodes=list('甲乙丙丁');graphs=[[],[('甲','乙'),('丙','丁')],[(nodes[0],n) for n in nodes[1:]],
            [(nodes[i],nodes[j]) for i in range(4) for j in range(i+1,4)]]
        for g,edges in enumerate(graphs):
            for quota in (0,2,4):
                for pop in (nodes,nodes[1:],nodes[:1]):
                    case=make_case(nodes,edges,quota,[1,0,1,1],pop,continuous=bool(g%2),serial=g)
                    with self.subTest(graph=g,quota=quota,pop=pop):
                        c,_=compiled(case);cert=solve(c.inquiry,c.information)
                        self.assertEqual((F(cert['lower']),F(cert['upper'])),vertex_oracle(case[2],case[4]))
                        self.assertTrue(replay(cert,inquiry=c.inquiry,information=c.information))

    def test_tighter_feasible_scientific_bounds_do_not_widen_interval(self):
        c,_=compiled(self.case);base=solve(c.inquiry,c.information)
        d=deepcopy(self.d);d['information']['bounds_kind']='CONDITIONAL_MEAN'
        for b in d['information']['bounds']:b.update(lower='1/6',upper='5/6')
        c,_=compiled((self.b,self.raw,d,self.claims,self.expected));tight=solve(c.inquiry,c.information)
        self.assertGreaterEqual(F(tight['lower']),F(base['lower']))
        self.assertLessEqual(F(tight['upper']),F(base['upper']))
        self.assertTrue(replay(tight,inquiry=c.inquiry,information=c.information))

    def test_names_order_and_row_order_do_not_change_mathematics(self):
        c,_=compiled(self.case);cert=solve(c.inquiry,c.information)
        b,raw,d=deepcopy(self.b),deepcopy(self.raw),deepcopy(self.d)
        names={n:'公司组-'+str(i) for i,n in enumerate(reversed(self.b['node_order']))}
        b['node_order']=[names[n] for n in reversed(b['node_order'])]
        for key,text in b['documents'].items():
            for a,v in names.items():text=text.replace(a,v)
            b['documents'][key]=text
        b['question_slots']['q1']=b['documents']['goal.txt']
        raw['reading']['intents']['q1']['question_id']=question_catalog(b)['q1']['question_id']
        q=raw['reading']['questions']['q1'];q['first']={names[k]:v for k,v in q['first'].items()};q['population']=[names[n] for n in q['population']]
        from cfm_id.source_locations import build_catalog
        catalog=build_catalog(b['documents'])
        raw['reported_assignment']['source_ids']=[s for s,v in catalog.items() if '所有同人数名单等概率' in v['text']]
        d['study']['node_order']=b['node_order'];d['study']['undirected_edges']=[[names[a],names[v]] for a,v in d['study']['undirected_edges']]
        for field in ('bounds','values'):
            for row in d['information'][field]:row['node']=names[row['node']]
            d['information'][field].reverse()
        expected=dict(classification='FIXED_POLICY',node_order=b['node_order'],assignment=[1]*4,unit_weights=['1/4']*4)
        c,_=compiled((b,raw,d,self.claims,expected));other=solve(c.inquiry,c.information)
        self.assertEqual((cert['lower'],cert['upper']),(other['lower'],other['upper']))
        self.assertNotEqual(cert['input_sha256'],other['input_sha256'])
        self.assertTrue(replay(other,inquiry=c.inquiry,information=c.information))

    def test_full_generic_chain_for_point_partial_and_three_populations(self):
        for pop in (list('ABCD'),list('BC'),['A']):
            case=make_case(list('ABCD'),[('A','B'),('B','C'),('C','D')],2,[1]*4,pop)
            b,raw,d,claims,expected=case;c,r=compiled(case);options=existing_reviews(b,raw,c,claims,expected)
            out=intake.submit(b,raw,query_id='q1',declaration=d,declaration_review=r,synthetic_protocol_selected=True,**options)
            self.assertEqual(out['state'],'POINT' if pop==['A'] else 'PARTIAL')
            self.assertTrue(out['bounded_certificate_replayed']);self.assertTrue(out['core_called'])
            self.assertEqual(out['reading_candidate'],raw);self.assertFalse(out['estimation_handoff_allowed'])
            self.assertTrue(replay(out['bounded_result'],inquiry=c.inquiry,information=c.information))

    def test_no_old_review_is_bypassed(self):
        c,r=compiled(self.case);options=existing_reviews(self.b,self.raw,c,self.claims,self.expected)
        for absent in ('context','packet','bounded_review','submission_review','assignment_review'):
            changed=dict(options);changed[absent]=None
            out=intake.submit(self.b,self.raw,query_id='q1',declaration=self.d,declaration_review=r,synthetic_protocol_selected=True,**changed)
            self.assertFalse(out.get('bounded_backend_called'));self.assertNotIn('bounded_result',out)

    def test_independent_context_inquiry_cannot_be_overwritten(self):
        c,r=compiled(self.case);options=existing_reviews(self.b,self.raw,c,self.claims,self.expected)
        binding=options['context'].core_port.bindings['q1']
        altered=replace(c.inquiry,target=replace(c.inquiry.target,policy_assignment=(0,)*4,target_digest=''))
        # Ordinary binding construction already rejects this mismatch. Simulate
        # stale state introduced outside the constructor to test the new gate.
        object.__setattr__(binding,'inquiry',altered)
        out=intake.submit(self.b,self.raw,query_id='q1',declaration=self.d,declaration_review=r,synthetic_protocol_selected=True,**options)
        self.assertEqual(out['state'],'CHECK_BLOCKED');self.assertFalse(out['bounded_backend_called'])
        self.assertEqual(options['context'].core_port.bindings['q1'].inquiry,altered)

    def test_replay_failure_does_not_publish_interval(self):
        c,r=compiled(self.case);options=existing_reviews(self.b,self.raw,c,self.claims,self.expected)
        with patch('cfm_id.bounded_policy.replay',return_value=False):
            out=intake.submit(self.b,self.raw,query_id='q1',declaration=self.d,declaration_review=r,synthetic_protocol_selected=True,**options)
        self.assertEqual(out['state'],'CHECK_BLOCKED');self.assertNotIn('bounded_result',out)

    def test_cli_is_offline_and_preserves_existing_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths={name:Path(tmp)/(name+'.json') for name in ('bundle','candidate','declaration','output')}
            for name,value in [('bundle',self.b),('candidate',self.raw),('declaration',self.d)]:
                paths[name].write_text(json.dumps(value,ensure_ascii=False),encoding='utf8')
            cmd=[sys.executable,'-B','-m','cfm_id.bounded_policy_intake','--query-id','q1']
            for name,path in paths.items():cmd.extend(['--'+name,str(path)])
            run=subprocess.run(cmd,capture_output=True,text=True)
            self.assertEqual(run.returncode,0,run.stderr);self.assertEqual(json.loads(run.stdout)['http_calls'],0)
            original=paths['output'].read_bytes()
            self.assertNotEqual(subprocess.run(cmd,capture_output=True).returncode,0)
            self.assertEqual(paths['output'].read_bytes(),original)


if __name__=='__main__':unittest.main()
