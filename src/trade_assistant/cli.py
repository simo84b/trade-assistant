from __future__ import annotations

from decimal import Decimal

import typer
from rich.console import Console
from rich.table import Table

from trade_assistant.bbs import BBSSetup, evaluate_bbs

app = typer.Typer(help="Paper-trading assistant (BBS and more).")
console = Console()


@app.command("bbs-eval")
def bbs_eval(
    symbol: str = typer.Argument(..., help="Ticker / symbol"),
    entry: Decimal = typer.Option(..., "--entry", help="Entry price"),
    stop: Decimal = typer.Option(..., "--stop", help="Initial stop loss (below entry)"),
    qty: int = typer.Option(..., "--qty", help="Number of shares"),
    gain: Decimal = typer.Option(
        ...,
        "--gain",
        help="Potential gain G per share (e.g. target_price - entry)",
    ),
    earnings_soon: bool = typer.Option(
        False,
        "--earnings-soon",
        help="Set if earnings (or similar) are imminent; discourages trade",
    ),
    account: Decimal | None = typer.Option(
        None,
        "--account",
        help="Optional total account equity for account risk %%",
    ),
) -> None:
    """Evaluate a Basic Buy Setup (long)."""
    setup = BBSSetup(
        symbol=symbol,
        entry_price=entry,
        stop_loss=stop,
        quantity=qty,
        potential_gain=gain,
        earnings_communication_imminent=earnings_soon,
        account_equity=account,
    )
    result = evaluate_bbs(setup)

    console.print(f"\n[bold]{result.symbol}[/bold] — {result.summary}\n")
    m = Table(show_header=False, box=None)
    m.add_row("G/R", f"{result.gr_ratio:.4f}")
    m.add_row("R (per share)", f"{result.r_per_share}")
    m.add_row("G (per share)", f"{result.g_per_share}")
    m.add_row("Position risk %", f"{result.position_risk_pct:.2f}%")
    m.add_row("Dollar risk", f"{result.dollar_risk}")
    m.add_row("Position notional", f"{result.position_notional}")
    if result.account_risk_pct is not None:
        m.add_row("Account risk %", f"{result.account_risk_pct:.2f}%")
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
