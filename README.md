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

1. **G/R** — \(G\) is your per-share potential gain (e.g. target minus entry). \(R = \text{entry} - \text{stop}\) per share. Require **G/R > 1.5**; **> 2.5** is treated as ideal (otherwise a warning).
2. **Position risk %** — Share count cancels: **(entry − stop) / entry × 100** (risk as a fraction of entry / position). Must be **< 10%**; about **5–6%** is ideal (values outside that band pass but may warn).
3. **Earnings** — If you mark **earnings (or similar) as imminent**, the setup is **discouraged** (fails the check). By default the CLI also queries **Yahoo Finance** (via [yfinance](https://github.com/ranaroussi/yfinance)) for the **next earnings date** and treats the setup as discouraged if that date falls within the next **3 weeks** (21 days). This mirrors the data shown on the [Yahoo earnings calendar](https://finance.yahoo.com/calendar/earnings); it can be missing or wrong, so treat it as advisory. Use `--no-auto-earnings` to skip the lookup, or `--weeks N` to change the window.

Optional: pass **account equity** to see **account risk %** = dollar risk ÷ equity (dollar risk = (entry − stop) × quantity).

## CLI

```bash
trade-assistant bbs-eval VLY --entry 12.16 --stop 11.39 --qty 350 --gain 2.0
```

Exit code **0** if the setup passes all BBS gates, **1** otherwise. Add `--earnings-soon` (manual), `--no-auto-earnings`, `--weeks 3`, or `--account 50000` as needed.

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
