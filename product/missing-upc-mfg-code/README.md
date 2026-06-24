# Missing UPC & MFG Code Tool

A browser-based tool for filling in missing UPCs and Manufacturer Part Numbers (MFG codes) in a Salesforce export, and correcting any existing values that don't match the Compass master file.

Part of the [ch-tools](https://github.com/caitlinsc/ch-tools) monorepo. Run it from the dashboard, or open `product/missing-upc-mfg-code/index.html` directly.

Everything runs in the browser. No data is uploaded anywhere.

## How to use it

1. **Upload your Salesforce export CSV** — the file with UPCs and/or MFG codes to check. The tool auto-detects columns by header name:
   - **SKU:** `SKU`, `Item Number`, `Item #`, `Product ID`, `Style Number`, `Part Number`, `ID`, etc.
   - **UPC:** `UPC`, `UPC Code`, `Barcode`, `GTIN`, `GTIN-12`, `GTIN-13`, etc.
   - **MFG code:** `MFG`, `MFG Code`, `MPN`, `Manufacturer Part Number`, `Vendor Part`, `Part Number`, etc.

   Cells that are blank, `0`, `N/A`, or `NONE` count as missing.

2. **Upload the Compass master CSV** — this is treated as the source of truth. The tool builds a SKU → UPC and SKU → MFG code lookup from it.

3. **Fill & correct from Compass** — for every SKU match:
   - A **missing** UPC or MFG code gets filled in from Compass.
   - An **existing** UPC or MFG code that doesn't match Compass gets **overwritten** with the Compass value.
   - A value that already matches Compass is left untouched.

   The preview table highlights both kinds of changes, with separate colors for filled vs. corrected cells, and rows still missing data after the pass are flagged.

4. **Download your results** — up to two files:
   - **Enriched CSV** — the full file with all fills and corrections applied.
   - **Correction log** — only appears if any existing values were overwritten. A CSV of `SKU, Field, Old Value, New Value` for every correction, so you can spot-check what changed before trusting the output.

UPCs are validated as 8–14 digit numeric strings — junk values like `3650F` in Compass are ignored and never used to fill or correct anything. MFG codes are accepted as-is (no format restriction). When the same SKU appears multiple times in Compass, the first valid value wins.

## ⚠️ Excel will silently destroy your data

**Do not use Excel to view, edit, or re-save any CSV in this workflow.** It corrupts SKUs in ways you won't notice until after you've uploaded bad data to Salesforce:

- Leading zeros are stripped (`0001476` → `1476`)
- Long numeric SKUs become floats with garbage trailing zeros
- SKUs containing `E` are interpreted as scientific notation (`70781555E104` becomes a 105-digit number)

**Use Google Sheets instead.** It treats CSV cells as text by default and round-trips safely.

If you must use Excel — e.g., the Compass download is `.xlsx` only — import via **Data → From Text/CSV** and explicitly mark the SKU column as **Text** before loading. Double-clicking a CSV will corrupt it before you can do anything.

## Built with

[PapaParse](https://www.papaparse.com/) for CSV parsing. Single-file vanilla JS — no build step.
