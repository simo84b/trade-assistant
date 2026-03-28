from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Literal

from trade_assistant.journal.db import connect, default_db_path
from trade_assistant.journal.models import Trade, TradeCreate, TradeEvent


def _parse_dt(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class JournalRepository:
    def __init__(self, db_path: Path | None = None) -> None:
        self._path = db_path or default_db_path()
        self._conn = connect(self._path)

    def close(self) -> None:
        self._conn.close()

    def path(self) -> Path:
        return self._path

    def add_trade(self, data: TradeCreate) -> int:
        opened = (data.opened_at or datetime.now(timezone.utc)).replace(microsecond=0)
        cur = self._conn.execute(
            """
            INSERT INTO trades (
                symbol, side, strategy, technique, status, quantity,
                entry_price, stop_loss, target_price, opened_at, notes
            ) VALUES (?, ?, ?, ?, 'open', ?, ?, ?, ?, ?, ?)
            """,
            (
                data.symbol.strip().upper(),
                data.side,
                data.strategy,
                data.technique,
                data.quantity,
                str(data.entry_price),
                str(data.stop_loss),
                str(data.target_price) if data.target_price is not None else None,
                opened.isoformat(),
                data.notes,
            ),
        )
        tid = int(cur.lastrowid)
        self._conn.execute(
            "INSERT INTO trade_events (trade_id, occurred_at, kind, detail) VALUES (?, ?, ?, ?)",
            (tid, opened.isoformat(), "opened", "Trade opened"),
        )
        return tid

    def add_event(self, trade_id: int, kind: str, detail: str | None = None) -> int:
        cur = self._conn.execute(
            "INSERT INTO trade_events (trade_id, occurred_at, kind, detail) VALUES (?, ?, ?, ?)",
            (trade_id, _now_iso(), kind, detail),
        )
        return int(cur.lastrowid)

    def update_stop(self, trade_id: int, new_stop: Decimal) -> None:
        row = self._conn.execute(
            "SELECT stop_loss FROM trades WHERE id = ? AND status = 'open'",
            (trade_id,),
        ).fetchone()
        if not row:
            raise LookupError("open trade not found")
        old = row["stop_loss"]
        self._conn.execute(
            "UPDATE trades SET stop_loss = ? WHERE id = ?",
            (str(new_stop), trade_id),
        )
        self.add_event(
            trade_id,
            "stop_update",
            f"stop {old} -> {new_stop}",
        )

    def close_trade(
        self,
        trade_id: int,
        exit_price: Decimal,
        realized_pnl: Decimal | None = None,
    ) -> None:
        row = self._conn.execute(
            "SELECT entry_price, quantity, side FROM trades WHERE id = ? AND status = 'open'",
            (trade_id,),
        ).fetchone()
        if not row:
            raise LookupError("open trade not found")
        entry = Decimal(row["entry_price"])
        qty = int(row["quantity"])
        side = row["side"]
        if realized_pnl is None:
            if side == "long":
                realized_pnl = (exit_price - entry) * qty
            else:
                realized_pnl = (entry - exit_price) * qty
        closed = _now_iso()
        self._conn.execute(
            """
            UPDATE trades SET status = 'closed', closed_at = ?, exit_price = ?, realized_pnl = ?
            WHERE id = ?
            """,
            (closed, str(exit_price), str(realized_pnl), trade_id),
        )
        self.add_event(
            trade_id,
            "closed",
            f"exit {exit_price} pnl {realized_pnl}",
        )

    def get_trade(self, trade_id: int) -> Trade | None:
        row = self._conn.execute("SELECT * FROM trades WHERE id = ?", (trade_id,)).fetchone()
        if not row:
            return None
        return self._row_to_trade(row)

    def list_trades(
        self,
        status: Literal["open", "closed", "all"] = "all",
        symbol: str | None = None,
        limit: int = 200,
    ) -> list[Trade]:
        q = "SELECT * FROM trades WHERE 1=1"
        params: list[object] = []
        if status != "all":
            q += " AND status = ?"
            params.append(status)
        if symbol:
            q += " AND symbol = ?"
            params.append(symbol.strip().upper())
        q += " ORDER BY opened_at DESC LIMIT ?"
        params.append(limit)
        rows = self._conn.execute(q, params).fetchall()
        return [self._row_to_trade(r) for r in rows]

    def list_events(self, trade_id: int) -> list[TradeEvent]:
        rows = self._conn.execute(
            "SELECT * FROM trade_events WHERE trade_id = ? ORDER BY occurred_at ASC, id ASC",
            (trade_id,),
        ).fetchall()
        return [
            TradeEvent(
                id=int(r["id"]),
                trade_id=int(r["trade_id"]),
                occurred_at=_parse_dt(r["occurred_at"]),
                kind=r["kind"],
                detail=r["detail"],
            )
            for r in rows
        ]

    def _row_to_trade(self, row: sqlite3.Row) -> Trade:
        return Trade(
            id=int(row["id"]),
            symbol=row["symbol"],
            side=row["side"],
            strategy=row["strategy"],
            technique=row["technique"],
            status=row["status"],
            quantity=int(row["quantity"]),
            entry_price=Decimal(row["entry_price"]),
            stop_loss=Decimal(row["stop_loss"]),
            target_price=Decimal(row["target_price"]) if row["target_price"] else None,
            opened_at=_parse_dt(row["opened_at"]),
            closed_at=_parse_dt(row["closed_at"]) if row["closed_at"] else None,
            exit_price=Decimal(row["exit_price"]) if row["exit_price"] else None,
            realized_pnl=Decimal(row["realized_pnl"]) if row["realized_pnl"] else None,
            notes=row["notes"],
        )
