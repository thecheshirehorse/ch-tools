# Vendor Order Planner

Turns an Eagle vendor export into a suggested reorder sheet. Upload the export, review the calculated quantities, and export an `.xlsx` order sheet ready to post.

Part of the [ch-tools](https://github.com/caitlinsc/ch-tools) monorepo.

## How it works

1. **Drop in an Eagle vendor export** (`.xls` or `.xlsx`). The tool expects columns named `SKU`, `Description`, `QOH`, `Store Closeout`, `Discontinued`, `Order Multiple`, `Posting Quantity`, `Primary Vendor`, and one column per month of sales history (e.g. `Jan 25`, `Feb 26`).

2. **Always-applied filters** remove:
   - `Store Closeout = Y`
   - `Discontinued = Y`
   - Any SKU starting with `ZZ`

   These aren't optional — they're stripped before anything else runs.

3. **Suggested quantity formula:**
   ```
   avg monthly sales (over the detected month columns) − QOH = amount needed
   ```
   If the amount needed is positive, it's rounded up to a multiple of `Order Multiple` (when **Round up to Order Multiple** is checked) or just rounded up to a whole unit otherwise. Items with zero average sales, or with QOH already covering a month of average sales, get a Post Qty of 0 and are skipped.

4. **Two adjustable options:**
   - **Exclude current month from average** (on by default) — the in-progress month is usually a partial month, so it's left out of the average unless unchecked.
   - **Round up to Order Multiple** (on by default) — rounds the suggested quantity up to the vendor's case/pack size instead of to a single unit.

5. **Review the results** — items needing reorder appear in the **To Order** table with Description, SKU, Mfg Part #, UPC, QOH, average monthly sales, order multiple, and suggested Post Qty. Everything else lands in the collapsible **Skipped** table with a reason (no recent sales, or already well-stocked).

6. **Export** generates a styled `.xlsx` containing only the SKUs that need reordering, with the original columns intact, Posting Quantity filled in, and a new Avg/Mo column inserted next to it. Header and Post Qty cells are colored for quick scanning, and the header row is frozen. All quantities are editable after export — this is a starting point, not a final order.

## Notes

- Month columns are detected by header pattern (`Mon YY`, e.g. `Mar 26`) and sorted oldest → newest automatically — no manual mapping needed.
- The vendor number shown at the top comes from the `Primary Vendor` value on the first data row, purely as a sanity-check label.
- Nothing leaves the browser; the file is parsed and processed client-side.

## Built with

[SheetJS (xlsx)](https://github.com/SheetJS/sheetjs) for reading the Eagle export and writing the styled output workbook.
