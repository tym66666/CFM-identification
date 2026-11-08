"""Demonstrate population batch + safe reuse of the original legacy handoff.

Run `python -m examples.run_batch_identification_and_legacy_bridge` (ER20),
or add `--er300` for the full 1,200-arm shared network (no model required).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from pfn_pipeline import identify, simulate_task
from pfn_pipeline.identification_batch import (
    bind_legacy_response_batch, replay_legacy_response_batch_bridge,
)
from pfn_pipeline.simulation import load_graph


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--er300', action='store_true', help='Use the fixed full ER300 network')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    if args.er300:
        task = simulate_task(seed=2026)
    else:
        graph = load_graph(root / 'pfn_pipeline/_internal/estimation/data/fixed_er_N20_p0.5_seed12345.json')
        task = simulate_task(seed=2026, adjacency=graph, budget=3)
    legacy = identify(task)
    link = bind_legacy_response_batch(legacy)
    replay_legacy_response_batch_bridge(link)
    batch = link.batch
    print(json.dumps({
        'node_count': task.n_nodes,
        'batch_shape': batch.shape,
        'coverage': batch.coverage_status,
        'verification_status': batch.verification_status,
        'batched_target_sha256': batch.batch_sha256,
        'first_node_ar0': batch.cell(batch.node_ids[0], 0, 0),
        'estimation': link.estimation_status,
        'estimation_request': 'existing replayed legacy response request ONLY',
        'model_weights_checked': False,
        'sample_data_estimability_proven': False,
    }, indent=2, ensure_ascii=False))

if __name__ == '__main__':
    main()
