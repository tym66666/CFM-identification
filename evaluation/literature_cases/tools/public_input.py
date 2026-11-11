"""Read-only, public-file input for the ordinary web workflow.

Does not read registry answers, construct facts, or grant scientific approval.
Network file roles/declarations must be explicitly present in the manifest.
"""
from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
import argparse

from cfm_id_llm.document_intake import MAX_ATTACHMENTS

PUBLIC = Path(__file__).resolve().parents[1] / "public"


def load_public(case_id: str, variant: str, *, public_root: Path = PUBLIC) -> dict:
    base = public_root.resolve()
    folder = (base / case_id / variant).resolve()
    if base not in folder.parents:
        raise ValueError("PUBLIC_CASE_PATH_REQUIRED")
    manifest = json.loads((folder / "submission_manifest.json").read_text("utf8"))
    if (manifest["case_id"], manifest["variant"]) != (case_id, variant):
        raise ValueError("MANIFEST_ID_MISMATCH")
    question = manifest.get("business_question_file", "business_question.md")
    names = [question, *manifest["supporting_files"]]
    if len(set(names)) != len(names) or len(names) - 1 > MAX_ATTACHMENTS:
        raise ValueError("INVALID_PUBLIC_FILE_LIST")
    paths = {}
    for name in names:
        path = (folder / name).resolve()
        if path.parent != folder or not path.is_file():
            raise ValueError("PUBLIC_FILE_REQUIRED")
        paths[name] = path
    network = manifest.get("network_upload")
    roles = {}
    if network:
        roles = {network["nodes_file"]: "network_nodes", network["edges_file"]: "network_edges"}
        if len(roles) != 2 or not set(roles) <= set(manifest["supporting_files"]):
            raise ValueError("NETWORK_FILES_REQUIRED")
        evidence = network["declaration_source"]
        if evidence["file"] not in paths or not evidence["quote"].strip():
            raise ValueError("NETWORK_DECLARATION_SOURCE_REQUIRED")
        if evidence["quote"] not in paths[evidence["file"]].read_text("utf8"):
            raise ValueError("NETWORK_DECLARATION_QUOTE_MISMATCH")
    payload = dict(question=paths[question].read_text("utf8"), synthetic=True,
                   allow_send=True, automatic_review=True, files=[
                       dict(name=name, role=roles.get(name, "document"),
                            content=base64.b64encode(paths[name].read_bytes()).decode())
                       for name in manifest["supporting_files"]])
    if network:
        payload["network"] = network["declaration"]
    return dict(case_id=case_id, variant=variant, payload=payload,
                input_sha256={name: hashlib.sha256(path.read_bytes()).hexdigest()
                              for name, path in paths.items()},
                manifest_sha256=hashlib.sha256((folder / "submission_manifest.json").read_bytes()).hexdigest(),
                origin="PUBLIC_FILES_ONLY", human_candidate_repairs=False)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--variant", choices=("original", "missing_condition", "changed_target"), default="original")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    value = load_public(args.case_id, args.variant)
    with args.output.open("x", encoding="utf8") as f:
        json.dump(value, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
