"""Trajectories are a graded deliverable and cannot be reconstructed after the fact, so
what the recorder captures is pinned here rather than discovered when a judge asks for it.

The retry case is the reason this wraps the provider instead of sitting beside it: retries
happen inside `complete_json`, where a caller cannot see them."""

import pytest

from solution.adapters.providers.base import LlmProvider, LlmRequest, MalformedResponse
from solution.adapters.providers.tracing import TracingProvider

SCHEMA = {
    "type": "object",
    "properties": {"question": {"type": "string"}},
    "required": ["question"],
}


def request(prompt: str = "ask about cloud") -> LlmRequest:
    return LlmRequest(
        call="generate_question", system="You interview.", prompt=prompt, schema=SCHEMA
    )


class ScriptedProvider(LlmProvider):
    name = "scripted"
    model = "scripted-1"

    def __init__(self, *responses):
        self._responses = list(responses)

    def _invoke(self, request: LlmRequest) -> str:
        item = self._responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def calls(store):
    return [event for event in store.events() if event.type == "model_call"]


def test_records_the_prompt_the_schema_and_the_reply(tmp_path, store_factory):
    store = store_factory(tmp_path)
    provider = TracingProvider(ScriptedProvider('{"question": "Why?"}'), store)

    provider.complete_json(request())

    (event,) = calls(store)
    assert event.data["call"] == "generate_question"
    assert event.data["system"] == "You interview."
    assert event.data["prompt"] == "ask about cloud"
    assert event.data["schema"] == SCHEMA
    assert event.data["raw"] == '{"question": "Why?"}'


def test_reports_the_wrapped_providers_identity_not_its_own(tmp_path, store_factory):
    """A trajectory that named the decorator would say nothing about which model ran."""
    store = store_factory(tmp_path)
    provider = TracingProvider(ScriptedProvider('{"question": "Why?"}'), store)

    assert (provider.name, provider.model) == ("scripted", "scripted-1")
    assert calls(store) == []

    provider.complete_json(request())
    assert calls(store)[0].data["model"] == "scripted-1"


def test_numbers_each_attempt_so_a_retry_is_visible(tmp_path, store_factory):
    """A call that succeeded on the second try is a different trace from one that did not."""
    store = store_factory(tmp_path)
    provider = TracingProvider(
        ScriptedProvider("not json at all", '{"question": "Why?"}'), store
    )

    provider.complete_json(request())

    assert [event.data["attempt"] for event in calls(store)] == [1, 2]
    assert calls(store)[0].data["raw"] == "not json at all"


def test_records_a_failed_call_before_letting_it_propagate(tmp_path, store_factory):
    """Otherwise a trajectory ends without saying why the run stopped."""
    store = store_factory(tmp_path)
    provider = TracingProvider(ScriptedProvider(MalformedResponse("CLI exited 1")), store)

    with pytest.raises(MalformedResponse):
        provider.complete_json(request(), max_attempts=1)

    (event,) = calls(store)
    assert "CLI exited 1" in event.data["error"]
    assert "raw" not in event.data


def test_carries_the_context_it_was_given_onto_every_event(tmp_path, store_factory):
    """One record can hold several agents; the label is what separates them."""
    store = store_factory(tmp_path)
    provider = TracingProvider(
        ScriptedProvider('{"question": "Why?"}'), store, context={"agent": "interviewer-0"}
    )

    provider.complete_json(request())

    assert calls(store)[0].data["agent"] == "interviewer-0"
