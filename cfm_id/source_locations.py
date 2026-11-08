"""Exact source locations for untrusted business materials.

A paragraph here means one nonblank original line, including its original
line ending. Blank lines have no record but remain part of the document hash
and offsets. No text, whitespace, line ending, or Unicode normalization occurs.

start/end use Python Unicode string indices (end exclusive), not UTF-8 byte
offsets or JavaScript UTF-16 code-unit offsets. Resolve on the Python side and
send the returned text to other runtimes instead of slicing with their indices.

A locator binds the document identity, the entire document, the location, and
the exact line. Any change anywhere in that document invalidates all its old
locators. Resolution establishes provenance only, never semantic entailment,
scientific approval, or identification.
"""
from __future__ import annotations

import hashlib
import json


def _sha256(text: str) -> str:
    try:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()
    except UnicodeEncodeError:
        raise ValueError("SOURCE_TEXT_MUST_BE_VALID_UTF8") from None


def build_catalog(documents: dict[str, str]) -> dict[str, dict]:
    """Index nonblank original lines without modifying the documents.

    Documents must be a nonempty dict with nonblank string IDs and string
    contents. Empty or whitespace-only documents are valid and yield no lines.
    sha256 hashes the exact returned text; document_sha256 hashes the complete
    original document, including blank lines.
    """
    if not isinstance(documents, dict) or not documents:
        raise ValueError("DOCUMENTS_MUST_BE_NONEMPTY_MAPPING")
    for doc_id, content in documents.items():
        if not isinstance(doc_id, str) or not doc_id.strip():
            raise ValueError("DOCUMENT_ID_MUST_BE_NONBLANK_STRING")
        if not isinstance(content, str):
            raise ValueError("DOCUMENT_CONTENT_MUST_BE_STRING")

    catalog = {}
    for doc_id, content in documents.items():
        document_sha256 = _sha256(content)
        offset = 0
        for text in content.splitlines(keepends=True):
            start, end = offset, offset + len(text)
            offset = end
            if not text.strip():
                continue
            text_sha256 = _sha256(text)
            binding = {
                "doc_id": doc_id,
                "document_sha256": document_sha256,
                "start": start,
                "end": end,
                "text_sha256": text_sha256,
            }
            source_id = "src_" + _sha256(json.dumps(
                binding, ensure_ascii=False, sort_keys=True,
                separators=(",", ":"),
            ))
            if source_id in catalog:
                raise ValueError("SOURCE_ID_COLLISION")
            catalog[source_id] = {
                "source_id": source_id,
                "doc_id": doc_id,
                "start": start,
                "end": end,
                "text": text,
                "sha256": text_sha256,
                "document_sha256": document_sha256,
            }
    return catalog


def resolve_sources(documents: dict[str, str], ids: list[str]) -> list[dict]:
    """Resolve distinct current IDs, in requested order, from rebuilt sources.

    No caller-provided catalog, quote, offset, or hash is trusted. Empty lists,
    duplicate IDs, unknown IDs, and locators from changed documents are rejected.
    """
    if not isinstance(ids, list) or not ids:
        raise ValueError("SOURCE_IDS_MUST_BE_NONEMPTY_LIST")
    if any(not isinstance(source_id, str) or not source_id.strip()
           for source_id in ids):
        raise ValueError("SOURCE_ID_MUST_BE_NONBLANK_STRING")
    if len(set(ids)) != len(ids):
        raise ValueError("SOURCE_IDS_MUST_BE_UNIQUE")
    catalog = build_catalog(documents)
    if any(source_id not in catalog for source_id in ids):
        raise ValueError("SOURCE_ID_UNKNOWN_OR_STALE")
    return [catalog[source_id] for source_id in ids]

