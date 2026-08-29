"""The executed prompt is read from the file that documents it, so the two cannot drift.
These tests protect that property and the placeholder substitution around it."""

import pytest

from solution.adapters.prompt_files import PromptFileError, fill, load_prompt_pair

DOCUMENT = """# A prompt

Some prose a reviewer reads.

## System prompt

```
You are an interviewer.
Reply with JSON.
```

## User prompt

```
Transcript: <<TRANSCRIPT>>
Elapsed: <<ELAPSED_MINUTES>>
```

More prose.
"""


def write(tmp_path, text=DOCUMENT):
    path = tmp_path / "prompt.md"
    path.write_text(text, encoding="utf-8")
    return path


def test_reads_the_system_and_user_prompts_from_the_documentation(tmp_path):
    system, user = load_prompt_pair(write(tmp_path))
    assert system == "You are an interviewer.\nReply with JSON."
    assert user.startswith("Transcript: <<TRANSCRIPT>>")


def test_fails_loudly_when_the_document_is_missing_a_prompt(tmp_path):
    with pytest.raises(PromptFileError, match="expected a system prompt"):
        load_prompt_pair(write(tmp_path, "# Only prose\n\nNo fenced blocks here.\n"))


def test_substitutes_placeholders():
    assert fill("Elapsed: <<ELAPSED_MINUTES>>", elapsed_minutes="7") == "Elapsed: 7"


def test_refuses_to_send_a_prompt_with_an_unfilled_placeholder():
    with pytest.raises(PromptFileError, match="RESUME"):
        fill("<<ROLE>> and <<RESUME>>", role="a job")


def test_the_real_baseline_prompt_loads_and_declares_its_placeholders():
    """Guards the actual iteration 0 prompt, not a fixture of it."""
    system, user = load_prompt_pair("baseline/prompt.md")
    assert "<<ROLE>>" in system and "<<RESUME>>" in system
    assert "<<TRANSCRIPT>>" in user and "<<ELAPSED_MINUTES>>" in user
    assert "message" in system
