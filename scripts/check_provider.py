"""Smoke-check a configured provider with one real, cheap model call.

    python scripts/check_provider.py ollama
    python scripts/check_provider.py claude_cli

Run this before an interview session. It answers one question - can this machine reach
the model named in config.yaml and get schema-shaped JSON back - and answers it in a few
seconds rather than in the middle of a 25-minute interview.
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from solution.adapters.providers import build_provider  # noqa: E402
from solution.adapters.providers.base import LlmRequest  # noqa: E402

SCHEMA = {
    "type": "object",
    "properties": {
        "ready": {"type": "boolean"},
        "model_name": {"type": "string"},
    },
    "required": ["ready", "model_name"],
}


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    config = yaml.safe_load((root / "config.yaml").read_text(encoding="utf-8"))
    name = sys.argv[1] if len(sys.argv) > 1 else config["provider"]["name"]
    provider = build_provider(config, name)

    request = LlmRequest(
        call="smoke_check",
        system="You reply with JSON only. No prose, no explanation.",
        prompt='Reply with {"ready": true, "model_name": "<the model you are>"}.',
        schema=SCHEMA,
    )

    response = provider.complete_json(request)
    print(f"provider     : {response.provider}")
    print(f"model        : {response.model}")
    print(f"latency      : {response.duration_ms} ms")
    print(f"payload      : {dict(response.payload)}")
    print(f"fingerprint  : {response.fingerprint[:16]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
