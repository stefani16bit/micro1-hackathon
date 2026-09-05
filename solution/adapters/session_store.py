"""Append-only session records.

Every question, answer, gate decision, scheduler state and model call is written here as
it happens. Two deliverables read from this file and nothing else: the metrics in
evals/results/ and the agent trajectories. Both would be worthless if the record could be
tidied up afterwards, so the store only ever appends.
"""

from __future__ import annotations

import json
import threading
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
    """Appends one JSON object per line. Safe to call from more than one thread.

    The lock is not decoration: from iteration 2 onwards the interviewer composes the next
    question in a background thread while the candidate answers, so two threads write to
    the same record. Without it their sequence numbers collide.
    """

    def __init__(self, path: Path | str, clock: Callable[[], float] = time.time) -> None:
        self.path = Path(path)
        self._clock = clock
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._sequence = self._count_existing()

    def _count_existing(self) -> int:
        """Read once at construction, so appending never re-reads the whole record."""
        if not self.path.exists():
            return 0
        with self.path.open("r", encoding="utf-8") as handle:
            return sum(1 for line in handle if line.strip())

    def append(self, event_type: str, **data: Any) -> SessionEvent:
        payload = {"type": event_type, "data": data}
        json.dumps(payload, ensure_ascii=False)

        with self._lock:
            self._sequence += 1
            event = SessionEvent(
                sequence=self._sequence,
                timestamp=self._clock(),
                type=event_type,
                data=data,
            )
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
