"""The port every model call goes through.

One interface, several adapters, chosen in config.yaml. The result claimed by this
project is about the architecture, not about one model, and that claim is only honest if
swapping the model is a one-line change a reviewer can make and verify.
"""

from __future__ import annotations

import hashlib
import json
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Mapping


class MalformedResponse(RuntimeError):
    """The model returned something that is not the JSON object the call asked for."""


@dataclass(frozen=True, slots=True)
class LlmRequest:
    call: str  # L1-L7 in the plan; also the label used in trajectories
    system: str
    prompt: str
    schema: Mapping[str, Any]

    @property
    def fingerprint(self) -> str:
        """Identity of this call, used to key recorded fixtures."""
        material = json.dumps(
            {
                "call": self.call,
                "system": self.system,
                "prompt": self.prompt,
                "schema": self.schema,
            },
            sort_keys=True,
            ensure_ascii=False,
        )
        return hashlib.sha256(material.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class LlmResponse:
    call: str
    payload: Mapping[str, Any]
    raw: str
    provider: str
    model: str
    fingerprint: str
    duration_ms: int


def _extract_value(text: str) -> str | None:
    """Find the first balanced JSON object *or array*, ignoring brackets inside strings.

    Arrays are matched as well as objects on purpose. Scanning for `{` alone would reach
    inside a top-level array and return its first element - which parses cleanly and is
    the wrong answer, the worst kind of failure. Taking the outermost value instead lets
    the caller reject the wrong shape with a message that says what it got.

    Bracket types are counted together rather than matched pairwise; genuinely mismatched
    brackets are left for json.loads to report, which it does better than this loop could.
    """
    depth = 0
    start: int | None = None
    in_string = False
    escaped = False

    for index, character in enumerate(text):
        if in_string:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                in_string = False
            continue
        if character == '"':
            in_string = True
        elif character in "{[":
            if depth == 0:
                start = index
            depth += 1
        elif character in "}]" and depth:
            depth -= 1
            if depth == 0 and start is not None:
                return text[start : index + 1]
    return None


def parse_json_payload(raw: str) -> Mapping[str, Any]:
    """Read the JSON object out of a model response.

    Models wrap objects in prose and fenced blocks no matter how firmly the prompt asks
    them not to, so this tolerates the wrapping rather than pretending it never happens.
    """
    candidate = _extract_value(raw)
    if candidate is None:
        raise MalformedResponse(f"no JSON found in response: {raw[:200]!r}")
    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError as error:
        raise MalformedResponse(f"invalid JSON: {error}") from error
    if isinstance(parsed, list):
        raise MalformedResponse(
            "expected a JSON object at the top level but got an array; the schema's "
            "required keys have to be on an object wrapping it"
        )
    if not isinstance(parsed, dict):
        raise MalformedResponse(f"expected a JSON object at the top level, got {type(parsed).__name__}")
    return parsed


def _require_declared_keys(payload: Mapping[str, Any], request: LlmRequest) -> None:
    required = tuple(request.schema.get("required", ()))
    missing = [key for key in required if key not in payload]
    if missing:
        raise MalformedResponse(f"response omitted required keys {missing}")


class LlmProvider(ABC):
    name: str = "unknown"
    model: str = "unknown"

    @abstractmethod
    def _invoke(self, request: LlmRequest) -> str:
        """Return the raw text the model produced."""

    def complete_json(self, request: LlmRequest, *, max_attempts: int = 2) -> LlmResponse:
        failures: list[str] = []
        for attempt in range(1, max_attempts + 1):
            started = time.perf_counter()
            raw = self._invoke(request)
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            try:
                payload = parse_json_payload(raw)
                _require_declared_keys(payload, request)
            except MalformedResponse as error:
                failures.append(f"attempt {attempt}: {error}")
                continue
            return LlmResponse(
                call=request.call,
                payload=payload,
                raw=raw,
                provider=self.name,
                model=self.model,
                fingerprint=request.fingerprint,
                duration_ms=elapsed_ms,
            )
        raise MalformedResponse(
            f"{request.call} failed after {max_attempts} attempts: " + "; ".join(failures)
        )
