"""Historical plain-JSON hash contract; keep its serialized bytes unchanged.

New typed contracts use their existing canonical serializers; this helper does
not coerce models, reject historical non-finite JSON, or merge hash protocols.
"""
from hashlib import sha256
import json


def canonical_hash(value):
    return sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                             separators=(",", ":")).encode("utf8")).hexdigest()
