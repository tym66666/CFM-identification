"""Read explicit public synthetic materials without importing evaluation code.

The caller supplies the material root. Benchmark defaults and gold data belong
in evaluation; CSV validation, source indexing and byte fingerprints live here.
This preserves the existing synthetic-only contract and grants no approvals.
"""
import csv
import json
from io import StringIO
from pathlib import Path
import re
from hashlib import sha256

def goal_slots(text):
    """Bounded business convention: explicit questions, or '希望知道：…；…。'."""
    out = {}
    for line in text.splitlines():
        if line.lstrip().startswith("#"):
            continue
        questions = re.findall(r"[^。？！?\n]+[？?]", line)
        if questions:
            clauses = questions
        else:
            match = re.search(r"(?:希望知道|想了解|想知道|问题)\s*[:：]([^。\n]+)", line)
            clauses = re.split("[；;]", match.group(1)) if match else []
        for clause in clauses:
            clause = clause.strip()
            if clause:
                out[f"q{len(out)+1}"] = clause
    if not out or len(out) > 6:
        raise ValueError("EXPLICIT_BUSINESS_GOALS_REQUIRED")
    return out


def sources(bundle):
    result = {}
    for name, content in bundle["documents"].items():
        for i, line in enumerate(content.splitlines(), 1):
            if line.strip() and not line.lstrip().startswith("#"):
                result[f"{name}:L{i}"] = line.strip()
    return result


def _rows(text):
    reader = csv.DictReader(StringIO(text))
    if not reader.fieldnames or len(reader.fieldnames) != len(set(reader.fieldnames)):
        raise ValueError("CSV_HEADER_INVALID")
    rows = list(reader)
    if len(rows) > 10000 or any(None in r or any(v is None for v in r.values()) for r in rows):
        raise ValueError("CSV_ROWS_INVALID")
    return reader.fieldnames, rows


def validate_tables(tables):
    units = tables["units.csv"]["rows"]
    nodes = [r["node_id"] for r in units]
    if not nodes or len(nodes) > 500 or len(nodes) != len(set(nodes)) or any(not n for n in nodes):
        raise ValueError("UNIT_IDS_INVALID")
    groups = {}
    for r in units:
        groups.setdefault(r["unit_group"], []).append(r["node_id"])
    node_set, edge_set = set(nodes), set()
    edges = []
    for r in tables["network_edges.csv"]["rows"]:
        a, b = r["source_id"], r["target_id"]
        edge = tuple(sorted((a, b)))
        if a not in node_set or b not in node_set or a == b or edge in edge_set:
            raise ValueError("NETWORK_EDGE_INVALID")
        if r.get("frozen_before_rollout") != "1":
            raise ValueError("NETWORK_NOT_DECLARED_PRETREATMENT")
        edge_set.add(edge)
        edges.append(list(edge))
    rates = {}
    for r in tables.get("cluster_randomization.csv", {}).get("rows", []):
        g = r["cluster_id"]
        if g in rates or g not in groups or r["member_count"] != str(len(groups[g])):
            raise ValueError("CLUSTER_TABLE_CONFLICT")
        rates[g] = r["randomization_probability"]
    if rates and set(rates) != set(groups):
        raise ValueError("CLUSTER_TABLE_INCOMPLETE")
    policies = {}
    for r in tables.get("candidate_policies.csv", {}).get("rows", []):
        p = policies.setdefault(r["policy_id"], {})
        node = r["node_id"]
        if node not in node_set or node in p or r["planned_tool_status"] not in ("0", "1"):
            raise ValueError("POLICY_TABLE_INVALID")
        p[node] = int(r["planned_tool_status"])
    if any(set(p) != node_set for p in policies.values()):
        raise ValueError("POLICY_TABLE_INCOMPLETE")
    group_of = {n: g for g, members in groups.items() for n in members}
    cross = {n for a, b in edges if group_of[a] != group_of[b] for n in (a, b)}
    return dict(nodes=nodes, edges=edges, groups=groups, cluster_rates=rates, policies=policies,
                units_with_cross_group_neighbors=[n for n in nodes if n in cross])


def load_bundle(case_id, *, public_root, clarification=None, design_addendum=None):
    root = Path(public_root).resolve()
    folder = (root / case_id).resolve()
    if folder.parent != root or not folder.is_dir():
        raise ValueError("PUBLIC_CASE_PATH_INVALID")
    manifest_path = folder / "submission_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf8"))
    if manifest.get("case_id") != case_id or manifest.get("synthetic") is not True:
        raise ValueError("PUBLIC_SYNTHETIC_MANIFEST_REQUIRED")
    names = [manifest["business_question_file"], *manifest["supporting_files"]]
    if len(names) != len(set(names)) or len(names) > 20:
        raise ValueError("MANIFEST_FILES_INVALID")
    documents, tables, inventory = {}, {}, {}
    for name in names:
        path = (folder / name).resolve()
        if path.parent != folder or path.suffix not in (".csv", ".md") or not path.is_file():
            raise ValueError("PUBLIC_FILE_PATH_INVALID")
        raw = path.read_bytes()
        if len(raw) > 1000000:
            raise ValueError("PUBLIC_FILE_TOO_LARGE")
        text = raw.decode("utf-8-sig")
        inventory[name] = dict(sha256=sha256(raw).hexdigest(), bytes=len(raw))
        if path.suffix == ".md":
            documents[name] = text
        else:
            headers, rows = _rows(text)
            # Only structural/design/policy data. Never retain realized outcomes.
            selected = {
                "units.csv": ("node_id", "unit_group"),
                "network_edges.csv": ("source_id", "target_id", "frozen_before_rollout"),
                "cluster_randomization.csv": ("cluster_id", "randomization_probability", "member_count"),
                "candidate_policies.csv": ("policy_id", "node_id", "planned_tool_status"),
            }.get(name)
            if selected and not set(selected) <= set(headers):
                raise ValueError("STRUCTURAL_COLUMNS_MISSING")
            tables[name] = dict(headers=headers, row_count=len(rows),
                                rows=[{k: r[k] for k in selected} for r in rows] if selected else [])
    if clarification:
        documents["target_clarification.txt"] = clarification
    if design_addendum:
        documents["design_addendum.txt"] = design_addendum
    active = "target_clarification.txt" if clarification else manifest["business_question_file"]
    structure = validate_tables(tables)
    return dict(case_id=case_id, synthetic=True, documents=documents, tables=tables,
        file_inventory=inventory, structure=structure, active_goal_document=active,
        question_slots=goal_slots(documents[active]), original_business_unchanged=True,
        revision_kind="EXPLICIT_CLARIFICATION" if clarification or design_addendum else "ORIGINAL_PUBLIC_MATERIALS")


def prompt_materials(bundle):
    catalog = dict(bundle["structure"])
    # Full edges are consumed by the local Core, bound by the file digest.
    catalog.pop("edges")
    catalog["network"] = dict(file="network_edges.csv", nodes=len(bundle["structure"]["nodes"]),
                              edges=len(bundle["structure"]["edges"]),
                              file_sha256=bundle["file_inventory"]["network_edges.csv"]["sha256"])
    catalog["policies"] = {k: dict(treated=[n for n, a in p.items() if a], untreated=[n for n, a in p.items() if not a])
                            for k, p in bundle["structure"]["policies"].items()}
    return dict(documents=bundle["documents"], source_catalog=sources(bundle), data_catalog=catalog,
                question_slots=bundle["question_slots"], active_goal_document=bundle["active_goal_document"],
                file_inventory=bundle["file_inventory"],
                finite_table_summaries={k: dict(headers=t["headers"], row_count=t["row_count"])
                                        for k, t in bundle["tables"].items()})
