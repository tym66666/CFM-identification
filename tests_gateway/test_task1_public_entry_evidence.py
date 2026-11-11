"""The public-entry evidence runner passes and reports fixture provenance.

This asserts actual end-to-end execution through the public intake / dispatch /
native entry points: every positive case reaches POINT + VERIFIED and replays
independently, and every gap/refusal case returns its expected reason code.
Reading provenance is a hand-written fixture; no language model is called.
"""
import tempfile
from pathlib import Path

import examples.task1_public_entry_evidence as evidence


def test_public_entry_evidence_passes():
    with tempfile.TemporaryDirectory() as folder:
        output = Path(folder) / 'out'
        summary = evidence.run(str(output))

        assert summary['passed'] is True
        prov = summary['reading_provenance']
        assert prov['hand_written_fixture'] is True
        assert prov['real_llm_runs'] == 0
        assert prov['model_api_calls'] == 0

        assert summary['positive_count'] >= 10
        assert summary['rejection_count'] >= 6
        for positive in summary['positives']:
            assert positive['state'] == 'POINT', positive
            assert positive['verification'] == 'VERIFIED', positive
            assert positive['independent_replay'] is True, positive
            assert positive['certificate'], positive
        for rejection in summary['rejections']:
            assert rejection['ok'] is True, rejection

        assert (output / 'SUMMARY.json').is_file()
