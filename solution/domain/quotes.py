"""Verbatim-quote checking.

A model asked for verbatim text will occasionally return a fluent paraphrase instead, so
the claim is checked rather than trusted: a quote that fails never reaches the report and
the slot is recorded as unevidenced. `research/interview-guidance.md` section 8 - "a rating
without a quote is an impression" - only holds if the quote is real.
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
