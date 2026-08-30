"""Produce the committable CV from the original.

    python scripts/redact_cv.py evals/cases/case-01

Usually there is no need to run this by hand: the preflight rebuilds `cv.pdf` whenever
`cv-original.pdf` changes. This entry point exists for inspecting the redaction on its own
and for the reproduction guide, where the step deserves to be visible rather than implied.

The redaction itself lives in `solution/adapters/cv_redaction.py`.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from solution.adapters.cv_redaction import redact, verify  # noqa: E402


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2

    case_dir = Path(argv[1])
    source = case_dir / "cv-original.pdf"
    if not source.exists():
        print(f"missing {source}")
        return 1

    result = redact(source, case_dir / "cv.pdf")
    print(f"wrote {result.target}")
    print(f"  source digest: {result.source_digest[:16]}  (recorded in the PDF metadata)")
    for item in result.removed:
        print(f"  removed: {item}")

    still_readable = verify(result.target, result.removed)
    if still_readable:
        print(f"\nWARNING: still readable in the output: {list(still_readable)}")
        return 1
    print("\nVerified: none of the removed strings are readable in cv.pdf.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
