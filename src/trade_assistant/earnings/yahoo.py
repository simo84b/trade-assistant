from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

import yfinance as yf


@dataclass(frozen=True)
class EarningsCheckResult:
    """Result of looking up the next earnings date (Yahoo Finance via yfinance)."""

    symbol: str
    horizon_days: int
    fetched_ok: bool
    next_earnings_date: date | None
    """Earliest upcoming earnings on or after *as_of* (local date), if known."""
    is_within_horizon: bool
    """True if *next_earnings_date* falls within [as_of, as_of + horizon_days] (inclusive)."""
    as_of: date
    error: str | None = None
    """Set when *fetched_ok* is False."""


def _to_date(x: Any) -> date | None:
    if x is None:
        return None
    if isinstance(x, date) and not isinstance(x, datetime):
        return x
    if isinstance(x, datetime):
        return x.date()
    if isinstance(x, str):
        try:
            return date.fromisoformat(x[:10])
        except ValueError:
            return None
    return None


def _next_from_calendar_dict(cal: dict[str, Any], as_of: date) -> date | None:
    raw = cal.get("Earnings Date")
    if raw is None:
        return None
    items = raw if isinstance(raw, (list, tuple)) else [raw]
    candidates: list[date] = []
    for it in items:
        d = _to_date(it)
        if d is not None:
            candidates.append(d)
    if not candidates:
        return None
    future = [d for d in candidates if d >= as_of]
    if not future:
        return None
    return min(future)


def _next_from_earnings_dates_df(df: Any, as_of: date) -> date | None:
    if df is None or (hasattr(df, "empty") and df.empty):
        return None
    idx = getattr(df, "index", None)
    if idx is None or len(idx) == 0:
        return None
    candidates: list[date] = []
    for ts in idx:
        if hasattr(ts, "date"):
            d = ts.date()  # type: ignore[union-attr]
        elif isinstance(ts, date):
            d = ts
        else:
            d = _to_date(ts)
        if d is not None:
            candidates.append(d)
    future = [d for d in candidates if d >= as_of]
    if not future:
        return None
    return min(future)


def check_upcoming_earnings(
    symbol: str,
    horizon_days: int = 21,
    *,
    as_of: date | None = None,
) -> EarningsCheckResult:
    """
    Return whether the next known earnings date falls within the next *horizon_days* days (inclusive).

    Data source: Yahoo Finance through ``yfinance`` (same underlying data as the
    `earnings calendar <https://finance.yahoo.com/calendar/earnings>`_). Results can be
    missing or delayed; treat as advisory.

    *horizon_days* default is 21 (three weeks).
    """
    sym = str(symbol).strip()
    ref = as_of or date.today()
    end = ref + timedelta(days=horizon_days)

    try:
        t = yf.Ticker(sym)
        cal = t.calendar
        next_d: date | None = None

        if isinstance(cal, dict):
            next_d = _next_from_calendar_dict(cal, ref)

        if next_d is None:
            try:
                df = t.get_earnings_dates(limit=12)
            except Exception:
                df = None
            next_d = _next_from_earnings_dates_df(df, ref)

        if next_d is None:
            return EarningsCheckResult(
                symbol=sym,
                horizon_days=horizon_days,
                fetched_ok=True,
                next_earnings_date=None,
                is_within_horizon=False,
                as_of=ref,
                error=None,
            )

        in_window = ref <= next_d <= end
        return EarningsCheckResult(
            symbol=sym,
            horizon_days=horizon_days,
            fetched_ok=True,
            next_earnings_date=next_d,
            is_within_horizon=in_window,
            as_of=ref,
            error=None,
        )
    except Exception as exc:  # noqa: BLE001 — surface as failed fetch
        return EarningsCheckResult(
            symbol=sym,
            horizon_days=horizon_days,
            fetched_ok=False,
            next_earnings_date=None,
            is_within_horizon=False,
            as_of=ref,
            error=str(exc),
        )
