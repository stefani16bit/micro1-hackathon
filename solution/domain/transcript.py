"""The record of one interview as it unfolds.

Time is accumulated here rather than read from a wall clock at the end, because both
halves of a turn cost the candidate something: the interviewer's thinking time comes out
of the same 25 minutes the candidate's answers do. Measuring only the answers would hide
a slow interviewer behind a shortened interview.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum


class Speaker(str, Enum):
    INTERVIEWER = "interviewer"
    CANDIDATE = "candidate"


@dataclass(frozen=True, slots=True)
class Utterance:
    text: str
    kind: str  # opening | primary | follow_up | clarification
    slot_id: str | None = None  # None before iteration 4, which has no slot concept


@dataclass(frozen=True, slots=True)
class Answer:
    text: str
    seconds_used: float
    over_deadline: bool = False


@dataclass(frozen=True, slots=True)
class TranscriptEntry:
    speaker: Speaker
    text: str
    seconds: float
    kind: str = ""
    slot_id: str | None = None
    over_deadline: bool = False


@dataclass(frozen=True, slots=True)
class Transcript:
    entries: tuple[TranscriptEntry, ...] = ()

    def with_question(self, utterance: Utterance, seconds: float) -> Transcript:
        entry = TranscriptEntry(
            speaker=Speaker.INTERVIEWER,
            text=utterance.text,
            seconds=seconds,
            kind=utterance.kind,
            slot_id=utterance.slot_id,
        )
        return replace(self, entries=self.entries + (entry,))

    def with_answer(self, answer: Answer) -> Transcript:
        entry = TranscriptEntry(
            speaker=Speaker.CANDIDATE,
            text=answer.text,
            seconds=answer.seconds_used,
            over_deadline=answer.over_deadline,
        )
        return replace(self, entries=self.entries + (entry,))

    @property
    def elapsed_seconds(self) -> float:
        return sum(entry.seconds for entry in self.entries)

    @property
    def questions(self) -> tuple[TranscriptEntry, ...]:
        return tuple(e for e in self.entries if e.speaker is Speaker.INTERVIEWER)

    @property
    def answers(self) -> tuple[TranscriptEntry, ...]:
        return tuple(e for e in self.entries if e.speaker is Speaker.CANDIDATE)

    def render(self) -> str:
        """The transcript as the model sees it, when the model is allowed to see it."""
        label = {Speaker.INTERVIEWER: "Interviewer", Speaker.CANDIDATE: "Candidate"}
        return "\n\n".join(f"{label[e.speaker]}: {e.text}" for e in self.entries)
