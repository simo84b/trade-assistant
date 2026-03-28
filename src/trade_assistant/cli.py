from __future__ import annotations

from decimal import Decimal

import typer
from rich.console import Console
from rich.table import Table

from trade_assistant import __version__
from trade_assistant.bbs import (
    BBSSetup,
    entry_from_last_high,
    evaluate_bbs,
    gain_per_share_from_target,
    stop_from_last_low,
)
from trade_assistant.earnings import EarningsCheckResult, check_upcoming_earnings
from trade_assistant.journal.commands import journal_app
from trade_assistant.sizing import optimal_quantity

# Typer flattens a *single* subcommand into the root CLI (SYMBOL becomes the first
# positional). A second command keeps `bbs-eval` as a real subcommand.
app = typer.Typer(help="Paper-trading assistant (BBS and more).")
app.add_typer(journal_app, name="journal")
console = Console()


@app.command("version")
def version_cmd() -> None:
    """Print the package version."""
    typer.echo(__version__)


def _parse_decimal(value: str) -> Decimal:
    """Parse CLI number; accepts 12.16 or 12,16."""
    return Decimal(value.strip().replace(",", "."))


@app.command("bbs-eval")
def bbs_eval(
    symbol: str = typer.Argument(..., help="Ticker / symbol"),
    high: str = typer.Option(
        ...,
        "--high",
        help="Last candle high (max of the candle you are using)",
    ),
    low: str = typer.Option(
        ...,
        "--low",
        help="Last candle low (min of the candle you are using)",
    ),
    target: str = typer.Option(
        ...,
        "--target",
        help="Target level (price); G per share = target - high",
    ),
    account: str = typer.Option(
        ...,
        "--account",
        help="Total capital available for trading (same currency as prices)",
    ),
    max_loss: str = typer.Option(
        ...,
        "--max-loss",
        help="Max $ loss per single operation for this strategy (absolute)",
    ),
    strategy: str = typer.Option(
        "core",
        "--strategy",
        help="Strategy label (e.g. core, swing); used for future presets; sizing uses --max-loss",
    ),
    slots: int | None = typer.Option(
        None,
        "--slots",
        min=1,
        max=20,
        help="Override concurrent-operation count (default: tiered from --account)",
    ),
    earnings_soon: bool = typer.Option(
        False,
        "--earnings-soon",
        help="Manual flag: earnings (or similar) imminent; discourages trade",
    ),
    no_auto_earnings: bool = typer.Option(
        False,
        "--no-auto-earnings",
        help="Do not query Yahoo for the next earnings date",
    ),
    weeks: int = typer.Option(
        3,
        "--weeks",
        min=1,
        max=52,
        help="Earnings window: flag if next earnings is within this many weeks (default 3)",
    ),
) -> None:
    """Evaluate a Basic Buy Setup (long).

    Entry and stop are derived from the last candle: entry = high + high*0.005,
    stop = low - low*0.005. G per share = target - high.

    Share count is computed from --account, tiered concurrent operations, and --max-loss:
    qty = min(floor(capital_per_op / entry), floor(max_loss / R_per_share)).
    """
    high_d = _parse_decimal(high)
    low_d = _parse_decimal(low)
    target_d = _parse_decimal(target)
    account_d = _parse_decimal(account)
    max_loss_d = _parse_decimal(max_loss)

    if low_d > high_d:
        console.print("[red]Error:[/red] --low must be <= --high (last candle min <= max).")
        raise typer.Exit(2)

    entry_d = entry_from_last_high(high_d)
    stop_d = stop_from_last_low(low_d)
    gain_d = gain_per_share_from_target(target_d, high_d)

    if stop_d >= entry_d:
        console.print(
            "[red]Error:[/red] Derived stop must be below derived entry. "
            "Check --high / --low (wider spread or invalid candle)."
        )
        raise typer.Exit(2)

    if gain_d <= 0:
        console.print(
            "[red]Error:[/red] G = target - high must be > 0 (target above last candle high)."
        )
        raise typer.Exit(2)

    r_per_share = entry_d - stop_d
    try:
        qty, num_ops, capital_per_op, q_cap, q_risk = optimal_quantity(
            account_d,
            entry_d,
            r_per_share,
            max_loss_d,
            num_concurrent_ops=slots,
        )
    except ValueError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(2) from exc

    if qty < 1:
        console.print(
            "[red]Error:[/red] Computed quantity is 0. "
            "Raise --account / --max-loss, lower entry (wider capital slice), "
            "or use --slots to change concurrent-operation count."
        )
        raise typer.Exit(2)

    horizon_days = weeks * 7

    auto: EarningsCheckResult | None = None
    if not no_auto_earnings:
        auto = check_upcoming_earnings(symbol, horizon_days=horizon_days)
        if not auto.fetched_ok and auto.error:
            console.print(
                f"[yellow]Warning:[/yellow] Could not fetch Yahoo earnings calendar for "
                f"{symbol!r}: {auto.error}. "
                "Use --no-auto-earnings to skip, or --earnings-soon to flag manually."
            )

    imminent = earnings_soon
    if auto is not None and auto.fetched_ok:
        imminent = imminent or auto.is_within_horizon

    fail_detail: str | None = None
    if earnings_soon:
        fail_detail = "Manual flag: earnings / communication imminent"
    elif (
        auto is not None
        and auto.fetched_ok
        and auto.is_within_horizon
        and auto.next_earnings_date
    ):
        fail_detail = (
            f"Next earnings on {auto.next_earnings_date.isoformat()} "
            f"(Yahoo; within {weeks} week(s) / {horizon_days} days)"
        )

    ok_detail: str | None = None
    if not imminent and auto is not None and auto.fetched_ok:
        if auto.next_earnings_date is not None:
            ok_detail = (
                f"Next earnings {auto.next_earnings_date.isoformat()} (Yahoo); "
                f"outside {weeks}-week window"
            )
        else:
            ok_detail = "No upcoming earnings date listed on Yahoo for this symbol"

    setup = BBSSetup(
        symbol=symbol,
        entry_price=entry_d,
        stop_loss=stop_d,
        quantity=qty,
        potential_gain=gain_d,
        earnings_communication_imminent=imminent,
        account_equity=account_d,
    )
    result = evaluate_bbs(
        setup,
        earnings_detail_fail=fail_detail,
        earnings_detail_ok=ok_detail,
    )

    console.print(f"\n[bold]{result.symbol}[/bold] — {result.summary}\n")
    m = Table(show_header=False, box=None)
    m.add_row("Account", f"{account_d}")
    m.add_row("Strategy", strategy)
    m.add_row("Concurrent operations", str(num_ops))
    m.add_row("Capital per operation", f"{capital_per_op}")
    m.add_row("Max loss / operation", f"{max_loss_d}")
    m.add_row("Shares (cap floor)", str(q_cap))
    m.add_row("Shares (risk floor)", str(q_risk))
    m.add_row("Shares (chosen qty)", str(qty))
    m.add_row("Last candle high", f"{high_d}")
    m.add_row("Last candle low", f"{low_d}")
    m.add_row("Target", f"{target_d}")
    m.add_row("Derived entry (high + high*0.005)", f"{entry_d}")
    m.add_row("Derived stop (low - low*0.005)", f"{stop_d}")
    m.add_row("Derived G (target - high)", f"{gain_d}")
    m.add_row("G/R", f"{result.gr_ratio:.4f}")
    m.add_row("R (per share)", f"{result.r_per_share}")
    m.add_row("G (per share)", f"{result.g_per_share}")
    m.add_row("Position risk %", f"{result.position_risk_pct:.2f}%")
    m.add_row("Dollar risk", f"{result.dollar_risk}")
    m.add_row("Position notional", f"{result.position_notional}")
    if result.account_risk_pct is not None:
        m.add_row("Account risk %", f"{result.account_risk_pct:.2f}%")
    if auto is not None:
        if auto.fetched_ok and auto.next_earnings_date is not None:
            m.add_row("Next earnings (Yahoo)", auto.next_earnings_date.isoformat())
            m.add_row(
                f"Within {weeks} week(s)",
                "yes" if auto.is_within_horizon else "no",
            )
        elif auto.fetched_ok:
            m.add_row("Next earnings (Yahoo)", "— (not listed)")
    console.print(m)

    t = Table(title="Rules")
    t.add_column("Rule")
    t.add_column("Status")
    t.add_column("Detail")
    for r in result.rules:
        style = "green" if r.severity == "ok" else ("yellow" if r.severity == "warn" else "red")
        status = "PASS" if r.passed else "FAIL"
        t.add_row(r.label, f"[{style}]{status}[/{style}]", r.detail)
    console.print(t)
    raise typer.Exit(0 if result.ok_to_trade else 1)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
