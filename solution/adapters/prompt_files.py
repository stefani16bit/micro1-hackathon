"""Reading prompts out of the markdown files that document them.

Agent instructions are a graded deliverable: a reviewer must be able to read the prompt
that was actually used. The usual way that goes wrong is a prompt documented in one file
and executed from a string literal in another, which drift apart within a week.

So the documentation is the source: the fenced code blocks in the markdown file are the
prompt, and there is no second copy to fall out of date.
"""

from __future__ import annotations

import re
from pathlib import Path

_FENCED = re.compile(r"^```[a-zA-Z]*\n(.*?)^```", re.MULTILINE | re.DOTALL)


class PromptFileError(ValueError):
    """The markdown file does not contain the prompts it was expected to."""


def load_fenced_blocks(path: Path | str) -> tuple[str, ...]:
    text = Path(path).read_text(encoding="utf-8")
    return tuple(match.group(1).rstrip("\n") for match in _FENCED.finditer(text))


def load_prompt_pair(path: Path | str) -> tuple[str, str]:
    """Return (system prompt, user prompt template) from the first two fenced blocks."""
    blocks = load_fenced_blocks(path)
    if len(blocks) < 2:
        raise PromptFileError(
            f"{path} has {len(blocks)} fenced block(s); expected a system prompt and a "
            "user prompt template"
        )
    return blocks[0], blocks[1]


def fill(template: str, **values: str) -> str:
    """Substitute <<PLACEHOLDER>> markers, failing loudly on any left unfilled."""
    result = template
    for key, value in values.items():
        result = result.replace(f"<<{key.upper()}>>", value)
    leftover = re.findall(r"<<[A-Z_]+>>", result)
    if leftover:
        raise PromptFileError(f"unfilled placeholders in prompt: {sorted(set(leftover))}")
    return result
