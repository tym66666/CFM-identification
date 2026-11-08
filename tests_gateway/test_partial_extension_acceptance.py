"""Tests of the developer scaffold's refusal to bless incomplete evidence."""
from copy import deepcopy
import unittest
from evaluation.partial_extension_acceptance import evaluate
from examples.partial_extension_reference import BoundedPolicyReference

class AcceptanceTests(unittest.TestCase):
    def test_existing_route_full_reference_suite(self):
        r=evaluate(BoundedPolicyReference())
        self.assertEqual(r['cases'],13);self.assertFalse(r['route_registered'])
        self.assertEqual(sum(x['independent_replay'] for x in r['rows']),4)
        self.assertEqual(sum(len(x['forged_certificates_rejected']) for x in r['rows']),12)
    def test_fake_replay_or_prepare_publication_rejected(self):
        class Fake(BoundedPolicyReference):
            def replay(self,case,cert):return True
        with self.assertRaisesRegex(ValueError,'FORGERY_ACCEPTED'):evaluate(Fake())
        class Prepare(Fake):
            def prepare(self,case):return {'state':'PARTIAL'}
        with self.assertRaisesRegex(ValueError,'PREPARE_PUBLISHED_RESULT'):evaluate(Prepare())
    def test_nonsharp_and_wrong_interval_cannot_pass(self):
        class Wrong(BoundedPolicyReference):
            def certificate(self,result):
                cert=deepcopy(super().certificate(result))
                if cert:cert['sharp']=False
                return cert
        with self.assertRaisesRegex(ValueError,'SHARPNESS_NOT_CERTIFIED'):evaluate(Wrong())
    def test_blocked_case_cannot_attach_certificate(self):
        class Leak(BoundedPolicyReference):
            def certificate(self,result):
                return super().certificate(result) or {'status':'PARTIAL'}
        with self.assertRaisesRegex(ValueError,'BLOCKED_CASE_PUBLISHED_CERTIFICATE'):evaluate(Leak())

if __name__=='__main__':unittest.main()

