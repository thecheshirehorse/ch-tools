# Closeout Cleaner

A browser-based tool that identifies out-of-stock closeout products by matching a Salesforce closeout export against a Compass inventory export. Outputs a CSV of SKUs that need to be disabled in Salesforce.

No server, no install, no API key. Just open the HTML file in any browser.

---

## How to use

**Run this weekly after pulling fresh exports from both systems.**

1. **Export from Salesforce** — run a product export scoped to the closeout category, filtered to online items only. Save as `.csv`.
2. **Export from Compass** — run an inventory export that includes `Item Number` and `Quantity on Hand`. Save as `.xlsx` or `.csv`.
3. **Open `closeout-oos-matcher.html`** in your browser.
4. Drop the SF export into the left box and the Compass export into the right box.
5. Click **Find OOS SKUs**.
6. Review the results, then click **Export SKU list** to download a dated `.csv`.

---

## What it does

- Expands variant SKUs from the SF export (the `variants` column is semicolon-separated; simple products use their `ID` directly)
- Sums `Quantity on Hand` across all stores (Swanzey + Saratoga)
- Flags any SKU with a combined qty of 0 as out of stock
- SKUs not found in Compass are excluded and counted separately — these are typically online-only items not stocked in store

---

## Output

The exported CSV contains three columns:

| Column | Description |
|--------|-------------|
| `SKU` | The variant or simple product SKU to disable |
| `Product Name` | Display name from the SF export |
| `Master ID` | The master product ID (populated for variants; blank for simple products) |

File is named `closeout-oos-YYYY-MM-DD.csv`.

---

## What to do with the output

For each SKU in the export, disable it in Salesforce by:

- Setting **Online**, **Searchable**, and **Searchable if Unavailable** to `No`
- Removing the product from all categories
- Moving it to the **Disabled** category

---

## Expected SF export columns

The tool expects a standard Salesforce product export with at least these columns:

- `ID` — product or master SKU
- `name__default` — product display name
- `variants` — semicolon-separated list of variant SKUs (blank for simple products)

## Expected Compass export columns

- `Item Number` — SKU
- `Quantity on Hand` — current inventory count
- `Store Short Name` — used to identify which location (qty is summed across all)
