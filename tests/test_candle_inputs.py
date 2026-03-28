from decimal import Decimal

from trade_assistant.bbs.candle_inputs import (
    CANDLE_EDGE,
    entry_from_last_high,
    gain_per_share_from_target,
    stop_from_last_low,
)


def test_entry_and_stop_formulas() -> None:
    high = Decimal("12.22")
    low = Decimal("11.45")
    assert entry_from_last_high(high) == high + (high * CANDLE_EDGE)
    assert stop_from_last_low(low) == low - (low * CANDLE_EDGE)


def test_gain_from_target() -> None:
    assert gain_per_share_from_target(Decimal("14.22"), Decimal("12.22")) == Decimal("2")


def test_breakout_entry_above_high() -> None:
    """Entry is 0.5% above high; stop 0.5% below low; G = target − high."""
    high = Decimal("12.22")
    low = Decimal("11.45")
    target = Decimal("14.22")
    e = entry_from_last_high(high)
    s = stop_from_last_low(low)
    g = gain_per_share_from_target(target, high)
    assert e == high * (Decimal("1") + CANDLE_EDGE)
    assert s == low * (Decimal("1") - CANDLE_EDGE)
    assert g == Decimal("2")
