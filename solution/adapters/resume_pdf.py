"""Reading a CV out of a PDF."""

from __future__ import annotations

from pathlib import Path


def read_resume_text(path: Path | str) -> str:
    """Extract the text layer of a CV, page by page.

    No layout reconstruction and no cleaning: the text is passed on as the PDF holds it,
    because the verbatim-quote check downstream compares against exactly this string.
    Silently tidying it here would make quotes that are genuinely in the CV fail.
    """
    import pymupdf

    with pymupdf.open(path) as document:
        return "\n".join(page.get_text() for page in document)
