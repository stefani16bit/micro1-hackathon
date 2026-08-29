"""A model asked for a verbatim quote will sometimes produce a plausible paraphrase
instead. Every rating in the final report rests on a quote, so quotes are checked against
the source in code rather than trusted."""

from solution.domain.quotes import quote_is_verbatim

RESUME = """
Owned end-to-end delivery of serverless flows on AWS, covering both application code
and the platform infrastructure: provisioned and configured API Gateways with Cognito
authorizers, HTTP/consumer Lambdas over SNS/SQS.
"""


def test_accepts_an_exact_quote():
    assert quote_is_verbatim("provisioned and configured API Gateways", RESUME)


def test_accepts_a_quote_whose_whitespace_differs():
    assert quote_is_verbatim("serverless flows on AWS,   covering\n\nboth application code", RESUME)


def test_accepts_a_quote_in_a_different_case():
    assert quote_is_verbatim("HTTP/CONSUMER lambdas over sns/sqs", RESUME)


def test_ignores_zero_width_characters_that_pdf_extraction_leaves_behind():
    assert quote_is_verbatim("Cognito​ authorizers", RESUME)


def test_rejects_a_plausible_paraphrase():
    assert not quote_is_verbatim("set up API gateways with Cognito", RESUME)


def test_rejects_an_empty_quote():
    assert not quote_is_verbatim("   ", RESUME)
