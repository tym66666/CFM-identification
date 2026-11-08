# NBIB v0.1: Network Business Identification Benchmark

This is the original benchmark's historical README, retained with the reference assets. Its version numbers, standalone status and generator commands describe that release. The original generator scripts and auxiliary documentation are not included in this asset directory. For the current repository's evaluation entry point, see the [NBIB semantic evaluation guide](../../docs/NBIB_A0_SEMANTIC_EVALUATION_ZH.md).

A standalone, reproducible synthetic benchmark for natural-language **business-to-causal-formalization**, aligned conceptually with the user-provided Causal-IDFM v2.7(+P1/P2) Identification contracts and Gateway v0.9. It is **not integrated** with either project.

21 Chinese business packets describe plausible questions, study protocols, fixed/observed networks and finite synthetic treatment/outcome data. Cases span 8 topologies, 14–300 nodes, D1/D2/D3/D4/D5/D6 assignment, observational adoption, and E1–E5 exposures. Three groups contain minimal controlled contrasts. One counterexample constructs identical observable joint distributions with different causal effects.

**Run:** `python scripts/generate.py --seed 20261017 && python scripts/validate.py --reproduce`.

**Keep strictly separate:** `benchmarks/network_business_identification/public/` (LLM input) vs `gold/` (expert labels and route candidates) vs `oracle/` (simulator secrets). All finite samples lack an admitted population observable A4 and cannot certify causal assumptions A5. Formal POINT and proof replay **have not been performed** for these generated cases. Public gold is useful for diagnostics, not a contamination-free blind benchmark.

See the historical [Chinese README](README_ZH.md). The original `CASE_MATRIX_ZH.md` and `EVALUATION_PROTOCOL_ZH.md` belong to the standalone release and are not bundled here.
