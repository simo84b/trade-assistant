from __future__ import annotations

from decimal import Decimal

# 0.5% factor: entry above the candle high; stop below the candle low.
CANDLE_EDGE = Decimal("0.005")


def entry_from_last_high(last_candle_high: Decimal) -> Decimal:
    """Entry = high + (high × 0.005), i.e. 0.5% above the last candle high."""
    return last_candle_high + (last_candle_high * CANDLE_EDGE)


def stop_from_last_low(last_candle_low: Decimal) -> Decimal:
    """Stop = min − (min × 0.005), i.e. 0.5% below the last candle low."""
    return last_candle_low - (last_candle_low * CANDLE_EDGE)


def gain_per_share_from_target(target: Decimal, last_candle_high: Decimal) -> Decimal:
    """G per share = target − max (last candle high)."""
    return target - last_candle_high
