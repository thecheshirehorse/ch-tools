# Mailing List Cleaner

A browser-based tool that cleans a mailing list CSV export — removing blanks, duplicates, employee/internal addresses, and PO Box noise — before it goes out to a mailing vendor.

Part of the [ch-tools](https://github.com/caitlinsc/ch-tools) monorepo.

## How to use

1. Open the tool (`index.html`) and choose your mailing list CSV. Expected columns: `Customer Number`, `Customer Name`, `Address 1`, `Address 2`, `Email Address` (column names are matched case-insensitively).
2. Click **Process**. You'll see the starting and final row counts plus a preview of the first 100 rows.
3. Click **Download Cleaned CSV** to save the result.

## What it does

In order:

1. **Remove blank rows** — any row where every field is empty.
2. **Remove exact duplicate rows** — rows that are identical across every column.
3. **Remove rows by Address 1 content** — drops any row whose Address 1 contains a configured keyword (`PARKING`, `LOADING DOCK`, `DO NOT DELIVER`, `ATTN: DO NOT DELIVER`) or street pattern (`ALLEY`, `CTY RD`, `COUNTY ROAD`).
4. **Remove employee/internal-tagged rows** — drops rows whose Customer Name contains `EMPLOYEE` or `DOOR TAG`.
5. **Strip name tags** — removes `(O-C)` from customer names wherever it appears.
6. **Promote Address 2 → Address 1** when Address 1 is blank but Address 2 has a value.
7. **Clear Address 2 for PO Boxes** — if Address 1 matches a PO Box pattern, Address 2 is blanked out (avoids the apartment/suite line from leftover store-pickup or secondary address data confusing a PO Box mailing).
8. **Deduplicate by Customer Number** — when the same Customer Number appears more than once, the row with an email address wins over one without. Rows with no Customer Number at all are kept as-is (not deduplicated against each other).

## Configuration

The keyword/pattern lists live near the top of `index.html` as plain JS arrays: `ADDRESS1_REMOVE_KEYWORDS`, `ADDRESS1_REMOVE_STREETS`, `NAME_TAG_REMOVE`, `NAME_TAG_STRIP`, `PO_BOX_PATTERNS`. Edit them directly in the file if the filtering rules need to change.

## Notes

- CSV parsing and export use [PapaParse](https://www.papaparse.com/), so quoted fields, embedded commas, and embedded newlines are handled correctly — this isn't a naive comma-split parser.
- Everything runs client-side in the browser. No data is uploaded anywhere.
