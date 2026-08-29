"""Verbatim-quote checking.

Every per-slot rating in the final report carries a quote from the candidate as its
evidence - `research/interview-guidance.md` section 8: "a rating without a quote is an
impression". That only holds if the quote is real. A model asked for verbatim text
will occasionally return a fluent paraphrase, so the claim is checked here instead of
trusted, and a quote that fails this check never reaches the report.
"""

from __future__ import annotations

import re

_ZERO_WIDTH = str.maketrans({"​": "", "‌": "", "‍": "", "﻿": ""})
_WHITESPACE = re.compile(r"\s+")


def normalise(text: str) -> str:
    """Collapse the differences that PDF extraction introduces but meaning does not."""
    return _WHITESPACE.sub(" ", text.translate(_ZERO_WIDTH)).strip().casefold()


def quote_is_verbatim(quote: str, source: str) -> bool:
    normalised_quote = normalise(quote)
    if not normalised_quote:
        return False
    return normalised_quote in normalise(source)
