from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class BBSSetup(BaseModel):
    """Inputs for a Basic Buy Setup (long) evaluation."""

    symbol: str = Field(..., min_length=1, description="Ticker or symbol.")
    entry_price: Decimal = Field(..., gt=0, description="Planned entry price.")
    stop_loss: Decimal = Field(..., gt=0, description="Initial stop loss price.")
    quantity: int = Field(..., gt=0, description="Number of shares (long).")
    potential_gain: Decimal = Field(
        ...,
        gt=0,
        description="Potential gain G (same currency as price). Use per-share reward: "
        "e.g. target_price - entry.",
    )
    # Earnings: if True, trade is discouraged regardless of other metrics.
    earnings_communication_imminent: bool = Field(
        default=False,
        description="True if earnings (or similar) are about to be released; discourages trade.",
    )
    # Optional: interpret risk % vs total account (see evaluation output).
    account_equity: Decimal | None = Field(
        default=None,
        gt=0,
        description="If set, account risk %% = dollar_risk / account_equity, where "
        "dollar_risk = (entry - stop_loss) × quantity.",
    )

    @field_validator("symbol", mode="before")
    @classmethod
    def strip_symbol(cls, v: str) -> str:
        return str(v).strip()

    @model_validator(mode="after")
    def _long_stop_below_entry(self) -> BBSSetup:
        if self.stop_loss >= self.entry_price:
            raise ValueError("For a long BBS, stop_loss must be below entry_price.")
        return self


class RuleStatus(BaseModel):
    """Single rule outcome."""

    rule_id: str
    passed: bool
    label: str
    detail: str
    severity: Literal["ok", "warn", "fail"]


class BBSEvaluation(BaseModel):
    """Result of BBS evaluation."""

    symbol: str
    ok_to_trade: bool
    summary: str
    # Core metrics
    r_per_share: Decimal
    g_per_share: Decimal
    gr_ratio: Decimal
    position_risk_pct: Decimal
    dollar_risk: Decimal
    position_notional: Decimal
    account_risk_pct: Decimal | None
    rules: list[RuleStatus]
