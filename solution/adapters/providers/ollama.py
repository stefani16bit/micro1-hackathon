"""Local Ollama adapter. Nothing leaves the machine."""

from __future__ import annotations

from typing import Any

from solution.adapters.providers.base import LlmProvider, LlmRequest


class OllamaProvider(LlmProvider):
    name = "ollama"

    def __init__(
        self,
        base_url: str,
        model: str,
        temperature: float = 0.0,
        seed: int | None = 42,
        timeout_seconds: float = 900.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.temperature = temperature
        self.seed = seed
        self.timeout_seconds = timeout_seconds

    def build_payload(self, request: LlmRequest) -> dict[str, Any]:
        options: dict[str, Any] = {"temperature": self.temperature}
        if self.seed is not None:
            options["seed"] = self.seed
        return {
            "model": self.model,
            "messages": [
                {"role": "system", "content": request.system},
                {"role": "user", "content": request.prompt},
            ],
            # Ollama enforces the JSON Schema server-side, which removes a whole class of
            # parsing failures instead of papering over them with retries.
            "format": dict(request.schema),
            "stream": False,
            "think": False,
            "options": options,
        }

    def _invoke(self, request: LlmRequest) -> str:
        import httpx

        response = httpx.post(
            f"{self.base_url}/api/chat",
            json=self.build_payload(request),
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        return response.json()["message"]["content"]
