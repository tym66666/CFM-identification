#!/usr/bin/env bash
# Reproduce v2.9 regression categories. No online APIs are called.
set -euo pipefail
cd "$(dirname "$0")/.."
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
# Some unchanged historical math tests import other tests as top-level modules.
export PYTHONPATH="${PWD}/tests:${PWD}${PYTHONPATH:+:${PYTHONPATH}}"
mode="${1:-all}"
case "$mode" in
  integration)
    python -B -m unittest tests.test_llm_core_integration tests.test_scientific_binding_hardening tests.test_json_route_packets tests.test_formal_benchmark tests.test_review_authorization tests.test_coverage_atlas tests.test_common_business_formal_backed -q ;;
  gateway)
    python -B -m unittest discover -s tests_gateway -p 'test*.py' -q ;;
  core)
    mapfile -t mods < <(find tests -maxdepth 1 -name 'test_*.py' ! -name 'test_pipeline_smoke.py' | sort | sed 's#/#.#g;s#\.py$##')
    python -B -m unittest "${mods[@]}" -q ;;
  pfn-smoke)
    python -B -m unittest tests.test_pipeline_smoke -q ;;
  all)
    "$0" core
    "$0" gateway
    "$0" pfn-smoke
    python -B -m examples.run_formal_benchmark --output assets/formal_benchmark_assets/formal_backed_results.json ;;
  *)
    printf 'Usage: %s {all|core|gateway|integration|pfn-smoke}\n' "$0" >&2
    exit 2 ;;
esac
