"""Iteration 0 - the single-prompt interviewer.

One prompt, the full transcript on every turn, and the model deciding everything else.
No slot plan, no coverage tracking, no verification. This is the floor the ladder is
measured against, and `PREREGISTRATION.md` states what we expect the floor to look like
before it was ever run.

The prompts are read from `baseline/prompt.md`, so the file a reviewer reads is the file
that executes.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from solution.adapters.prompt_files import fill, load_prompt_pair
from solution.adapters.providers.base import LlmProvider, LlmRequest
from solution.application.runner import Interviewer
from solution.domain.models import TimeBudget
from solution.domain.transcript import Transcript, Utterance

SCHEMA: Mapping[str, Any] = {
    "type": "object",
    "properties": {"message": {"type": "string"}},
    "required": ["message"],
}


class SinglePromptInterviewer(Interviewer):
    label = "iteration-0-single-prompt"

    def __init__(
        self,
        provider: LlmProvider,
        role_text: str,
        resume_text: str,
        budget: TimeBudget,
        prompt_path: Path | str = "baseline/prompt.md",
    ) -> None:
        system_template, self._user_template = load_prompt_pair(prompt_path)
        self._system = fill(system_template, role=role_text, resume=resume_text)
        self._provider = provider
        self._budget = budget

    def next_utterance(self, transcript: Transcript) -> Utterance | None:
        prompt = fill(
            self._user_template,
            transcript=transcript.render() or "(the interview has not started yet)",
        )
        response = self._provider.complete_json(
            LlmRequest(
                call="baseline_turn",
                system=self._system,
                prompt=prompt,
                schema=SCHEMA,
            )
        )
        return Utterance(
            text=str(response.payload["message"]).strip(),
            kind="opening" if not transcript.entries else "question",
            slot_id=None,
        )
