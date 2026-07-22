#!/usr/bin/env python3
"""
ShipStation Fulfillment Dashboard Tool
=======================================
A local Flask web app that pulls order/fulfillment data from ShipStation and
generates a self-contained, static HTML dashboard you can push to your
GitHub tools dashboard.

Flow:
  1. Login with ShipStation V1 API key + secret (held in memory only, never
     written to disk).
  2. Fetches all currently-open orders (aging snapshot) and all shipped
     orders for the trailing N months (historical fill-time trend).
  3. Builds a self-contained fulfillment_dashboard.html with the data baked
     in as JSON, plus charts rendered client-side.
  4. Download the HTML and commit it to your repo. Re-run any time for a
     fresh snapshot.

Usage:
    pip install flask requests
    python shipstation_fulfillment_dashboard.py

Then open http://localhost:5058 in your browser.
"""

import argparse
import base64
import json
import os
import socket
import time
import webbrowser
from datetime import datetime, timedelta
from threading import Lock, Thread

from flask import Flask, render_template_string, request, jsonify, send_file
import requests

# ─── ShipStation API ──────────────────────────────────────────────────────────

API_BASE = "https://ssapi.shipstation.com"
RATE_LIMIT_DELAY = 1.6  # ~37 req/min, safely under the 40/min cap

api_lock = Lock()
last_request_time = 0


def ss_headers(api_key, api_secret):
    creds = base64.b64encode(f"{api_key}:{api_secret}".encode()).decode()
    return {"Authorization": f"Basic {creds}", "Content-Type": "application/json"}


def ss_request(method, path, api_key, api_secret, json_data=None, params=None):
    global last_request_time
    with api_lock:
        elapsed = time.time() - last_request_time
        if elapsed < RATE_LIMIT_DELAY:
            time.sleep(RATE_LIMIT_DELAY - elapsed)
        last_request_time = time.time()
    url = f"{API_BASE}{path}"
    headers = ss_headers(api_key, api_secret)
    resp = requests.request(method, url, headers=headers, json=json_data, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json() if resp.text else {}


def fetch_warehouses(api_key, api_secret):
    """Returns {warehouseId: displayName}."""
    data = ss_request("GET", "/warehouses", api_key, api_secret)
    out = {}
    for w in data if isinstance(data, list) else data.get("warehouses", []):
        out[w.get("warehouseId")] = w.get("warehouseName") or w.get("originAddress", {}).get("name") or "Unknown"
    return out


def fetch_tags(api_key, api_secret):
    """Returns the account's ShipStation tags as [{tagId, name, color}, ...]."""
    data = ss_request("GET", "/accounts/listtags", api_key, api_secret)
    return data if isinstance(data, list) else []


def fetch_orders(api_key, api_secret, params_base, progress_cb=None):
    """Paginate through /orders for a given filter set."""
    page = 1
    results = []
    while True:
        params = dict(params_base, page=page, pageSize=500, sortBy="OrderDate", sortDir="ASC")
        data = ss_request("GET", "/orders", api_key, api_secret, params=params)
        batch = data.get("orders", [])
        if not batch:
            break
        results.extend(batch)
        total_pages = data.get("pages", 1)
        if progress_cb:
            progress_cb(len(results), total_pages, page)
        if page >= total_pages:
            break
        page += 1
    return results


OPEN_STATUSES = ["awaiting_shipment", "on_hold", "pending_fulfillment"]

AGING_BUCKETS = [
    ("<1", 0, 1),
    ("1-2", 1, 2),
    ("2-4", 2, 4),
    ("4-8", 4, 8),
    ("8-24", 8, 24),
    ("24-36", 24, 36),
    ("36-48", 36, 48),
    ("48-72", 48, 72),
    ("72-96", 72, 96),
    ("96+", 96, float("inf")),
]


def parse_ss_date(s):
    if not s:
        return None
    # Most ShipStation timestamps look like "2026-07-21T14:32:00.0000000",
    # but shipDate comes back date-only, e.g. "2026-07-21".
    s = s.split(".")[0]
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def bucket_for_hours(hours):
    for label, lo, hi in AGING_BUCKETS:
        if lo <= hours < hi:
            return label
    return AGING_BUCKETS[-1][0]


def business_hours_elapsed(start, end, closed_weekdays=(5, 6)):
    """Hours between start and end, excluding full closed weekdays (default Sat/Sun)."""
    if not start or not end or end <= start:
        return 0.0
    total = 0.0
    cursor = datetime(start.year, start.month, start.day)
    while cursor < end:
        day_end = cursor + timedelta(days=1)
        if cursor.weekday() not in closed_weekdays:
            seg_start = max(cursor, start)
            seg_end = min(day_end, end)
            if seg_end > seg_start:
                total += (seg_end - seg_start).total_seconds() / 3600
        cursor = day_end
    return total


def location_name(order, warehouses):
    wid = (order.get("advancedOptions") or {}).get("warehouseId")
    return warehouses.get(wid, "Unassigned")


def build_snapshot(open_orders, warehouses, sla_hours=48):
    """Current aging snapshot, overall + by location, plus the breach list.

    Also returns an `order_detail` row per open order (hours open, both raw
    and weekend-adjusted, plus tagIds) so the dashboard can let the viewer
    toggle tag-based exclusions live in the browser after the fact, rather
    than locking in a choice of "normal order" tags at generation time.
    """
    now = datetime.utcnow()
    by_location = {}
    overall_counts = {label: 0 for label, _, _ in AGING_BUCKETS}
    breach_list = []
    order_detail = []

    for o in open_orders:
        order_date = parse_ss_date(o.get("orderDate"))
        if not order_date:
            continue
        hours = (now - order_date).total_seconds() / 3600
        label = bucket_for_hours(hours)
        loc = location_name(o, warehouses)
        items = o.get("items") or []
        top_sku = items[0].get("sku") if items else ""
        carrier = o.get("carrierCode") or o.get("requestedShippingService") or ""

        overall_counts[label] += 1
        by_location.setdefault(loc, {lb: 0 for lb, _, _ in AGING_BUCKETS})
        by_location[loc][label] += 1

        if hours >= sla_hours:
            breach_list.append({
                "orderNumber": o.get("orderNumber"),
                "orderDate": o.get("orderDate"),
                "hoursOpen": round(hours, 1),
                "location": loc,
                "carrier": carrier,
                "sku": top_sku,
                "status": o.get("orderStatus"),
            })

        order_detail.append({
            "orderNumber": o.get("orderNumber"),
            "orderDate": o.get("orderDate"),
            "hoursOpen": round(hours, 1),
            "normalHoursOpen": round(business_hours_elapsed(order_date, now), 1),
            "location": loc,
            "carrier": carrier,
            "sku": top_sku,
            "status": o.get("orderStatus"),
            "tagIds": sorted(o.get("tagIds") or []),
        })

    breach_list.sort(key=lambda r: r["hoursOpen"], reverse=True)

    total = sum(overall_counts.values()) or 1
    overall_pct = {k: round(100 * v / total, 1) for k, v in overall_counts.items()}
    location_pct = {}
    for loc, counts in by_location.items():
        loc_total = sum(counts.values()) or 1
        location_pct[loc] = {k: round(100 * v / loc_total, 1) for k, v in counts.items()}

    return {
        "overall_counts": overall_counts,
        "overall_pct": overall_pct,
        "by_location_counts": by_location,
        "by_location_pct": location_pct,
        "breach_list": breach_list,
        "total_open": sum(overall_counts.values()),
        "order_detail": order_detail,
    }


def build_trend(shipped_orders, warehouses, sla_hours=48):
    """Weekly fill-time trend, overall + by location, from shipped orders."""
    weekly = {}  # week_start -> {"hours": [...], "loc": {loc: [hours...]}}
    carrier_counts = {}
    sku_counts = {}

    for o in shipped_orders:
        order_date = parse_ss_date(o.get("orderDate"))
        ship_date = parse_ss_date(o.get("shipDate"))
        if not order_date or not ship_date:
            continue
        fill_hours = (ship_date - order_date).total_seconds() / 3600
        if fill_hours < 0:
            continue
        loc = location_name(o, warehouses)
        week_start = (order_date - timedelta(days=order_date.weekday())).strftime("%Y-%m-%d")

        wk = weekly.setdefault(week_start, {"all": [], "loc": {}})
        wk["all"].append(fill_hours)
        wk["loc"].setdefault(loc, []).append(fill_hours)

        carrier = o.get("carrierCode") or "unknown"
        c = carrier_counts.setdefault(carrier, {"count": 0, "breach": 0})
        c["count"] += 1
        if fill_hours >= sla_hours:
            c["breach"] += 1

        for item in (o.get("items") or []):
            sku = item.get("sku") or "unknown"
            s = sku_counts.setdefault(sku, {"count": 0, "breach": 0})
            s["count"] += 1
            if fill_hours >= sla_hours:
                s["breach"] += 1

    weeks_sorted = sorted(weekly.keys())
    trend = {
        "weeks": weeks_sorted,
        "avg_fill_hours": [round(sum(weekly[w]["all"]) / len(weekly[w]["all"]), 1) for w in weeks_sorted],
        "pct_breach": [
            round(100 * sum(1 for h in weekly[w]["all"] if h >= sla_hours) / len(weekly[w]["all"]), 1)
            for w in weeks_sorted
        ],
        "by_location": {},
    }
    all_locs = set()
    for w in weeks_sorted:
        all_locs.update(weekly[w]["loc"].keys())
    for loc in all_locs:
        trend["by_location"][loc] = [
            round(sum(weekly[w]["loc"].get(loc, [0])) / len(weekly[w]["loc"][loc]), 1)
            if weekly[w]["loc"].get(loc) else None
            for w in weeks_sorted
        ]

    top_skus = sorted(sku_counts.items(), key=lambda kv: kv[1]["breach"], reverse=True)[:25]

    return {
        "trend": trend,
        "carrier_breakdown": carrier_counts,
        "top_sku_breaches": [{"sku": k, **v} for k, v in top_skus],
    }


# ─── Flask App ────────────────────────────────────────────────────────────────

app = Flask(__name__)

with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "chart.umd.min.js"), "r", encoding="utf-8") as _f:
    CHARTJS_JS = _f.read()

state = {
    "api_key": "",
    "api_secret": "",
    "status": "idle",       # idle | fetching_open | fetching_history | building | done | error
    "message": "",
    "progress": {"open_orders": 0, "history_pages": 0},
    "dashboard_path": None,
    "error": None,
}
state_lock = Lock()


LOGIN_HTML = r"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>ShipStation Fulfillment Dashboard</title>
<style>
  body { font-family: -apple-system, Segoe UI, Arial, sans-serif; background:#f4f5f7; margin:0; padding:0; }
  .wrap { max-width: 520px; margin: 80px auto; background:#fff; border-radius:10px; box-shadow:0 2px 12px rgba(0,0,0,0.08); padding:36px; }
  h1 { font-size: 20px; margin-bottom: 4px; }
  p.sub { color:#666; margin-top:0; margin-bottom: 24px; font-size: 14px; }
  label { display:block; font-size:13px; font-weight:600; margin:14px 0 4px; color:#333; }
  input[type=text], input[type=password], input[type=number] {
    width:100%; box-sizing:border-box; padding:9px 10px; border:1px solid #ccc; border-radius:6px; font-size:14px;
  }
  button { margin-top:22px; width:100%; padding:11px; background:#5b21b6; color:#fff; border:none; border-radius:6px; font-size:15px; cursor:pointer; }
  button:hover { background:#4c1d95; }
  .row { display:flex; gap:12px; }
  .row > div { flex:1; }
  #status { margin-top:18px; font-size:13px; color:#555; white-space:pre-line; }
  .bar { height:8px; background:#eee; border-radius:4px; overflow:hidden; margin-top:8px; }
  .bar > div { height:100%; background:#5b21b6; width:0%; transition:width .3s; }
  a.dl { display:inline-block; margin-top:14px; color:#5b21b6; font-weight:600; }
</style>
</head>
<body>
<div class="wrap">
  <h1>ShipStation Fulfillment Dashboard</h1>
  <p class="sub">Credentials are used only for this run and are never written to disk.</p>

  <label>API Key</label>
  <input type="text" id="api_key" autocomplete="off">
  <label>API Secret</label>
  <input type="password" id="api_secret" autocomplete="off">

  <div class="row">
    <div>
      <label>SLA (hours)</label>
      <input type="number" id="sla_hours" value="48">
    </div>
    <div>
      <label>History (months)</label>
      <input type="number" id="months" value="12">
    </div>
  </div>

  <button onclick="generate()">Generate Dashboard</button>
  <div id="status"></div>
</div>

<script>
async function generate() {
  const api_key = document.getElementById('api_key').value.trim();
  const api_secret = document.getElementById('api_secret').value.trim();
  const sla_hours = parseInt(document.getElementById('sla_hours').value) || 48;
  const months = parseInt(document.getElementById('months').value) || 12;
  if (!api_key || !api_secret) { alert('Enter API key and secret'); return; }

  document.getElementById('status').textContent = 'Connecting...';
  const r = await fetch('/api/generate', {
    method: 'POST', headers: {'Content-Type':'application/json'},
    body: JSON.stringify({api_key, api_secret, sla_hours, months})
  });
  const data = await r.json();
  if (!r.ok) { document.getElementById('status').textContent = 'Error: ' + (data.error || 'unknown'); return; }
  poll();
}

async function poll() {
  const r = await fetch('/api/status');
  const s = await r.json();
  let txt = s.message || s.status;
  document.getElementById('status').innerHTML = txt +
    (s.status !== 'done' && s.status !== 'error' ? '<div class="bar"><div style="width:' + (s.pct||0) + '%"></div></div>' : '');
  if (s.status === 'done') {
    document.getElementById('status').innerHTML += '<br><a class="dl" href="/api/download">Download fulfillment_dashboard.html &darr;</a>';
    return;
  }
  if (s.status === 'error') { return; }
  setTimeout(poll, 1000);
}
</script>
</body>
</html>
"""


@app.route("/")
def index():
    return render_template_string(LOGIN_HTML)


def run_pipeline(api_key, api_secret, sla_hours, months):
    try:
        with state_lock:
            state["status"] = "fetching_open"
            state["message"] = "Fetching open orders..."

        warehouses = fetch_warehouses(api_key, api_secret)
        tag_catalog = {
            t["tagId"]: {"name": t.get("name") or f"Tag {t['tagId']}", "color": t.get("color") or "#999999"}
            for t in fetch_tags(api_key, api_secret)
        }

        open_orders = []
        for status_val in OPEN_STATUSES:
            def cb(n, total_pages, page, s=status_val):
                with state_lock:
                    state["message"] = f"Fetching open orders ({s})... {n} so far"
            open_orders.extend(fetch_orders(api_key, api_secret, {"orderStatus": status_val}, progress_cb=cb))

        with state_lock:
            state["status"] = "fetching_history"
            state["message"] = f"Fetching {months} months of shipped orders..."

        date_end = datetime.utcnow()
        date_start = date_end - timedelta(days=30 * months)

        def cb2(n, total_pages, page):
            with state_lock:
                state["message"] = f"Fetching shipment history... {n} orders so far (page {page}/{total_pages})"
                state["pct"] = min(95, int(100 * page / max(total_pages, 1)))

        shipped_orders = fetch_orders(api_key, api_secret, {
            "orderStatus": "shipped",
            "orderDateStart": date_start.strftime("%Y-%m-%d"),
            "orderDateEnd": date_end.strftime("%Y-%m-%d"),
        }, progress_cb=cb2)

        with state_lock:
            state["status"] = "building"
            state["message"] = "Building dashboard..."

        snapshot = build_snapshot(open_orders, warehouses, sla_hours)
        history = build_trend(shipped_orders, warehouses, sla_hours)

        payload = {
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "sla_hours": sla_hours,
            "months": months,
            "snapshot": snapshot,
            "history": history,
            "bucket_labels": [lb for lb, _, _ in AGING_BUCKETS],
            "bucket_ranges": [[lo, hi] for _, lo, hi in AGING_BUCKETS],
            "tag_catalog": tag_catalog,
        }

        out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fulfillment_dashboard.html")
        html = DASHBOARD_TEMPLATE.replace("__CHARTJS_JS__", CHARTJS_JS).replace("__DATA_JSON__", json.dumps(payload))
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(html)

        with state_lock:
            state["status"] = "done"
            state["message"] = f"Done. {len(open_orders)} open orders, {len(shipped_orders)} shipped orders analyzed."
            state["dashboard_path"] = out_path
            state["pct"] = 100

    except requests.HTTPError as e:
        with state_lock:
            state["status"] = "error"
            state["message"] = f"ShipStation API error: {e}"
    except Exception as e:
        with state_lock:
            state["status"] = "error"
            state["message"] = f"Error: {e}"


@app.route("/api/generate", methods=["POST"])
def api_generate():
    data = request.get_json(force=True)
    api_key = data.get("api_key", "")
    api_secret = data.get("api_secret", "")
    sla_hours = data.get("sla_hours", 48)
    months = data.get("months", 12)
    with state_lock:
        if state["status"] not in ("idle", "done", "error"):
            return jsonify({"error": "A generation is already in progress"}), 409
        state["status"] = "fetching_open"
        state["message"] = "Starting..."
        state["pct"] = 0
        state["error"] = None
    Thread(target=run_pipeline, args=(api_key, api_secret, sla_hours, months), daemon=True).start()
    return jsonify({"ok": True})


@app.route("/api/status")
def api_status():
    with state_lock:
        return jsonify({
            "status": state["status"],
            "message": state["message"],
            "pct": state.get("pct", 0),
        })


@app.route("/api/download")
def api_download():
    with state_lock:
        path = state.get("dashboard_path")
    if not path or not os.path.exists(path):
        return "Not ready", 404
    return send_file(path, as_attachment=True, download_name="fulfillment_dashboard.html")


# ─── Dashboard HTML template (this is what gets saved & pushed to GitHub) ─────

DASHBOARD_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>ShipStation Fulfillment Dashboard</title>
<script>__CHARTJS_JS__</script>
<style>
  :root { --purple:#5b21b6; --red:#dc2626; --bg:#f4f5f7; --card:#ffffff; --text:#1f2430; --muted:#6b7280; --border:#e5e7eb; }
  * { box-sizing: border-box; }
  body { font-family: -apple-system, "Segoe UI", Arial, sans-serif; background:var(--bg); color:var(--text); margin:0; padding:24px; }
  h1 { font-size:22px; margin:0 0 4px; }
  .meta { color:var(--muted); font-size:13px; margin-bottom:24px; }
  .grid { display:grid; grid-template-columns: repeat(2, 1fr); gap:20px; }
  .card { background:var(--card); border:1px solid var(--border); border-radius:10px; padding:20px; }
  .card.full { grid-column: 1 / -1; }
  .card h2 { font-size:15px; margin:0 0 14px; }
  table { width:100%; border-collapse:collapse; font-size:13px; }
  th, td { text-align:left; padding:6px 8px; border-bottom:1px solid var(--border); }
  th { color:var(--muted); font-weight:600; }
  .tag { display:inline-block; padding:2px 8px; border-radius:12px; font-size:11px; font-weight:600; }
  .tag.swanzey { background:#ede9fe; color:#5b21b6; }
  .tag.saratoga { background:#fee2e2; color:#dc2626; }
  .tag.other { background:#f3f4f6; color:#374151; }
  .kpis { display:flex; gap:16px; margin-bottom:20px; flex-wrap:wrap; }
  .kpi { background:var(--card); border:1px solid var(--border); border-radius:10px; padding:16px 20px; min-width:140px; }
  .kpi .num { font-size:24px; font-weight:700; }
  .kpi .lbl { font-size:12px; color:var(--muted); }
  select { padding:6px 10px; border-radius:6px; border:1px solid var(--border); font-size:13px; }
  canvas { max-width:100%; }
  .tag-cb-row { display:inline-flex; align-items:center; gap:6px; font-size:13px; margin:0 14px 8px 0; cursor:pointer; }
  .tag-dot { display:inline-block; width:10px; height:10px; border-radius:50%; flex-shrink:0; }
</style>
</head>
<body>
<h1>Open Order Aging &amp; Fulfillment History</h1>
<div class="meta" id="meta"></div>

<div class="kpis" id="kpis"></div>

<div class="grid">
  <div class="card">
    <h2>Current Aging &mdash; Overall</h2>
    <canvas id="agingOverall" height="220"></canvas>
  </div>
  <div class="card">
    <h2>Current Aging &mdash; By Location</h2>
    <select id="locSelect"></select>
    <canvas id="agingByLoc" height="220"></canvas>
  </div>
  <div class="card full">
    <h2>Normal Order Aging &mdash; Weekend-Adjusted</h2>
    <div id="tagFilters" style="margin-bottom:10px;"></div>
    <div class="meta" id="normalMeta" style="margin-bottom:10px;"></div>
    <canvas id="agingNormal" height="160"></canvas>
  </div>
  <div class="card full">
    <h2>Weekly Fill-Time Trend (avg hours to ship)</h2>
    <canvas id="trendChart" height="110"></canvas>
  </div>
  <div class="card">
    <h2>Carrier Breakdown (SLA breach rate)</h2>
    <canvas id="carrierChart" height="220"></canvas>
  </div>
  <div class="card">
    <h2>Top SKUs by SLA Breach Count</h2>
    <table id="skuTable"><thead><tr><th>SKU</th><th>Shipped</th><th>Breaches</th><th>Breach %</th></tr></thead><tbody></tbody></table>
  </div>
  <div class="card full">
    <h2>Currently Open &amp; Past SLA (sorted oldest first)</h2>
    <table id="breachTable"><thead><tr><th>Order #</th><th>Order Date</th><th>Hours Open</th><th>Location</th><th>Carrier</th><th>SKU</th><th>Status</th></tr></thead><tbody></tbody></table>
  </div>
  <div class="card full">
    <h2>Normal Orders Past SLA &mdash; Weekend-Adjusted (sorted oldest first)</h2>
    <table id="normalBreachTable"><thead><tr><th>Order #</th><th>Order Date</th><th>Hours Open (Wknd-Adj)</th><th>Location</th><th>Carrier</th><th>SKU</th><th>Status</th></tr></thead><tbody></tbody></table>
  </div>
</div>

<script>
const DATA = __DATA_JSON__;

function locTagClass(loc) {
  const l = (loc||"").toLowerCase();
  if (l.includes("swanzey")) return "swanzey";
  if (l.includes("saratoga")) return "saratoga";
  return "other";
}

function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, c => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  }[c]));
}

document.getElementById('meta').textContent =
  `Generated ${new Date(DATA.generated_at).toLocaleString()} · SLA: ${DATA.sla_hours}h · History window: ${DATA.months} months`;

// KPIs
const snap = DATA.snapshot;
const totalOpen = Object.values(snap.overall_counts).reduce((a,b)=>a+b,0);
const breachCount = snap.breach_list.length;
const breachPct = totalOpen ? (100*breachCount/totalOpen).toFixed(1) : 0;
const avgFillRecent = DATA.history.trend.avg_fill_hours.length ? DATA.history.trend.avg_fill_hours[DATA.history.trend.avg_fill_hours.length-1] : null;
const kpis = [
  {num: totalOpen, lbl: "Open Orders"},
  {num: breachCount, lbl: "Past SLA Now"},
  {num: breachPct + "%", lbl: "% Currently Breaching"},
  {num: (avgFillRecent!==null ? avgFillRecent+"h" : "—"), lbl: "Avg Fill Time (latest week)"},
  {num: 0, lbl: "Normal Orders Past SLA (Wknd-Adj)", id: "kpiNormalBreach"},
];
document.getElementById('kpis').innerHTML = kpis.map(k => `<div class="kpi"><div class="num"${k.id ? ` id="${k.id}"` : ''}>${k.num}</div><div class="lbl">${k.lbl}</div></div>`).join('');

// Aging overall
const labels = DATA.bucket_labels;
const slaIdx = labels.indexOf("48-72");
function barColors() {
  return labels.map((_, i) => i >= slaIdx ? "#dc2626" : "#5b21b6");
}
new Chart(document.getElementById('agingOverall'), {
  type: 'bar',
  data: { labels, datasets: [{ label: '% of open orders', data: labels.map(l => snap.overall_pct[l] || 0), backgroundColor: barColors() }] },
  options: { indexAxis: 'y', plugins: { legend: { display: false } }, scales: { x: { ticks: { callback: v => v + '%' } } } }
});

// Aging by location
const locSelect = document.getElementById('locSelect');
const locs = Object.keys(snap.by_location_pct);
locSelect.innerHTML = locs.map(l => `<option value="${l}">${l}</option>`).join('');
let locChart;
function renderLocChart(loc) {
  const pct = snap.by_location_pct[loc] || {};
  const data = labels.map(l => pct[l] || 0);
  if (locChart) locChart.destroy();
  locChart = new Chart(document.getElementById('agingByLoc'), {
    type: 'bar',
    data: { labels, datasets: [{ label: '% of open orders — ' + loc, data, backgroundColor: barColors() }] },
    options: { indexAxis: 'y', plugins: { legend: { display: false } }, scales: { x: { ticks: { callback: v => v + '%' } } } }
  });
}
if (locs.length) renderLocChart(locs[0]);
locSelect.addEventListener('change', e => renderLocChart(e.target.value));

// Normal order aging — interactive: pick tags to exclude, live in the browser
const orderDetail = snap.order_detail || [];
const bucketRanges = DATA.bucket_ranges;
function bucketForHours(hours) {
  for (let i = 0; i < bucketRanges.length; i++) {
    if (hours >= bucketRanges[i][0] && hours < bucketRanges[i][1]) return labels[i];
  }
  return labels[labels.length - 1];
}

const tagCatalog = DATA.tag_catalog || {};
const presentTagIds = new Set();
orderDetail.forEach(o => (o.tagIds || []).forEach(id => presentTagIds.add(id)));
const presentTags = Array.from(presentTagIds).filter(id => tagCatalog[id]);
const tagFilterBox = document.getElementById('tagFilters');
tagFilterBox.innerHTML = presentTags.length
  ? '<div style="font-size:12px;color:var(--muted);margin-bottom:6px;">Exclude tagged orders from the "normal" view below:</div>' +
    presentTags.map(id => `
      <label class="tag-cb-row">
        <input type="checkbox" class="tag-cb" value="${id}">
        <span class="tag-dot" style="background:${esc(tagCatalog[id].color)}"></span>
        ${esc(tagCatalog[id].name)}
      </label>`).join('')
  : '<div style="font-size:12px;color:var(--muted);">No tags found on currently-open orders.</div>';

let normalChart;
function recomputeNormal() {
  const excluded = new Set(Array.from(document.querySelectorAll('.tag-cb:checked')).map(el => parseInt(el.value, 10)));
  const normalOrders = orderDetail.filter(o => !(o.tagIds || []).some(id => excluded.has(id)));
  const counts = {};
  labels.forEach(l => counts[l] = 0);
  const breaches = [];
  normalOrders.forEach(o => {
    counts[bucketForHours(o.normalHoursOpen)]++;
    if (o.normalHoursOpen >= DATA.sla_hours) breaches.push(o);
  });
  breaches.sort((a, b) => b.normalHoursOpen - a.normalHoursOpen);
  const total = normalOrders.length || 1;
  const pct = labels.map(l => Math.round(1000 * counts[l] / total) / 10);

  document.getElementById('normalMeta').textContent = normalOrders.length
    ? `${normalOrders.length} normal orders analyzed (elapsed time skips full weekend days)`
    : 'No normal orders to analyze (all open orders excluded, or there are none).';

  if (normalChart) normalChart.destroy();
  normalChart = new Chart(document.getElementById('agingNormal'), {
    type: 'bar',
    data: { labels, datasets: [{ label: '% of normal open orders', data: pct, backgroundColor: barColors() }] },
    options: { indexAxis: 'y', plugins: { legend: { display: false } }, scales: { x: { ticks: { callback: v => v + '%' } } } }
  });

  document.getElementById('kpiNormalBreach').textContent = breaches.length;

  const normalBreachBody = document.querySelector('#normalBreachTable tbody');
  normalBreachBody.innerHTML = breaches.map(o =>
    `<tr><td>${esc(o.orderNumber)}</td><td>${o.orderDate ? esc(new Date(o.orderDate).toLocaleString()) : ''}</td><td>${o.normalHoursOpen}</td>` +
    `<td><span class="tag ${locTagClass(o.location)}">${esc(o.location)}</span></td><td>${esc(o.carrier)}</td><td>${esc(o.sku)}</td><td>${esc(o.status)}</td></tr>`
  ).join('');
}
document.querySelectorAll('.tag-cb').forEach(cb => cb.addEventListener('change', recomputeNormal));
recomputeNormal();

// Trend
const trend = DATA.history.trend;
const trendDatasets = [{ label: 'Overall avg fill time (h)', data: trend.avg_fill_hours, borderColor: '#5b21b6', backgroundColor: '#5b21b6', tension: 0.2 }];
Object.keys(trend.by_location).forEach((loc, i) => {
  trendDatasets.push({ label: loc + ' avg fill time (h)', data: trend.by_location[loc], borderColor: i===0 ? '#dc2626' : '#059669', tension: 0.2 });
});
new Chart(document.getElementById('trendChart'), {
  type: 'line',
  data: { labels: trend.weeks, datasets: trendDatasets },
  options: { plugins: { legend: { position: 'bottom' } }, scales: { y: { title: { display:true, text:'hours' } } } }
});

// Carrier breakdown
const carriers = Object.entries(DATA.history.carrier_breakdown);
new Chart(document.getElementById('carrierChart'), {
  type: 'bar',
  data: {
    labels: carriers.map(c => c[0]),
    datasets: [{ label: 'Breach %', data: carriers.map(c => c[1].count ? Math.round(1000*c[1].breach/c[1].count)/10 : 0), backgroundColor: '#5b21b6' }]
  },
  options: { plugins: { legend: { display:false } }, scales: { y: { ticks: { callback: v => v + '%' } } } }
});

// SKU table
const skuBody = document.querySelector('#skuTable tbody');
skuBody.innerHTML = DATA.history.top_sku_breaches.map(s =>
  `<tr><td>${esc(s.sku)}</td><td>${s.count}</td><td>${s.breach}</td><td>${s.count ? Math.round(1000*s.breach/s.count)/10 : 0}%</td></tr>`
).join('');

// Breach table
const breachBody = document.querySelector('#breachTable tbody');
breachBody.innerHTML = snap.breach_list.map(o =>
  `<tr><td>${esc(o.orderNumber)}</td><td>${o.orderDate ? esc(new Date(o.orderDate).toLocaleString()) : ''}</td><td>${o.hoursOpen}</td>` +
  `<td><span class="tag ${locTagClass(o.location)}">${esc(o.location)}</span></td><td>${esc(o.carrier)}</td><td>${esc(o.sku)}</td><td>${esc(o.status)}</td></tr>`
).join('');
</script>
</body>
</html>
"""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=5058)
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()

    def wait_and_open_browser():
        deadline = time.time() + 30
        while time.time() < deadline:
            try:
                with socket.create_connection((args.host, args.port), timeout=0.5):
                    break
            except OSError:
                time.sleep(0.2)
        webbrowser.open(f"http://{args.host}:{args.port}")

    Thread(target=wait_and_open_browser, daemon=True).start()
    app.run(host=args.host, port=args.port, debug=False)


if __name__ == "__main__":
    main()
