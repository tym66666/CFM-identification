"""Bounded original-line evidence units; no claim-aware expansion or repair.

Never combine documents or nonadjacent lines. Full materials remain available.
Offsets count Python Unicode characters, end exclusive. Large lines are split
deterministically without dropping or overlapping characters.
"""
from hashlib import sha256
from .audit import fingerprint_business_case
from .quality_formulator import A0QualityValidationError

MAX_CHARS = 1000


def build_catalog(case):
    prefix = fingerprint_business_case(case)[:12]
    rows = []
    for source_id, text in case.source_map().items():
        offset = 0
        for line in text.splitlines(keepends=True):
            start, end = offset, offset + len(line)
            offset = end
            if not line.strip() or len(line) < 2:
                continue  # Full materials retain non-citable one-character lines.
            while start < end:
                stop = min(start + MAX_CHARS, end)
                if end - stop == 1:
                    stop -= 1  # Keep a two-character tail; no overlap or loss.
                quote = text[start:stop]
                rows.append(dict(ref=f'p{prefix}_{len(rows)+1:04d}',source_id=source_id,
                    start=start,end=stop,quote=quote,
                    sha256=sha256(quote.encode('utf8')).hexdigest(),
                    document_sha256=sha256(text.encode('utf8')).hexdigest()))
                if len(rows) > 512:
                    raise A0QualityValidationError('Source catalog exceeds limit',code='A0_REFERENCE_CATALOG_LIMIT')
                start = stop
    return rows
