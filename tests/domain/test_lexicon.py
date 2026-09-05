"""The lexicon is the foundation of the carry-over metric, so its failure modes matter
more than its successes: a term it misses is a tunnel it will not detect."""

from solution.domain.lexicon import extract_terms

LEXICON = frozenset({"react", "node.js", "postgresql", "aws", "oauth2", "code review"})


def test_matches_lexicon_terms_regardless_of_case():
    assert extract_terms("We used React and react-router.", LEXICON) >= {"react"}


def test_strips_surrounding_punctuation_but_keeps_internal_dots():
    assert "node.js" in extract_terms("The backend was Node.js, mostly.", LEXICON)


def test_recognises_internal_capitals_absent_from_the_lexicon():
    assert "graphql" in extract_terms("We exposed a GraphQL layer.", LEXICON)


def test_recognises_uppercase_acronyms():
    assert extract_terms("The API used JWT over TLS.", LEXICON) >= {"api", "jwt", "tls"}


def test_ignores_ordinary_sentence_initial_capitals():
    terms = extract_terms("The team shipped it. Later we refactored.", LEXICON)
    assert terms == frozenset()


def test_ignores_single_letter_capitals():
    assert extract_terms("I built it.", LEXICON) == frozenset()


def test_matches_multi_word_lexicon_entries():
    assert "code review" in extract_terms("I ran the code review process.", LEXICON)


def test_returns_normalised_lowercase_terms():
    assert all(t == t.lower() for t in extract_terms("AWS and PostgreSQL", LEXICON))
