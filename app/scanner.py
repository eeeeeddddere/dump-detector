"""High-level scan orchestration: fetch Gate.io data → run detectors → score."""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass

from .detector import detect, severity_for
from .gateio import GateIOClient, gather_limited
from .models import Signal, Timeframe

log = logging.getLogger(__name__)

CANDLE_LIMIT = 120
DEFAULT_MIN_VOLUME_USDT = 500_000.0
# Gate.io's public REST API rate-limits aggressive clients. Keep concurrency
# modest and the client handles 429 retries with backoff.
SCAN_CONCURRENCY = 5


@dataclass
class ScanResult:
    signals: list[Signal]
    scanned: int


async def _tickers_by_contract(client: GateIOClient) -> dict[str, dict]:
    raw = await client.tickers()
    out: dict[str, dict] = {}
    for t in raw:
        name = t.get("contract")
        if isinstance(name, str):
            out[name] = t
    return out


def _parse_volume_usdt(ticker: dict) -> float:
    """Gate.io futures ticker exposes 24h USD/USDT volume as ``volume_24h_quote``.

    Fall back to ``volume_24h_settle`` or base volume * last price so we can
    still filter illiquid pairs even if the field shape changes.
    """
    for key in ("volume_24h_quote", "volume_24h_settle"):
        raw = ticker.get(key)
        if raw is None:
            continue
        try:
            return float(raw)
        except (TypeError, ValueError):
            continue
    base = ticker.get("volume_24h_base") or ticker.get("volume_24h") or 0
    last = ticker.get("last") or 0
    try:
        return float(base) * float(last)
    except (TypeError, ValueError):
        return 0.0


async def _scan_one(
    client: GateIOClient,
    contract: str,
    timeframe: Timeframe,
    ticker: dict,
) -> Signal | None:
    candles = await client.candles(contract, interval=timeframe, limit=CANDLE_LIMIT)
    det = detect(candles)
    sev = severity_for(det.score)
    if sev is None:
        return None
    last_price = candles[-1].c if candles else float(ticker.get("last", 0) or 0)
    change_raw = ticker.get("change_percentage")
    try:
        change_pct = float(change_raw) if change_raw is not None else None
    except (TypeError, ValueError):
        change_pct = None
    return Signal(
        contract=contract,
        symbol=contract.replace("_", "/"),
        timeframe=timeframe,
        score=det.score,
        severity=sev,  # type: ignore[arg-type]
        signal_type=det.signal_type or "Bearish signal",
        reason=det.reason,
        last_price=last_price,
        change_24h_pct=change_pct,
        volume_24h_usdt=_parse_volume_usdt(ticker),
        breakdown=det.score_breakdown,
        detected_at=int(time.time()),
    )


async def run_scan(
    timeframes: list[Timeframe],
    min_volume_usdt: float = DEFAULT_MIN_VOLUME_USDT,
    limit: int | None = None,
) -> ScanResult:
    """Scan every liquid USDT perpetual on Gate.io across `timeframes`.

    Returns the combined list of signals meeting MEDIUM severity or higher,
    sorted by score descending.
    """
    async with GateIOClient() as client:
        contracts, tickers_map = await asyncio.gather(
            client.contracts(), _tickers_by_contract(client)
        )

        qualified: list[str] = []
        for c in contracts:
            name = c.get("name")
            if not isinstance(name, str) or not name.endswith("_USDT"):
                continue
            if c.get("in_delisting") or c.get("trade_status") == "delisted":
                continue
            ticker = tickers_map.get(name)
            if not ticker:
                continue
            if _parse_volume_usdt(ticker) < min_volume_usdt:
                continue
            qualified.append(name)

        if limit is not None:
            qualified = qualified[:limit]

        log.info("scanning %d contracts across %s", len(qualified), timeframes)

        tasks = [
            _scan_one(client, name, tf, tickers_map[name])
            for name in qualified
            for tf in timeframes
        ]
        results = await gather_limited(tasks, concurrency=SCAN_CONCURRENCY)

    signals = [s for s in results if isinstance(s, Signal)]
    signals.sort(key=lambda s: s.score, reverse=True)
    return ScanResult(signals=signals, scanned=len(qualified))
