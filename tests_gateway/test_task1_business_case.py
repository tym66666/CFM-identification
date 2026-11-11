"""Task-1 complete business case runs through the full dispatch to POINT."""
import json
import tempfile
from pathlib import Path

import examples.task1_business_case_reference as ref


def _run():
    with tempfile.TemporaryDirectory() as d:
        summary = ref.run(str(Path(d) / 'out'))
        return summary


def test_business_case_all_point():
    summary = _run()
    assert summary['passed'] is True
    assert summary['model_api_calls'] == 0
    assert len(summary['rows']) == 4
    for row in summary['rows']:
        assert row['state'] == 'POINT'
        assert row['independent_replay'] is True


def test_fact_reference_assignment_kinds():
    # Both new designs must be expressed as the new business assignment kinds.
    assert ref.DESIGNS['D7_unequal']['kind'] == 'UNEQUAL_PROBABILITY_FIXED_QUOTA'
    assert ref.DESIGNS['D8_rerandomized']['kind'] == 'RERANDOMIZED_BALANCED'
