"""Telling "ask me that again" from an answer.

The rule is asymmetric on purpose and the tests are too: mistaking a real answer for a
request to repeat costs the candidate the substance of their turn, so the false positives
are tested harder than the false negatives.
"""

from solution.domain.clarification import is_clarification_request


class TestRequestsThatCount:
    def test_the_plain_english_ask(self):
        assert is_clarification_request("Sorry, what do you mean by that?")

    def test_the_plain_portuguese_ask(self):
        """The respondent is Brazilian and the interview is in English; under time
        pressure people fall back to their first language."""
        assert is_clarification_request("Não entendi, poderia me explicar melhor?")

    def test_a_short_bare_question(self):
        assert is_clarification_request("Which part of it?")

    def test_a_request_with_no_question_mark(self):
        assert is_clarification_request("I don't understand the question")


class TestAnswersThatMustNotCount:
    def test_a_long_answer_that_ends_on_a_rhetorical_question(self):
        """Thinking aloud is answering. This is the expensive false positive."""
        answer = (
            "We had duplicate payments coming through, so I added an idempotency key "
            "derived from the transaction id and did a conditional write against it. The "
            "first request wins and the rest read the stored result. It held up under "
            "load, though you always wonder what happens at the next order of magnitude, "
            "right?"
        )
        assert not is_clarification_request(answer)

    def test_a_short_but_declarative_answer(self):
        assert not is_clarification_request("A missing index on the ledger table.")

    def test_an_empty_turn_is_not_a_request(self):
        """The clock running out, or a mis-key. Spending a clarification on it would take
        one the candidate never asked for."""
        assert not is_clarification_request("")
        assert not is_clarification_request("   ")

    def test_an_answer_that_merely_contains_the_word_explain(self):
        assert not is_clarification_request(
            "I had to explain the tradeoff to the team before we shipped it."
        )
