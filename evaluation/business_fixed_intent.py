"""Compatibility import. New runtime code uses cfm_id_llm.readers.fixed_policy.

Protocol values, public call signatures and referenced type identities are retained.
Reference conversion and scoring, when present, remain evaluation-only.
"""
from cfm_id_llm.readers.fixed_policy import *  # noqa: F401,F403
from cfm_id_llm.readers import fixed_policy as _implementation


def __getattr__(name):
    # Preserve explicit access to historical private helpers without copies.
    return getattr(_implementation, name)
