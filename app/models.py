"""Pydantic data models for Dump Detector API."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Timeframe = Literal["15m", "1h"]
Severity = Literal["HIGH", "MEDIUM"]


class Candle(BaseModel):
    """One OHLCV candle. Timestamps are unix seconds."""

    t: int
    o: float
    h: float
    l: float
    c: float
    v: float


class ScoreBreakdown(BaseModel):
    pattern: int = 0
    volume_spike: int = 0
    support_break: int = 0
    bearish_structure: int = 0
    strong_candle: int = 0

    @property
    def total(self) -> int:
        return min(
            100,
            self.pattern
            + self.volume_spike
            + self.support_break
            + self.bearish_structure
            + self.strong_candle,
        )


class Signal(BaseModel):
    contract: str = Field(..., description="Gate.io contract id, e.g. BTC_USDT")
    symbol: str = Field(..., description="Display symbol, e.g. BTC/USDT")
    timeframe: Timeframe
    score: int
    severity: Severity
    signal_type: str
    reason: str
    last_price: float
    change_24h_pct: float | None = None
    volume_24h_usdt: float | None = None
    breakdown: ScoreBreakdown
    detected_at: int = Field(..., description="Unix seconds when signal was produced")


class ScanResponse(BaseModel):
    signals: list[Signal]
    scanned: int
    demo: bool
    timeframe: Timeframe | Literal["all"]
    generated_at: int
