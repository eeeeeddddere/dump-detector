"""Thin async client for the Gate.io USDT perpetual futures REST API.

Docs: https://www.gate.io/docs/developers/apiv4/#futures
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from .models import Candle

log = logging.getLogger(__name__)

BASE_URL = "https://api.gateio.ws/api/v4"
SETTLE = "usdt"
DEFAULT_TIMEOUT = httpx.Timeout(connect=5.0, read=15.0, write=10.0, pool=5.0)


class GateIOClient:
    """Async Gate.io futures client. Safe to reuse across requests."""

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client or httpx.AsyncClient(
            base_url=BASE_URL,
            timeout=DEFAULT_TIMEOUT,
            headers={"Accept": "application/json"},
        )
        self._owns_client = client is None

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def __aenter__(self) -> "GateIOClient":
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.aclose()

    async def _get(
        self, path: str, params: dict[str, Any] | None = None, max_retries: int = 3
    ) -> Any:
        delay = 0.5
        for attempt in range(max_retries + 1):
            r = await self._client.get(path, params=params)
            if r.status_code == 429:
                if attempt == max_retries:
                    r.raise_for_status()
                retry_after = r.headers.get("Retry-After")
                try:
                    wait = float(retry_after) if retry_after else delay
                except ValueError:
                    wait = delay
                await asyncio.sleep(min(wait, 5.0))
                delay *= 2
                continue
            r.raise_for_status()
            return r.json()
        raise RuntimeError("unreachable")

    async def contracts(self) -> list[dict[str, Any]]:
        """List all USDT-settled perpetual contracts."""
        return await self._get(f"/futures/{SETTLE}/contracts")

    async def tickers(self) -> list[dict[str, Any]]:
        """24h ticker snapshot for every contract."""
        return await self._get(f"/futures/{SETTLE}/tickers")

    async def candles(
        self,
        contract: str,
        interval: str = "15m",
        limit: int = 100,
    ) -> list[Candle]:
        """Fetch candlesticks for one contract.

        Gate.io returns items like:
            {"t": 1680000000, "v": 1234, "c": "27000", "h": "27100",
             "l": "26900", "o": "26950", "sum": "..."}
        """
        raw = await self._get(
            f"/futures/{SETTLE}/candlesticks",
            params={"contract": contract, "interval": interval, "limit": limit},
        )
        out: list[Candle] = []
        for row in raw:
            try:
                out.append(
                    Candle(
                        t=int(row["t"]),
                        o=float(row["o"]),
                        h=float(row["h"]),
                        l=float(row["l"]),
                        c=float(row["c"]),
                        v=float(row["v"]),
                    )
                )
            except (KeyError, TypeError, ValueError) as exc:
                log.debug("skipping malformed candle for %s: %s", contract, exc)
        out.sort(key=lambda k: k.t)
        return out


async def gather_limited(
    coros: list, concurrency: int = 10
) -> list[Any]:
    """Run coroutines with bounded concurrency, swallowing exceptions."""
    sem = asyncio.Semaphore(concurrency)

    async def _run(c):
        async with sem:
            try:
                return await c
            except Exception as exc:  # noqa: BLE001 — we log + continue
                log.warning("gather_limited task failed: %s", exc)
                return None

    return await asyncio.gather(*(_run(c) for c in coros))
