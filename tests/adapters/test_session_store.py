"""Session records are the only source of both the metrics and the trajectories
deliverable, which is why they are written as the interview happens and never rewritten.
A record that can be edited after the fact is not evidence."""

import json

import pytest

from solution.adapters.session_store import SessionStore


def store(tmp_path, start=1_700_000_000.0):
    ticks = iter(start + n for n in range(1000))
    return SessionStore(tmp_path / "session.jsonl", clock=lambda: next(ticks))


def test_records_events_with_an_increasing_sequence(tmp_path):
    subject = store(tmp_path)
    subject.append("question_asked", slot_id="backend")
    subject.append("answer_received", characters=412)
    assert [e.sequence for e in subject.events()] == [1, 2]


def test_round_trips_the_event_payload(tmp_path):
    subject = store(tmp_path)
    subject.append("gate_rejected", violations=["carry_over"], evidence={"carry_over": ["react"]})
    (event,) = subject.events()
    assert event.type == "gate_rejected"
    assert event.data["evidence"]["carry_over"] == ["react"]


def test_stamps_each_event_from_the_injected_clock(tmp_path):
    subject = store(tmp_path, start=42.0)
    subject.append("opening")
    assert subject.events()[0].timestamp == 42.0


def test_never_rewrites_a_line_it_has_already_written(tmp_path):
    subject = store(tmp_path)
    subject.append("first", value=1)
    first_line = subject.path.read_text(encoding="utf-8").splitlines()[0]
    subject.append("second", value=2)
    assert subject.path.read_text(encoding="utf-8").splitlines()[0] == first_line


def test_every_line_is_independently_parsable(tmp_path):
    subject = store(tmp_path)
    subject.append("a")
    subject.append("b")
    lines = subject.path.read_text(encoding="utf-8").strip().splitlines()
    assert [json.loads(line)["type"] for line in lines] == ["a", "b"]


def test_an_unwritten_session_simply_has_no_events(tmp_path):
    assert store(tmp_path).events() == ()


def test_refuses_payloads_it_cannot_serialise(tmp_path):
    with pytest.raises(TypeError):
        store(tmp_path).append("broken", value=object())
