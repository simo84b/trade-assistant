from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Literal

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
    next_ex_dividend_date: date | None = None
    """Earliest upcoming ex-dividend date on or after *as_of*, if known."""
    ex_dividend_within_horizon: bool = False
    next_dividend_date: date | None = None
    """Earliest upcoming dividend payment date on or after *as_of*, if known."""
    dividend_within_horizon: bool = False
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


def _next_from_calendar_key(cal: dict[str, Any], key: str, as_of: date) -> date | None:
    raw = cal.get(key)
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


def _within_horizon(d: date | None, *, as_of: date, end: date) -> bool:
    return d is not None and as_of <= d <= end


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


def dividend_calendar_rule_text(
    check: EarningsCheckResult,
    *,
    weeks: int,
) -> tuple[str, Literal["ok", "warn"]]:
    """
    Build Rules-table detail for ex-dividend and dividend payment dates (Yahoo calendar).

    Warn severity when either date falls within *check*'s horizon; always ``passed=True``.
    """
    horizon_days = check.horizon_days
    parts: list[str] = []
    warn = False

    if check.next_ex_dividend_date is not None:
        d = check.next_ex_dividend_date.isoformat()
        if check.ex_dividend_within_horizon:
            warn = True
            parts.append(
                f"Ex-dividend on {d} (Yahoo): last trading day to buy shares and still "
                "receive the declared cash dividend on the payment date; the stock often "
                "adjusts down around this date as the payout is priced out. "
                f"This falls within your {weeks}-week ({horizon_days}-day) window."
            )
        else:
            parts.append(
                f"Next ex-dividend on {d} (Yahoo): last day to purchase and receive the "
                f"upcoming dividend — outside your {weeks}-week window."
            )

    if check.next_dividend_date is not None:
        d = check.next_dividend_date.isoformat()
        if check.dividend_within_horizon:
            warn = True
            parts.append(
                f"Dividend payment on {d} (Yahoo): the company pays the cash dividend to "
                "shareholders who held the stock before the ex-dividend date. "
                f"This falls within your {weeks}-week ({horizon_days}-day) window."
            )
        else:
            parts.append(
                f"Next dividend payment on {d} (Yahoo) — outside your {weeks}-week window."
            )

    if not parts:
        return (
            "No upcoming ex-dividend or dividend payment dates listed on Yahoo for this symbol.",
            "ok",
        )

    if warn:
        parts.append("Review dividend timing before entering.")
    return (" ".join(parts), "warn" if warn else "ok")


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
        cal_dict: dict[str, Any] = cal if isinstance(cal, dict) else {}
        next_d: date | None = None
        ex_div_d: date | None = None
        div_pay_d: date | None = None

        if cal_dict:
            next_d = _next_from_calendar_key(cal_dict, "Earnings Date", ref)
            ex_div_d = _next_from_calendar_key(cal_dict, "Ex-Dividend Date", ref)
            div_pay_d = _next_from_calendar_key(cal_dict, "Dividend Date", ref)

        if next_d is None:
            try:
                df = t.get_earnings_dates(limit=12)
            except Exception:
                df = None
            next_d = _next_from_earnings_dates_df(df, ref)

        if (
            next_d is None
            and ex_div_d is None
            and div_pay_d is None
        ):
            return EarningsCheckResult(
                symbol=sym,
                horizon_days=horizon_days,
                fetched_ok=True,
                next_earnings_date=None,
                is_within_horizon=False,
                as_of=ref,
                error=None,
            )

        return EarningsCheckResult(
            symbol=sym,
            horizon_days=horizon_days,
            fetched_ok=True,
            next_earnings_date=next_d,
            is_within_horizon=_within_horizon(next_d, as_of=ref, end=end),
            as_of=ref,
            next_ex_dividend_date=ex_div_d,
            ex_dividend_within_horizon=_within_horizon(ex_div_d, as_of=ref, end=end),
            next_dividend_date=div_pay_d,
            dividend_within_horizon=_within_horizon(div_pay_d, as_of=ref, end=end),
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
