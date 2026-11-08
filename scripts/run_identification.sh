#!/usr/bin/env bash
# Causal-IDFM v3.0 Identification-only: no PFN training / Estimation / Policy.
set -euo pipefail
cd "$(dirname "$0")/.."
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
mode="${1:-fast}"
case "$mode" in
  fast)
    bash scripts/run_identification_only.sh fast
    python -B -m unittest tests_gateway.test_trusted_core tests.test_integration_and_ui tests.test_presentation_clarity tests.test_no_key_curated -q
    ;;
  id-all) bash scripts/run_identification_only.sh id-all ;;
  gateway)
    read -ra mods <<< "$(find tests_gateway -maxdepth 1 -name 'test_*.py' | sort | sed 's#/#.#g;s#\.py$##' | tr '\n' ' ')"
    echo "Gateway v0.12: ${#mods[@]} test modules"
    for ((i=0;i<${#mods[@]};i+=4)); do
      echo "Gateway group $((i/4+1))"
      if timeout 35 python -B -m unittest "${mods[@]:i:4}" -q; then
        continue
      fi
      echo 'Gateway combined group did not complete; isolate each original module without suppressing any failures.' >&2
      for module in "${mods[@]:i:4}"; do
        timeout 35 python -B -m unittest "$module" -q
      done
    done
    ;;
  demo)
    python -B -m examples.build_supervisor --output-dir assets/supervisor_templates
    python -B -m examples.build_no_key_curated --output-dir assets/supervisor_templates
    cp assets/supervisor_templates/CFM_ID_Supervisor_Results.html cfm_id/web/
    cp assets/supervisor_templates/CFM_ID_Coverage_Map.html cfm_id/web/
    cp assets/supervisor_templates/CFM_ID_Supervisor_Results.json cfm_id/web/
    cp assets/supervisor_templates/CFM_ID_No_Key_Curated_Business_Live_Demo.html cfm_id/web/
    cp assets/supervisor_templates/CFM_ID_No_Key_Curated_Business_Live_Demo.json cfm_id/web/
    ;;
  *) echo 'Usage: bash scripts/run_identification.sh {fast|id-all|gateway|demo}' >&2;exit 2;;
esac
