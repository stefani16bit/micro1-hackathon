"""Print a session record as a readable transcript.

    python scripts/show_session.py evals/results/iteration-00/session-20260829-205109.jsonl

The session records are JSONL because they are machine input first. This renders one for
a human - it is how a trajectory gets reviewed without opening a JSON file by hand.
"""

from __future__ import annotations

import sys
import textwrap
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from solution.adapters.session_store import SessionStore  # noqa: E402

WIDTH = 88


def wrap(text: str, indent: str = "    ") -> str:
    paragraphs = text.split("\n")
    return "\n".join(
        textwrap.fill(p, width=WIDTH, initial_indent=indent, subsequent_indent=indent) or indent
        for p in paragraphs
    )


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2

    events = SessionStore(Path(argv[1])).events()
    question_number = 0

    for event in events:
        if event.type == "run_metadata":
            data = event.data
            print(f"\n{'=' * WIDTH}")
            print(f"  iteration {data.get('iteration')}   "
                  f"{data.get('provider')}:{data.get('model')}   commit {data.get('commit')}")
            print(f"  slots: {', '.join(data.get('slot_ids', []))}")
            print(f"{'=' * WIDTH}")

        elif event.type == "smoke_run":
            print("\n  ** SMOKE RUN - canned candidate, not a measurement **")

        elif event.type == "question_asked":
            question_number += 1
            kind = event.data.get("kind", "")
            slot = event.data.get("slot_id") or "-"
            seconds = event.data.get("generation_seconds", 0)
            print(f"\n  INTERVIEWER  Q{question_number}  [{kind}, slot={slot}, {seconds}s]")
            print(wrap(event.data.get("text", "")))

        elif event.type == "answer_received":
            seconds = event.data.get("seconds_used", 0)
            flag = "  OVER DEADLINE" if event.data.get("over_deadline") else ""
            print(f"\n  CANDIDATE  [{seconds}s]{flag}")
            print(wrap(event.data.get("text", "") or "(no answer)"))

        elif event.type == "opening_answer_replayed":
            print(f"\n  [frozen opening answer replayed, "
                  f"{event.data.get('characters')} characters]")

        elif event.type == "interview_ended":
            data = event.data
            print(f"\n{'=' * WIDTH}")
            print(f"  ended: {data.get('reason')}   "
                  f"questions: {data.get('questions_asked')}   "
                  f"elapsed: {data.get('elapsed_seconds', 0) / 60:.1f} min")
            print(f"{'=' * WIDTH}\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
