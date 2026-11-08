"""Compatibility import. New runtime code uses cfm_id.workflows.mean_order_review.

Protocol values, public call signatures and referenced type identities are retained.
Reference conversion and scoring, when present, remain evaluation-only.
"""
from cfm_id.workflows.mean_order_review import *  # noqa: F401,F403
from cfm_id.workflows import mean_order_review as _implementation


def __getattr__(name):
    # Preserve explicit access to historical private helpers without copies.
    return getattr(_implementation, name)
