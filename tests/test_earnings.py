from datetime import date
from unittest.mock import MagicMock, patch

from trade_assistant.earnings.yahoo import (
    EarningsCheckResult,
    check_upcoming_earnings,
    dividend_calendar_rule_text,
)


def test_within_horizon_from_calendar() -> None:
    fake = MagicMock()
    fake.calendar = {"Earnings Date": [date(2026, 4, 10)]}
    fake.get_earnings_dates.return_value = None

    with patch("trade_assistant.earnings.yahoo.yf.Ticker", return_value=fake):
        r = check_upcoming_earnings("TEST", horizon_days=21, as_of=date(2026, 3, 28))

    assert r.fetched_ok is True
    assert r.next_earnings_date == date(2026, 4, 10)
    assert r.is_within_horizon is True


def test_outside_horizon_from_calendar() -> None:
    fake = MagicMock()
    fake.calendar = {"Earnings Date": [date(2026, 5, 1)]}
    fake.get_earnings_dates.return_value = None

    with patch("trade_assistant.earnings.yahoo.yf.Ticker", return_value=fake):
        r = check_upcoming_earnings("TEST", horizon_days=21, as_of=date(2026, 3, 28))

    assert r.fetched_ok is True
    assert r.next_earnings_date == date(2026, 5, 1)
    assert r.is_within_horizon is False


def test_no_date_listed() -> None:
    fake = MagicMock()
    fake.calendar = {}
    fake.get_earnings_dates.return_value = None

    with patch("trade_assistant.earnings.yahoo.yf.Ticker", return_value=fake):
        r = check_upcoming_earnings("TEST", horizon_days=21, as_of=date(2026, 3, 28))

    assert r.fetched_ok is True
    assert r.next_earnings_date is None
    assert r.is_within_horizon is False


def test_earnings_today_counts_as_within() -> None:
    d = date(2026, 4, 10)
    fake = MagicMock()
    fake.calendar = {"Earnings Date": [d]}
    fake.get_earnings_dates.return_value = None

    with patch("trade_assistant.earnings.yahoo.yf.Ticker", return_value=fake):
        r = check_upcoming_earnings("TEST", horizon_days=21, as_of=d)

    assert r.is_within_horizon is True


def test_dividend_dates_within_horizon() -> None:
    fake = MagicMock()
    fake.calendar = {
        "Earnings Date": [date(2026, 5, 1)],
        "Ex-Dividend Date": date(2026, 4, 5),
        "Dividend Date": date(2026, 4, 10),
    }
    fake.get_earnings_dates.return_value = None

    with patch("trade_assistant.earnings.yahoo.yf.Ticker", return_value=fake):
        r = check_upcoming_earnings("TEST", horizon_days=21, as_of=date(2026, 3, 28))

    assert r.next_ex_dividend_date == date(2026, 4, 5)
    assert r.ex_dividend_within_horizon is True
    assert r.next_dividend_date == date(2026, 4, 10)
    assert r.dividend_within_horizon is True
    assert r.is_within_horizon is False


def test_dividend_dates_outside_horizon() -> None:
    fake = MagicMock()
    fake.calendar = {
        "Ex-Dividend Date": date(2026, 5, 15),
        "Dividend Date": date(2026, 6, 1),
    }
    fake.get_earnings_dates.return_value = None

    with patch("trade_assistant.earnings.yahoo.yf.Ticker", return_value=fake):
        r = check_upcoming_earnings("TEST", horizon_days=21, as_of=date(2026, 3, 28))

    assert r.ex_dividend_within_horizon is False
    assert r.dividend_within_horizon is False


def test_dividend_rule_text_warns_with_explanation() -> None:
    check = EarningsCheckResult(
        symbol="TEST",
        horizon_days=21,
        fetched_ok=True,
        next_earnings_date=None,
        is_within_horizon=False,
        as_of=date(2026, 3, 28),
        next_ex_dividend_date=date(2026, 4, 5),
        ex_dividend_within_horizon=True,
        next_dividend_date=None,
        dividend_within_horizon=False,
    )
    detail, severity = dividend_calendar_rule_text(check, weeks=3)
    assert severity == "warn"
    assert "Ex-dividend on 2026-04-05" in detail
    assert "last trading day to buy" in detail
    assert "Review dividend timing" in detail
