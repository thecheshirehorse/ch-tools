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

Enter your ShipStation V1 API key and secret, your SLA in hours (default 24),
and how many weeks of history to analyze (default 52). **Credentials are held
in memory for this run only and are never written to disk** — same as the
ShipStation Image Tool.

### Step 2: Fetch

The tool pulls:
- **Open orders** (`awaiting_shipment`, `on_hold`, `pending_fulfillment`) — the
  current aging snapshot, same buckets as ShipStation's built-in "Open Order
  Aging" report (`<1`, `1-2`, `2-4`, `4-8`, `8-24`, `24-36`, `36-48`, `48-72`,
  `72-96`, `96+` hours).
- **Shipped orders** for the trailing N weeks — used to compute historical
  fill-time trend (order date → ship date), split by week.
- **Your account's ShipStation tags** (name + color) — embedded in the
  dashboard so you can filter by tag interactively after the fact (see below),
  without needing to decide upfront which tags matter.

Both are split by warehouse location (Swanzey / Saratoga, or whatever your
`/warehouses` are named), so the dashboard shows overall and per-location
views.

Requests are throttled to ~37/minute to stay under ShipStation's 40 req/min
cap, so a full year (52 weeks) pull for a few thousand orders/month takes a
few minutes — a progress bar shows what's happening.

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
orders takes ~1.6s due to rate limiting. Reduce the "History (weeks)" field
if you just want a faster look.

## One-Click Weekly Report

`weekly_report.py` is a one-click companion to the interactive tool, meant
for a coworker to run without needing a ShipStation API key or the browser
login flow. It reuses the same fetch/build logic, regenerates
`fulfillment_dashboard.html`, and opens it — ready to attach to an email
and send from whatever email client is already logged in.

Since this is meant to run weekly, its history window defaults to **1 week**
in `config.json` (vs. the interactive tool's 52-week default) — each report
only covers the shipped-order activity since the last one, not a rolling
year every time.

**No email credentials are ever stored.** The only thing saved to disk is
the ShipStation API key/secret (needed so the fetch can run without
someone typing it in each time) — nothing that could send mail or access
anything beyond ShipStation order data.

### One-time setup

1. Run the interactive tool (`start_dashboard_tool.bat`) at least once
   first, so its `.venv` and dependencies already exist.
2. Copy `config.example.json` to `config.json` (already gitignored — never
   commit it) and fill in your ShipStation V1 API key/secret.
3. Double-click `run_weekly_report.bat` to test it. It fetches fresh data,
   regenerates `fulfillment_dashboard.html`, and opens it in your browser.

### Weekly use

Whoever's covering it double-clicks `run_weekly_report.bat`, waits for it
to finish (progress prints in the console window), and attaches the
dashboard that opens to an email themselves.

## Auto-Published Version (GitHub Actions)

There's also a fully automated path that needs no one to run anything
locally: `.github/workflows/shipstation-weekly-report.yml` runs on a
schedule (Sunday nights) and on-demand (the Actions tab's "Run workflow"
button), fetches the same data, and commits the result as
`weekly_dashboard.html` — which shows up as **"ShipStation Weekly Report
(Auto)"** on the ch-tools dashboard, viewable directly with no
download/attach step.

This only works because the credential moves from a local file to a
**GitHub Actions secret** — encrypted at rest, never exposed in the page
itself (unlike a browser-side approach, which isn't possible anyway since
GitHub Pages is fully static and ShipStation's API doesn't allow
cross-origin browser requests).

### One-time setup

1. In the repo on GitHub: **Settings → Secrets and variables → Actions →
   New repository secret**. Add two secrets:
   - `SHIPSTATION_API_KEY`
   - `SHIPSTATION_API_SECRET`

   (Enter these directly on GitHub's site — never paste real credentials
   into a chat/AI tool.)
2. That's it. The workflow will run on its next scheduled trigger, or
   manually via **Actions → ShipStation weekly report → Run workflow**.

### Notes

- The workflow writes an ephemeral `config.json` from the secrets, runs
  `weekly_report.py` exactly as it runs locally, then deletes that file
  before finishing — nothing from the secrets ever gets committed.
- `weekly_dashboard.html` is a separate, deliberately-named file from the
  gitignored `fulfillment_dashboard.html` used by the local tools — this
  one *is* meant to be committed automatically every week.
- The existing "Encrypt and deploy to Pages" workflow already re-runs on
  every push to `master`, so once this workflow commits, the site
  redeploys with the fresh report automatically — no extra wiring needed.
- Cron schedules are UTC and don't follow daylight saving time, so the
  actual local time drifts by an hour between EDT and EST.
