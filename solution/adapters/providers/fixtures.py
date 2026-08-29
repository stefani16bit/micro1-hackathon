"""Recorded model responses, so the test suite needs no model, no network and no key.

Fixtures are keyed by request fingerprint. Change a prompt and the fingerprint changes,
which surfaces as a missing fixture rather than as a stale recording quietly replayed -
that silent staleness is what makes recorded tests untrustworthy.
"""

from __future__ import annotations

import json
from pathlib import Path

from solution.adapters.providers.base import LlmProvider, LlmRequest


class UnknownFixture(RuntimeError):
    """No response was recorded for this exact request."""


class FixtureProvider(LlmProvider):
    name = "fixture"
    model = "fixture"

    def __init__(self, directory: Path) -> None:
        self.directory = Path(directory)

    def _invoke(self, request: LlmRequest) -> str:
        path = self.directory / f"{request.fingerprint}.json"
        if not path.exists():
            raise UnknownFixture(
                f"no recorded response for fingerprint {request.fingerprint} "
                f"(call={request.call}); re-record with the recording provider"
            )
        return json.loads(path.read_text(encoding="utf-8"))["raw"]


class RecordingProvider(LlmProvider):
    """Wraps a live provider and writes every response to the fixture directory."""

    def __init__(self, inner: LlmProvider, directory: Path) -> None:
        self.inner = inner
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)

    @property
    def name(self) -> str:
        return self.inner.name

    @property
    def model(self) -> str:
        return self.inner.model

    def _invoke(self, request: LlmRequest) -> str:
        raw = self.inner._invoke(request)
        path = self.directory / f"{request.fingerprint}.json"
        path.write_text(
            json.dumps(
                {"fingerprint": request.fingerprint, "call": request.call, "raw": raw},
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return raw
