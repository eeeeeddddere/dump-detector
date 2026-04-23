# Dump Detector

Scans **Gate.io USDT perpetual futures** for bearish setups and flags coins with a
high probability of dumping. Built for short opportunities on volatile altcoins.

![style](https://img.shields.io/badge/style-dark%20trading%20dashboard-0b0d10)
![stack](https://img.shields.io/badge/stack-FastAPI%20%2B%20vanilla%20JS-3ddc97)

---

## Features

- **Live scan** of every USDT-settled perpetual on Gate.io (`/futures/usdt/contracts`,
  `/tickers`, `/candlesticks`), with a configurable 24h-volume filter to skip dead pairs.
- **Timeframes:** 15m (priority) and 1h.
- **Dump patterns detected:**
  - Double Top
  - Head and Shoulders
  - Rising Wedge → breakdown
  - Fake pump → dump
  - Support break
  - Big red candle + volume spike
  - Lower highs + lower lows (bearish structure)
- **Dump Score (0–100)** with transparent breakdown:
  - pattern `+30`, volume spike `+20`, support break `+25`,
    bearish structure `+15`, strong red candle `+10`.
  - `80–100 → 🔴 HIGH`, `60–79 → 🟠 MEDIUM`, `<60 ignored`.
- **Dark trading-dashboard UI** with inline TradingView charts per signal,
  sortable by score / volume / 24h change, filterable by timeframe, and an optional
  30s / 60s auto-refresh.
- **Demo mode** with pre-saved signals for instant first-load results.

---

## Quickstart

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Open <http://localhost:8000> and click **Искать дампы**.

By default the UI loads with **Demo mode ON** so you see results instantly.
Uncheck it to hit Gate.io live (a full scan usually takes ~15–30 seconds).

### Run the test suite

```bash
pytest -q
```

---

## API

| Method | Path              | Description                                                      |
| ------ | ----------------- | ---------------------------------------------------------------- |
| GET    | `/`               | Serves the frontend.                                             |
| GET    | `/healthz`        | Liveness probe.                                                  |
| GET    | `/api/demo`       | Returns pre-saved demo signals. `?timeframe=15m\|1h\|all`.       |
| GET    | `/api/scan`       | Runs a live Gate.io scan. Query params below.                    |

### `/api/scan` query parameters

| Name         | Type    | Default   | Description                                                      |
| ------------ | ------- | --------- | ---------------------------------------------------------------- |
| `timeframe`  | enum    | `15m`     | `15m`, `1h`, or `all`.                                           |
| `min_volume` | float   | `500000`  | Minimum 24h USDT volume for a contract to be scanned.            |
| `limit`      | int     | *(none)*  | Cap on contracts scanned (useful to keep latency bounded).       |
| `demo`       | bool    | `false`   | If `true`, returns pre-saved signals without hitting Gate.io.    |

### Response shape

```json
{
  "signals": [
    {
      "contract": "SOL_USDT",
      "symbol": "SOL/USDT",
      "timeframe": "15m",
      "score": 91,
      "severity": "HIGH",
      "signal_type": "Rising Wedge breakdown",
      "reason": "rising wedge breakdown + volume spike + support break",
      "last_price": 142.37,
      "change_24h_pct": -3.8,
      "volume_24h_usdt": 482000000,
      "breakdown": {
        "pattern": 30, "volume_spike": 20, "support_break": 25,
        "bearish_structure": 15, "strong_candle": 10
      },
      "detected_at": 1714000000
    }
  ],
  "scanned": 182,
  "demo": false,
  "timeframe": "15m",
  "generated_at": 1714000000
}
```

---

## How the detection works

Each detector operates on the most recent ~120 candles and returns a boolean.
The scorer sums the weights of every detector that fires and caps the result at 100.

- **Swing highs/lows** are found with a simple `left=2, right=2` pivot window.
- **Double Top**: two pivot highs within ±1.5% of each other, current close below
  the valley between them.
- **Head & Shoulders**: three pivot highs where the middle is highest, shoulders
  within ±2% of each other, close below the neckline (lowest low between shoulders).
- **Rising Wedge**: three higher pivot lows, flattening highs (slope < lows slope),
  current close below the extrapolated rising-lows trendline.
- **Fake pump → dump**: ≥4% pump in the last ~12 candles followed by a close that
  erases >60% of the pump's gains.
- **Support break**: last close below the min of the prior 20 candles' lows.
- **Bearish structure**: last 3 pivot highs trending down **and** last 3 pivot lows
  trending down.
- **Volume spike**: last candle volume ≥ 2× the 20-candle average.
- **Strong red candle**: red body ≥ 1.5× the 14-candle ATR.

The implementation is intentionally pragmatic — the goal is to surface *plausible*
short setups on a noisy altcoin universe, not to ship a research-grade TA library.

---

## Project layout

```
dump-detector/
├── app/
│   ├── main.py        # FastAPI entrypoint, /api/scan, /api/demo, /healthz
│   ├── gateio.py      # Thin async Gate.io REST client
│   ├── scanner.py     # Orchestrates contract filtering + per-contract scans
│   ├── detector.py    # Pattern detectors + scoring
│   ├── demo.py        # Pre-saved demo signals
│   └── models.py      # Pydantic models
├── static/            # index.html, style.css, app.js (vanilla, no build step)
├── tests/             # pytest suite (detectors + API)
├── requirements.txt
└── README.md
```

---

## Disclaimer

This tool surfaces technical setups that **historically** precede dumps. It is
**not financial advice** and is **not** a trading bot. Always do your own
research and manage risk.
