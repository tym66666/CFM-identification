"""Replay two recorded readings through the common entry; no API credentials.

From the source root: python examples/legacy/business_extension/run_offline.py
This validates the reading boundary, not theorems or new model performance.
"""
from pathlib import Path
import hashlib
import json
import sys
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2]))
from cfm_id.business_entry import preview, prepare_request


def read(path):
    return json.loads((HERE / path).read_text(encoding="utf8"))


def main():
    provenance = read("recorded/provenance.json")
    for path, digest in provenance["files"].items():
        if hashlib.sha256((HERE / path).read_bytes()).hexdigest() != digest:
            raise ValueError("Recorded example changed: use a new case and fresh reading")
    envelope = read("recorded/study_envelope.json")
    summary = []
    with patch("socket.socket.connect", side_effect=AssertionError("OFFLINE_ONLY")):
        for name in ("positive", "negative"):
            bundle = read(f"public/{name}_bundle.json")
            candidate = read(f"recorded/{name}_candidate.json")
            prepare_request(bundle, "D2_ARM", envelope, contract="legacy-v0551")
            result = preview(bundle, candidate, "D2_ARM", envelope, contract="legacy-v0551")
            expected = read("research/expected_behavior.json")[name]
            if result["state"] != expected["state"] or result["core_called"]:
                raise ValueError("Unexpected reading boundary result")
            summary.append({"case": name, "state": result["state"], "core_called": False})
    print(json.dumps({"recorded_readings": summary, "http_calls": 0,
                      "new_certificates": 0}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
