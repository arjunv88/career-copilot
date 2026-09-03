from discovery.filters import (
    company_size_allowed,
    company_size_score,
)


def test_large_company():

    assert (
        company_size_allowed("Large")
        is True
    )

    assert (
        company_size_score("Large")
        == 100.0
    )


def test_small_company():

    assert (
        company_size_allowed("Small")
        is False
    )

    assert (
        company_size_score("Small")
        == 30.0
    )


def test_unknown_company():

    assert (
        company_size_allowed("Unknown")
        is True
    )

    assert (
        company_size_score("Unknown")
        == 50.0
    )