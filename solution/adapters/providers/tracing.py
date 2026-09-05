"""Recording what every model call actually sent and received.

Deliverable 3 of agentic-workflows.md section 8 asks for a trace per agent, readable from
the agent's instructions through to its final result, including retries. Nothing in this
project recorded a prompt before this module existed: the turn loop stored only how long
generation took, and the role extractor, the résumé matcher and the judge stored nothing
at all.

Section 9 is the reason this arrives before the first measured run rather than after it -
"capture trajectories as work happens; they cannot be reconstructed later".

The decorator shape is borrowed from `RecordingProvider` in fixtures.py, and for the same
reason: wrapping is the only way to observe every attempt, because retries happen inside
`complete_json` where a caller cannot see them.
"""

from __future__ import annotations

from typing import Any, Mapping

from solution.adapters.providers.base import LlmProvider, LlmRequest
from solution.adapters.session_store import SessionStore


class TracingProvider(LlmProvider):
    """Wraps a provider and writes one `model_call` event per attempt.

    Attempts are numbered rather than collapsed. A call that succeeded on the second try
    is a different trace from one that succeeded immediately, and the retry is exactly the
    kind of thing the trajectories deliverable asks to be visible.
    """

    def __init__(
        self,
        inner: LlmProvider,
        store: SessionStore,
        context: Mapping[str, Any] | None = None,
    ) -> None:
        self.inner = inner
        self.store = store
        self.context = dict(context or {})
        self._attempts: dict[str, int] = {}

    @property
    def name(self) -> str:
        return self.inner.name

    @property
    def model(self) -> str:
        return self.inner.model

    def _invoke(self, request: LlmRequest) -> str:
        attempt = self._attempts.get(request.fingerprint, 0) + 1
        self._attempts[request.fingerprint] = attempt

        try:
            raw = self.inner._invoke(request)
        except Exception as error:
            self.store.append(
                "model_call",
                call=request.call,
                attempt=attempt,
                provider=self.inner.name,
                model=self.inner.model,
                fingerprint=request.fingerprint,
                system=request.system,
                prompt=request.prompt,
                schema=dict(request.schema),
                error=f"{type(error).__name__}: {error}",
                **self.context,
            )
            raise

        self.store.append(
            "model_call",
            call=request.call,
            attempt=attempt,
            provider=self.inner.name,
            model=self.inner.model,
            fingerprint=request.fingerprint,
            system=request.system,
            prompt=request.prompt,
            schema=dict(request.schema),
            raw=raw,
            **self.context,
        )
        return raw
