from __future__ import annotations
import copy
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]


def load(name: str):
    return json.loads((ROOT / "examples" / name).read_text(encoding="utf-8"))


def case_and_draft(name: str = "sales_ambiguous"):
    return copy.deepcopy(load(f"{name}.json")), copy.deepcopy(load(f"{name}_mock_response.json"))
