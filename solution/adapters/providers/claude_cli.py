"""Claude Code CLI adapter, driven non-interactively as a pure text generator.

Every tool is disabled: this call must not read the filesystem or run anything. It is a
model call that happens to be delivered through a CLI.
"""

from __future__ import annotations

import json
import subprocess

from solution.adapters.providers.base import LlmProvider, LlmRequest, MalformedResponse


class ClaudeCliProvider(LlmProvider):
    name = "claude_cli"

    def __init__(
        self,
        binary: str = "claude",
        model: str = "sonnet",
        timeout_seconds: float = 900.0,
    ) -> None:
        self.binary = binary
        self.model = model
        self.timeout_seconds = timeout_seconds

    def build_command(self, request: LlmRequest) -> list[str]:
        return [
            self.binary,
            "--print",
            "--output-format",
            "json",
            "--model",
            self.model,
            "--disallowed-tools",
            "*",
            "--append-system-prompt",
            request.system,
            request.prompt,
        ]

    def _invoke(self, request: LlmRequest) -> str:
        completed = subprocess.run(
            self.build_command(request),
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=self.timeout_seconds,
        )
        if completed.returncode != 0:
            raise MalformedResponse(
                f"claude CLI exited {completed.returncode}: {completed.stderr[:400]}"
            )
        try:
            return json.loads(completed.stdout)["result"]
        except (json.JSONDecodeError, KeyError) as error:
            raise MalformedResponse(f"unexpected CLI envelope: {error}") from error
