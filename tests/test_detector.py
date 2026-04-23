"""Synthetic-candle tests for the dump detector.

These tests use hand-crafted OHLCV series to exercise each detector in
isolation and to sanity-check that scoring produces HIGH/MEDIUM severities
when multiple signals fire together.
"""
from __future__ import annotations

import math

from app.detector import (
    detect,
    detect_bearish_structure,
    detect_double_top,
    detect_fake_pump_dump,
    detect_head_and_shoulders,
    detect_rising_wedge_breakdown,
    detect_strong_red_candle,
    detect_support_break,
    detect_volume_spike,
    severity_for,
)
from app.models import Candle


def _candle(i: int, o: float, h: float, l: float, c: float, v: float = 1000.0) -> Candle:
    return Candle(t=1_700_000_000 + i * 900, o=o, h=h, l=l, c=c, v=v)


def _series(closes: list[float], volumes: list[float] | None = None) -> list[Candle]:
    """Build a realistic OHLC series from a list of closes.

    Each candle's open is the previous close; its high/low vary around the
    mid-point so that swing pivots can be detected cleanly.
    """
    if volumes is None:
        volumes = [1000.0] * len(closes)
    candles: list[Candle] = []
    for i, (c, v) in enumerate(zip(closes, volumes)):
        o = closes[i - 1] if i > 0 else c
        mid = (o + c) / 2
        wick = max(abs(c - o), 0.05 * abs(mid)) * 0.5 + 0.0005 * abs(mid)
        # Stagger the wick so consecutive candles have slightly different
        # extremes — otherwise pivot detection sees flat runs.
        jitter = 0.003 * abs(mid) * math.sin(i * 1.7)
        h = max(o, c) + wick + jitter
        l = min(o, c) - wick - jitter
        candles.append(_candle(i, o, h, l, c, v))
    return candles


def test_volume_spike_triggers_when_last_candle_is_outlier():
    base = [1000.0] * 30 + [3500.0]
    candles = _series([100.0] * 31, volumes=base)
    assert detect_volume_spike(candles) is True


def test_volume_spike_rejects_flat_volume():
    candles = _series([100.0] * 30, volumes=[1000.0] * 30)
    assert detect_volume_spike(candles) is False


def test_strong_red_candle_requires_red_body_larger_than_atr():
    # Build 25 tight candles (small ATR) then one big red candle.
    candles: list[Candle] = []
    for i in range(25):
        candles.append(_candle(i, 100.0, 100.2, 99.8, 100.0, 1000.0))
    candles.append(_candle(25, 100.0, 100.2, 94.0, 94.5, 2000.0))
    assert detect_strong_red_candle(candles) is True


def test_strong_red_candle_rejects_small_body():
    candles: list[Candle] = []
    for i in range(25):
        candles.append(_candle(i, 100.0, 100.2, 99.8, 100.0, 1000.0))
    candles.append(_candle(25, 100.0, 100.1, 99.8, 99.9, 1000.0))
    assert detect_strong_red_candle(candles) is False


def test_support_break_detects_close_under_recent_lows():
    closes = [100.0, 101.0, 99.5, 100.5, 99.0, 100.0, 101.0] * 4 + [96.0]
    candles = _series(closes)
    assert detect_support_break(candles) is True


def _zigzag(values: list[float], step: float = 0.3) -> list[float]:
    """Expand a list of pivot targets into a dense path that oscillates
    around each target, so _find_pivots sees clean swings."""
    out: list[float] = []
    for i, v in enumerate(values):
        if i == 0:
            out.append(v)
            continue
        prev = values[i - 1]
        # Three interpolated points between prev and v.
        for k in range(1, 4):
            out.append(prev + (v - prev) * (k / 4))
        out.append(v)
        out.append(v - step if i % 2 == 0 else v + step)
    return out


def test_bearish_structure_finds_lower_highs_and_lower_lows():
    # Zigzag with monotonically falling pivots.
    pivots = [110.0, 104.0, 108.0, 102.0, 106.0, 100.0, 104.0, 98.0]
    closes = [100.0] * 10 + _zigzag(pivots, step=0.5)
    candles = _series(closes)
    assert detect_bearish_structure(candles) is True


def test_double_top_triggers_after_neckline_break():
    # Two clear peaks at ~110 with a valley at ~104, then close below the valley.
    pivots = [100.0, 110.0, 104.0, 110.2, 103.0]
    closes = [100.0] * 25 + _zigzag(pivots, step=0.4) + [97.0]
    candles = _series(closes)
    assert detect_double_top(candles) is True


def test_head_and_shoulders_triggers_after_neckline_break():
    # Left shoulder 108, head 115, right shoulder 108, then break neckline.
    pivots = [100.0, 108.0, 103.0, 115.0, 104.0, 108.0, 100.0]
    closes = [100.0] * 15 + _zigzag(pivots, step=0.5) + [95.0]
    candles = _series(closes)
    assert detect_head_and_shoulders(candles) is True


def test_rising_wedge_breakdown_triggers():
    # Higher lows (100→102→104) + flattening highs (106→106.5→107), then breakdown.
    pivots = [100.0, 106.0, 102.0, 106.5, 104.0, 107.0]
    closes = [100.0] * 15 + _zigzag(pivots, step=0.3) + [97.0]
    candles = _series(closes)
    assert detect_rising_wedge_breakdown(candles) is True


def test_fake_pump_dump_triggers():
    closes = [100.0] * 20
    closes += [101.0, 103.0, 106.0, 108.0, 110.0]  # +10% pump
    closes += [107.0, 104.0, 101.0]  # dump erases the pump
    candles = _series(closes)
    assert detect_fake_pump_dump(candles) is True


def test_detect_aggregates_multiple_signals_into_high_severity():
    # Rising wedge into breakdown + huge red final candle + volume spike →
    # pattern(30) + volume_spike(20) + support_break(25) + strong_candle(10) = 85
    pivots = [100.0, 106.0, 102.0, 106.5, 104.0, 107.0]
    closes = [100.0] * 30 + _zigzag(pivots, step=0.3)
    volumes = [800.0] * len(closes)
    # Append a big red breakdown candle with huge volume.
    closes.append(95.0)
    volumes.append(5000.0)
    candles = _series(closes, volumes=volumes)
    # Emphasize the red body on the last candle.
    last = candles[-1]
    candles[-1] = Candle(t=last.t, o=107.0, h=107.2, l=94.0, c=95.0, v=5000.0)

    det = detect(candles)
    assert det.score >= 60, det
    sev = severity_for(det.score)
    assert sev in {"HIGH", "MEDIUM"}
    assert det.signal_type
    assert det.reason


def test_detect_returns_empty_for_insufficient_candles():
    candles = _series([100.0] * 10)
    det = detect(candles)
    assert det.score == 0
    assert det.signal_type == ""


def test_severity_thresholds():
    assert severity_for(85) == "HIGH"
    assert severity_for(80) == "HIGH"
    assert severity_for(65) == "MEDIUM"
    assert severity_for(59) is None
