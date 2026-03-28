from decimal import Decimal
from pathlib import Path

from trade_assistant.journal.models import TradeCreate
from trade_assistant.journal.repository import JournalRepository


def test_add_list_close(tmp_path: Path) -> None:
    db = tmp_path / "j.db"
    repo = JournalRepository(db)
    try:
        tid = repo.add_trade(
            TradeCreate(
                symbol="VLY",
                quantity=350,
                entry_price=Decimal("12.16"),
                stop_loss=Decimal("11.39"),
                target_price=Decimal("14.0"),
                technique="bbs",
            )
        )
        open_rows = repo.list_trades(status="open")
        assert len(open_rows) == 1
        assert open_rows[0].id == tid
        repo.close_trade(tid, Decimal("13.0"))
        closed = repo.list_trades(status="closed")
        assert len(closed) == 1
        assert closed[0].exit_price == Decimal("13.0")
        assert closed[0].realized_pnl is not None
    finally:
        repo.close()


def test_update_stop_and_events(tmp_path: Path) -> None:
    db = tmp_path / "j.db"
    repo = JournalRepository(db)
    try:
        tid = repo.add_trade(
            TradeCreate(
                symbol="X",
                quantity=10,
                entry_price=Decimal("10"),
                stop_loss=Decimal("9"),
            )
        )
        repo.update_stop(tid, Decimal("9.5"))
        ev = repo.list_events(tid)
        kinds = [e.kind for e in ev]
        assert "opened" in kinds
        assert "stop_update" in kinds
    finally:
        repo.close()
