from decimal import Decimal

import pytest

from trade_assistant.bbs import BBSSetup, evaluate_bbs


def test_valley_national_example_metrics() -> None:
    """Valley National Bancorp: entry 12.16, 350 shares, stop 11.39."""
    setup = BBSSetup(
        symbol="VLY",
        entry_price=Decimal("12.16"),
        stop_loss=Decimal("11.39"),
        quantity=350,
        potential_gain=Decimal("2.00"),  # e.g. target ~14.16 → G/R ≈ 2.6
        earnings_communication_imminent=False,
    )
    out = evaluate_bbs(setup)
    assert out.r_per_share == Decimal("0.77")
    assert out.position_notional == Decimal("12.16") * 350
    assert out.dollar_risk == Decimal("0.77") * 350
    # (12.16 - 11.39) / 12.16 * 100
    assert abs(out.position_risk_pct - Decimal("6.332236842105263157894736842")) < Decimal("0.01")


def test_gr_fails_below_1_5() -> None:
    setup = BBSSetup(
        symbol="X",
        entry_price=Decimal("10"),
        stop_loss=Decimal("9"),
        quantity=100,
        potential_gain=Decimal("1"),  # G/R = 1
        earnings_communication_imminent=False,
    )
    out = evaluate_bbs(setup)
    assert out.ok_to_trade is False


def test_earnings_blocks() -> None:
    setup = BBSSetup(
        symbol="X",
        entry_price=Decimal("10"),
        stop_loss=Decimal("9"),
        quantity=100,
        potential_gain=Decimal("5"),
        earnings_communication_imminent=True,
    )
    out = evaluate_bbs(setup)
    assert out.ok_to_trade is False


def test_invalid_long_stop() -> None:
    with pytest.raises(ValueError):
        BBSSetup(
            symbol="X",
            entry_price=Decimal("10"),
            stop_loss=Decimal("11"),
            quantity=100,
            potential_gain=Decimal("2"),
        )
