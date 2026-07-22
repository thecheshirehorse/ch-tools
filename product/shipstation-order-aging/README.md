# ShipStation Fulfillment Dashboard Tool

A local web app that pulls order and fulfillment data from ShipStation and generates
a self-contained, static HTML dashboard — ready to push to your GitHub tools
dashboard. Re-run it any time you want a fresh snapshot.

## Requirements

```bash
pip install flask requests
```

## Quick Start

```bash
python shipstation_fulfillment_dashboard.py
```

Open **http://localhost:5058** in your browser (it opens automatically).

| Flag     | Default     | Description       |
|----------|-------------|-------------------|
| `--port` | 5058        | Port to run on    |
| `--host` | 127.0.0.1   | Host to bind to   |

## How It Works

### Step 1: Login

Enter your ShipStation V1 API key and secret, your SLA in hours (default 48),
and how many months of history to analyze (default 12). **Credentials are held
in memory for this run only and are never written to disk** — same as the
ShipStation Image Tool.

### Step 2: Fetch

The tool pulls:
- **Open orders** (`awaiting_shipment`, `on_hold`, `pending_fulfillment`) — the
  current aging snapshot, same buckets as ShipStation's built-in "Open Order
  Aging" report (`<1`, `1-2`, `2-4`, `4-8`, `8-24`, `24-36`, `36-48`, `48-72`,
  `72-96`, `96+` hours).
- **Shipped orders** for the trailing N months — used to compute historical
  fill-time trend (order date → ship date), split by week.
- **Your account's ShipStation tags** (name + color) — embedded in the
  dashboard so you can filter by tag interactively after the fact (see below),
  without needing to decide upfront which tags matter.

Both are split by warehouse location (Swanzey / Saratoga, or whatever your
`/warehouses` are named), so the dashboard shows overall and per-location
views.

Requests are throttled to ~37/minute to stay under ShipStation's 40 req/min
cap, so a full 12-month pull for a few thousand orders/month takes a few
minutes — a progress bar shows what's happening.

### Step 3: Download

Once done, click the download link to save `fulfillment_dashboard.html`.
Commit that file to your GitHub tools dashboard repo — it's fully
self-contained (data and Chart.js are both baked directly into the file), no
backend, CDN, or live API calls needed to view it.

## What's in the Dashboard

- **KPI row** — open orders, orders currently past SLA, breach %, latest
  week's average fill time, and normal orders past SLA (weekend-adjusted)
- **Current aging** — overall bar chart, plus a per-location chart (dropdown
  to switch between Swanzey / Saratoga)
- **Normal Order Aging (weekend-adjusted)** — same aging buckets, but lets
  you check off tags *inside the dashboard itself* (ISPU, problem, backorder,
  etc.) to exclude those orders live — no need to decide upfront or
  regenerate to try a different combination. Elapsed time is measured in
  business hours, so a Friday order still sitting Monday morning isn't
  counted as a weekend of delay. Includes its own breach list and KPI tile,
  both of which update as you check/uncheck tags. Only tags that actually
  appear on a currently-open order are shown as options.
- **Weekly fill-time trend** — line chart, overall + by location, over the
  requested history window
- **Carrier breakdown** — SLA breach rate by carrier
- **Top SKUs by breach count** — which SKUs show up most often in shipments
  that missed SLA
- **Breach list** — every currently open order past SLA, sorted oldest first,
  with location/carrier/SKU/status

## Notes

- Uses the Order resource's own `orderDate`/`shipDate` fields (fill time =
  shipDate − orderDate), rather than a separate `/shipments` call — this
  keeps the historical pull to a single paginated endpoint.
- If a warehouse isn't returned by `/warehouses` or an order has no
  `advancedOptions.warehouseId`, it's grouped under "Unassigned."
- Re-running the tool regenerates `fulfillment_dashboard.html` from scratch
  with fresh data — there's no incremental/progress file like the image
  tool, since this is a read-only reporting pull, not something you're
  working through item by item.
- "Weekend-adjusted" hours treat Saturday and Sunday as fully closed (no
  hours counted), regardless of order volume on those days. Weekday hours
  count in full — there's no finer-grained store-hours model.

## Troubleshooting

**"ShipStation API error"** — usually an invalid/expired API key or secret.
Regenerate in ShipStation → Settings → Account → API Settings.

**Takes a long time** — expected for large history windows; each page of 500
orders takes ~1.6s due to rate limiting. Reduce the "History (months)" field
if you just want a faster look.
