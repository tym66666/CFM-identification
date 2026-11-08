"""Strict, offline audit I/O. Failure reports never echo file contents."""
from collections import Counter
import hashlib
import json
import math
from pathlib import Path


class AuditFailure(ValueError):
    def __init__(self, code, artifact=None):
        super().__init__(code)
        self.code = code
        self.artifact = Path(artifact).name if artifact else None

    def record(self):
        return dict(classification=self.code, artifact=self.artifact)


def require(condition, code, artifact=None):
    if not condition:
        raise AuditFailure(code, artifact)


def strict_json(text, artifact=None):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate")
            result[key] = value
        return result

    def constant(_):
        raise ValueError("nonfinite")

    def finite(value):
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError("nonfinite")
        if isinstance(value, dict):
            for v in value.values():
                finite(v)
        if isinstance(value, list):
            for v in value:
                finite(v)
    try:
        value = json.loads(text, object_pairs_hook=pairs, parse_constant=constant)
        finite(value)
        return value
    except (ValueError, RecursionError):
        raise AuditFailure("ARTIFACT_PARSE_FAILURE", artifact) from None


def read_bytes(path):
    try:
        return Path(path).read_bytes()
    except FileNotFoundError:
        raise AuditFailure("ARTIFACT_MISSING", path) from None
    except OSError:
        raise AuditFailure("ARTIFACT_IO_FAILURE", path) from None


def read_json(path):
    try:
        text = read_bytes(path).decode("utf-8-sig")
    except UnicodeError:
        raise AuditFailure("ARTIFACT_PARSE_FAILURE", path) from None
    return strict_json(text, path)


def digest(path):
    return hashlib.sha256(read_bytes(path)).hexdigest()


def inside(base, relative):
    base = Path(base).resolve()
    path = Path(relative)
    require(not path.is_absolute() and ".." not in path.parts, "INVALID_ARTIFACT_PATH")
    resolved = (base / path).resolve()
    require(resolved.is_relative_to(base), "INVALID_ARTIFACT_PATH")
    return resolved


def ratio(numerator, denominator):
    return dict(numerator=numerator, denominator=denominator,
                rate=numerator / denominator if denominator else None)


def write_report(path, report):
    """Never overwrite old evidence, including on malformed-input exits."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf8") as handle:
        handle.write(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def status_counts(rows):
    return dict(Counter(r["classification"] for r in rows))
