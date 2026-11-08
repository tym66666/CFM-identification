"""Rehashed hostile evidence; feasible endpoints alone are not a proof."""
from copy import deepcopy
from fractions import Fraction as F
import subprocess
import sys
import unittest
from unittest.mock import patch
from cfm_id_bridge.scientific_binding import sha
from cfm_id.mean_order_contract import MeanOrderProblem, input_digest
from cfm_id.mean_order_solver import solve
from cfm_id.mean_order_verify import replay
from examples.mean_order_fixture import make_problem


def rehash(c):
    c.pop('certificate_sha256',None); c['certificate_sha256']=sha(c)
    return c


class MeanOrderReplayTests(unittest.TestCase):
    def setUp(self):
        self.p=make_problem(); self.c=solve(self.p)
        self.assertTrue(replay(self.c,problem=self.p))

    def rejects(self,c,p=None):
        self.assertFalse(replay(rehash(c),problem=self.p if p is None else p))

    def test_verifier_independent_of_all_producer_primitives(self):
        with patch('cfm_id.mean_order_solver.solve',side_effect=AssertionError('solver')), \
             patch('cfm_id.mean_order_solver.analyze',side_effect=AssertionError('preflight')), \
             patch('cfm_id.mean_order_solver._compile',side_effect=AssertionError('compiler')), \
             patch('cfm_id.mean_order_solver._linear',side_effect=AssertionError('linear')), \
             patch('cfm_id.mean_order_solver._dual',side_effect=AssertionError('dual')), \
             patch('cfm_id.mean_order_solver._incompatibility',side_effect=AssertionError('farkas')):
            self.assertTrue(replay(self.c,problem=self.p))

    def test_rehashed_scalar_scope_status_and_admission_forgery(self):
        fields=dict(version='old',theorem='UNKNOWN',input_sha256='0'*64,model_scope='MEAN_BOX',
            status='POINT',lower='0',upper='2',width='0',sharp=False,scientific_approval=True,
            production_admission=True,estimation_handoff_allowed=True,unexpected='extra',
            informative_relative_to_bounds_only=1,baseline_bounds_only_range=['-2','2'],
            realization='INDEPENDENT_UNIFORM_FOR_EACH_SIGNATURE')
        for k,v in fields.items():
            with self.subTest(field=k):
                c=deepcopy(self.c); c[k]=v; self.rejects(c)

    def test_dual_missing_negative_noncanonical_unknown_or_wrong_sign(self):
        for field in ('lower_dual','upper_dual'):
            for value in ({}, {'unknown-row':'1'}, {next(iter(self.c[field])):'-1'},
                          {next(iter(self.c[field])):'0.25'}, {next(iter(self.c[field])):'0'}):
                with self.subTest(field=field,value=value):
                    c=deepcopy(self.c); c[field]=value; self.rejects(c)
        c=deepcopy(self.c); c['lower_dual']=deepcopy(c['upper_dual']); self.rejects(c)

    def test_feasible_inner_world_is_not_a_sharp_lower_bound(self):
        c=deepcopy(self.c)
        for row in c['cells']:
            row['lower_world']=str((F(row['lower_world'])+F(row['upper_world']))/2)
        c['lower']='3/5'; c['width']='2/5'
        # All A4, bounds and orders hold, objective is 3/5; optimality fails.
        self.rejects(c)

    def test_feasible_nonmaximal_upper_world_is_rejected(self):
        c=deepcopy(self.c)
        for row in c['cells']:
            row['upper_world']=str((F(row['lower_world'])+F(row['upper_world']))/2)
        c['upper']='3/5'; c['width']='2/5'
        self.rejects(c)

    def test_missing_duplicate_or_noncanonical_cells(self):
        edits=[lambda c:c['cells'].pop(),lambda c:c['cells'].append(deepcopy(c['cells'][0])),
            lambda c:c['cells'][0]['cell'].__setitem__(1,True),lambda c:c['cells'][0].update(support='1/2'),
            lambda c:c['cells'][0].update(lower_world='NaN'),lambda c:c['cells'][0].update(upper_world=1),
            lambda c:c['cells'][0].update(extra=0),lambda c:c['cells'][0].update(cell=tuple(c['cells'][0]['cell']))]
        for i,edit in enumerate(edits):
            with self.subTest(edit=i):
                c=deepcopy(self.c); edit(c); self.rejects(c)

    def test_changed_order_input_and_recomputed_hash_cannot_reuse_old_dual(self):
        p=MeanOrderProblem.model_validate(self.p.model_dump()|{'node_orders':[dict(node=n,mode='OWN') for n in self.p.node_order]})
        c=deepcopy(self.c); c['input_sha256']=input_digest(p); self.rejects(c,p)

    def test_changed_direction_and_recomputed_input_hash_rejected(self):
        p=MeanOrderProblem.model_validate(self.p.model_dump()|{'first':self.p.second,'second':self.p.first})
        c=deepcopy(self.c); c['input_sha256']=input_digest(p); self.rejects(c,p)

    def test_changed_a4_and_recomputed_input_hash_rejected(self):
        d=self.p.model_dump(); d['values'][0]['value']='1/2'; p=MeanOrderProblem.model_validate(d)
        c=deepcopy(self.c); c['input_sha256']=input_digest(p); self.rejects(c,p)

    def test_zero_weight_a4_cannot_be_discarded(self):
        p=make_problem(weights=['1','0','0','0']); c=solve(p)
        for row in c['cells']:
            if row['cell']==['D',1,0]: row['lower_world']='1'
        self.rejects(c,p)

    def test_alternative_valid_worlds_are_accepted_not_byte_compared(self):
        p=make_problem(first=[1]*4,second=[1]*4); c=solve(p)
        for r in c['cells']:
            if r['cell'][1:]==[1,1]: r['upper_world']='1'
        self.assertTrue(replay(rehash(c),problem=p))
        self.assertEqual(c['upper_dual'],{})

    def test_constraint_ids_are_semantic_and_handle_unusual_node_names(self):
        p=make_problem(nodes=['A:[]','B"','中文'],edges=[['A:[]','B"']],quota=1)
        c=solve(p); self.assertTrue(replay(c,problem=p))
        p2=MeanOrderProblem.model_validate(p.model_dump()|{'bounds':list(reversed(p.model_dump()['bounds']))})
        c['input_sha256']=input_digest(p2)
        self.assertTrue(replay(rehash(c),problem=p2))

    def test_farkas_certificate_tampering_and_fake_incompatibility(self):
        data=self.p.model_dump(); data['values'][0]['value']='-1/10'; p=MeanOrderProblem.model_validate(data)
        c=solve(p); self.assertTrue(replay(c,problem=p))
        for proof in ({},{next(iter(c['farkas'])):'1'}, {k:'-1' for k in c['farkas']},{'unknown':'1'}):
            bad=deepcopy(c); bad['farkas']=proof; self.rejects(bad,p)
        bad=deepcopy(c); bad['input_sha256']=input_digest(self.p); self.rejects(bad)

    def test_optimized_python_cannot_disable_validation(self):
        code='''from examples.mean_order_fixture import make_problem
from cfm_id.mean_order_solver import solve
from cfm_id.mean_order_verify import replay
from cfm_id_bridge.scientific_binding import sha
p=make_problem(); c=solve(p); valid=replay(c,problem=p)
c['lower_dual']={}; c.pop('certificate_sha256'); c['certificate_sha256']=sha(c)
print(valid,replay(c,problem=p))'''
        run=subprocess.run([sys.executable,'-B','-O','-c',code],check=True,capture_output=True,text=True)
        self.assertEqual(run.stdout.strip(),'True False')


if __name__=='__main__': unittest.main()
