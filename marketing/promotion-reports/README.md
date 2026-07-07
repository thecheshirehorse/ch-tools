# Promotion Ledger

A single-file dashboard for tracking Salesforce B2C Commerce promotion exports and comparing the same campaign year over year — without the averaging bug.

## Why this exists

The Promotions dashboard export gives you per-promotion rows, but any "total" row or year-over-year rollup built by averaging `std_revenue_per_order`, `units_per_order`, or `order_conversion_rate` across rows is wrong whenever order volume is uneven between rows. This tool ignores those columns entirely and recalculates:

- **Revenue Per Order** = Σ Order Net ÷ Σ Orders
- **Units Per Order** = Σ Units ÷ Σ Orders
- **Conversion Rate** = Σ Orders ÷ Σ Visits

always from the summed raw counts, whether that's rolling up sub-promotions within one campaign, or comparing one campaign across years.

## Running it

No build step, no server — open `index.html` directly in a browser. This holds revenue and campaign data, so it's kept off GitHub Pages: `ch-tools` is a public repo, and Pages would serve this file at a public URL even without a link from the dashboard. Run it locally only.

## Using it

1. **Import** — paste the export from the Promotions dashboard (tab- or comma-separated both work), or upload the file directly. Click **Parse export**, uncheck any rows you don't want, then **Add row(s) to ledger**. This jumps you straight to the Ledger tab on the campaign you just added.
   - If a Promotion ID or Campaign ID doesn't start with a 4-digit year (e.g. `2026 - 4th of July Sale`), set a fallback year before confirming.
   - Re-importing the same promotion (same Promotion ID + Site) updates it in place rather than duplicating it — safe to re-paste a corrected export.
2. **Ledger** — every recurring campaign shows up as a card with its latest year's Revenue Per Order and the year-over-year change. Click a card to see the full year-by-year table and charts. The table's columns are ordered to match the "SF Analytics - Promotions" Google Sheet's per-campaign tabs, so you can read a row and type it straight into the matching sheet.
3. **All Rows** — every individual row you've imported, with a delete button for anything added by mistake.

All data lives in this browser's local storage — it isn't backed up anywhere. Since the Google Sheet is the durable record, transcribe each month's numbers there after importing.

## A note on "same promotion"

Campaigns are matched across years by the text of `campaign_id` with the leading year stripped — so `2025 - 4th of July Sale` and `2026 - 4th of July Sale` are treated as the same recurring promotion. If a campaign's name changes slightly year to year, it'll show up as a separate card; you can still compare it manually via the All Rows table.
