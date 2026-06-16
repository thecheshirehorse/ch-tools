# Missing UPC & MFG Code Tool

A browser-based tool for filling in missing UPCs and Manufacturer Part Numbers (MPNs) in product CSVs and producing Salesforce-ready upload files.

**Live tool:** [https://caitlinsc.github.io/missing-upc-mfg-code/](https://caitlinsc.github.io/missing-upc-mfg-code/)

Everything runs in the browser. No data is uploaded anywhere.

## How to use it

1. **Upload your main CSV** — the file with missing UPCs and/or MPN values. The tool auto-detects columns by header name:
   - **SKU:** `SKU`, `Item Number`, `Item #`, `Product ID`, `Style Number`, `Part Number`, `ID`, etc.
   - **UPC:** `UPC`, `UPC Code`, `Barcode`, `GTIN`, `GTIN-12`, `GTIN-13`, etc.
   - **MPN:** `MFG`, `MFG Code`, `MPN`, `Manufacturer Part Number`, `Vendor Part`, `Part Number`, etc.

   Cells that are blank, `0`, `N/A`, or `NONE` count as missing.

2. **(Optional) Filter** — preview rows that already have UPCs, or download just the rows still needing them.

3. **Fill from IMU** — upload the IMU master CSV (Compass export works as-is). The tool builds a SKU → UPC and SKU → MPN lookup, fills in both missing fields in one pass, and shows a preview. Rows still missing either value are highlighted.

4. **Download Salesforce-ready files** — three download options:
   - **SF UPC file** — two-column CSV (`ID,UPC`) of rows where a UPC was filled.
   - **SF MFG file** — two-column CSV (`ID,ManufacturerPartNumber`) of rows where an MPN was filled.
   - **Full enriched CSV** — the complete file with all filled values included.

   If your Salesforce import expects different field names, rename the headers before uploading.

UPCs are validated as 8–14 digit numeric strings — junk values like `3650F` are ignored. MPN values are accepted as-is (no format restriction). When the same SKU appears multiple times in IMU, the first valid value wins.

## ⚠️ Excel will silently destroy your data

**Do not use Excel to view, edit, or re-save any CSV in this workflow.** It corrupts SKUs in ways you won't notice until after you've uploaded bad data to Salesforce:

- Leading zeros are stripped (`0001476` → `1476`)
- Long numeric SKUs become floats with garbage trailing zeros
- SKUs containing `E` are interpreted as scientific notation (`70781555E104` becomes a 105-digit number)

**Use Google Sheets instead.** It treats CSV cells as text by default and round-trips safely.

If you must use Excel — e.g., the Compass download is `.xlsx` only — import via **Data → From Text/CSV** and explicitly mark the SKU column as **Text** before loading. Double-clicking a CSV will corrupt it before you can do anything.

## Built with

[PapaParse](https://www.papaparse.com/) for CSV parsing. Single-file vanilla JS — no build step.
