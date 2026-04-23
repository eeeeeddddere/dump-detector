"""Pre-saved demo signals for instant first-load results."""
from __future__ import annotations

import time

from .models import ScoreBreakdown, Signal

_NOW = int(time.time())


def demo_signals() -> list[Signal]:
    """Return a deterministic list of illustrative dump signals."""
    raw = [
        {
            "contract": "SOL_USDT",
            "timeframe": "15m",
            "signal_type": "Rising Wedge breakdown",
            "reason": "rising wedge breakdown + volume spike + support break",
            "last_price": 142.37,
            "change_24h_pct": -3.8,
            "volume_24h_usdt": 482_000_000,
            "breakdown": ScoreBreakdown(
                pattern=30, volume_spike=20, support_break=25, bearish_structure=15, strong_candle=10
            ),
        },
        {
            "contract": "DOGE_USDT",
            "timeframe": "15m",
            "signal_type": "Double Top",
            "reason": "double top + volume spike + big red candle",
            "last_price": 0.1624,
            "change_24h_pct": -2.1,
            "volume_24h_usdt": 198_000_000,
            "breakdown": ScoreBreakdown(
                pattern=30, volume_spike=20, support_break=0, bearish_structure=15, strong_candle=10
            ),
        },
        {
            "contract": "XRP_USDT",
            "timeframe": "1h",
            "signal_type": "Head and Shoulders",
            "reason": "head and shoulders + support break + lower highs",
            "last_price": 0.5182,
            "change_24h_pct": -1.4,
            "volume_24h_usdt": 312_000_000,
            "breakdown": ScoreBreakdown(
                pattern=30, volume_spike=0, support_break=25, bearish_structure=15, strong_candle=10
            ),
        },
        {
            "contract": "PEPE_USDT",
            "timeframe": "15m",
            "signal_type": "Fake pump → dump",
            "reason": "fake pump → dump + volume spike + big red candle",
            "last_price": 0.00000812,
            "change_24h_pct": -5.2,
            "volume_24h_usdt": 76_400_000,
            "breakdown": ScoreBreakdown(
                pattern=30, volume_spike=20, support_break=0, bearish_structure=15, strong_candle=10
            ),
        },
        {
            "contract": "AVAX_USDT",
            "timeframe": "1h",
            "signal_type": "Support break",
            "reason": "support break + lower highs + lower lows + volume spike",
            "last_price": 32.18,
            "change_24h_pct": -2.7,
            "volume_24h_usdt": 128_500_000,
            "breakdown": ScoreBreakdown(
                pattern=0, volume_spike=20, support_break=25, bearish_structure=15, strong_candle=10
            ),
        },
        {
            "contract": "ARB_USDT",
            "timeframe": "15m",
            "signal_type": "Bearish structure",
            "reason": "lower highs + lower lows + support break + volume spike",
            "last_price": 0.7321,
            "change_24h_pct": -1.8,
            "volume_24h_usdt": 54_200_000,
            "breakdown": ScoreBreakdown(
                pattern=0, volume_spike=20, support_break=25, bearish_structure=15, strong_candle=10
            ),
        },
    ]

    signals: list[Signal] = []
    for item in raw:
        bd: ScoreBreakdown = item["breakdown"]  # type: ignore[assignment]
        score = bd.total
        severity = "HIGH" if score >= 80 else "MEDIUM"
        contract = str(item["contract"])
        signals.append(
            Signal(
                contract=contract,
                symbol=contract.replace("_", "/"),
                timeframe=item["timeframe"],  # type: ignore[arg-type]
                score=score,
                severity=severity,  # type: ignore[arg-type]
                signal_type=str(item["signal_type"]),
                reason=str(item["reason"]),
                last_price=float(item["last_price"]),  # type: ignore[arg-type]
                change_24h_pct=float(item["change_24h_pct"]),  # type: ignore[arg-type]
                volume_24h_usdt=float(item["volume_24h_usdt"]),  # type: ignore[arg-type]
                breakdown=bd,
                detected_at=_NOW,
            )
        )
    signals.sort(key=lambda s: s.score, reverse=True)
    return signals
