"""Independent replay checks for signed, jointly attained policy contrasts."""
from copy import deepcopy
from fractions import Fraction as F
import subprocess
import sys
import unittest
from unittest.mock import patch

from cfm_id_bridge.scientific_binding import sha
from cfm_id.bounded_contrast_solver import solve
from cfm_id.bounded_contrast_verify import replay
from examples.bounded_contrast_fixture import make_case
from pfn_pipeline._internal.identification.randomized_arm_family import (
    SupportEngine, ExposureSpec,
)


def rehash(cert):
    cert.pop('certificate_sha256', None)
    cert['certificate_sha256'] = sha(cert)
    return cert


def fixture(first=None, second=None, population=None):
    nodes = list('ABCD')
    return make_case(nodes, [('A', 'B'), ('B', 'C'), ('C', 'D')], 2,
                     [1] * 4 if first is None else first,
                     [0] * 4 if second is None else second,
                     nodes if population is None else population, serial=9100)


class IndependentContrastReplayTests(unittest.TestCase):
    def setUp(self):
        self.payload = fixture()
        self.inquiries = self.payload['inquiries']
        self.information = self.payload['information']
        self.cert = solve(self.inquiries, self.information)
        self.assertTrue(replay(self.cert, inquiries=self.inquiries, information=self.information))

    def check(self, cert):
        return replay(cert, inquiries=self.inquiries, information=self.information)

    def test_replay_cannot_call_producer_or_shared_numeric_primitives(self):
        with patch('cfm_id.bounded_contrast_solver.solve', side_effect=AssertionError('producer called')), \
             patch('cfm_id.bounded_contrast_solver.analyze', side_effect=AssertionError('producer coefficients called')), \
             patch.object(SupportEngine, 'evaluate', side_effect=AssertionError('support engine called')), \
             patch.object(ExposureSpec, 'classify', side_effect=AssertionError('classifier called')):
            self.assertTrue(self.check(self.cert))

    def test_rehashed_scalar_and_scope_forgery_rejected(self):
        mutations = dict(
            version='bounded-policy-mean-1', theorem='FINITE_SIGNATURE_MEAN_BOX',
            input_sha256='0' * 64, target_sha256='0' * 64,
            status='POINT', lower='-1', upper='1', width='0',
            logical_range=['-2', '2'], informative=not self.cert['informative'],
            sharp=False, model_scope='FULL_LAW', realization='DETERMINISTIC_PER_NODE_SIGNATURE',
            production_admission=True, estimation_handoff_allowed=True,
            unexpected='unverified',
        )
        for key, value in mutations.items():
            with self.subTest(field=key):
                changed = deepcopy(self.cert)
                changed[key] = value
                self.assertFalse(self.check(rehash(changed)))
        # A valid-looking wider interval is still not this model's sharp set.
        changed = deepcopy(self.cert)
        changed.update(lower='-1', upper='1', width='2')
        self.assertFalse(self.check(rehash(changed)))

    def test_rehashed_signed_terms_rejected(self):
        negative = next(i for i, t in enumerate(self.cert['bound_terms']) if F(t['coefficient']) < 0)
        edits = dict(coefficient='1/4', basis='NOT_A4', cell_lower='-1', cell_upper='2',
                     lower_contribution='1', upper_contribution='-1', ignored='extra')
        for key, value in edits.items():
            with self.subTest(field=key):
                changed = deepcopy(self.cert)
                changed['bound_terms'][negative][key] = value
                self.assertFalse(self.check(rehash(changed)))
        changed = deepcopy(self.cert)
        changed['bound_terms'].reverse()
        self.assertFalse(self.check(rehash(changed)))
        changed = deepcopy(self.cert)
        changed['bound_terms'][0]['coefficient'] = F(changed['bound_terms'][0]['coefficient'])
        self.assertFalse(self.check(rehash(changed)))
        changed = deepcopy(self.cert)
        changed['bound_terms'][0]['cell'] = tuple(changed['bound_terms'][0]['cell'])
        self.assertFalse(self.check(rehash(changed)))

    def test_complete_cell_table_and_canonical_numbers_required(self):
        mutations = [
            lambda c: c['cells'].pop(),
            lambda c: c['cells'].append(deepcopy(c['cells'][0])),
            lambda c: c['cells'][0]['cell'].__setitem__(1, True),
            lambda c: c['cells'][0]['cell'].__setitem__(2, 3),
            lambda c: c['cells'][0].update(support='2/4'),
            lambda c: c['cells'][0].update(lower_world='NaN'),
            lambda c: c['cells'][0].update(upper_world=True),
            lambda c: c['cells'][0].update(extra='unknown'),
            lambda c: c.update(lower=F(c['lower'])),
            lambda c: c.update(width=0),
            lambda c: c.update(informative=1),
        ]
        for index, mutate in enumerate(mutations):
            with self.subTest(mutation=index):
                changed = deepcopy(self.cert)
                mutate(changed)
                self.assertFalse(self.check(rehash(changed)))

    def test_negative_coefficient_world_must_achieve_shared_endpoint(self):
        # The reverse comparison has unsupported negative target coordinates.
        p = fixture(first=[0] * 4, second=[1] * 4)
        cert = solve(p['inquiries'], p['information'])
        term = next(t for t in cert['bound_terms']
                    if F(t['coefficient']) < 0 and t['basis'] == 'MEAN_BOUNDS')
        row = next(r for r in cert['cells'] if r['cell'] == term['cell'])
        self.assertEqual(row['lower_world'], term['cell_upper'])
        self.assertEqual(row['upper_world'], term['cell_lower'])
        changed = deepcopy(cert)
        row = next(r for r in changed['cells'] if r['cell'] == term['cell'])
        row['lower_world'], row['upper_world'] = row['upper_world'], row['lower_world']
        self.assertFalse(replay(rehash(changed), inquiries=p['inquiries'], information=p['information']))

    def test_non_target_a4_worlds_cannot_be_discarded(self):
        p = fixture(population=['A'])
        cert = solve(p['inquiries'], p['information'])
        target_terms = {tuple(t['cell']) for t in cert['bound_terms']}
        row = next(r for r in cert['cells'] if r['a4_value'] is not None
                   and tuple(r['cell']) not in target_terms)
        row['lower_world'] = '1' if row['a4_value'] != '1' else '0'
        self.assertFalse(replay(rehash(cert), inquiries=p['inquiries'], information=p['information']))

    def test_ordered_pair_cannot_be_swapped_under_original_certificate(self):
        qs = dict(first=self.inquiries['second'], second=self.inquiries['first'])
        infos = dict(first=self.information['second'], second=self.information['first'])
        self.assertFalse(replay(self.cert, inquiries=qs, information=infos))
        reverse = solve(qs, infos)
        self.assertEqual((F(reverse['lower']), F(reverse['upper'])),
                         (-F(self.cert['upper']), -F(self.cert['lower'])))
        self.assertTrue(replay(reverse, inquiries=qs, information=infos))

    def test_full_cancellation_keeps_feasible_unknown_cells(self):
        p = fixture(first=[1] * 4, second=[1] * 4)
        cert = solve(p['inquiries'], p['information'])
        self.assertEqual((cert['status'], cert['lower'], cert['upper']), ('POINT', '0', '0'))
        self.assertEqual(cert['bound_terms'], [])
        self.assertEqual(cert['logical_range'], ['0', '0'])
        # Any feasible assignment to cancelled unknowns works; the verifier
        # must check mathematics, not demand the producer's midpoint convention.
        free = next(r for r in cert['cells'] if r['a4_value'] is None)
        free.update(lower_world='0', upper_world='1')
        self.assertTrue(replay(rehash(cert), inquiries=p['inquiries'], information=p['information']))
        cert.update(status='PARTIAL', lower='-1', upper='1', width='2')
        self.assertFalse(replay(rehash(cert), inquiries=p['inquiries'], information=p['information']))

    def test_proof_checks_survive_python_optimization(self):
        code = '''from examples.bounded_contrast_fixture import make_case
from cfm_id.bounded_contrast_solver import solve
from cfm_id.bounded_contrast_verify import replay
from cfm_id_bridge.scientific_binding import sha
p=make_case(list('ABCD'), [('A','B'),('B','C'),('C','D')], 2, [1]*4, [0]*4, list('ABCD'))
c=solve(p['inquiries'],p['information'])
valid=replay(c,inquiries=p['inquiries'],information=p['information'])
c['lower']='-1'; c.pop('certificate_sha256'); c['certificate_sha256']=sha(c)
print(valid,replay(c,inquiries=p['inquiries'],information=p['information']))'''
        run = subprocess.run([sys.executable, '-B', '-O', '-c', code],
                             capture_output=True, text=True, check=True)
        self.assertEqual(run.stdout.strip(), 'True False')


if __name__ == '__main__':
    unittest.main()
