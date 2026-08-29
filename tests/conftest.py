import pytest

from solution.adapters.session_store import SessionStore


@pytest.fixture
def store_factory():
    """A session store on a deterministic clock, so recorded timestamps are stable."""

    def make(tmp_path, start: float = 1_700_000_000.0) -> SessionStore:
        ticks = iter(start + n for n in range(100_000))
        return SessionStore(tmp_path / "session.jsonl", clock=lambda: next(ticks))

    return make
