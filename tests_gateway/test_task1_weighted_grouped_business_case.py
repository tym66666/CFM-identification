"""Weighted/grouped exposures run through the full dispatch to POINT."""
import tempfile
from pathlib import Path

import examples.task1_weighted_grouped_business_case as ref


def _run():
    with tempfile.TemporaryDirectory() as d:
        return ref.run(str(Path(d) / 'out'))


def test_weighted_grouped_business_case_all_point():
    summary = _run()
    assert summary['passed'] is True
    assert summary['model_api_calls'] == 0
    assert len(summary['rows']) == 4
    rows = {(r['scenario'], r['query']): r for r in summary['rows']}
    assert set(rows) == {('W_weighted_D7', 'q1'), ('W_weighted_D7', 'q2'),
                         ('G_grouped_D8', 'q1'), ('G_grouped_D8', 'q2')}
    for row in rows.values():
        assert row['state'] == 'POINT'
        assert row['independent_replay'] is True


def test_scenarios_use_new_exposure_kinds():
    assert ref.SCENARIOS['W_weighted_D7']['exposure']['kind'] == 'WEIGHTED_EXPOSURE'
    assert ref.SCENARIOS['G_grouped_D8']['exposure']['kind'] == 'GROUPED_EXPOSURE'
    # Grouped coordinates are lists with one component per group, never a lone 0/1.
    assert ref.SCENARIOS['G_grouped_D8']['direct_exposure'] == '[1, 0]'
