# Compass → Shopify Inventory Converter

A single-page tool for converting Compass inventory reports into upload-ready CSVs for Shopify's inventory import.

## Usage

1. Open the tool in your browser
2. Confirm the **Shopify location name** is correct — it defaults to `8 Whittemore Farm Rd`
3. Choose your quantity mode (see below)
4. Drop in your Compass CSV export or click to browse
5. Click **Download Shopify CSV** — the file is ready to upload directly to Shopify

## Quantity modes

- **On Hand** — sets Shopify inventory to the current on-hand count from Compass (recommended for full syncs)
- **Available** — uses the available quantity (on hand minus committed), useful if you want to exclude reserved stock

## Column mapping

| Compass | Shopify |
|---|---|
| Item Number | SKU, Handle |
| Item Description | Title |
| On Hand | On hand (new) |
| Incoming | Incoming (not editable) |
| Committed | Committed (not editable) |
| Available | Available (not editable) |

Option fields (Option1/2/3), HS Code, and COO are left blank so Shopify ignores them on import.

## Uploading to Shopify

In your Shopify admin: **Products → Inventory → Import** — upload the downloaded CSV. Make sure the location name in the file matches your store exactly or Shopify will reject the rows.

## Notes

- All processing happens in the browser — no data is uploaded anywhere
- Requires a CSV export from Compass with at minimum `Item Number`, `Item Description`, and `On Hand` columns
