"""API-level tests using FastAPI's TestClient."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_healthz():
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_demo_endpoint_returns_signals():
    r = client.get("/api/demo")
    assert r.status_code == 200
    body = r.json()
    assert body["demo"] is True
    assert len(body["signals"]) >= 3
    for sig in body["signals"]:
        assert sig["score"] >= 60
        assert sig["severity"] in {"HIGH", "MEDIUM"}
        assert sig["symbol"].endswith("/USDT")
        assert set(sig["breakdown"].keys()) >= {
            "pattern",
            "volume_spike",
            "support_break",
            "bearish_structure",
            "strong_candle",
        }


def test_demo_endpoint_filters_by_timeframe():
    r = client.get("/api/demo", params={"timeframe": "1h"})
    assert r.status_code == 200
    body = r.json()
    assert all(s["timeframe"] == "1h" for s in body["signals"])


def test_scan_demo_flag_returns_demo_payload():
    r = client.get("/api/scan", params={"demo": "true"})
    assert r.status_code == 200
    body = r.json()
    assert body["demo"] is True
    assert body["signals"]


def test_index_is_served():
    r = client.get("/")
    assert r.status_code == 200
    assert "Dump Detector" in r.text
