"""Formal identification rule entry for the randomized-network arm family.

This is the *formal* route, and it is **not** a new identification system: it
forwards to the existing certificate path (``pfn_pipeline.identify`` →
``RandomizedNetworkArmBackend`` + ``IdentificationVerifier``). A caller supplies
a complete ``TaskSpec`` (known design/exposure law + confirmed assumptions); the
backend consumes the declared population information and issues a VERIFIED POINT
certificate bound to the theorem contract, which can be independently replayed.

It deliberately does **not** expose the target-value verification helper (which
recomputes expectations from outcomes the caller already has). That audit tool
lives in ``tests/task1_target_helpers.py`` and is never a substitute for formal
identification; treating its arithmetic as "formal policy identification" is
exactly what this boundary forbids.
"""
from __future__ import annotations


def identify(task):
    """Formal POINT identification + certificate for one randomized-network arm.

    ``task`` is a complete :class:`pfn_pipeline.contracts.TaskSpec` built by one
    of the ``make_*_arm_task`` constructors (including the task-1 unequal /
    rerandomized designs and weighted / grouped exposures). Returns the existing
    :class:`pfn_pipeline.contracts.IdentificationResult` with its certificate.
    """
    from pfn_pipeline.identification import identify as _identify
    return _identify(task)


def replay(result):
    """Re-verify a saved population identification certificate (proof replay)."""
    from pfn_pipeline.identification import replay_population_identification
    return replay_population_identification(result)


__all__ = ["identify", "replay"]
