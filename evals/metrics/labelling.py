"""Deciding which competency a question was about.

**The instrument never reads the interviewer's own label.** Iteration 0 cannot produce one
- it has no slot concept - so measuring later iterations by self-report would apply a
different instrument to each end of the ladder and make the comparison meaningless. Every
question from every iteration is labelled here from its text alone.

This is the rule layer of the cascade. Questions it cannot resolve go to a blind judge,
and the share resolved by each layer is reported with every result, so a reader can see
how much of a number rests on a model's opinion. That share is the reason the matching
below bothers with inflection: a keyword form the rule fails to recognise does not go
away, it moves a piece of the headline number out of code and into a model's opinion.

Matching stays word-bounded and morphological rather than prefix-based, because a prefix
match would count "reaction" as "react" - and a false positive here silently inflates
coverage, which is the one number the whole project rests on.
"""

from __future__ import annotations

import re
from typing import Sequence

from solution.domain.models import Slot

_ADDED_SUFFIXES = ("s", "es", "ed", "ing", "er", "ers")
_IDENTIFIER_MARKS = ".+#/"


def _stem(word: str) -> str:
    """Strip one inflectional ending, undoing a doubled consonant if there is one."""
    for suffix in ("ing", "ed"):
        if word.endswith(suffix) and len(word) - len(suffix) >= 3:
            root = word[: -len(suffix)]
            if len(root) >= 4 and root[-1] == root[-2] and root[-1] not in "aeiou":
                return root[:-1]  # debugging -> debugg -> debug
            return root
    if word.endswith("ies") and len(word) > 4:
        return word[:-3] + "y"
    if word.endswith("s") and not word.endswith("ss") and len(word) > 3:
        return word[:-1]
    return word


def inflections(keyword: str) -> set[str]:
    """The written forms a keyword plausibly takes in a question.

    Identifiers containing punctuation (node.js, C++) are left exactly as they are: they
    do not inflect, and generating forms for them would only invite false positives.
    Multi-word keywords inflect on their last word only - "code review" becomes
    "code reviews", never "codes review".
    """
    keyword = keyword.lower().strip()
    if any(mark in keyword for mark in _IDENTIFIER_MARKS):
        return {keyword}

    head, _, last = keyword.rpartition(" ")
    base = last or keyword
    root = _stem(base)

    forms = {base, root}
    forms.update(root + suffix for suffix in _ADDED_SUFFIXES)
    if root.endswith("y") and len(root) > 2:
        forms.add(root[:-1] + "ies")
    if root.endswith("e") and len(root) > 2:
        forms.update({root[:-1] + "ed", root[:-1] + "ing"})
    if len(root) >= 3 and root[-1] not in "aeiou":
        forms.update({root + root[-1] + "ing", root + root[-1] + "ed"})

    prefix = f"{head} " if head else ""
    return {prefix + form for form in forms}


def mentions_keyword(text: str, keyword: str) -> bool:
    """Word-boundary match on any inflected form, so 'reaction' never counts as 'react'."""
    lowered = text.lower()
    return any(
        re.search(rf"(?<!\w){re.escape(form)}(?!\w)", lowered) for form in inflections(keyword)
    )


def slots_named_in(question: str, slots: Sequence[Slot]) -> tuple[str, ...]:
    matched = []
    for slot in slots:
        vocabulary = (slot.name, *slot.keywords)
        if any(mentions_keyword(question, phrase) for phrase in vocabulary):
            matched.append(slot.id)
    return tuple(matched)


def label_by_rule(question: str, slots: Sequence[Slot]) -> str | None:
    """Return the slot this question is about, or None if the rule cannot say.

    None means one of two things, and both are escalated rather than guessed: the question
    names no slot vocabulary at all, or it names more than one. Slot keywords are disjoint
    by construction, so a question matching two slots genuinely spans them - and a
    question that genuinely spans frontend, backend and the database is usually asking
    about the boundary, which only a judge reading the whole sentence can see.
    """
    matched = slots_named_in(question, slots)
    return matched[0] if len(matched) == 1 else None
