from unittest.mock import MagicMock, patch

from trade_assistant.market_data.yahoo_profile import fetch_yahoo_company_profile


def test_profile_sector_and_industry() -> None:
    fake = MagicMock()
    fake.info = {"sector": "Financial Services", "industry": "Banks - Regional"}

    with patch("trade_assistant.market_data.yahoo_profile.yf.Ticker", return_value=fake):
        r = fetch_yahoo_company_profile("VLY")

    assert r.fetched_ok is True
    assert r.sector == "Financial Services"
    assert r.industry == "Banks - Regional"


def test_profile_missing_sector_still_ok_fetch() -> None:
    fake = MagicMock()
    fake.info = {"quoteType": "EQUITY"}

    with patch("trade_assistant.market_data.yahoo_profile.yf.Ticker", return_value=fake):
        r = fetch_yahoo_company_profile("TEST")

    assert r.fetched_ok is True
    assert r.sector is None
    assert r.industry is None


def test_profile_fetch_failure() -> None:
    with patch(
        "trade_assistant.market_data.yahoo_profile.yf.Ticker",
        side_effect=RuntimeError("network down"),
    ):
        r = fetch_yahoo_company_profile("TEST")

    assert r.fetched_ok is False
    assert r.error == "network down"
