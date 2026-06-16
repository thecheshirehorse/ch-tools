# ShipStation Product Image Tool v2

A local web app that automatically matches and assigns product images from your Cheshire Horse website to ShipStation products. The tool runs in two phases: first it auto-matches everything it can by SKU, then it presents only the leftovers for you to handle manually.

## Requirements

```bash
pip install flask requests openpyxl beautifulsoup4
```

## Quick Start

```bash
python shipstation_image_tool.py
```

Open **http://localhost:5050** in your browser.

| Flag     | Default     | Description       |
|----------|-------------|-------------------|
| `--port` | 5050        | Port to run on    |
| `--host` | 127.0.0.1   | Host to bind to   |

## How It Works

### Step 1: Login

Enter your ShipStation V1 API key and secret.

### Step 2: Scan

The tool fetches every product from ShipStation and filters down to those with no `thumbnailUrl`. If you've run the tool before, previously handled products (pushed, skipped, closeout) are excluded automatically thanks to the saved progress file.

### Step 3: Auto-Match (Phase 1)

Click "Start Auto-Match" and the tool runs through every remaining product on its own. For each one, it searches cheshirehorse.com by SKU, follows through to product detail pages, and looks for a matching image. You see a progress bar and live counters while it works.

Three outcomes per product:

- **Exact SKU match** — the image filename matches the ShipStation SKU (e.g. `030336.jpg` or `030336-1.jpg` for SKU `030336`). The tool pushes the image to ShipStation automatically.
- **No images found** — the SKU doesn't exist on the website. The tool marks it as a closeout automatically.
- **Images found, no exact match** — there are product images but the filenames don't match the SKU. The tool queues it for manual review.

### Step 4: Manual Review (Phase 2)

After auto-match finishes, the tool presents only the products that need your help. The counter shows just these remaining items (e.g. "1 / 47" instead of "1 / 23192").

Each product shows:

- **SKU and product name**
- **Search by SKU link** — opens cheshirehorse.com in a dedicated browser window (always reuses the same window, no tab clutter)
- **Image picker** — thumbnails scraped from your site, displayed in a scrollable row with extracted SKU labels
- **Drop zone** — drag an image from your website and it pushes to ShipStation immediately
- **Paste field** — right-click an image → "Copy image address" → paste and click Set

Three actions:

- **Push to ShipStation** — sends the selected image URL
- **Closeout** — flags as discontinued, no image needed
- **Skip** — pass for now, come back later

### Step 5: Done

Summary of how many were auto-pushed, manually pushed, closed out, and skipped. Download the XLSX for a full report.

## Persistence

A `progress.json` file is saved in the same directory as the script. Every action (push, skip, closeout) is written immediately. When you restart the tool:

- Previously handled products are filtered out
- The results screen shows how many were already handled
- You pick up where you left off

Click "Reset Progress" on the results screen to start fresh.

## XLSX Export

Available at every stage. Includes all products missing images with their current status.

| Status   | Color  | Meaning                                   |
|----------|--------|-------------------------------------------|
| Missing  | Amber  | Not yet reviewed                          |
| Pushed   | Green  | Image assigned and pushed to ShipStation  |
| Closeout | Orange | Flagged as closeout, no image needed      |
| Skipped  | Gray   | Passed on for now                         |

## SKU Matching Rules

The tool extracts the filename from each Demandware CDN image URL (e.g. `030336` from `.../images/products/030336.jpg`) and compares it to the ShipStation SKU. An image is considered an exact match if:

- The filename equals the SKU exactly (e.g. `030336.jpg` for SKU `030336`)
- The filename is the SKU plus `-1` (e.g. `030336-1.jpg` for SKU `030336`)

Other suffixes like `-2`, `-3`, `_alt` are not auto-matched. They'll appear in the manual picker for you to choose from.

## Image Scraping

The tool's Python server fetches your website directly (not through the browser), so it isn't blocked by robots.txt or CORS. For each product it:

1. Searches `cheshirehorse.com/search?q={SKU}`
2. Finds product page links in the results
3. Follows through to up to 5 product detail pages
4. Extracts images from `<img>` tags, `og:image` meta, JSON-LD structured data, `data-imgs` attributes, and CSS background images
5. Normalizes all images to 650×650 resolution

## Notes

- ShipStation's API requires a full PUT to update a product. The tool preserves all existing fields and only changes `thumbnailUrl`.
- API requests to ShipStation are throttled to ~37/minute to stay under the 40 req/min rate limit. The auto-match phase processes as fast as the website scraping allows — ShipStation is usually the bottleneck.
- The `thumbnailUrl` is the admin thumbnail in ShipStation only. It doesn't affect your SFCC storefront or shipping labels.
- The `progress.json` file is plain JSON — you can inspect or edit it manually if needed.

## Troubleshooting

**"Invalid credentials"** — API key or secret is wrong or expired. Regenerate in ShipStation → Settings → Account → API Settings.

**Auto-match is slow** — Each product requires fetching your search page plus up to 5 PDPs. With thousands of products, the auto-match phase can take a while. The progress bar and counters keep you informed.

**Image picker shows wrong images** — The scraper pulls all product images from the search results and linked PDPs. If a SKU search returns unrelated products, those images will appear too. Use the SKU labels on each thumbnail to identify the right one.

**Drag and drop doesn't work** — Right-click the image → "Copy image address" → paste into the URL field instead.

**Want to start over** — Click "Reset Progress" on the results screen. This deletes the progress file and re-scans everything.

**Products with no SKU** — These can't be auto-matched or tracked in the progress file. They'll appear in the manual phase with "No SKU" displayed.
