"""Append-only session records.

Every question, answer, gate decision, scheduler state and model call is written here as
it happens. Two deliverables read from this file and nothing else: the metrics in
evals/results/ and the agent trajectories. Both would be worthless if the record could be
tidied up afterwards, so the store only ever appends.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping


@dataclass(frozen=True, slots=True)
class SessionEvent:
    sequence: int
    timestamp: float
    type: str
    data: Mapping[str, Any]


class SessionStore:
    def __init__(self, path: Path | str, clock: Callable[[], float] = time.time) -> None:
        self.path = Path(path)
        self._clock = clock
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _next_sequence(self) -> int:
        if not self.path.exists():
            return 1
        with self.path.open("r", encoding="utf-8") as handle:
            return sum(1 for line in handle if line.strip()) + 1

    def append(self, event_type: str, **data: Any) -> SessionEvent:
        event = SessionEvent(
            sequence=self._next_sequence(),
            timestamp=self._clock(),
            type=event_type,
            data=data,
        )
        # Serialise before opening the file: a payload that cannot be written must fail
        # without leaving a truncated line behind.
        line = json.dumps(
            {
                "seq": event.sequence,
                "ts": event.timestamp,
                "type": event.type,
                "data": event.data,
            },
            ensure_ascii=False,
        )
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
        return event

    def events(self) -> tuple[SessionEvent, ...]:
        if not self.path.exists():
            return ()
        records = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            raw = json.loads(line)
            records.append(
                SessionEvent(
                    sequence=raw["seq"],
                    timestamp=raw["ts"],
                    type=raw["type"],
                    data=raw.get("data", {}),
                )
            )
        return tuple(records)
