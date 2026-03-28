from decimal import Decimal

import pytest

from trade_assistant.sizing import concurrent_operations, optimal_quantity


@pytest.mark.parametrize(
    ("account", "expected"),
    [
        (Decimal("2500"), 2),
        (Decimal("3000"), 2),
        (Decimal("3000.01"), 3),
        (Decimal("6000"), 3),
        (Decimal("6000.01"), 4),
        (Decimal("10000"), 4),
        (Decimal("10000.01"), 5),
        (Decimal("20000"), 5),
        (Decimal("75000"), 5),
        (Decimal("75000.01"), 8),
    ],
)
def test_concurrent_operations_tiers(account: Decimal, expected: int) -> None:
    assert concurrent_operations(account) == expected


def test_optimal_quantity_min_of_cap_and_risk() -> None:
    # account 10000 -> 4 ops -> 2500 per op; entry 10 -> 250 shares cap
    # max_loss 200, R=1 -> 200 shares risk
    account = Decimal("10000")
    entry = Decimal("10")
    r = Decimal("1")
    max_loss = Decimal("200")
    qty, n, cap_op, q_cap, q_risk = optimal_quantity(account, entry, r, max_loss)
    assert n == 4
    assert cap_op == Decimal("2500")
    assert q_cap == 250
    assert q_risk == 200
    assert qty == 200


def test_optimal_quantity_slots_override() -> None:
    qty, n, _, _, _ = optimal_quantity(
        Decimal("10000"),
        Decimal("10"),
        Decimal("1"),
        Decimal("500"),
        num_concurrent_ops=2,
    )
    assert n == 2
    assert qty == 500  # min(5000 cap, 500 risk)


def test_concurrent_operations_rejects_non_positive() -> None:
    with pytest.raises(ValueError):
        concurrent_operations(Decimal("0"))
