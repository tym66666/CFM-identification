"""Production typed-A4 gates for the legacy ER/PFN majority-response handoff."""
from __future__ import annotations

import copy
import unittest

from pfn_pipeline._internal.identification.majority_response import (
    make_majority_response_spec, MajorityResponseBackend, verify_majority_response,
    majority_response_a4_reason,
)
from pfn_pipeline._internal.identification.schemas import (
    InformationObject, NetworkExposureSpec, IdentificationSpec,
)


def _spec():
    net = NetworkExposureSpec(
        network_id='majority-v22-three', node_ids=['a','b','c'],
        undirected_edges=[('a','b'),('a','c'),('b','c')]
    )
    return make_majority_response_spec(
        net, source='synthetic randomized three-node protocol',
        evidence='explicit synthetic fixture, not real-world proof',
        admitted=True, synthetic=True, query_authority='TRUSTED_FIXTURE'
    )


def _replace_op(spec, **updates):
    clone = IdentificationSpec.model_validate(spec.model_dump(mode='python'))
    data = clone.information_signature.objects[0].randomized_arm_observable.model_dump(mode='python')
    data.update(updates)
    from pfn_pipeline._internal.identification.schemas import RandomizedArmObservableV21
    clone.information_signature.objects[0].randomized_arm_observable=RandomizedArmObservableV21.model_validate(data)
    return clone


class MajorityTypedA4Tests(unittest.TestCase):
    def test_existing_official_constructor_remains_verified(self):
        spec=_spec()
        result=MajorityResponseBackend().solve(spec)
        self.assertEqual(result.status,'POINT')
        checked=verify_majority_response(spec,result)
        self.assertEqual(checked.verification_status,'VERIFIED')
        self.assertIsNone(majority_response_a4_reason(spec))

    def test_variable_only_population_data_is_not_sufficient(self):
        spec=_spec()
        old=spec.information_signature.objects[0]
        old.randomized_arm_observable=None
        self.assertTrue({'treatment','outcome'}<=set(old.variables))
        self.assertEqual(majority_response_a4_reason(spec),'MAJORITY_RESPONSE_TYPED_A4_REQUIRED')
        self.assertNotEqual(MajorityResponseBackend().solve(spec).status,'POINT')

    def test_wrong_study_design_graph_or_outcome_coordinates_rejected(self):
        base=_spec()
        kwargs=(
            {'network_fingerprint':'wrong-network'},
            {'assignment_law_fingerprint':'wrong-q'},
            {'exposure_fingerprint':'wrong-g'},
            {'node_order':('b','a','c')},
            {'outcome_nodes':('a','b')},
            {'treatment':'wrong-treatment'},
            {'outcome':'wrong-outcome'},
            {'context_symbol':'wrong-W'},
        )
        for updated in kwargs:
            with self.subTest(updated=updated):
                spec=_replace_op(base,**updated)
                self.assertIsNotNone(majority_response_a4_reason(spec))
                self.assertNotEqual(MajorityResponseBackend().solve(spec).status,'POINT')

    def test_unadmitted_and_finite_sample_sources_rejected(self):
        for update in ({'admission':'PROPOSED'},
                       {'availability':'FINITE_SAMPLE_ESTIMATE'}):
            with self.subTest(update=update):
                spec=_replace_op(_spec(),**update)
                self.assertIsNotNone(majority_response_a4_reason(spec))

    def test_valid_node_full_and_full_joint_laws_suffice(self):
        for op in ('NODE_FULL_LAW','FULL_JOINT_LAW'):
            with self.subTest(op=op):
                spec=_replace_op(_spec(),operator=op,exposure_fingerprint=None,
                                 arm_coverage=None,arm_cells=())
                self.assertIsNone(majority_response_a4_reason(spec))
                result=verify_majority_response(spec,MajorityResponseBackend().solve(spec))
                self.assertEqual((result.status,result.verification_status),('POINT','VERIFIED'))

    def test_explicit_incomplete_arm_coverage_fails(self):
        spec=_replace_op(_spec(),arm_coverage='EXPLICIT_CELLS',
                        arm_cells=(('a',0,0),('a',1,1),('b',0,0)))
        self.assertIsNotNone(majority_response_a4_reason(spec))
        self.assertNotEqual(MajorityResponseBackend().solve(spec).status,'POINT')

    def test_explicit_complete_arm_coverage_succeeds(self):
        cells=tuple((n,a,s) for n in ('a','b','c') for a in (0,1) for s in (0,1))
        spec=_replace_op(_spec(),arm_coverage='EXPLICIT_CELLS',arm_cells=cells)
        self.assertIsNone(majority_response_a4_reason(spec))
        self.assertEqual(verify_majority_response(spec,MajorityResponseBackend().solve(spec)).verification_status,
                         'VERIFIED')

    def test_same_source_id_conflicting_semantics_are_rejected(self):
        spec=_spec()
        original=spec.information_signature.objects[0]
        clone=InformationObject.model_validate(original.model_dump(mode='python'))
        clone.randomized_arm_observable=_replace_op(_spec(),admission='PROPOSED').information_signature.objects[0].randomized_arm_observable
        spec.information_signature.objects.append(clone)
        self.assertEqual(majority_response_a4_reason(spec),'MAJORITY_A4_CONFLICTING_SOURCE_ID')

    def test_tampered_certificate_or_a4_after_issue_fails_replay(self):
        spec=_spec()
        result=MajorityResponseBackend().solve(spec)
        updated=_replace_op(spec,network_fingerprint='tampered')
        self.assertNotEqual(verify_majority_response(updated,result).verification_status,'VERIFIED')
        tampered=result.model_copy(deep=True)
        tampered.certificate['source_spec_sha256']='0'*64
        self.assertNotEqual(verify_majority_response(spec,tampered).verification_status,'VERIFIED')


if __name__=='__main__':
    unittest.main()
