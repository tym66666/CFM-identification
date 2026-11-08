#!/usr/bin/env bash
# Identification-owned execution only. Never runs PFN training or Policy.
# Old platform-wide regression is preserved in scripts/run_checks.sh.
set -euo pipefail
cd "$(dirname "$0")/.."
export PYTHONPATH="${PWD}/tests:${PWD}${PYTHONPATH:+:${PYTHONPATH}}"
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
mode="${1:-fast}"
case "$mode" in
  fast)
    python -B -m unittest tests.test_identification_only_contract \
        tests.test_minimal_correct_core_stabilization \
        tests.test_minimal_core_maintenance_diagnostics -q
    python -B -m examples.minimal_correct_core_golden --output /tmp/cfm_idonly_golden.json >/dev/null
    cmp /tmp/cfm_idonly_golden.json assets/benchmark_assets_stabilization/minimal_golden_expected.json
    echo 'Identification-only FAST: real Core, golden/replay, negative admissions and locked JSON PASS'
    ;;
  demo)
    python -B -m examples.build_identification_only_demo --output-dir "${2:-assets/identification_only_templates}"
    ;;
  id-all)
    # Exclude the only four legacy tests importing PFN training/estimation, or
    # depending on its simulation & checkpoint. No training is required for ID.
    mapfile -t mods < <(find tests -maxdepth 1 -name 'test_*.py' \
      ! -name 'test_pipeline_smoke.py' \
      ! -name 'test_identification_integration.py' \
      ! -name 'test_identification_estimation_contract.py' \
      ! -name 'test_batch_identification.py' \
      ! -name 'test_minimal_pfn_diagnostic_ablation.py' | sort | sed 's#/#.#g;s#\.py$##')
    echo "Identification-only ID-ALL: ${#mods[@]} modules; at most six per isolated interpreter"
    # Run moderately sized chunks for speed. If a legacy group stalls only in
    # combination, re-run its individual modules and explain the fallback.
    for ((first=0;first<${#mods[@]};first+=6)); do
      chunk=("${mods[@]:first:6}")
      echo "ID-ALL group $((first/6+1)): ${chunk[*]}"
      if timeout 65 python -B -m unittest "${chunk[@]}" -q; then
        continue
      fi
      echo 'Group did not complete; isolating each module to diagnose the inherited test interaction.' >&2
      for module in "${chunk[@]}"; do
        echo "ID-ALL isolated module: $module"
        timeout 45 python -B -m unittest "$module" -q
      done
    done
    ;;
  research-partial)
    python -B -m research_partial.star7_bounded_r2_policy_demo --output-dir "${2:-research_partial/output}"
    ;;
  *)
    echo 'Usage: bash scripts/run_identification_only.sh {fast|demo|id-all|research-partial} [directory]' >&2
    exit 2
    ;;
esac
