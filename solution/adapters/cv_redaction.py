"""Producing the committable CV from the original.

Reads `cv-original.pdf` (never committed) and writes `cv.pdf` with direct contact details
removed - not covered with a black rectangle, but deleted from the PDF's text layer, so
the parser downstream cannot read them either.

Kept deliberately: name, public professional profiles, and the entire professional
history. The candidate is the author of this project and signs their own work; what has
no place in a public repository is a personal phone number and email address
(agentic-workflows.md ground rule 8).

The digest of the source file is written into the redacted PDF's metadata. That is what
lets the preflight notice a swapped CV: the redacted file carries the identity of the
original it came from, so nothing has to stay in sync in a separate sidecar.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

import pymupdf

PATTERNS = (
    re.compile(r"\+?\d[\d\s()\-]{8,}\d"),
    re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"),
)

_SOURCE_KEY = "source-sha256="


def file_digest(path: Path | str) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def recorded_source_digest(redacted: Path | str) -> str | None:
    """The digest of the original this redacted CV was produced from, if it says."""
    path = Path(redacted)
    if not path.exists():
        return None
    try:
        with pymupdf.open(path) as document:
            keywords = (document.metadata or {}).get("keywords") or ""
    except Exception:
        return None
    for part in keywords.split():
        if part.startswith(_SOURCE_KEY):
            return part[len(_SOURCE_KEY) :]
    return None


@dataclass(frozen=True, slots=True)
class RedactionResult:
    target: Path
    removed: tuple[str, ...]
    source_digest: str


def redact(source: Path | str, target: Path | str) -> RedactionResult:
    source, target = Path(source), Path(target)
    digest = file_digest(source)
    document = pymupdf.open(source)
    removed: list[str] = []

    for page in document:
        text = page.get_text()
        for pattern in PATTERNS:
            for match in pattern.findall(text):
                candidate = match.strip()
                if len(candidate) < 6:
                    continue
                for rect in page.search_for(candidate):
                    page.add_redact_annot(rect, text="[redacted]", fill=(1, 1, 1))
                    removed.append(candidate)
        page.apply_redactions()

    metadata = dict(document.metadata or {})
    metadata["keywords"] = f"{_SOURCE_KEY}{digest}"
    document.set_metadata(metadata)
    document.save(target, garbage=4, deflate=True)
    document.close()

    return RedactionResult(target=target, removed=tuple(sorted(set(removed))), source_digest=digest)


def verify(target: Path | str, removed: tuple[str, ...]) -> tuple[str, ...]:
    """Return any removed string still readable in the output - empty means clean."""
    with pymupdf.open(target) as document:
        text = "\n".join(page.get_text() for page in document)
    return tuple(item for item in removed if item in text)
