/* Dump Detector frontend controller. */

const els = {
  scanBtn: document.getElementById("scan-btn"),
  refreshBtn: document.getElementById("refresh-btn"),
  timeframe: document.getElementById("timeframe"),
  minVolume: document.getElementById("min-volume"),
  sort: document.getElementById("sort"),
  autoRefresh: document.getElementById("auto-refresh"),
  refreshInterval: document.getElementById("refresh-interval"),
  demoMode: document.getElementById("demo-mode"),
  status: document.getElementById("status"),
  summary: document.getElementById("summary"),
  lastUpdated: document.getElementById("last-updated"),
  signals: document.getElementById("signals"),
  empty: document.getElementById("empty-state"),
  template: document.getElementById("signal-template"),
};

const state = {
  signals: [],
  scanned: 0,
  inFlight: null,
  timer: null,
};

function setStatus(text, level = "muted") {
  els.status.textContent = text;
  els.status.className = `status ${level}`;
}

function formatPrice(p) {
  if (p == null || !Number.isFinite(p)) return "–";
  if (p >= 1000) return p.toLocaleString(undefined, { maximumFractionDigits: 2 });
  if (p >= 1) return p.toFixed(3);
  if (p >= 0.01) return p.toFixed(4);
  if (p >= 0.0001) return p.toFixed(6);
  return p.toPrecision(3);
}

function formatVolume(v) {
  if (v == null || !Number.isFinite(v) || v <= 0) return "vol –";
  if (v >= 1e9) return `vol $${(v / 1e9).toFixed(2)}B`;
  if (v >= 1e6) return `vol $${(v / 1e6).toFixed(1)}M`;
  if (v >= 1e3) return `vol $${(v / 1e3).toFixed(0)}K`;
  return `vol $${v.toFixed(0)}`;
}

function formatChange(c) {
  if (c == null || !Number.isFinite(c)) return "24h –";
  const sign = c > 0 ? "+" : "";
  return `24h ${sign}${c.toFixed(2)}%`;
}

function sortSignals(signals) {
  const mode = els.sort.value;
  const copy = [...signals];
  if (mode === "score") {
    copy.sort((a, b) => b.score - a.score);
  } else if (mode === "volume") {
    copy.sort((a, b) => (b.volume_24h_usdt || 0) - (a.volume_24h_usdt || 0));
  } else if (mode === "change") {
    copy.sort((a, b) => (a.change_24h_pct ?? 0) - (b.change_24h_pct ?? 0));
  }
  return copy;
}

function renderBreakdown(bd, parent) {
  parent.innerHTML = "";
  const items = [
    ["pattern", bd.pattern, "+30"],
    ["volume", bd.volume_spike, "+20"],
    ["support", bd.support_break, "+25"],
    ["structure", bd.bearish_structure, "+15"],
    ["candle", bd.strong_candle, "+10"],
  ];
  for (const [label, value, max] of items) {
    const chip = document.createElement("span");
    chip.className = "chip" + (value > 0 ? " active" : "");
    chip.textContent = `${label} ${value > 0 ? `+${value}` : `0/${max.slice(1)}`}`;
    parent.appendChild(chip);
  }
}

function attachChart(host, signal) {
  host.innerHTML = "";
  const id = `tv-${signal.contract}-${signal.timeframe}-${Math.random().toString(36).slice(2, 8)}`;
  const mount = document.createElement("div");
  mount.id = id;
  mount.style.height = "100%";
  host.appendChild(mount);

  const intervalMap = { "15m": "15", "1h": "60" };
  try {
    new TradingView.widget({
      container_id: id,
      symbol: `GATEIO:${signal.contract.replace("_", "")}.P`,
      interval: intervalMap[signal.timeframe] || "15",
      theme: "dark",
      style: "1",
      locale: "en",
      autosize: true,
      toolbar_bg: "#12161c",
      hide_top_toolbar: false,
      hide_side_toolbar: true,
      allow_symbol_change: true,
    });
  } catch (err) {
    host.textContent = "Chart unavailable.";
  }
}

function renderSignals() {
  const sorted = sortSignals(state.signals);
  els.signals.innerHTML = "";
  if (sorted.length === 0) {
    els.empty.hidden = false;
    els.summary.textContent = `Scanned ${state.scanned} contract${state.scanned === 1 ? "" : "s"} — nothing qualified.`;
    return;
  }
  els.empty.hidden = true;
  for (const sig of sorted) {
    const node = els.template.content.firstElementChild.cloneNode(true);
    const sevClass = sig.severity === "HIGH" ? "sev-high" : "sev-medium";
    node.classList.add(sevClass);
    node.querySelector(".symbol").textContent = sig.symbol;
    node.querySelector(".timeframe-badge").textContent = sig.timeframe;
    node.querySelector(".score").textContent = sig.score;
    node.querySelector(".severity").textContent = sig.severity;
    node.querySelector(".signal-type").textContent = sig.signal_type;
    node.querySelector(".price").textContent = `price ${formatPrice(sig.last_price)}`;
    const changeEl = node.querySelector(".change");
    changeEl.textContent = formatChange(sig.change_24h_pct);
    if (sig.change_24h_pct != null) {
      changeEl.classList.add(sig.change_24h_pct < 0 ? "negative" : "positive");
    }
    node.querySelector(".volume").textContent = formatVolume(sig.volume_24h_usdt);
    node.querySelector(".reason").textContent = sig.reason;
    renderBreakdown(sig.breakdown, node.querySelector(".breakdown"));

    const chartHost = node.querySelector(".chart-host");
    const chartToggleBtn = node.querySelector(".chart-toggle button");
    chartToggleBtn.addEventListener("click", () => {
      if (chartHost.hidden) {
        chartHost.hidden = false;
        chartToggleBtn.textContent = "Hide chart";
        attachChart(chartHost, sig);
      } else {
        chartHost.hidden = true;
        chartToggleBtn.textContent = "Show chart";
        chartHost.innerHTML = "";
      }
    });

    els.signals.appendChild(node);
  }
  const highs = sorted.filter((s) => s.severity === "HIGH").length;
  const meds = sorted.filter((s) => s.severity === "MEDIUM").length;
  els.summary.textContent = `Scanned ${state.scanned} contract${state.scanned === 1 ? "" : "s"} · ${highs} HIGH · ${meds} MEDIUM`;
}

async function runScan({ silent = false } = {}) {
  if (state.inFlight) return;
  const demo = els.demoMode.checked;
  const params = new URLSearchParams({
    timeframe: els.timeframe.value,
    demo: String(demo),
  });
  if (!demo) {
    params.set("min_volume", els.minVolume.value || "500000");
  }
  const url = `/api/scan?${params.toString()}`;
  if (!silent) {
    setStatus(demo ? "Loading demo signals…" : "Scanning Gate.io futures (this can take 15–30s)…");
  }
  els.scanBtn.disabled = true;
  els.refreshBtn.disabled = true;

  const controller = new AbortController();
  state.inFlight = controller;
  try {
    const res = await fetch(url, { signal: controller.signal });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.detail || `HTTP ${res.status}`);
    }
    const data = await res.json();
    state.signals = data.signals || [];
    state.scanned = data.scanned || 0;
    renderSignals();
    const when = new Date((data.generated_at || Date.now() / 1000) * 1000);
    els.lastUpdated.textContent = `updated ${when.toLocaleTimeString()}${data.demo ? " (demo)" : ""}`;
    setStatus(
      data.demo
        ? `Demo: ${state.signals.length} pre-saved signal${state.signals.length === 1 ? "" : "s"}.`
        : `Live: ${state.signals.length} signal${state.signals.length === 1 ? "" : "s"} from ${state.scanned} contracts.`,
      "ok",
    );
  } catch (err) {
    if (err.name === "AbortError") return;
    console.error(err);
    setStatus(`Error: ${err.message}`, "error");
  } finally {
    state.inFlight = null;
    els.scanBtn.disabled = false;
    els.refreshBtn.disabled = state.signals.length === 0 && !els.autoRefresh.checked ? false : false;
    els.refreshBtn.disabled = false;
  }
}

function configureAutoRefresh() {
  if (state.timer) {
    clearInterval(state.timer);
    state.timer = null;
  }
  if (!els.autoRefresh.checked) return;
  const seconds = parseInt(els.refreshInterval.value, 10) || 60;
  state.timer = setInterval(() => runScan({ silent: true }), seconds * 1000);
}

els.scanBtn.addEventListener("click", () => runScan());
els.refreshBtn.addEventListener("click", () => runScan());
els.autoRefresh.addEventListener("change", configureAutoRefresh);
els.refreshInterval.addEventListener("change", configureAutoRefresh);
els.sort.addEventListener("change", renderSignals);
els.timeframe.addEventListener("change", () => {
  if (state.signals.length > 0) runScan({ silent: true });
});
els.demoMode.addEventListener("change", () => {
  setStatus(
    els.demoMode.checked
      ? "Demo mode ON — click “Искать дампы” for instant sample signals."
      : "Demo mode OFF — click “Искать дампы” to hit Gate.io live.",
  );
});
