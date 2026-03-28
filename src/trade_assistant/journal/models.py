from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


Side = Literal["long"]
TradeStatus = Literal["open", "closed"]


class Trade(BaseModel):
    id: int
    symbol: str
    side: Side = "long"
    strategy: str = "core"
    technique: str | None = None
    status: TradeStatus
    quantity: int
    entry_price: Decimal
    stop_loss: Decimal
    target_price: Decimal | None = None
    opened_at: datetime
    closed_at: datetime | None = None
    exit_price: Decimal | None = None
    realized_pnl: Decimal | None = None
    notes: str | None = None


class TradeEvent(BaseModel):
    id: int
    trade_id: int
    occurred_at: datetime
    kind: str
    detail: str | None = None


class TradeCreate(BaseModel):
    symbol: str
    side: Side = "long"
    strategy: str = "core"
    technique: str | None = None
    quantity: int = Field(..., gt=0)
    entry_price: Decimal
    stop_loss: Decimal
    target_price: Decimal | None = None
    opened_at: datetime | None = None
    notes: str | None = None
