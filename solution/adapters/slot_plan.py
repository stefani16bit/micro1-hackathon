"""Loading the frozen slot plan.

The plan is produced once from the job description, reviewed by a human, and committed.
After that it is read-only for the rest of the project: it is the denominator of the
primary metric, so a plan that changes between runs would silently invalidate the whole
comparison. Validation here is strict for the same reason.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

import yaml

from solution.domain.models import Slot, SlotKind


class SlotPlanError(ValueError):
    """The slot plan on disk is not usable as the basis of a measurement."""


@dataclass(frozen=True, slots=True)
class SlotPlan:
    role: str
    source: str
    frozen_at: str
    slots: tuple[Slot, ...]
    excluded: tuple[Mapping[str, Any], ...] = field(default_factory=tuple)

    @property
    def denominator(self) -> int:
        """Coverage is measured over exactly these slots."""
        return len(self.slots)

    @property
    def keywords(self) -> frozenset[str]:
        return frozenset(k.lower() for slot in self.slots for k in slot.keywords)

    def by_id(self, slot_id: str) -> Slot:
        for slot in self.slots:
            if slot.id == slot_id:
                return slot
        raise KeyError(slot_id)


def _build_slot(raw: Mapping[str, Any], index: int) -> Slot:
    where = f"slot #{index + 1}"
    try:
        slot_id = str(raw["id"])
        name = str(raw["name"])
        rank = int(raw["rank"])
        kind_value = str(raw["kind"])
        keywords = tuple(str(k).strip() for k in raw.get("keywords", []) if str(k).strip())
    except KeyError as error:
        raise SlotPlanError(f"{where} is missing required field {error}") from error

    if not keywords:
        raise SlotPlanError(
            f"{where} ({slot_id}) declares no keywords; carry-over detection needs them"
        )

    try:
        kind = SlotKind(kind_value)
    except ValueError as error:
        allowed = ", ".join(k.value for k in SlotKind)
        raise SlotPlanError(
            f"{where} ({slot_id}) has unknown kind {kind_value!r}; "
            f"expected one of {allowed}"
        ) from error

    return Slot(id=slot_id, name=name, kind=kind, keywords=keywords, rank=rank)


def load_slot_plan(path: Path | str) -> SlotPlan:
    source_path = Path(path)
    document = yaml.safe_load(source_path.read_text(encoding="utf-8")) or {}
    raw_slots = document.get("slots") or []

    if not raw_slots:
        raise SlotPlanError(f"{source_path} declares no slots; a plan needs at least one")

    slots = tuple(_build_slot(raw, index) for index, raw in enumerate(raw_slots))

    identifiers = [slot.id for slot in slots]
    duplicates = {i for i in identifiers if identifiers.count(i) > 1}
    if duplicates:
        raise SlotPlanError(f"duplicate slot ids: {sorted(duplicates)}")

    ranks = sorted(slot.rank for slot in slots)
    if ranks != list(range(1, len(slots) + 1)):
        raise SlotPlanError(
            f"rank must be a contiguous sequence from 1 to {len(slots)}; found {ranks}"
        )

    return SlotPlan(
        role=str(document.get("role", "")),
        source=str(document.get("source", "")),
        frozen_at=str(document.get("frozen_at", "")),
        slots=tuple(sorted(slots, key=lambda s: s.rank)),
        excluded=tuple(document.get("excluded") or ()),
    )
