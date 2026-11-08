"""Graphical, scientific-gate and exact-population acceptance; no live LLM."""
import unittest
from copy import deepcopy
from fractions import Fraction as F
from itertools import combinations,product
from unittest.mock import patch
from cfm_id_bridge.scientific_binding import sha
from cfm_id.dag_backdoor_contract import BackdoorProblem,DECISIONS
from cfm_id.dag_backdoor import prepare,submit
from cfm_id.dag_backdoor_solver import solve,moral_separation
from cfm_id.dag_backdoor_verify import replay,active_paths
from examples.dag_backdoor_reference import make_problem,synthetic_review,cases


def changed(p,**updates):
    d=p.model_dump();d.update(updates);return BackdoorProblem.model_validate(d)


def rehash(c):
    c=deepcopy(c);c.pop('certificate_sha256',None);c['certificate_sha256']=sha(c);return c


class BackdoorTests(unittest.TestCase):
    def run_case(self,p,review='fixture'):
        return submit(p,review=synthetic_review(p) if review=='fixture' else review,research_protocol_selected=True)

    def test_frozen_reference_cases(self):
        for name,p,state,answer in cases():
            with self.subTest(name=name):
                result=self.run_case(p);self.assertEqual(result['state'],state)
                self.assertFalse(result['production_admission']);self.assertFalse(result['estimation_handoff_allowed'])
                if state=='POINT':
                    c=result['certificate'];self.assertEqual(c['adjustment'],answer)
                    self.assertTrue(replay(c,problem=p));self.assertIsNone(c['numeric_value'])
                else:
                    self.assertEqual(result['reason_code'],answer);self.assertNotIn('certificate',result)

    def test_prepare_and_no_review_never_solve(self):
        p=make_problem()
        with patch('cfm_id.dag_backdoor.solve',side_effect=AssertionError('solver called')):
            self.assertEqual(prepare(p)['state'],'REVIEW_REQUIRED')
            self.assertFalse(prepare(p)['worksheet']['is_approval'])
            self.assertEqual(self.run_case(p,None)['state'],'REVIEW_REQUIRED')
            self.assertEqual(submit(p,review=synthetic_review(p))['state'],'REVIEW_REQUIRED')
            self.assertEqual(submit(p,review=synthetic_review(p),research_protocol_selected=1)['state'],'REVIEW_REQUIRED')

    def test_pending_rejected_stale_and_missing_decisions(self):
        p=make_problem();r=synthetic_review(p)
        variants=[(r.model_copy(update={'decisions':{**r.decisions,DECISIONS[0]:'PENDING'}}),'REVIEW_REQUIRED'),
                  (r.model_copy(update={'decisions':{**r.decisions,DECISIONS[1]:'REJECTED'}}),'CHECK_BLOCKED'),
                  (r.model_copy(update={'problem_sha256':'0'*64}),'CHECK_BLOCKED'),
                  (r.model_copy(update={'decisions':{}}),'CHECK_BLOCKED')]
        with patch('cfm_id.dag_backdoor.solve',side_effect=AssertionError('solver called')):
            for review,state in variants:self.assertEqual(self.run_case(p,review)['state'],state)

    def test_bad_graph_and_information_stop(self):
        p=make_problem()
        variants=[(changed(p,edges=p.edges+[['Y','Z']]),'DIRECTED_CYCLE'),
                  (changed(p,edges=p.edges+[['Z','X']]),'INVALID_DIRECTED_EDGE'),
                  (changed(p,graph_status='UNKNOWN'),'CAUSAL_GRAPH_NOT_DECLARED'),
                  (changed(p,additional_restrictions=['unmodeled selection']),'ADDITIONAL_MODEL_RESTRICTIONS_NOT_ADAPTED')]
        for key,value,reason in [('availability','FINITE_SAMPLE','FULL_SYMBOLIC_POPULATION_LAW_REQUIRED'),
                                 ('strictly_positive_joint',None,'POPULATION_POSITIVITY_UNDECLARED'),
                                 ('strictly_positive_joint',False,'NONPOSITIVE_LAW_NOT_ADAPTED'),
                                 ('variables',['X','Y'],'COMPLETE_OBSERVED_JOINT_LAW_REQUIRED')]:
            variants.append((changed(p,information={**p.information.model_dump(),key:value}),reason))
        for problem,reason in variants:
            result=self.run_case(problem);self.assertEqual(result['reason_code'],reason);self.assertFalse(result['backend_called'])

    def test_latent_cannot_be_adjusted_and_budget_is_not_nonid(self):
        p=make_problem(['U','X','Y'],[['U','X'],['U','Y']],['U'],['U'])
        self.assertEqual(prepare(p)['reason_code'],'OBSERVED_DISJOINT_ADJUSTMENT_REQUIRED')
        p=make_problem(['X','Y',*list('ABCDEFG')],[['X','Y']])
        self.assertEqual(prepare(p)['reason_code'],'DAG_REPLAY_RESOURCE_LIMIT')

    def test_rename_and_order_invariance(self):
        p=make_problem();mapping={'Z':'previous,ability','X':'训练甲','Y':'完成乙'}
        q=changed(p,nodes=[mapping[n] for n in reversed(p.nodes)],observed=[mapping[n] for n in reversed(p.observed)],
            edges=[[mapping[a],mapping[b]] for a,b in reversed(p.edges)],treatment=mapping['X'],outcome=mapping['Y'],
            information={**p.information.model_dump(),'variables':[mapping[n] for n in p.observed]})
        self.assertEqual(self.run_case(q)['certificate']['adjustment'],[mapping['Z']])
        self.assertFalse(replay(solve(p),problem=q))

    def test_recomputed_hash_does_not_validate_false_proof(self):
        p=make_problem();c=solve(p)
        variants=[]
        for key,value in [('problem_sha256','0'*64),('information_sha256','0'*64),('adjustment',[]),
                          ('numeric_value','1/2'),('positivity','EMPIRICALLY_VERIFIED')]:
            variants.append({**c,key:value})
        a=deepcopy(c);a['functional']['conditional']['given']=['X'];variants.append(a)
        a=deepcopy(c);a['target']['outcome']='Z';variants.append(a)
        a=deepcopy(c);a['graphical_trace']['reachable_after_conditioning'].append('Y');variants.append(a)
        a=deepcopy(c);a['extra_claim']='all graphs identifiable';variants.append(a)
        for forged in variants:self.assertFalse(replay(rehash(forged),problem=p))

    def test_verifier_does_not_call_solver_helpers(self):
        p=make_problem();c=solve(p)
        with (patch('cfm_id.dag_backdoor_solver.moral_separation',side_effect=AssertionError('shared solver')),
              patch('cfm_id.dag_backdoor_solver.functional',side_effect=AssertionError('shared compiler'))):
            self.assertTrue(replay(c,problem=p))

    def test_replay_failure_is_not_published(self):
        p=make_problem()
        with patch('cfm_id.dag_backdoor.replay',return_value=False):
            r=self.run_case(p);self.assertEqual(r['state'],'CHECK_BLOCKED');self.assertNotIn('certificate',r)

    def test_all_four_node_topological_graphs_separation(self):
        nodes=list('ABCD');possible=list(combinations(nodes,2));count=0
        for bits in product((0,1),repeat=len(possible)):
            edges=[e for e,b in zip(possible,bits) if b]
            for x,y in ((x,y) for x in nodes for y in nodes if x!=y):
                others=[v for v in nodes if v not in (x,y)]
                for flags in product((0,1),repeat=len(others)):
                    z=[v for v,f in zip(others,flags) if f]
                    a,_=moral_separation(nodes,edges,x,y,z)
                    self.assertEqual(a,not active_paths(nodes,edges,x,y,z));count+=1
        self.assertEqual(count,3072)

    def test_exact_scm_interventions_agree_with_adjustment(self):
        # Independent population enumeration from binary structural kernels.
        # Truth is formed by intervention, never from the solver's expression.
        nodes=list('ABCD');possible=list(combinations(nodes,2));count=0
        def enumerate_law(edges,forced=None):
            rows=[]
            for vals in product((0,1),repeat=4):
                row=dict(zip(nodes,vals));mass=F(1)
                for i,n in enumerate(nodes):
                    if forced and n==forced[0]:
                        if row[n]!=forced[1]:mass=F(0);break
                        continue
                    parents=[a for a,b in edges if b==n]
                    prob=F(1+(i+sum((j+1)*row[a] for j,a in enumerate(parents)))%4,5)
                    mass*=prob if row[n] else 1-prob
                rows.append((row,mass))
            return rows
        template=make_problem().model_dump()
        for bits in product((0,1),repeat=6):
            edges=[list(e) for e,b in zip(possible,bits) if b];joint=enumerate_law(edges)
            for x,y in [('A','D'),('B','D'),('D','A')]:
                for latent in [[],['C']]:
                    observed=[n for n in nodes if n not in latent]
                    p=BackdoorProblem.model_validate({**template,'nodes':nodes,'observed':observed,'latent':latent,
                        'edges':edges,'treatment':x,'outcome':y,'information':{**template['information'],'variables':observed}})
                    r=self.run_case(p)
                    if r['state']!='POINT':continue
                    z=r['certificate']['adjustment']
                    for xv in (0,1):
                        truth=sum(m for row,m in enumerate_law(edges,(x,xv)) if row[y]==1)
                        estimate=F(0)
                        for zv in product((0,1),repeat=len(z)):
                            same=lambda row:all(row[n]==v for n,v in zip(z,zv))
                            pz=sum(m for row,m in joint if same(row))
                            den=sum(m for row,m in joint if same(row) and row[x]==xv)
                            num=sum(m for row,m in joint if same(row) and row[x]==xv and row[y]==1)
                            estimate+=pz*num/den
                        self.assertEqual(estimate,truth);count+=1
        self.assertGreater(count,400)


if __name__=='__main__':unittest.main()
