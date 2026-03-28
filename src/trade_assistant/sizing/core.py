from __future__ import annotations

from decimal import Decimal

# Ambiguous tiers use the higher slot count (smaller slice per operation, more conservative).


def concurrent_operations(account: Decimal) -> int:
    """
    How many concurrent operations to plan for, based on total trading capital.

    Tiers (account in same currency as *account*):
    - <= 3000: 2
    - (3000, 6000]: 3
    - (6000, 10000]: 4  (user range 3-4)
    - (10000, 20000]: 5  (user range 4-5)
    - (20000, 75000]: 5
    - > 75000: 8  (user range 6-10)
    """
    if account <= 0:
        raise ValueError("account must be positive")
    if account <= Decimal("3000"):
        return 2
    if account <= Decimal("6000"):
        return 3
    if account <= Decimal("10000"):
        return 4
    if account <= Decimal("20000"):
        return 5
    if account <= Decimal("75000"):
        return 5
    return 8


def optimal_quantity(
    account: Decimal,
    entry: Decimal,
    r_per_share: Decimal,
    max_loss_dollars: Decimal,
    *,
    num_concurrent_ops: int | None = None,
) -> tuple[int, int, Decimal, int, int]:
    """
    Compute share count for one operation.

    - *capital_per_op* = account / num_concurrent_ops
    - *q_cap* = floor(capital_per_op / entry)
    - *q_risk* = floor(max_loss_dollars / r_per_share)
    - *qty* = min(q_cap, q_risk)

    Returns (qty, num_ops, capital_per_op, q_cap, q_risk).
    """
    if entry <= 0:
        raise ValueError("entry must be positive")
    if r_per_share <= 0:
        raise ValueError("r_per_share must be positive")
    if max_loss_dollars <= 0:
        raise ValueError("max_loss must be positive")

    n = num_concurrent_ops if num_concurrent_ops is not None else concurrent_operations(account)
    if n < 1:
        raise ValueError("num_concurrent_ops must be >= 1")

    capital_per_op = account / Decimal(n)
    q_cap = int(capital_per_op // entry)
    q_risk = int(max_loss_dollars // r_per_share)
    qty = min(q_cap, q_risk)
    return qty, n, capital_per_op, q_cap, q_risk
