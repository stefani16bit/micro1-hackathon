"""Produce the committable CV from the original.

    python scripts/redact_cv.py evals/cases/case-01

Reads `cv-original.pdf` (never committed) and writes `cv.pdf` with direct contact details
removed - not covered with a black rectangle, but deleted from the PDF's text layer, so
the parser downstream cannot read them either.

Kept deliberately: name, public professional profiles, and the entire professional
history. The candidate is the author of this project and signs their own work; what has
no place in a public repository is a personal phone number and email address
(CLAUDE.md ground rule 8).

The script exists so the redaction is reproducible and reviewable rather than a manual
step nobody can check.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pymupdf

# Patterns for direct contact details. Anything matching is removed from the text layer.
PATTERNS = (
    re.compile(r"\+?\d[\d\s()\-]{8,}\d"),  # phone numbers
    re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"),  # email addresses
)


def redact(source: Path, target: Path) -> list[str]:
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

    document.save(target, garbage=4, deflate=True)
    document.close()
    return removed


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2

    case_dir = Path(argv[1])
    source = case_dir / "cv-original.pdf"
    target = case_dir / "cv.pdf"

    if not source.exists():
        print(f"missing {source}")
        return 1

    removed = redact(source, target)
    print(f"wrote {target}")
    for item in sorted(set(removed)):
        print(f"  removed: {item}")

    leftovers = pymupdf.open(target)[0].get_text()
    still_there = [item for item in set(removed) if item in leftovers]
    if still_there:
        print(f"\nWARNING: still readable in the output: {still_there}")
        return 1
    print("\nVerified: none of the removed strings are readable in cv.pdf.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
