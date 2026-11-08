#!/usr/bin/env bash
# One canonical entry point for NEW minimal-core stabilization verification.
# Avoid silently executing GPU/PFN training during 1-second math debugging.
set -euo pipefail
cd "$(dirname "$0")/.."
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
export PYTHONPATH="${PWD}/tests:${PWD}${PYTHONPATH:+:${PYTHONPATH}}"
mode="${1:-fast}"
case "$mode" in
  fast)
    python -B -m unittest tests.test_minimal_correct_core_stabilization -q
    output="$(mktemp)"
    trap 'rm -f "$output"' EXIT
    python -B -m examples.minimal_correct_core_golden --output "$output"
    cmp -s "$output" assets/benchmark_assets_stabilization/minimal_golden_expected.json || {
      echo 'Golden output differs from locked baseline; review maths, A4/A5 and reason codes before updating!' >&2
      exit 1
    }
    echo 'FAST GOLDEN: test, exact independent oracle, certificate replay and snapshot PASS'
    ;;
  r3-ablate)
    python -B -m unittest tests.test_minimal_core_maintenance_diagnostics -q
    output="$(mktemp)"
    trap 'rm -f "$output"' EXIT
    python -B -m examples.minimal_r3_a4_representation_ablation --output "$output"
    cmp -s "$output" assets/benchmark_assets_stabilization/minimal_r3_representation_expected.json || {
      echo 'R3 p-standardized representation Golden changed. Inspect A4 law / A5 / target before updating.' >&2
      exit 1
    }
    echo 'R3 A4 REPRESENTATION GOLDEN: FULL/FACTORIZED/MIXTURE + ABLATION PASS'
    ;;
  r3-audit)
    python -B -m scripts.audit_r3_representation_boundaries --output "${2:-/tmp/cfm_id_r3_readonly_audit.json}"
    ;;
  pfn-diagnose)
    python -B -m scripts.diagnose_legacy_pfn_smoke --test checkpoint \
      --timeout 180 --stack-after 45 --report "${2:-/tmp/cfm_id_legacy_pfn_smoke_diagnostic.json}"
    ;;
  pfn-ablate)
    # This is a developer DIAGNOSTIC ONLY. Both arms use the same test and
    # distinct fresh processes; it does not modify training or causal Core.
    # Calling 'env -u' is essential because this runner normally pins threads.
    report_dir="${2:-/tmp/cfm_id_pfn_thread_ablation}"
    mkdir -p "$report_dir"
    python -B -m scripts.diagnose_legacy_pfn_smoke --test checkpoint \
      --thread-mode controlled --repetitions 2 --timeout 120 \
      --stack-after 35 --report "$report_dir/controlled.json"
    env -u OMP_NUM_THREADS -u MKL_NUM_THREADS -u OPENBLAS_NUM_THREADS \
      python -B -m scripts.diagnose_legacy_pfn_smoke --test checkpoint \
      --thread-mode inherited --repetitions 2 --timeout 120 \
      --stack-after 35 --report "$report_dir/inherited.json"
    echo 'PFN diagnostic ablation completed; review BOTH reports before attributing root cause.'
    ;;
  integration)
    python -B -m unittest tests.test_production_a4_and_business \
        tests.test_review_authorization tests.test_llm_core_integration -q
    ;;
  scale)
    python -B -m unittest tests.test_stabilization_scaling -q
    ;;
  core)
    bash scripts/run_checks.sh core
    ;;
  core-split)
    # Same discovery set as scripts/run_checks.sh core, executed in
    # independent 6-module subprocess groups to isolate historical stalls.
    mapfile -t modules < <(find tests -maxdepth 1 -name 'test_*.py' ! -name 'test_pipeline_smoke.py' | sort | sed 's#/#.#g;s#\.py$##')
    count=${#modules[@]}
    printf 'SPLIT CORE: %s modules; groups of 6\n' "$count"
    for ((first=0; first<count; first+=6)); do
      chunk=("${modules[@]:first:6}")
      printf 'SPLIT CORE: group %s-%s\n' "$((first+1))" "$((first+${#chunk[@]}))"
      timeout 100 python -B -m unittest "${chunk[@]}" -q
    done
    ;;
  gateway)
    bash scripts/run_checks.sh gateway
    ;;
  pfn-smoke)
    # Keep all nine historical tests, but require a bounded, observable terminal.
    python -B -m scripts.diagnose_legacy_pfn_smoke --test full \
      --thread-mode controlled --timeout 360 --stack-after 90 \
      --report "${2:-/tmp/cfm_id_pfn_full_smoke.json}"
    ;;
  all)
    "$0" fast
    "$0" integration
    "$0" scale
    "$0" core
    "$0" gateway
    "$0" pfn-smoke
    ;;
  *)
    echo 'Usage: scripts/run_minimal_stabilization_checks.sh {fast|r3-ablate|r3-audit|pfn-diagnose|pfn-ablate|integration|scale|core|core-split|gateway|pfn-smoke|all}' >&2
    exit 2
    ;;
esac
