# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

A collection of internal tools for **Cheshire Horse** (an equestrian retailer with two stores: Store 3 in Swanzey NH and Store 5 in Saratoga NY). The root `index.html` is a searchable dashboard that links to all tools. There is no build step and no shared framework — each tool is self-contained.

## Tool types and patterns

**HTML tools** — Static single-file browser tools in `<category>/<tool-name>/index.html`. All logic is inline JS; no server required. Users open them directly in a browser or via GitHub Pages.

**Python tools** — Local Flask apps that spin up on localhost. Each has a `.bat` double-click launcher for non-technical users on Windows. Dependencies are in `requirements.txt` local to the tool.

**CLI scripts** — Standalone Python scripts invoked from the command line with file arguments.

## Running the Python tools

**Rewards Account Creator** (`customers/rewards-customer-upload/`)
```
# Windows: double-click start_eagle_import.bat
python app.py         # opens http://localhost:5000
```
Persistent state lives in `cheshire_eagle_data.json` (same folder). This file contains real customer PII once used — do not commit it with real data.

**RPH Review** (`product/rph-review/`)
```
# One-time setup
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

# Weekly run (drop files in data/ first)
python rph_review.py data/RPH_MM-DD-YY.xls data/cheshire-enrichment.xlsx
# opens http://localhost:5057
```
Windows: double-click `start_rph_review.bat` (handles venv and deps automatically). Class-rule decisions persist to `rules.db` (SQLite) and shrink the next week's manual review queue.

**Google Feed Refresh** (`product/google-feed-refresh/`)
```
python build_feed.py <catalog.xml> <pricebook.xml> [output.tsv]
```

## External systems (context for tool logic)

| System | Role |
|--------|------|
| Epicor Eagle POS | Point-of-sale; customer records imported via CSV |
| Salesforce Commerce Cloud (SFCC) | E-commerce platform (cheshirehorse.com) |
| Compass | Inventory/merchandising master |
| Google Merchant Center | Google Shopping feed target |
| ShipStation | Order fulfillment |
| PSM (Pet Store Marketer) | Loyalty marketing sync |
| Astro Loyalty | Loyalty redemptions |

## RPH classification rule cascade

The RPH Review tool applies these rules in order — first match wins:
1. Drop · Closeout — `Store Closeout? = Y`
2. Drop · Coupon — Department H1 or H2
3. Drop · Delivery — Department 80
4. Auto · C20 — Class code C20 (Cheshire Special Orders)
5. Class rule — user-saved "always upload / always skip" (persisted in `rules.db`)
6. Manual review — everything else

## Rewards customer number format

| Store | Prefix | Example |
|-------|--------|---------|
| Store 3 (Swanzey NH) | `*9` | `*98051` |
| Store 5 (Saratoga NY) | `*5` | `*58085` |

Eagle requires dates as `mm/dd/yy` (2-digit year), names uppercased, sort name as `QQ` + last name (max 10 chars), zip padded to 5 digits.

## Adding a tool to the dashboard

Edit the `TOOLS` array in the root `index.html`. Each entry needs: `name`, `icon`, `desc`, `type` (`"html"`, `"python"`, or `"terminal"`), `category` (`"product"`, `"customers"`, `"marketing"`, or `"other"`), and either `url` (for HTML tools) or `cmd` + `note` (for Python/bat tools). Tools without a `url` or `cmd` and with `private: true` show a "Private repo" placeholder card.

## Data files

Weekly inputs (RPH exports, enrichment XLSXs, catalog XMLs) are gitignored and must not be committed — they contain real vendor and inventory data. The `data/` subdirectory inside `product/rph-review/` is the expected drop location.
