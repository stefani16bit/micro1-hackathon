"""Technical-term extraction.

The carry-over metric is a set comparison, not a judgement call, and this module is what
makes that possible. It is deliberately conservative: it recognises terms it can justify
(a curated lexicon, internal capitalisation, acronyms, dotted or suffixed identifiers)
and stays silent otherwise. A term it misses is a tunnel it will not detect, so the
lexicon is committed to the repository and reviewed alongside the slot plan.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable

_TRIM = ".,;:!?()[]{}<>\"'`"
_SPLIT = re.compile(r"[\s/]+")

_BASE_LEXICON_PATH = Path(__file__).parent / "data" / "tech_lexicon.txt"


def _tokens(text: str) -> Iterable[str]:
    for raw in _SPLIT.split(text):
        token = raw.strip(_TRIM)
        if token:
            yield token


def _looks_technical(token: str) -> bool:
    if len(token) < 2:
        return False
    if any(character.isupper() for character in token[1:]):
        return True  # PostgreSQL, GraphQL, JavaScript
    if token.isupper() and token.isalpha():
        return True  # API, AWS, JWT
    if any(mark in token for mark in ".+#") and any(c.isalpha() for c in token):
        return True  # Node.js, C++, C#
    return False


def extract_terms(text: str, lexicon: frozenset[str]) -> frozenset[str]:
    """Return the normalised technical terms present in `text`."""
    lowered = text.lower()
    found: set[str] = set()

    for phrase in lexicon:
        if " " in phrase and re.search(rf"(?<!\w){re.escape(phrase)}(?!\w)", lowered):
            found.add(phrase)

    for token in _tokens(text):
        normalised = token.lower()
        if normalised in lexicon or _looks_technical(token):
            found.add(normalised)

    return frozenset(found)


def load_base_lexicon(path: Path | None = None) -> frozenset[str]:
    source = path or _BASE_LEXICON_PATH
    if not source.exists():
        return frozenset()
    lines = source.read_text(encoding="utf-8").splitlines()
    return frozenset(
        line.strip().lower() for line in lines if line.strip() and not line.startswith("#")
    )


def build_lexicon(
    slot_keywords: Iterable[str], base: frozenset[str] | None = None
) -> frozenset[str]:
    """The working lexicon is the committed base list plus every keyword the frozen slot
    plan declares, so the role's own vocabulary is always recognised."""
    resolved = load_base_lexicon() if base is None else base
    return frozenset(resolved | {keyword.strip().lower() for keyword in slot_keywords})
