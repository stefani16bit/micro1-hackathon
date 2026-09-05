"""Iterations 1-3: the interviewer whose topic selection is not the model's to make.

    rung 1    scheduler                       the topic stops being the model's choice
    rung 2    scheduler + context isolation   the transcript stops reaching it
    rung 3    scheduler + isolation + gate    nothing unverified reaches the candidate

State is rebuilt from the transcript rather than accumulated on the instance, which keeps
`next_utterance` a pure function of what is in the record - `evals/metrics/branching.py`
relies on that when it rewinds a run and resamples it.
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any, Mapping

from solution.adapters.prompt_files import fill, load_fenced_blocks, load_prompt_pair
from solution.adapters.providers.base import LlmProvider, LlmRequest, MalformedResponse
from solution.adapters.session_store import SessionStore
from solution.adapters.slot_plan import SlotPlan
from solution.application.runner import Interviewer
from solution.domain.clarification import is_clarification_request
from solution.domain.gate import GateContext, check_clarification, check_question
from solution.domain.lexicon import build_lexicon, extract_terms
from solution.domain.models import Action, ActionType, ResumeEvidence, Slot, SlotKind, TimeBudget
from solution.domain.scheduler import decide_next
from solution.domain.session import SessionState
from solution.domain.transcript import Speaker, Transcript, TranscriptEntry, Utterance

SCHEMA: Mapping[str, Any] = {
    "type": "object",
    "properties": {"question": {"type": "string"}},
    "required": ["question"],
}

TEMPLATES: Mapping[SlotKind, tuple[str, str]] = {
    SlotKind.LANGUAGE_FRAMEWORK: (
        "What is the most demanding thing you have built with {slot}, and what made it demanding?",
        "Suppose you had to build a feature with {slot} on a system you do not know - how would "
        "you approach it?",
    ),
    SlotKind.DATA_STORAGE: (
        "Tell me about a time {slot} was the bottleneck - how did you find it, and what did you "
        "change?",
        "Suppose {slot} was the bottleneck in a system you did not write - how would you approach "
        "finding out why?",
    ),
    SlotKind.INFRA_OPS: (
        "Tell me about a production problem in {slot} that you were responsible for - what did "
        "you do?",
        "Imagine you are paged for a production problem in {slot} on an unfamiliar system - what "
        "would you do first?",
    ),
    SlotKind.CROSS_CUTTING: (
        "Tell me about a time {slot} mattered on something you built - what did you do?",
        "Suppose you were asked to take {slot} on for a team that has never done it - how would "
        "you start?",
    ),
}

OPENING = (
    "Thanks for making the time. To start, tell me about yourself and the work you have been doing."
)

MOVING_ON = (
    "That one was about {slot} - let me leave it there rather than spend more of your time "
    "on a question I did not put well, and move us to something else. "
)

RESTATE_FALLBACK = (
    "Sorry - let me put that another way. {question}"
)


class ScheduledInterviewer(Interviewer):
    """Topic from the plan and the clock; wording from the model; verification in code."""

    def __init__(
        self,
        *,
        provider: LlmProvider,
        plan: SlotPlan,
        evidence: Mapping[str, ResumeEvidence],
        budget: TimeBudget,
        iteration: int,
        sees_transcript: bool,
        gated: bool,
        max_followups_per_slot: int = 1,
        prompt_path: Path | str = "solution/agent_instructions/interviewer.md",
        store: SessionStore | None = None,
    ) -> None:
        self._prompt_path = prompt_path
        self._system, self._user_template = load_prompt_pair(prompt_path)
        self._provider = provider
        self._plan = plan
        self._evidence = dict(evidence)
        self._budget = budget
        self._sees_transcript = sees_transcript
        self._gated = gated
        self._max_followups = max_followups_per_slot
        self._store = store
        self._lexicon = build_lexicon(plan.keywords)
        self.label = f"iteration-{iteration}-scheduled"
        self._end_reason: str | None = None

        self.may_compose_ahead = not sees_transcript
        self._ahead: threading.Thread | None = None
        self._speculation: tuple[str, str] | None = None

    def _state_from(self, transcript: Transcript) -> SessionState:
        """What the schedule knows, read back off the record."""
        state = SessionState.initial(self._plan.slots)
        seen: set[str] = set()
        for entry in transcript.questions:
            if entry.kind == "opening":
                state = state.evolve(opening_asked=True)
                continue
            if entry.kind == "clarification":
                continue
            if not entry.slot_id:
                continue
            if entry.slot_id in seen:
                state = state.with_followup_asked(entry.slot_id)
            else:
                seen.add(entry.slot_id)
                state = state.with_primary_asked(entry.slot_id)
        return state.evolve(elapsed_seconds=int(transcript.elapsed_seconds))

    def _evidence_terms(self, evidence: ResumeEvidence | None) -> frozenset[str]:
        """The technologies this slot's own CV line names, which are never drift."""
        if evidence is None or not evidence.quote:
            return frozenset()
        return extract_terms(evidence.quote, self._lexicon)

    def _prior_answer_terms(self, transcript: Transcript) -> frozenset[str]:
        terms: set[str] = set()
        for entry in transcript.entries:
            if entry.speaker is Speaker.CANDIDATE:
                terms |= extract_terms(entry.text, self._lexicon)
        return frozenset(terms)

    def _last_answer_to(self, slot_id: str, transcript: Transcript) -> str | None:
        """What the candidate said when this competency was last asked about.

        The one thing a follow-up is allowed to see, and nothing else. A follow-up stays on
        the slot the schedule already chose, so this cannot move the interview - which is
        why it is a bounded exception to the isolation rather than a hole in it.
        """
        entries = transcript.entries
        for index in range(len(entries) - 1, 0, -1):
            entry = entries[index]
            if entry.speaker is not Speaker.CANDIDATE:
                continue
            asked = entries[index - 1]
            if asked.speaker is Speaker.INTERVIEWER and asked.slot_id == slot_id:
                return entry.text
        return None

    def next_utterance(self, transcript: Transcript) -> Utterance | None:
        self._collect_ahead()

        state = self._state_from(transcript)
        asking_again, already_clarified = self._clarification_state(transcript)

        if asking_again and not already_clarified:
            return self._clarify(transcript)

        action = decide_next(
            state,
            self._budget,
            followup_wanted=not asking_again,
            max_followups_per_slot=self._max_followups,
        )
        self._record(
            "scheduler_decided",
            action=action.type.value,
            slot_id=action.slot.id if action.slot else None,
            reason=action.reason,
            elapsed_seconds=state.elapsed_seconds,
        )

        if action.type is ActionType.END:
            self._end_reason = action.reason
            return None
        if action.type is ActionType.OPENING:
            return Utterance(text=OPENING, kind="opening", slot_id=None)

        utterance = self._ask(action, transcript)
        if asking_again:
            abandoned = self._last_question(transcript)
            preamble = MOVING_ON.format(
                slot=self._slot_name(abandoned.slot_id if abandoned else None)
            )
            self._record("moved_on_after_second_clarification",
                         abandoned_slot=abandoned.slot_id if abandoned else None,
                         next_slot=utterance.slot_id)
            return Utterance(text=preamble + utterance.text, kind=utterance.kind,
                             slot_id=utterance.slot_id)
        return utterance

    def stopped_because(self) -> str:
        return self._end_reason or "interviewer_finished"

    def compose_ahead(self, transcript: Transcript) -> None:
        """Compose the question the schedule will most likely ask next, in the background.

        Speculative, and validated at the turn boundary rather than trusted: the decision
        is taken again once the answer's real duration is known, and anything that does not
        match is thrown away. Only primaries are composed this way - a follow-up needs the
        answer that has not been given yet.
        """
        if not self.may_compose_ahead or self._ahead is not None:
            return
        self._speculation = None
        self._ahead = threading.Thread(
            target=self._compose_ahead, args=(transcript,), daemon=True
        )
        self._ahead.start()

    def _compose_ahead(self, transcript: Transcript) -> None:
        state = self._state_from(transcript)
        state = state.evolve(
            elapsed_seconds=state.elapsed_seconds + self._budget.expected_answer_seconds
        )
        action = decide_next(
            state,
            self._budget,
            followup_wanted=False,
            max_followups_per_slot=self._max_followups,
        )
        if action.type is not ActionType.PRIMARY or action.slot is None:
            return
        try:
            text = self._compose(action, transcript)
        except Exception as error:
            self._record("composed_ahead_failed", slot_id=action.slot.id, error=str(error))
            return
        self._speculation = (action.slot.id, text)
        self._record("composed_ahead", slot_id=action.slot.id, question=text)

    def _collect_ahead(self) -> None:
        if self._ahead is None:
            return
        self._ahead.join()
        self._ahead = None

    def _take_speculation(self, action: Action) -> str | None:
        """The composed-ahead question, if the schedule still wants exactly that one."""
        speculation, self._speculation = self._speculation, None
        if speculation is None or action.slot is None:
            return None
        slot_id, text = speculation
        if action.type is not ActionType.PRIMARY or slot_id != action.slot.id:
            self._record("speculation_discarded", composed_for=slot_id,
                         wanted=action.slot.id, wanted_kind=action.type.value)
            return None
        self._record("speculation_used", slot_id=slot_id)
        return text

    def _clarification_state(self, transcript: Transcript) -> tuple[bool, bool]:
        """(the candidate is asking to have the question repeated, we already repeated it)"""
        answers = transcript.answers
        if not answers:
            return False, False
        asking = is_clarification_request(answers[-1].text)
        last = self._last_question(transcript)
        return asking, bool(last is not None and last.kind == "clarification")

    @staticmethod
    def _last_question(transcript: Transcript) -> TranscriptEntry | None:
        questions = transcript.questions
        return questions[-1] if questions else None

    def _slot_name(self, slot_id: str | None) -> str:
        for slot in self._plan.slots:
            if slot.id == slot_id:
                return slot.name
        return "that"

    def _clarify(self, transcript: Transcript) -> Utterance:
        """Restate the question. Never explain it - that would answer it."""
        original = self._last_question(transcript)
        assert original is not None
        text = self._generate_clarification(original.text)

        if text is not None:
            allowed = extract_terms(original.text, self._lexicon)
            result = check_clarification(
                text, GateContext(slot=self._plan.slots[0], lexicon=self._lexicon,
                                  allowed_terms=allowed)
            )
            self._record("clarification_checked", passed=result.passed,
                         violations=[v.value for v in result.violations],
                         evidence={k: list(v) for k, v in result.evidence.items()}, text=text)
            if not result.passed:
                text = None

        if text is None:
            text = RESTATE_FALLBACK.format(question=original.text)
            self._record("clarification_fallback_used", slot_id=original.slot_id)

        return Utterance(text=text, kind="clarification", slot_id=original.slot_id)

    def _generate_clarification(self, question: str) -> str | None:
        blocks = load_fenced_blocks(self._prompt_path)
        if len(blocks) < 3:
            return None
        try:
            response = self._provider.complete_json(
                LlmRequest(call="clarify", system=blocks[2],
                           prompt=f"YOUR QUESTION\n\n{question}", schema=SCHEMA)
            )
        except MalformedResponse:
            return None
        return str(response.payload["question"]).strip() or None

    def _ask(self, action: Action, transcript: Transcript) -> Utterance:
        slot = action.slot
        assert slot is not None
        text = self._take_speculation(action) or self._compose(action, transcript)
        return Utterance(
            text=text,
            kind="follow_up" if action.type is ActionType.FOLLOW_UP else "primary",
            slot_id=slot.id,
        )

    def _compose(self, action: Action, transcript: Transcript) -> str:
        """Generate one question, verify it, and fall back to a template if it will not do.

        Runs on the interview's own thread or on the composing-ahead one, so it touches no
        instance state beyond the configuration fixed in `__init__`.
        """
        slot = action.slot
        assert slot is not None
        evidence = self._evidence.get(slot.id)
        behavioural = bool(evidence and evidence.has_experience)
        prior = self._prior_answer_terms(transcript)
        deepening = (
            self._last_answer_to(slot.id, transcript)
            if action.type is ActionType.FOLLOW_UP
            else None
        )

        for attempt in (1, 2):
            candidate = self._generate(slot, evidence, behavioural, transcript, deepening)
            if candidate is None:
                break
            if not self._gated:
                return candidate

            result = check_question(
                candidate,
                GateContext(
                    slot=slot,
                    lexicon=self._lexicon,
                    prior_answer_terms=prior,
                    allowed_terms=self._evidence_terms(evidence) | self._deepening_terms(deepening),
                    expect_behavioural=behavioural,
                ),
            )
            self._record(
                "gate_checked",
                slot_id=slot.id,
                attempt=attempt,
                passed=result.passed,
                violations=[v.value for v in result.violations],
                evidence={k: list(v) for k, v in result.evidence.items()},
                question=candidate,
            )
            if result.passed:
                return candidate

        text = self._fallback(slot, behavioural)
        self._record("fallback_used", slot_id=slot.id, question=text)
        return text

    def _deepening_terms(self, deepening: str | None) -> frozenset[str]:
        """A follow-up may name what the answer it follows up on named.

        Without this the gate rejects every deepening question as carry-over, which is the
        one place picking up the candidate's own words is the entire point.
        """
        if not deepening:
            return frozenset()
        return extract_terms(deepening, self._lexicon)

    def _generate(
        self,
        slot: Slot,
        evidence: ResumeEvidence | None,
        behavioural: bool,
        transcript: Transcript,
        deepening: str | None = None,
    ) -> str | None:
        prompt = fill(
            self._user_template,
            slot_name=slot.name,
            has_experience="yes" if behavioural else "no",
            evidence=(evidence.quote if evidence and evidence.quote else "(nothing specific)"),
            transcript_block=(
                f"INTERVIEW SO FAR\n{transcript.render()}\n\n" if self._sees_transcript else ""
            ),
            followup_block=(
                "THIS IS A FOLLOW-UP. Their answer to your first question on this "
                f"competency:\n{deepening}\n\nGo one level deeper into what they described - "
                "ask for the part they left out. Do not start a new topic.\n\n"
                if deepening
                else ""
            ),
        )
        try:
            response = self._provider.complete_json(
                LlmRequest(
                    call="scheduled_turn",
                    system=self._system,
                    prompt=prompt,
                    schema=SCHEMA,
                )
            )
        except MalformedResponse:
            self._record("generation_failed", slot_id=slot.id)
            return None
        return str(response.payload["question"]).strip() or None

    def _fallback(self, slot: Slot, behavioural: bool) -> str:
        template = TEMPLATES[slot.kind][0 if behavioural else 1]
        return template.format(slot=slot.name)

    def _record(self, event: str, **data: Any) -> None:
        if self._store is not None:
            self._store.append(event, **data)
