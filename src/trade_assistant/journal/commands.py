from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from trade_assistant.journal.db import default_db_path
from trade_assistant.journal.models import Trade, TradeCreate
from trade_assistant.journal.repository import JournalRepository

journal_app = typer.Typer(help="Core trading journal: open trades and history (SQLite).")
console = Console()


def _parse_decimal(value: str) -> Decimal:
    return Decimal(value.strip().replace(",", "."))


def _repo(ctx: typer.Context) -> JournalRepository:
    path: Path = ctx.obj["db_path"]
    return JournalRepository(path)


@journal_app.callback()
def journal_callback(
    ctx: typer.Context,
    db: Path | None = typer.Option(
        None,
        "--db",
        help="SQLite file (default: ~/.trade-assistant/trades.db or TRADE_ASSISTANT_DB)",
        path_type=Path,
    ),
) -> None:
    ctx.ensure_object(dict)
    ctx.obj["db_path"] = db.expanduser() if db is not None else default_db_path()


@journal_app.command("add")
def journal_add(
    ctx: typer.Context,
    symbol: str = typer.Argument(..., help="Ticker"),
    entry: str = typer.Option(..., "--entry", help="Entry fill price"),
    stop: str = typer.Option(..., "--stop", help="Current stop loss"),
    qty: int = typer.Option(..., "--qty", help="Shares", min=1),
    target: str | None = typer.Option(None, "--target", help="Target price (optional)"),
    strategy: str = typer.Option("core", "--strategy", help="e.g. core, swing"),
    technique: str | None = typer.Option(None, "--technique", help="e.g. bbs"),
    notes: str | None = typer.Option(None, "--notes", help="Free text"),
) -> None:
    """Record a new open trade."""
    repo = _repo(ctx)
    try:
        tid = repo.add_trade(
            TradeCreate(
                symbol=symbol,
                quantity=qty,
                entry_price=_parse_decimal(entry),
                stop_loss=_parse_decimal(stop),
                target_price=_parse_decimal(target) if target is not None else None,
                strategy=strategy,
                technique=technique,
                notes=notes,
            )
        )
        console.print(f"[green]Trade #{tid}[/green] saved ({symbol.upper()}). DB: {repo.path()}")
    finally:
        repo.close()


@journal_app.command("open")
def journal_open(ctx: typer.Context) -> None:
    """List open trades."""
    repo = _repo(ctx)
    try:
        rows = repo.list_trades(status="open")
        _print_trade_table(rows, title="Open trades")
    finally:
        repo.close()


@journal_app.command("list")
def journal_list(
    ctx: typer.Context,
    open_only: bool = typer.Option(False, "--open", help="Only open trades"),
    closed_only: bool = typer.Option(False, "--closed", help="Only closed trades"),
    symbol: str | None = typer.Option(None, "--symbol", "-s", help="Filter ticker"),
    limit: int = typer.Option(100, "--limit", min=1, max=2000),
) -> None:
    """List trades (default: all recent)."""
    if open_only and closed_only:
        console.print("[red]Use only one of --open or --closed.[/red]")
        raise typer.Exit(2)
    repo = _repo(ctx)
    try:
        st: str
        if open_only:
            st = "open"
        elif closed_only:
            st = "closed"
        else:
            st = "all"
        rows = repo.list_trades(status=st, symbol=symbol, limit=limit)
        _print_trade_table(rows, title="Trades")
    finally:
        repo.close()


@journal_app.command("show")
def journal_show(
    ctx: typer.Context,
    trade_id: int = typer.Argument(..., help="Trade id"),
) -> None:
    """Show one trade and its event history."""
    repo = _repo(ctx)
    try:
        t = repo.get_trade(trade_id)
        if not t:
            console.print(f"[red]No trade #{trade_id}[/red]")
            raise typer.Exit(1)
        _print_trade_table([t], title=f"Trade #{trade_id}")
        ev = repo.list_events(trade_id)
        et = Table(title="History")
        et.add_column("When")
        et.add_column("Kind")
        et.add_column("Detail")
        for e in ev:
            et.add_row(e.occurred_at.isoformat(), e.kind, e.detail or "")
        console.print(et)
    finally:
        repo.close()


@journal_app.command("close")
def journal_close(
    ctx: typer.Context,
    trade_id: int = typer.Argument(..., help="Trade id"),
    exit_px: str = typer.Option(..., "--exit", help="Exit price"),
    pnl: str | None = typer.Option(
        None,
        "--pnl",
        help="Realized P/L (optional; default (exit-entry)*qty for long)",
    ),
) -> None:
    """Close an open trade."""
    repo = _repo(ctx)
    try:
        ex = _parse_decimal(exit_px)
        pnl_d = _parse_decimal(pnl) if pnl is not None else None
        try:
            repo.close_trade(trade_id, ex, pnl_d)
        except LookupError:
            console.print(f"[red]Open trade #{trade_id} not found.[/red]")
            raise typer.Exit(1) from None
        console.print(f"[green]Trade #{trade_id} closed.[/green]")
    finally:
        repo.close()


@journal_app.command("log")
def journal_log(
    ctx: typer.Context,
    trade_id: int = typer.Argument(..., help="Trade id"),
    message: str = typer.Argument(..., help="Note text"),
) -> None:
    """Append a note to the trade history."""
    repo = _repo(ctx)
    try:
        if not repo.get_trade(trade_id):
            console.print(f"[red]No trade #{trade_id}[/red]")
            raise typer.Exit(1)
        repo.add_event(trade_id, "note", message)
        console.print(f"[green]Logged on #{trade_id}[/green]")
    finally:
        repo.close()


@journal_app.command("update-stop")
def journal_update_stop(
    ctx: typer.Context,
    trade_id: int = typer.Argument(..., help="Trade id"),
    stop: str = typer.Option(..., "--stop", help="New stop price"),
) -> None:
    """Update stop on an open trade (logged)."""
    repo = _repo(ctx)
    try:
        try:
            repo.update_stop(trade_id, _parse_decimal(stop))
        except LookupError:
            console.print(f"[red]Open trade #{trade_id} not found.[/red]")
            raise typer.Exit(1) from None
        console.print(f"[green]Stop updated on #{trade_id}[/green]")
    finally:
        repo.close()


def _print_trade_table(rows: list[Trade], title: str) -> None:
    if not rows:
        console.print("(none)")
        return
    t = Table(title=title)
    t.add_column("Id")
    t.add_column("Sym")
    t.add_column("Strat")
    t.add_column("St")
    t.add_column("Qty")
    t.add_column("Entry")
    t.add_column("Stop")
    t.add_column("Target")
    t.add_column("Exit")
    t.add_column("PnL")
    t.add_column("Opened")
    for r in rows:
        t.add_row(
            str(r.id),
            r.symbol,
            r.strategy,
            r.status,
            str(r.quantity),
            str(r.entry_price),
            str(r.stop_loss),
            str(r.target_price) if r.target_price is not None else "",
            str(r.exit_price) if r.exit_price is not None else "",
            str(r.realized_pnl) if r.realized_pnl is not None else "",
            r.opened_at.isoformat()[:19],
        )
    console.print(t)
