"""Provider selection. One factory, so every entry point resolves the model the same way."""

from __future__ import annotations

from typing import Any, Mapping

from solution.adapters.providers.base import (
    LlmProvider,
    LlmRequest,
    LlmResponse,
    MalformedResponse,
)
from solution.adapters.providers.claude_cli import ClaudeCliProvider
from solution.adapters.providers.fixtures import FixtureProvider, RecordingProvider, UnknownFixture
from solution.adapters.providers.ollama import OllamaProvider

__all__ = [
    "ClaudeCliProvider",
    "FixtureProvider",
    "LlmProvider",
    "LlmRequest",
    "LlmResponse",
    "MalformedResponse",
    "OllamaProvider",
    "RecordingProvider",
    "UnknownFixture",
    "build_provider",
]


def build_provider(config: Mapping[str, Any], name: str | None = None) -> LlmProvider:
    """Build the provider named in config.yaml, or the one explicitly requested."""
    provider_config = config["provider"]
    resolved = name or provider_config["name"]

    if resolved == "ollama":
        settings = provider_config["ollama"]
        return OllamaProvider(
            base_url=settings["base_url"],
            model=settings["model"],
            temperature=settings.get("temperature", 0.0),
            seed=settings.get("seed"),
        )

    if resolved == "claude_cli":
        settings = provider_config["claude_cli"]
        return ClaudeCliProvider(binary=settings["binary"], model=settings["model"])

    raise ValueError(f"unknown provider {resolved!r}; expected 'ollama' or 'claude_cli'")
