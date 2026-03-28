from __future__ import annotations

import os
import sqlite3
from pathlib import Path


def default_db_path() -> Path:
    p = os.environ.get("TRADE_ASSISTANT_DB")
    if p:
        return Path(p).expanduser()
    return Path.home() / ".trade-assistant" / "trades.db"


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def connect(path: Path) -> sqlite3.Connection:
    ensure_parent(path)
    conn = sqlite3.connect(path, isolation_level=None)
    conn.row_factory = sqlite3.Row
    _init_schema(conn)
    return conn


def _init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        PRAGMA foreign_keys = ON;

        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            side TEXT NOT NULL DEFAULT 'long',
            strategy TEXT NOT NULL DEFAULT 'core',
            technique TEXT,
            status TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            entry_price TEXT NOT NULL,
            stop_loss TEXT NOT NULL,
            target_price TEXT,
            opened_at TEXT NOT NULL,
            closed_at TEXT,
            exit_price TEXT,
            realized_pnl TEXT,
            notes TEXT
        );

        CREATE TABLE IF NOT EXISTS trade_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trade_id INTEGER NOT NULL REFERENCES trades(id) ON DELETE CASCADE,
            occurred_at TEXT NOT NULL,
            kind TEXT NOT NULL,
            detail TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_trades_status ON trades(status);
        CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades(symbol);
        CREATE INDEX IF NOT EXISTS idx_events_trade ON trade_events(trade_id);
        """
    )
