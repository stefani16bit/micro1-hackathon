"""How the 25 minutes were spent.

Coverage is a set, so it is blind to the thing a candidate actually loses: an interviewer
that reaches every competency can still spend four of its ten questions on one situation
and leave the other five a question each. That is what this module measures. No model is
involved - the questions are already labelled, and these are counts over those labels.

Unresolved questions break a chain and stay out of the histogram, but stay in the
denominator: they were asked, and the candidate spent time on them.
"""

from __future__ import annotations

import math
from typing import Mapping, Sequence


def slot_histogram(slot_ids: Sequence[str | None]) -> dict[str, int]:
    """How many questions each competency received. Unresolved labels are excluded."""
    counts: dict[str, int] = {}
    for slot_id in slot_ids:
        if slot_id:
            counts[slot_id] = counts.get(slot_id, 0) + 1
    return dict(sorted(counts.items()))


def longest_chain(slot_ids: Sequence[str | None]) -> int:
    """The longest run of consecutive questions on the same competency.

    This is the direct measure of "three or four questions about one situation". An
    unresolved label breaks the run rather than extending it: a question nobody could
    label is not evidence that the interviewer stayed on topic, and assuming otherwise
    would make the metric flatter the interviewer exactly where the instrument is weakest.
    """
    best = 0
    current = 0
    previous: str | None = None

    for slot_id in slot_ids:
        if slot_id and slot_id == previous:
            current += 1
        elif slot_id:
            current = 1
        else:
            current = 0
        previous = slot_id
        best = max(best, current)

    return best


def max_slot_share(slot_ids: Sequence[str | None]) -> float:
    """The share of the question budget that went to the single most-asked competency.

    Denominated in every question asked, including the ones the cascade could not label -
    see the module docstring for why they stay in the denominator.
    """
    if not slot_ids:
        return 0.0
    counts = slot_histogram(slot_ids)
    if not counts:
        return 0.0
    return max(counts.values()) / len(slot_ids)


def normalised_entropy(slot_ids: Sequence[str | None], denominator: int) -> float:
    """How evenly the questions were spread, on a 0-1 scale.

    1.0 is one question per competency across all of them; 0.0 is every question on one.
    Normalised by `log(denominator)` - the entropy of a perfectly even interview over the
    frozen plan - so the number means the same thing for a plan of six slots and a plan of
    ten, and can be compared across roles.
    """
    counts = slot_histogram(slot_ids)
    total = sum(counts.values())
    if total == 0 or denominator <= 1:
        return 0.0

    entropy = -sum((n / total) * math.log(n / total) for n in counts.values())
    return max(0.0, entropy / math.log(denominator))


def describe(slot_ids: Sequence[str | None], denominator: int) -> dict:
    """Everything above, as one block for the session's `.metrics.json`."""
    counts = slot_histogram(slot_ids)
    return {
        "questions": len(slot_ids),
        "unresolved": sum(1 for slot_id in slot_ids if not slot_id),
        "slot_histogram": counts,
        "longest_chain": longest_chain(slot_ids),
        "max_slot_share": round(max_slot_share(slot_ids), 3),
        "normalised_entropy": round(normalised_entropy(slot_ids, denominator), 3),
        "most_asked_slot": max(counts, key=counts.get) if counts else None,
    }


def render(allocation: Mapping[str, object], ceiling: int | None = None) -> list[str]:
    """The allocation block as it appears under `interview measure`.

    `ceiling` is what the schedule guarantees for this iteration, when it guarantees
    anything. Printing the two together is the whole point: a chain of 4 means nothing on
    its own, and means a great deal beside a ceiling of 2.
    """
    chain = allocation.get("longest_chain", 0)
    chain_line = f"  longest chain    {chain} consecutive questions on one competency"
    if ceiling is not None:
        chain_line += f"   (the schedule allows {ceiling})"

    histogram = allocation.get("slot_histogram") or {}
    spread = "  ".join(f"{slot}:{count}" for slot, count in histogram.items()) or "-"

    return [
        "",
        chain_line,
        f"  most asked       {allocation.get('most_asked_slot') or '-'}"
        f"   ({float(allocation.get('max_slot_share') or 0):.0%} of the questions)",
        f"  spread           {float(allocation.get('normalised_entropy') or 0):.2f}"
        f"   (1.00 is one question per competency)",
        f"  per competency   {spread}",
    ]
