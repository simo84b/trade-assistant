# trade-assistant

Standalone Python helper for paper trading (e.g. ProRealTime): evaluate setups and manage trades. This version implements **Basic Buy Setup (BBS)** checks; core trading management and other techniques can be added later.

## Setup

```bash
cd trade-assistant
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
```

## BBS rules (implemented)

**CLI inputs (last candle + target)** — You pass the **last candle** high/low and a **target** price. The tool derives:

- **Entry** = high + (high × 0.005) — 0.5% above the last candle high.
- **Stop** = low − (low × 0.005)
- **G** per share = **target − high** (reward measured from the candle high to your target)

Internally, evaluation still uses **entry**, **stop**, and **G** as before: \(R = \text{entry} - \text{stop}\) per share.

1. **G/R** — Require **G/R > 1.5**; **> 2.5** is treated as ideal (otherwise a warning).
2. **Position risk %** — Share count cancels: **(entry − stop) / entry × 100** (risk as a fraction of entry / position). Must be **< 10%**; about **5–6%** is ideal (values outside that band pass but may warn).
3. **Earnings** — If you mark **earnings (or similar) as imminent**, the setup is **discouraged** (fails the check). By default the CLI also queries **Yahoo Finance** (via [yfinance](https://github.com/ranaroussi/yfinance)) for the **next earnings date** and treats the setup as discouraged if that date falls within the next **3 weeks** (21 days). This mirrors the data shown on the [Yahoo earnings calendar](https://finance.yahoo.com/calendar/earnings); it can be missing or wrong, so treat it as advisory. Use `--no-auto-earnings` to skip the lookup, or `--weeks N` to change the window.

**Sizing** — You pass **`--account`** (total capital) and **`--max-loss`** (max loss per single operation, absolute $, strategy-specific in spirit). The tool picks a **concurrent-operation count** from the account tier (ambiguous ranges use the higher slot count so each slice is smaller), then:

`qty = min(floor((account / slots) / entry), floor(max_loss / R_per_share))`.

Override the slot count with **`--slots`** if you want 3 vs 4 (or 6 vs 10) explicitly. **`--strategy`** is reserved for labels (e.g. core vs swing); today **`--max-loss`** is always explicit.

**Account risk %** in the output is dollar risk ÷ **account** (dollar risk = (entry − stop) × qty).

## CLI

Use the `bbs-eval` subcommand (the app also exposes `version` so Typer keeps subcommands explicit):

```bash
trade-assistant bbs-eval VLY --high 12.22 --low 11.45 --target 14.22 --account 10000 --max-loss 200
```

Exit code **0** if the setup passes all BBS gates, **1** otherwise. Add `--earnings-soon` (manual), `--no-auto-earnings`, `--weeks 3`, or `--slots 4` as needed.

## Core trading journal

SQLite journal for **open** and **closed** trades (append-only **history** per trade: open, stop updates, notes, close). Default database: **`~/.trade-assistant/trades.db`**, or set **`TRADE_ASSISTANT_DB`**, or pass **`journal --db path/to/file.db`** on each command.

| Command | Purpose |
|--------|---------|
| `journal add` | New open position (`--entry`, `--stop`, `--qty`, optional `--target`, `--strategy`, `--technique`, `--notes`) |
| `journal open` | List open trades |
| `journal list` | Recent trades (`--open` / `--closed` / default all; `--symbol`) |
| `journal show ID` | Trade + event timeline |
| `journal close ID --exit PRICE` | Close (`--pnl` optional; else long P/L = (exit − entry) × qty) |
| `journal log ID "text"` | Add a note to history |
| `journal update-stop ID --stop PRICE` | Move stop (logged) |

Examples:

```bash
trade-assistant journal add VLY --entry 12.16 --stop 11.39 --qty 350 --target 14.0 --technique bbs
trade-assistant journal open
trade-assistant journal show 1
trade-assistant journal close 1 --exit 13.50
```

## Private Git repository

Create the repo on your host (GitHub, etc.), then:

```bash
cd trade-assistant
git init
git add .
git commit -m "Initial commit: BBS evaluation"
git branch -M main
git remote add origin <your-private-repo-url>
git push -u origin main
```

## License

Private / personal use unless you add a license file.
