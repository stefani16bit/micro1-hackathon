"""Interview state. Every transition returns a new state, so a session's history is a
list of immutable snapshots rather than a mutable object nobody can reconstruct later."""

from __future__ import annotations

from dataclasses import dataclass, replace
from types import MappingProxyType
from typing import Iterable, Mapping

from solution.domain.models import Slot


@dataclass(frozen=True, slots=True)
class SlotProgress:
    slot_id: str
    primary_asked: bool = False
    followups_asked: int = 0
    closed: bool = False


@dataclass(frozen=True, slots=True)
class SessionState:
    slots: tuple[Slot, ...]
    progress: Mapping[str, SlotProgress]
    elapsed_seconds: int = 0
    opening_asked: bool = False

    @classmethod
    def initial(cls, slots: Iterable[Slot]) -> SessionState:
        ordered = tuple(sorted(slots, key=lambda s: s.rank))
        return cls(
            slots=ordered,
            progress=MappingProxyType({s.id: SlotProgress(s.id) for s in ordered}),
        )

    def evolve(self, **changes) -> SessionState:
        return replace(self, **changes)

    def _with_progress(self, slot_id: str, **changes) -> SessionState:
        updated = dict(self.progress)
        updated[slot_id] = replace(self.progress[slot_id], **changes)
        return replace(self, progress=MappingProxyType(updated))

    def with_primary_asked(self, slot_id: str) -> SessionState:
        return self._with_progress(slot_id, primary_asked=True)

    def with_followup_asked(self, slot_id: str) -> SessionState:
        current = self.progress[slot_id].followups_asked
        return self._with_progress(slot_id, followups_asked=current + 1)

    def with_closed(self, slot_id: str) -> SessionState:
        return self._with_progress(slot_id, closed=True)

    @property
    def open_slots(self) -> tuple[Slot, ...]:
        return tuple(s for s in self.slots if not self.progress[s.id].closed)

    @property
    def remaining_primaries(self) -> int:
        """Slots that still owe the candidate their one guaranteed question."""
        return sum(
            1
            for s in self.slots
            if not self.progress[s.id].closed and not self.progress[s.id].primary_asked
        )
