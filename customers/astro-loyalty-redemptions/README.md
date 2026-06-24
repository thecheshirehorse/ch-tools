# Astro Loyalty — Redemption Entry

A manual data-entry tool for logging Astro Loyalty offer redemptions in-store, then exporting them in the format Astro expects for upload. Works as a standalone local app — your working data is a JSON file you save and reopen, not something stored in the cloud.

Part of the [ch-tools](https://github.com/caitlinsc/ch-tools) monorepo.

## How it works

1. **Open or create a data file** — on load, you're prompted to open an existing `.json` backup or start fresh. If your browser supports the File System Access API (Chrome/Edge), **Save** writes directly back to that file; otherwise **Save as…** downloads a new copy each time (Firefox/Safari fallback) and you replace your saved copy manually.

2. **Import current offer programs** (optional but recommended) — drop in a vendor offers export (`.xls`, `.xlsx`, `.csv`, or `.tsv`). The tool reads `Astro Program ID`, `Manufacturer`, `Program Title`, `Program Description`, and start/end dates, and populates the Program dropdown on the entry form. Re-importing shows you how many programs were added, updated, or removed compared to what you had.

3. **Log a redemption** — fill in the form: Program (from the imported list, which auto-fills manufacturer), Customer ID, name, address, transaction ID/date, UPC, product description (with autocomplete suggestions based on past entries for the selected program), and quantity/rebate amount. UPCs under 12 digits are auto-padded with leading zeros.

4. **Review and manage entries** — the table below the form lists everything entered, filterable by month. Use **Clear month** (or **Clear all**) to delete entries you no longer need — this is permanent, with a confirmation prompt.

5. **Export for Astro** — **Download CSV** or **Download XLSX** export the filtered (or all) rows in Astro's expected column order. Filenames follow the pattern `ASTRO_OFFER_REDEMPTION_MM_YYYY.csv` (or `_ALL_MM_YYYY` if no month filter is applied).

## Export columns

```
Astro Program ID, CustomerID, Customer First Name, Customer Last Name,
Customer Address, Customer City, Customer State, Customer Zip,
Customer Email, Customer Phone, TransactionID, Transaction Date,
UPC, Product Description, Quantity Free/Rebate Amount
```

## Notes

- All data lives in the JSON file you open/save — there's no server and no shared database. Back up that file the way you'd back up any working spreadsheet.
- The tool warns you with a browser "unsaved changes" prompt if you try to close the tab with unsaved entries.
- Everything runs client-side; nothing is uploaded anywhere except the file you explicitly choose to save.

## Built with

[PapaParse](https://www.papaparse.com/) for CSV parsing/export, [SheetJS (xlsx)](https://github.com/SheetJS/sheetjs) for Excel import/export, and the browser's native File System Access API for local file save/load where supported.
