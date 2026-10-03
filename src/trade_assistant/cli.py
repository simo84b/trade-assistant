from __future__ import annotations

import tomllib
from decimal import Decimal, InvalidOperation
from pathlib import Path
import re
from typing import Literal

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
from trade_assistant.earnings import (
    EarningsCheckResult,
    check_upcoming_earnings,
    dividend_calendar_rule_text,
)
from trade_assistant.market_data import YahooCompanyProfile, fetch_yahoo_company_profile
from trade_assistant.journal.commands import journal_app
from trade_assistant.sizing import optimal_quantity

# Typer flattens a *single* subcommand into the root CLI (SYMBOL becomes the first
# positional). A second command keeps `bbs-eval` as a real subcommand.
app = typer.Typer(help="Paper-trading assistant (BBS and more).")
app.add_typer(journal_app, name="journal")
config_app = typer.Typer(help="Manage user configuration.")
app.add_typer(config_app, name="config")
console = Console()


@app.command("version")
def version_cmd() -> None:
    """Print the package version."""
    typer.echo(__version__)


def _parse_decimal(value: str) -> Decimal:
    """Parse CLI number; accepts 12.16 or 12,16."""
    return Decimal(value.strip().replace(",", "."))


def _bbs_user_config_path() -> Path:
    return Path.home() / ".trade-assistant" / "config.toml"


def _load_bbs_user_defaults(required: tuple[str, ...]) -> dict[str, str]:
    """Load optional BBS sizing defaults from the user's TOML config."""
    path = _bbs_user_config_path()
    try:
        with path.open("rb") as config_file:
            config = tomllib.load(config_file)
    except FileNotFoundError:
        return {}
    except OSError as exc:
        raise ValueError(f"Could not read user config at {path}: {exc}") from exc
    except tomllib.TOMLDecodeError as exc:
        raise ValueError(f"Invalid TOML in user config at {path}: {exc}") from exc

    bbs_config = config.get("bbs_eval", {})
    if not isinstance(bbs_config, dict):
        raise ValueError(f"The [bbs_eval] section in {path} must be a TOML table.")

    defaults: dict[str, str] = {}
    for key in required:
        if key not in bbs_config:
            continue
        value = bbs_config[key]
        if isinstance(value, bool) or not isinstance(value, (str, int, float)):
            raise ValueError(f"bbs_eval.{key} in {path} must be a number or numeric string.")
        defaults[key] = str(value)
    return defaults


def _save_bbs_user_defaults(account: str | None, max_loss: str | None) -> Path:
    """Update BBS sizing defaults without replacing unrelated user config."""
    path = _bbs_user_config_path()
    values: dict[str, str] = {}
    for key, value in (("account", account), ("max_loss", max_loss)):
        if value is None:
            continue
        try:
            parsed = _parse_decimal(value)
        except (InvalidOperation, ValueError) as exc:
            raise ValueError(f"{key.replace('_', '-')} must be a valid number.") from exc
        if not parsed.is_finite() or parsed <= 0:
            raise ValueError(f"{key.replace('_', '-')} must be a positive finite number.")
        values[key] = str(parsed)

    try:
        content = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        content = ""
    except (OSError, UnicodeError) as exc:
        raise ValueError(f"Could not read user config at {path}: {exc}") from exc

    try:
        config = tomllib.loads(content)
    except tomllib.TOMLDecodeError as exc:
        raise ValueError(f"Invalid TOML in user config at {path}: {exc}") from exc
    bbs_config = config.get("bbs_eval", {})
    if not isinstance(bbs_config, dict):
        raise ValueError(f"The [bbs_eval] section in {path} must be a TOML table.")

    lines = content.splitlines()
    section_start: int | None = None
    section_end = len(lines)
    for index, line in enumerate(lines):
        if re.match(r"^\s*\[bbs_eval\]\s*(?:#.*)?$", line):
            section_start = index
        elif re.match(r"^\s*\[", line):
            if section_start is not None:
                section_end = index
                break
            if re.match(r"^\s*\[bbs_eval\.", line):
                raise ValueError(
                    f"Cannot update an implicit [bbs_eval] table in {path}; "
                    "use a standalone [bbs_eval] section."
                )

    if section_start is None:
        if bbs_config:
            raise ValueError(
                f"Cannot update the existing bbs_eval table in {path}; "
                "use a standalone [bbs_eval] section."
            )
        if content and not content.endswith("\n"):
            lines.append("")
        if lines and lines[-1] != "":
            lines.append("")
        lines.extend(("[bbs_eval]", *(f'{key} = "{value}"' for key, value in values.items())))
    else:
        section = lines[section_start + 1 : section_end]
        updated_keys: set[str] = set()
        for index, line in enumerate(section):
            match = re.match(r"^\s*(account|max_loss)\s*=", line)
            if match and match.group(1) in values:
                key = match.group(1)
                section[index] = f'{key} = "{values[key]}"'
                updated_keys.add(key)
        for key, value in values.items():
            if key not in updated_keys:
                section.append(f'{key} = "{value}"')
        lines[section_start + 1 : section_end] = section

    output = "\n".join(lines).rstrip() + "\n"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(output, encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"Could not write user config at {path}: {exc}") from exc
    return path


@config_app.command("set")
def config_set(
    account: str | None = typer.Option(
        None,
        "--account",
        help="Default total capital available for trading",
    ),
    max_loss: str | None = typer.Option(
        None,
        "--max-loss",
        help="Default max loss per single operation",
    ),
) -> None:
    """Set or update BBS sizing defaults in the user config."""
    if account is None and max_loss is None:
        console.print("[red]Error:[/red] Provide --account, --max-loss, or both.")
        raise typer.Exit(2)
    try:
        path = _save_bbs_user_defaults(account, max_loss)
    except ValueError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(2) from exc
    console.print(f"[green]BBS defaults saved[/green] to {path}")


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
    account: str | None = typer.Option(
        None,
        "--account",
        help="Total capital available for trading (overrides user config)",
    ),
    max_loss: str | None = typer.Option(
        None,
        "--max-loss",
        help="Max $ loss per single operation (overrides user config)",
    ),
    strategy: str = typer.Option(
        "core",
        "--strategy",
        help="Strategy label (e.g. core, swing); used for future presets",
    ),
    slots: int | None = typer.Option(
        None,
        "--slots",
        min=1,
        max=20,
        help="Override concurrent-operation count (default: tiered from account)",
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
    no_auto_profile: bool = typer.Option(
        False,
        "--no-auto-profile",
        help="Do not query Yahoo Finance for company sector / industry",
    ),
    weeks: int = typer.Option(
        3,
        "--weeks",
        min=1,
        max=52,
        help="Calendar window: earnings fail if within N weeks; ex-div/dividend dates warn (default 3)",
    ),
) -> None:
    """Evaluate a Basic Buy Setup (long).

    Entry and stop are derived from the last candle: entry = high + high*0.005,
    stop = low - low*0.005. G per share = target - high.

    Share count is computed from the configured or supplied account, tiered
    concurrent operations, and configured or supplied max loss:
    qty = min(floor(capital_per_op / entry), floor(max_loss / R_per_share)).
    """
    missing_values = tuple(
        key
        for key, value in (("account", account), ("max_loss", max_loss))
        if value is None
    )
    try:
        defaults = _load_bbs_user_defaults(missing_values) if missing_values else {}
    except ValueError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(2) from exc

    account = account if account is not None else defaults.get("account")
    max_loss = max_loss if max_loss is not None else defaults.get("max_loss")
    missing = [
        option
        for option, value in (("--account", account), ("--max-loss", max_loss))
        if value is None
    ]
    if missing:
        names = " and ".join(missing)
        console.print(
            f"[red]Error:[/red] {names} required. Supply the option(s) or set "
            f"them in the bbs_eval table in {_bbs_user_config_path()}."
        )
        raise typer.Exit(2)

    try:
        high_d = _parse_decimal(high)
        low_d = _parse_decimal(low)
        target_d = _parse_decimal(target)
        account_d = _parse_decimal(account)
        max_loss_d = _parse_decimal(max_loss)
    except (InvalidOperation, ValueError) as exc:
        console.print("[red]Error:[/red] Prices, account, and max-loss must be valid numbers.")
        raise typer.Exit(2) from exc

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

    profile: YahooCompanyProfile | None = None
    if not no_auto_profile:
        profile = fetch_yahoo_company_profile(symbol)
        if not profile.fetched_ok and profile.error:
            console.print(
                f"[yellow]Warning:[/yellow] Could not fetch Yahoo company profile for "
                f"{symbol!r}: {profile.error}. Use --no-auto-profile to skip."
            )

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

    dividend_detail: str | None = None
    dividend_severity: Literal["ok", "warn"] = "ok"
    if auto is not None and auto.fetched_ok:
        dividend_detail, dividend_severity = dividend_calendar_rule_text(
            auto,
            weeks=weeks,
        )

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
        dividend_calendar_detail=dividend_detail,
        dividend_calendar_severity=dividend_severity,
    )

    console.print(f"\n[bold]{result.symbol}[/bold] — {result.summary}\n")
    m = Table(show_header=False, box=None)
    if profile is not None:
        if profile.fetched_ok and profile.sector:
            sector_line = profile.sector
            if profile.industry:
                sector_line = f"{profile.sector} — {profile.industry}"
            m.add_row("Sector (Yahoo)", sector_line)
        elif profile.fetched_ok:
            m.add_row("Sector (Yahoo)", "— (not listed)")
        else:
            m.add_row("Sector (Yahoo)", "— (unavailable)")
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
