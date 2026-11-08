"""Presentation-only entry point: replay the existing pipeline before rendering.
No saved Core status, candidate success flag, or generated prose is trusted here.
No provider network implementation is imported or configured by this module.
"""
from __future__ import annotations
import json
from . import structured_witness_flat_candidate as pipeline

from cfm_id.workflows.legacy_network.result_view import VERSION

from cfm_id.workflows.legacy_network.result_view import STATES
from cfm_id.workflows.legacy_network.result_view import _view

def evaluate_for_display(bundle, raw, packet, *, provider=None, context=None, hours_review=None, query_id="q1"):
    """Use explicit existing reviews; never construct/approve reviews in presentation."""
    result=pipeline.evaluate_with_candidates(bundle,raw,packet,provider=provider,context=context,
        hours_review=hours_review,enable_candidates=True,synthetic_protocol_selected=True)
    if result.get("estimation_called") or result.get("policy_called") or result.get("estimation_handoff_allowed"):
        raise ValueError("Identification-only display cannot accept downstream execution")
    return _view(bundle,raw,result,context=context,qid=query_id),result

def standalone_html(views, template):
    """Escaped JSON + textContent rendering; no dynamic HTML from model content."""
    data=json.dumps(dict(version=VERSION,cases=views),ensure_ascii=False).replace("<","\\u003c").replace("\u2028","\\u2028").replace("\u2029","\\u2029")
    if template.count("__DISPLAY_DATA__")!=1:raise ValueError("Expected a single data slot")
    return template.replace("__DISPLAY_DATA__",data)
