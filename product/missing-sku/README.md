# Missing SKU

A simple web tool to compare a SKU list exported from IMU against one exported from Salesforce, and identify SKUs that are present in IMU but missing from Salesforce.

Part of the [ch-tools](https://github.com/caitlinsc/ch-tools) monorepo.

## How to Use

1. Open the tool from the [ch-tools dashboard](https://github.com/caitlinsc/ch-tools), or open `index.html` directly.
2. Upload the IMU SKU file (Excel — `.xls` or `.xlsx`).
3. Upload the Salesforce SKU file (CSV).
4. Adjust matching options if needed (see below).
5. Click **Compare Lists**.
6. Review the missing SKUs in the table.
7. Optionally click **Download Missing SKUs CSV** to save the results.

## File Requirements

Both files should have a column with a header containing "SKU". The tool scans the first 10 rows for a SKU header, so files with a title row above the headers (common in Salesforce report exports) work fine. If no SKU header is found, the tool falls back to the first column and shows a warning so you can sanity-check.

- **IMU file:** Excel (`.xls` or `.xlsx`)
- **Salesforce file:** CSV (`.csv`)

## Matching Options

By default the comparison is forgiving in the ways that usually matter:

- **Case-insensitive** (on by default) — `ABC-123` and `abc-123` are treated as the same SKU.
- **Trim whitespace** (on by default) — leading and trailing spaces are ignored.
- **Ignore leading zeros** (off by default) — turn this on if one system zero-pads SKUs and the other doesn't (e.g. `00123` vs `123`).

## Features

- Detects the SKU column automatically and shows which column was used for each file.
- Shows row counts for both files plus a count of missing SKUs.
- De-duplicates the missing list.
- Handles long numeric SKUs without scientific-notation corruption.
- Handles CSV fields with quoted commas correctly.

## Requirements

A modern web browser with JavaScript enabled. No install or backend — everything runs in the browser, and no data is uploaded anywhere.
