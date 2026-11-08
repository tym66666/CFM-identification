from copy import deepcopy
import json
import unittest
from evaluation import business_materials as current
from evaluation.nbib_acceptance import DATA,material_input,read
from evaluation.business_materials_intake import sources

class DesignProvenanceSchemaTests(unittest.TestCase):
    def test_allowed_enum_matches_validator_domain(self):
        for cid in ('H25-service_arm','H25-factory_arm'):
            b=material_input(cid);_,user=current.make_request(b);m=json.loads(user)
            prop=m['output_schema']['properties']['study']['properties']['design_sources']
            expected=set(sources(b)) | ({'cluster_randomization.csv'} if 'cluster_randomization.csv' in b['tables'] else set())
            self.assertEqual(set(prop['items']['enum']),expected)
            self.assertEqual(prop['minItems'],1)
            self.assertNotIn('units.csv',expected)
            self.assertNotIn('network_edges.csv',expected)
            self.assertEqual(m['documents'],b['documents'])

    def test_invalid_extra_file_is_not_silently_dropped(self):
        refs=read(DATA/'research_only/formal_references.json');r=deepcopy(refs['H25-missing_independence'])
        b=material_input('H25-missing_independence');raw=r['raw_reading']
        raw['questions']['q1']['remaining_evidence_span']=None
        raw['study']['design_sources'].append('network_edges.csv')
        result=current.evaluate_draft(b,raw,r['science_packet'],synthetic_protocol_selected=True)
        self.assertEqual(result['reason_code'],'DESIGN_SOURCE_INVALID')
        self.assertFalse(result['results'])

    def test_missing_independence_stays_missing_with_valid_sources(self):
        refs=read(DATA/'research_only/formal_references.json');r=deepcopy(refs['H25-missing_independence'])
        raw=r['raw_reading'];raw['questions']['q1']['remaining_evidence_span']=None
        result=current.evaluate_draft(material_input('H25-missing_independence'),raw,r['science_packet'],synthetic_protocol_selected=True)
        self.assertEqual(result['reason_code'],'INDEPENDENT_GROUP_DRAWS_NOT_DECLARED')
        self.assertFalse(result['results'])
        self.assertFalse(result['production_admission'])

if __name__=='__main__':unittest.main()
