from __future__ import annotations

from decimal import Decimal

from trade_assistant.bbs.models import BBSEvaluation, BBSSetup, RuleStatus


def _d(x: Decimal | int | float) -> Decimal:
    if isinstance(x, Decimal):
        return x
    return Decimal(str(x))


def evaluate_bbs(setup: BBSSetup) -> BBSEvaluation:
    """
    Evaluate a Basic Buy Setup (long).

    - R (risk per share) = entry - stop_loss.
    - G (potential gain per share) = setup.potential_gain (must be in the same unit as price).
    - G/R = potential_gain / R.
    - Position risk %%: (entry - stop) / entry × 100 (share count cancels; same as dollar_risk / notional).
    """
    entry = setup.entry_price
    stop = setup.stop_loss
    qty = setup.quantity

    r_per_share = entry - stop
    g_per_share = setup.potential_gain
    gr_ratio = g_per_share / r_per_share if r_per_share > 0 else Decimal("0")

    position_notional = entry * qty
    dollar_risk = r_per_share * qty
    position_risk_pct = (r_per_share / entry) * Decimal("100")

    account_risk_pct: Decimal | None = None
    if setup.account_equity is not None:
        account_risk_pct = (dollar_risk / setup.account_equity) * Decimal("100")

    rules: list[RuleStatus] = []

    # G/R
    if gr_ratio > Decimal("2.5"):
        rules.append(
            RuleStatus(
                rule_id="gr_ratio",
                passed=True,
                label="G/R ratio",
                detail=f"{gr_ratio:.2f} (ideal: > 2.5)",
                severity="ok",
            )
        )
    elif gr_ratio > Decimal("1.5"):
        rules.append(
            RuleStatus(
                rule_id="gr_ratio",
                passed=True,
                label="G/R ratio",
                detail=f"{gr_ratio:.2f} (acceptable: > 1.5; ideal would be > 2.5)",
                severity="warn",
            )
        )
    else:
        rules.append(
            RuleStatus(
                rule_id="gr_ratio",
                passed=False,
                label="G/R ratio",
                detail=f"{gr_ratio:.2f} (must be > 1.5; G and R are per-share)",
                severity="fail",
            )
        )

    # Position risk %
    if position_risk_pct >= Decimal("10"):
        rules.append(
            RuleStatus(
                rule_id="position_risk_pct",
                passed=False,
                label="Position risk (%% of entry)",
                detail=f"{position_risk_pct:.2f}%% (must stay below 10%%)",
                severity="fail",
            )
        )
    elif position_risk_pct > Decimal("6.5") or position_risk_pct < Decimal("5"):
        rules.append(
            RuleStatus(
                rule_id="position_risk_pct",
                passed=True,
                label="Position risk (%% of entry)",
                detail=f"{position_risk_pct:.2f}%% (ideally about 5–6%%)",
                severity="warn",
            )
        )
    else:
        rules.append(
            RuleStatus(
                rule_id="position_risk_pct",
                passed=True,
                label="Position risk (%% of entry)",
                detail=f"{position_risk_pct:.2f}%%",
                severity="ok",
            )
        )

    # Optional account risk (informational / future hard rule)
    if account_risk_pct is not None:
        rules.append(
            RuleStatus(
                rule_id="account_risk_pct",
                passed=True,
                label="Account risk (%% of equity)",
                detail=f"{account_risk_pct:.2f}%% (dollar risk / account)",
                severity="ok",
            )
        )

    # Earnings
    if setup.earnings_communication_imminent:
        rules.append(
            RuleStatus(
                rule_id="earnings",
                passed=False,
                label="Earnings / communication",
                detail="Imminent earnings or similar — trade discouraged",
                severity="fail",
            )
        )
    else:
        rules.append(
            RuleStatus(
                rule_id="earnings",
                passed=True,
                label="Earnings / communication",
                detail="No earnings flag set",
                severity="ok",
            )
        )

    ok_to_trade = all(r.passed for r in rules)

    warns = [r for r in rules if r.severity == "warn"]
    if ok_to_trade and warns:
        summary = "Acceptable setup with warnings — review before entering."
    elif ok_to_trade:
        summary = "Setup passes BBS rules."
    else:
        summary = "Setup does not pass BBS rules — do not enter without a deliberate override."

    return BBSEvaluation(
        symbol=setup.symbol,
        ok_to_trade=ok_to_trade,
        summary=summary,
        r_per_share=r_per_share,
        g_per_share=g_per_share,
        gr_ratio=gr_ratio,
        position_risk_pct=position_risk_pct,
        dollar_risk=dollar_risk,
        position_notional=position_notional,
        account_risk_pct=account_risk_pct,
        rules=rules,
    )
