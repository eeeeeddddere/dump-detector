"""FastAPI entrypoint for Dump Detector."""
from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .demo import demo_signals
from .models import ScanResponse, Signal, Timeframe
from .scanner import DEFAULT_MIN_VOLUME_USDT, run_scan

log = logging.getLogger("dump_detector")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

app = FastAPI(
    title="Dump Detector",
    description="Find Gate.io USDT perpetual futures with bearish setups.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/demo", response_model=ScanResponse)
async def api_demo(
    timeframe: Timeframe | Literal["all"] = "all",
) -> ScanResponse:
    signals: list[Signal] = demo_signals()
    if timeframe != "all":
        signals = [s for s in signals if s.timeframe == timeframe]
    return ScanResponse(
        signals=signals,
        scanned=len(signals),
        demo=True,
        timeframe=timeframe,
        generated_at=int(time.time()),
    )


@app.get("/api/scan", response_model=ScanResponse)
async def api_scan(
    timeframe: Timeframe | Literal["all"] = Query(
        "15m", description="Candlestick timeframe to scan."
    ),
    min_volume: float = Query(
        DEFAULT_MIN_VOLUME_USDT,
        ge=0,
        description="Minimum 24h USDT volume to include a contract.",
    ),
    limit: int | None = Query(
        None,
        ge=1,
        le=400,
        description="Cap on number of contracts to scan (useful for quick runs).",
    ),
    demo: bool = Query(False, description="Return pre-saved demo signals instead of live data."),
) -> ScanResponse:
    if demo:
        return await api_demo(timeframe=timeframe)

    tfs: list[Timeframe]
    if timeframe == "all":
        tfs = ["15m", "1h"]
    else:
        tfs = [timeframe]

    try:
        result = await run_scan(timeframes=tfs, min_volume_usdt=min_volume, limit=limit)
    except Exception as exc:
        log.exception("live scan failed")
        raise HTTPException(status_code=502, detail=f"Gate.io scan failed: {exc}") from exc

    return ScanResponse(
        signals=result.signals,
        scanned=result.scanned,
        demo=False,
        timeframe=timeframe,
        generated_at=int(time.time()),
    )


if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.get("/", include_in_schema=False)
    async def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")
