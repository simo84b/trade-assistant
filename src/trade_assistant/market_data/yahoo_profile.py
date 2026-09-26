from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import yfinance as yf


@dataclass(frozen=True)
class YahooCompanyProfile:
    """Company classification from Yahoo Finance (via ``yfinance``)."""

    symbol: str
    fetched_ok: bool
    sector: str | None
    industry: str | None
    error: str | None = None
    """Set when *fetched_ok* is False."""


def _clean_label(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    s = value.strip()
    return s or None


def fetch_yahoo_company_profile(symbol: str) -> YahooCompanyProfile:
    """
    Load sector (and industry) for *symbol* from Yahoo Finance.

    Same underlying source as the ticker quote page on
    `Yahoo Finance <https://finance.yahoo.com/quote/>` (``yfinance`` → ``Ticker.info``).
    Fields can be missing for some symbols; treat as advisory.
    """
    sym = str(symbol).strip()
    try:
        info = yf.Ticker(sym).info
        if not isinstance(info, dict) or not info:
            return YahooCompanyProfile(
                symbol=sym,
                fetched_ok=False,
                sector=None,
                industry=None,
                error="Empty profile response from Yahoo",
            )
        return YahooCompanyProfile(
            symbol=sym,
            fetched_ok=True,
            sector=_clean_label(info.get("sector")),
            industry=_clean_label(info.get("industry")),
            error=None,
        )
    except Exception as exc:  # noqa: BLE001 — surface as failed fetch
        return YahooCompanyProfile(
            symbol=sym,
            fetched_ok=False,
            sector=None,
            industry=None,
            error=str(exc),
        )
