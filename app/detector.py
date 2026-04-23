"""Bearish chart-pattern detection + dump scoring.

The pattern detectors here are deliberately pragmatic rather than
research-grade: the goal is to surface plausible short setups on a
noisy altcoin universe, not to be a perfect TA engine.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .models import Candle, ScoreBreakdown

# Scoring weights (per project spec).
W_PATTERN = 30
W_VOLUME_SPIKE = 20
W_SUPPORT_BREAK = 25
W_BEARISH_STRUCTURE = 15
W_STRONG_CANDLE = 10

# Minimum candles required for meaningful detection.
MIN_CANDLES = 40


@dataclass
class Detection:
    score_breakdown: ScoreBreakdown = field(default_factory=ScoreBreakdown)
    signal_type: str = ""
    reasons: list[str] = field(default_factory=list)

    @property
    def score(self) -> int:
        return self.score_breakdown.total

    @property
    def reason(self) -> str:
        return " + ".join(self.reasons) if self.reasons else "no strong signal"


def _find_pivots(
    candles: list[Candle], left: int = 2, right: int = 2
) -> tuple[list[int], list[int]]:
    """Return indices of swing highs and swing lows.

    A pivot high at i requires h[i] > h[j] for every j != i in
    [i-left, i+right]; pivot lows are defined symmetrically. Strict
    inequality avoids flat-line data producing thousands of false pivots.
    """
    highs: list[int] = []
    lows: list[int] = []
    n = len(candles)
    for i in range(left, n - right):
        win = range(i - left, i + right + 1)
        max_h = max(candles[j].h for j in win if j != i)
        min_l = min(candles[j].l for j in win if j != i)
        if candles[i].h > max_h:
            highs.append(i)
        if candles[i].l < min_l:
            lows.append(i)
    return highs, lows


def _pct(a: float, b: float) -> float:
    if b == 0:
        return 0.0
    return (a - b) / b * 100.0


def detect_volume_spike(
    candles: list[Candle], mult: float = 1.8, within: int = 3
) -> bool:
    """Any of the last `within` candles has volume >= mult * avg of the
    preceding 20 candles. Widening the window past the single most recent
    candle catches dumps that have already exhausted their peak bar."""
    if len(candles) < 22 + within:
        return False
    baseline_start = -(within + 21)
    baseline_end = -within - 1
    prev = candles[baseline_start:baseline_end]
    avg = sum(c.v for c in prev) / len(prev)
    if avg <= 0:
        return False
    return any(c.v >= mult * avg for c in candles[-within:])


def detect_strong_red_candle(
    candles: list[Candle], atr_mult: float = 1.5, within: int = 3
) -> bool:
    """Any of the last `within` candles is red with body > atr_mult * ATR."""
    if len(candles) < 16 + within:
        return False
    trs: list[float] = []
    start = -(15 + within)
    for i in range(start, -within):
        a, b = candles[i], candles[i - 1]
        trs.append(max(a.h - a.l, abs(a.h - b.c), abs(a.l - b.c)))
    atr = sum(trs) / len(trs) if trs else 0.0
    if atr <= 0:
        return False
    for c in candles[-within:]:
        if c.c < c.o and abs(c.o - c.c) >= atr_mult * atr:
            return True
    return False


def detect_support_break(
    candles: list[Candle], lookback: int = 20, within: int = 3
) -> bool:
    """Any close within the last `within` candles dipped below the lowest
    low of the preceding `lookback` candles (i.e. a recent support break)."""
    if len(candles) < lookback + within + 1:
        return False
    baseline_start = -(lookback + within)
    baseline_end = -within
    support = min(c.l for c in candles[baseline_start:baseline_end])
    return any(c.c < support for c in candles[-within:])


def detect_bearish_structure(candles: list[Candle]) -> bool:
    """Last ~10 candles show lower highs AND lower lows via pivots."""
    window = candles[-25:]
    if len(window) < 10:
        return False
    highs, lows = _find_pivots(window, left=2, right=2)
    recent_highs = [window[i].h for i in highs[-3:]]
    recent_lows = [window[i].l for i in lows[-3:]]
    if len(recent_highs) < 2 or len(recent_lows) < 2:
        return False
    lh = all(recent_highs[i] < recent_highs[i - 1] for i in range(1, len(recent_highs)))
    ll = all(recent_lows[i] < recent_lows[i - 1] for i in range(1, len(recent_lows)))
    return lh and ll


def detect_double_top(candles: list[Candle]) -> bool:
    """Two pivot highs within ~1% of each other, with current price below
    the valley between them (neckline break)."""
    window = candles[-60:]
    if len(window) < 20:
        return False
    highs, _ = _find_pivots(window, left=3, right=3)
    if len(highs) < 2:
        return False
    i2, i1 = highs[-1], highs[-2]
    if i2 - i1 < 4:
        return False
    h1, h2 = window[i1].h, window[i2].h
    if abs(_pct(h1, h2)) > 1.5:
        return False
    valley = min(c.l for c in window[i1 : i2 + 1])
    return window[-1].c < valley


def detect_head_and_shoulders(candles: list[Candle]) -> bool:
    """Three pivot highs where the middle ("head") is highest and shoulders
    are within ~2% of each other; current price below the neckline."""
    window = candles[-80:]
    if len(window) < 25:
        return False
    highs, lows = _find_pivots(window, left=3, right=3)
    if len(highs) < 3 or len(lows) < 2:
        return False
    ls, head, rs = highs[-3], highs[-2], highs[-1]
    if not (window[head].h > window[ls].h and window[head].h > window[rs].h):
        return False
    if abs(_pct(window[ls].h, window[rs].h)) > 2.0:
        return False
    neckline_candidates = [lows[i] for i in range(len(lows)) if ls < lows[i] < rs]
    if not neckline_candidates:
        return False
    neckline = min(window[i].l for i in neckline_candidates)
    return window[-1].c < neckline


def detect_rising_wedge_breakdown(candles: list[Candle]) -> bool:
    """Higher lows + flattening highs across last N candles, with current
    candle breaking below the rising-lows trendline."""
    window = candles[-30:]
    if len(window) < 15:
        return False
    highs, lows = _find_pivots(window, left=2, right=2)
    if len(lows) < 3 or len(highs) < 2:
        return False
    lo_prices = [window[i].l for i in lows[-3:]]
    if not all(lo_prices[i] > lo_prices[i - 1] for i in range(1, len(lo_prices))):
        return False
    hi_prices = [window[i].h for i in highs[-2:]]
    hi_slope = hi_prices[-1] - hi_prices[0]
    lo_slope = lo_prices[-1] - lo_prices[0]
    if lo_slope <= 0 or hi_slope >= lo_slope:
        return False
    x0, y0 = lows[-2], lo_prices[-2]
    x1, y1 = lows[-1], lo_prices[-1]
    if x1 == x0:
        return False
    slope = (y1 - y0) / (x1 - x0)
    projected = y1 + slope * (len(window) - 1 - x1)
    return window[-1].c < projected


def detect_fake_pump_dump(candles: list[Candle]) -> bool:
    """A sharp pump in the last ~10 candles followed by a red candle that
    erases most of the pump's gains."""
    if len(candles) < 15:
        return False
    window = candles[-12:]
    start = window[0].c
    peak_idx = max(range(len(window)), key=lambda i: window[i].h)
    peak = window[peak_idx].h
    pump_pct = _pct(peak, start)
    if pump_pct < 4.0:
        return False
    last = window[-1]
    retrace = _pct(last.c, peak)
    return peak_idx < len(window) - 1 and retrace < -0.6 * pump_pct


def detect(candles: list[Candle]) -> Detection:
    """Run every detector and assemble a Detection with scoring + reasons."""
    det = Detection()
    if len(candles) < MIN_CANDLES:
        return det

    pattern_name: str | None = None
    if detect_head_and_shoulders(candles):
        pattern_name = "Head and Shoulders"
    elif detect_double_top(candles):
        pattern_name = "Double Top"
    elif detect_rising_wedge_breakdown(candles):
        pattern_name = "Rising Wedge breakdown"
    elif detect_fake_pump_dump(candles):
        pattern_name = "Fake pump → dump"

    if pattern_name:
        det.score_breakdown.pattern = W_PATTERN
        det.signal_type = pattern_name
        det.reasons.append(pattern_name.lower())

    if detect_volume_spike(candles):
        det.score_breakdown.volume_spike = W_VOLUME_SPIKE
        det.reasons.append("volume spike")

    if detect_support_break(candles):
        det.score_breakdown.support_break = W_SUPPORT_BREAK
        det.reasons.append("support break")
        if not det.signal_type:
            det.signal_type = "Support break"

    if detect_bearish_structure(candles):
        det.score_breakdown.bearish_structure = W_BEARISH_STRUCTURE
        det.reasons.append("lower highs + lower lows")
        if not det.signal_type:
            det.signal_type = "Bearish structure"

    if detect_strong_red_candle(candles):
        det.score_breakdown.strong_candle = W_STRONG_CANDLE
        det.reasons.append("big red candle")
        if not det.signal_type:
            det.signal_type = "Strong red candle"

    return det


def severity_for(score: int) -> str | None:
    if score >= 80:
        return "HIGH"
    if score >= 60:
        return "MEDIUM"
    return None
