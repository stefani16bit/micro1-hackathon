"""The rule layer resolves what it can; whatever it cannot goes to a model. So every
keyword form it fails to recognise moves a piece of the headline number out of code and
into a model's opinion. These tests bound that, and bound the false positives that
loosening the match would otherwise let in."""

from evals.metrics.labelling import inflections, mentions_keyword


class TestInflections:
    def test_recovers_the_stem_of_a_doubled_consonant_gerund(self):
        assert "debug" in inflections("debugging")

    def test_offers_regular_verb_endings(self):
        assert {"refactored", "refactoring", "refactors"} <= inflections("refactor")

    def test_handles_y_to_ies(self):
        assert "queries" in inflections("query")

    def test_offers_the_plural_of_a_noun(self):
        assert "migrations" in inflections("migration")

    def test_leaves_a_dotted_identifier_alone(self):
        """node.js must not sprout node.jsing."""
        assert inflections("node.js") == {"node.js"}

    def test_inflects_only_the_last_word_of_a_phrase(self):
        assert "code reviews" in inflections("code review")
        assert not any(form.startswith("codes ") for form in inflections("code review"))


class TestMatching:
    def test_matches_an_inflected_form_in_a_sentence(self):
        assert mentions_keyword("How did you debug that?", "debugging")

    def test_matches_the_exact_keyword(self):
        assert mentions_keyword("Tell me about React.", "react")

    def test_does_not_match_a_longer_unrelated_word(self):
        """'reaction' is the false positive that a prefix match would let through."""
        assert not mentions_keyword("What is your reaction to that?", "react")

    def test_does_not_match_a_keyword_inside_another_word(self):
        assert not mentions_keyword("The subquery was fine.", "query")

    def test_matches_a_multi_word_keyword(self):
        assert mentions_keyword("We ran a code review on it.", "code review")
