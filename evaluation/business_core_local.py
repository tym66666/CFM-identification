"""Local exact singleton-mean equivalence. Uses the unchanged v0.20.3 prompt.

A mean over an explicitly singleton set has its sole weight equal to one.
This does not fill in an unknown population or an unknown averaging rule.
Original model responses and source references remain stored unchanged.
"""
from copy import deepcopy
from .business_core_pilot_base import canonical_hash, evaluate_draft as evaluate_numeric
from .business_core_pilot import numeric_projection
from .business_core_source_refs import resolve_sources, source_catalog, make_request

VERSION = "business-core-local-v0.20.4"
PROMPT_VERSION = "business-core-pilot-v0.20.3"


def canonical_singleton_mean(numeric):
    projected = deepcopy(numeric)
    changes = []
    for i, target in enumerate(projected["targets"], 1):
        nodes = target.get("nodes")
        if (isinstance(nodes, list) and len(nodes) == 1 and target["aggregation"] == "equal_mean"
                and target["kind"] in ("arm", "comparison", "fixed_plan")):
            target["aggregation"] = "single"
            changes.append(dict(query_id=f"q{i}", from_aggregation="equal_mean",
                                to_aggregation="single", node=nodes[0],
                                reason="Exact identity: equal mean over one explicit node has weight 1"))
    return projected, changes


def evaluate_draft(question, raw, packet, *, synthetic_protocol_selected=False):
    if synthetic_protocol_selected is not True:
        return evaluate_numeric(question, {}, packet, synthetic_protocol_selected=False)
    numeric = numeric_projection(resolve_sources(question, raw))
    projected, changes = canonical_singleton_mean(numeric)
    result = evaluate_numeric(question, projected, packet, synthetic_protocol_selected=True)
    result.update(version=VERSION, prompt_version=PROMPT_VERSION,
                  model_draft_sha256=canonical_hash(raw),
                  pre_identity_draft_sha256=canonical_hash(numeric),
                  normalized_draft_sha256=canonical_hash(projected),
                  source_catalog_sha256=canonical_hash(source_catalog(question)),
                  exact_equivalences_applied=changes,
                  source_reference_precision_verified=False)
    return result
