from datetime import date
from unittest.mock import MagicMock, patch

from trade_assistant.earnings.yahoo import check_upcoming_earnings


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
