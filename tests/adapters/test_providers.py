"""Provider tests run with no model and no network. That is the point: a reviewer must be
able to clone this repository and run the suite before deciding whether to download 8 GB."""

import json

import pytest

from solution.adapters.providers.base import (
    LlmProvider,
    LlmRequest,
    MalformedResponse,
    parse_json_payload,
)
from solution.adapters.providers.claude_cli import ClaudeCliProvider
from solution.adapters.providers.fixtures import FixtureProvider, UnknownFixture
from solution.adapters.providers.ollama import OllamaProvider

SCHEMA = {
    "type": "object",
    "properties": {"question": {"type": "string"}},
    "required": ["question"],
}


def request(prompt: str = "ask about cloud") -> LlmRequest:
    return LlmRequest(call="generate_question", system="You interview.", prompt=prompt, schema=SCHEMA)


class ScriptedProvider(LlmProvider):
    """A provider whose raw output is dictated by the test."""

    name = "scripted"
    model = "scripted"

    def __init__(self, *responses: str):
        self._responses = list(responses)
        self.calls = 0

    def _invoke(self, request: LlmRequest) -> str:
        self.calls += 1
        return self._responses.pop(0)


class TestJsonExtraction:
    def test_reads_a_bare_object(self):
        assert parse_json_payload('{"question": "Tell me about AWS?"}') == {
            "question": "Tell me about AWS?"
        }

    def test_reads_an_object_inside_a_fenced_block(self):
        raw = 'Here you go:\n```json\n{"question": "Why?"}\n```\nHope that helps.'
        assert parse_json_payload(raw) == {"question": "Why?"}

    def test_ignores_prose_around_the_object(self):
        assert parse_json_payload('Sure. {"question": "Why?"} Done.') == {"question": "Why?"}

    def test_is_not_fooled_by_braces_inside_strings(self):
        raw = '{"question": "What does {this} mean?"}'
        assert parse_json_payload(raw) == {"question": "What does {this} mean?"}

    def test_raises_when_there_is_no_object_at_all(self):
        with pytest.raises(MalformedResponse):
            parse_json_payload("I would rather not answer that.")


class TestFingerprint:
    def test_is_stable_for_an_identical_request(self):
        assert request().fingerprint == request().fingerprint

    def test_changes_when_the_prompt_changes(self):
        assert request("a").fingerprint != request("b").fingerprint


class TestRetryAndValidation:
    def test_retries_once_when_the_first_response_is_unparsable(self):
        provider = ScriptedProvider("not json at all", '{"question": "Why?"}')
        assert provider.complete_json(request()).payload == {"question": "Why?"}
        assert provider.calls == 2

    def test_gives_up_with_a_clear_error_after_exhausting_retries(self):
        provider = ScriptedProvider("nope", "still nope", "nope again")
        with pytest.raises(MalformedResponse):
            provider.complete_json(request(), max_attempts=3)

    def test_rejects_a_payload_that_omits_a_required_key(self):
        provider = ScriptedProvider('{"answer": "wrong shape"}', '{"question": "Right?"}')
        assert provider.complete_json(request()).payload == {"question": "Right?"}

    def test_records_which_provider_and_model_produced_the_answer(self):
        response = ScriptedProvider('{"question": "Why?"}').complete_json(request())
        assert (response.provider, response.model, response.call) == (
            "scripted",
            "scripted",
            "generate_question",
        )


class TestFixtureProvider:
    def test_replays_a_recorded_response(self, tmp_path):
        req = request()
        fixture = {"fingerprint": req.fingerprint, "raw": '{"question": "Recorded?"}'}
        (tmp_path / f"{req.fingerprint}.json").write_text(json.dumps(fixture), encoding="utf-8")
        provider = FixtureProvider(tmp_path)
        assert provider.complete_json(req).payload == {"question": "Recorded?"}

    def test_names_the_missing_fingerprint_when_nothing_was_recorded(self, tmp_path):
        with pytest.raises(UnknownFixture, match=request().fingerprint[:12]):
            FixtureProvider(tmp_path).complete_json(request())


class TestOllamaPayload:
    def test_pins_determinism_and_hands_the_schema_to_the_server(self):
        provider = OllamaProvider(base_url="http://localhost:11434", model="gemma4:12b", seed=42)
        payload = provider.build_payload(request())
        assert payload["model"] == "gemma4:12b"
        assert payload["format"] == SCHEMA
        assert payload["stream"] is False
        assert payload["think"] is False
        assert payload["options"] == {"temperature": 0.0, "seed": 42}

    def test_sends_the_system_prompt_as_its_own_message(self):
        provider = OllamaProvider(base_url="http://x", model="m")
        messages = provider.build_payload(request())["messages"]
        assert [m["role"] for m in messages] == ["system", "user"]


class TestClaudeCliCommand:
    def test_runs_non_interactively_with_no_tools_available(self):
        command = ClaudeCliProvider(binary="claude", model="sonnet").build_command(request())
        assert command[0] == "claude"
        assert "--print" in command
        assert command[command.index("--output-format") + 1] == "json"
        assert command[command.index("--disallowed-tools") + 1] == "*"
        assert command[command.index("--model") + 1] == "sonnet"
