# Store Address Scrubber

A local browser tool for finding and removing store/warehouse addresses that ShipStation incorrectly saves to customer records in Salesforce Commerce Cloud (SFCC).

## The Problem

A ShipStation integration bug causes store pickup addresses to get written into customer address books as if they were the customer's own address. Over time this pollutes thousands of customer records with your store locations, which can cause issues with shipping, order routing, and customer communications.

## What This Tool Does

Drop in your SFCC customer XML export (or a CSV) along with your ShipStation open orders export, and the tool will:

1. Parse the file (handling namespaced SFCC XML, emoji/surrogate characters, and large files)
2. Require an open orders CSV from ShipStation to protect customers with active orders
3. Scan every address node for matches against your store addresses
4. Skip any customer whose name appears in the open orders list
5. Show you exactly which records matched — and which were skipped — so you can verify before committing
6. Export a **clean addresses XML** containing only affected customers with their store addresses removed, ready for SFCC merge-mode import

The clean file is surgical: it only contains the address books of affected customers, with store addresses stripped out. No other customer data is modified.

## Setup

No setup required. It's a single HTML file with no dependencies.

1. Open `index.html` in this folder, or via the [ch-tools dashboard](https://github.com/caitlinsc/ch-tools)
2. Drop your file in

Everything runs locally in your browser. No data is sent anywhere.

## Pre-Configured Store Addresses

The tool comes pre-loaded with:

- **8 Whittemore Farm Road / Rd** (NH Store — Swanzey, NH 03446)
- **402 Geyser Rd / Road** (NY Store — Saratoga Springs, NY 12866)

You can add or remove addresses in the config step before scanning.

## Open Orders Protection

Before scanning, you must upload a ShipStation open orders CSV export. The tool primarily matches on the **Recipient** column, with `Name` or `Customer Name` used as a fallback if Recipient is missing in some matching paths. Any customer with an open order is skipped entirely — their addresses will not be touched, even if they have a store address on file.

This prevents breaking any shipments that are currently in progress.

## How to Import the Clean File into SFCC

1. Go to **Business Manager → Administration → Site Development → Import & Export**
2. Upload the generated `_clean_addresses.xml` file
3. Select **Customers** as the import type

---

### ⚠️ USE MERGE MODE ⚠️

### Always set the import mode to MERGE.

### NEVER use Delete mode — it will delete entire customer records, not just addresses.

### NEVER use Replace mode — it will wipe other customer data.

### MERGE mode overwrites only the address book for the affected customers, leaving everything else (credentials, profiles, order history) untouched.

---

4. Run the import
5. Spot-check a few customer records to confirm store addresses are gone and other addresses remain

## Supported File Formats

- **XML** — SFCC/Salesforce customer exports with `<customer-list>` root and namespaced `<customer>` → `<addresses>` → `<address>` structure. Handles invalid XML character references (emoji surrogate pairs) automatically.
- **CSV** — Flat customer/order exports. The tool auto-detects address columns and lets you choose which fields to match against. CSV mode clears matched address fields in the export.

## File Structure

```
index.html   — The tool (standalone, no dependencies)
README.md    — This file
```
