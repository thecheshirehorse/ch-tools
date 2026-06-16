# RPH Review

Tooling for the weekly Salesforce product upload at The Cheshire Horse. Takes the Thursday RPH report from Eagle, joins it against a Cheshire-stores enrichment export, applies a rule cascade to filter out non-Cheshire and non-product items, and presents the remaining SKUs in a local web UI for human review. The approved batch is exported as CSV (Tier 1) and will eventually push directly to Salesforce via OCAPI (Tier 2).

Status: working concept. Validated on the 5/7/26 RPH — 110 of 215 SKUs approved in a single review session. See `docs/PROJECT_BRIEF.md` for full project context and next steps.

## Quick start

```bash
# One-time setup
python -m venv .venv
source .venv/bin/activate         # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Drop this week's files into data/ (gitignored)
#   data/RPH_MM-DD-YY.xls
#   data/cheshire-enrichment.xlsx

# Run
python rph_review.py data/RPH_05-07-26.xls data/cheshire-enrichment.xlsx
# Then open http://localhost:5057
```

The first run creates `rules.db` next to the script. Class rules persist across runs — each "Always upload" or "Always skip" decision narrows the next week's review queue.

## What's in here

```
rph_review.py             # Flask app + classification logic
RPH_Review_Concept.html   # Self-contained demo (5/7 data baked in, no setup)
requirements.txt
docs/
  PROJECT_BRIEF.md        # Project state, what's built, what's next
  concept_README.md       # Notes from the 5/7 concept run
data/                     # Weekly inputs (gitignored)
  README.md               # What goes here
```

## The rule cascade

Each SKU on the RPH is classified in this order — first match wins:

1. **Drop · Closeout** — Store Closeout flag = Y
2. **Drop · Coupon** — Department code H1 or H2
3. **Drop · Delivery** — Department 80 (delivery/system items)
4. **Auto · C20** — Class C20 (Cheshire Horse Special Orders, buyer-flagged)
5. **Class rule** — User-set "always upload" or "always skip" for that class code
6. **Manual review** — Everything else

The 5/7 baseline: 50 auto-drops, 9 auto-uploads, 156 sent to manual review. With the 6 class rules persisted from that session, the next week's manual pile should drop noticeably.

## What this doesn't do yet

- Push to Salesforce. Currently exports an approved CSV. Tier 2 = OCAPI Data API integration, blocked on (a) image source decision and (b) confirming OCAPI client scope.
- Pull product images.
- Sync with the Monday board.

## Data files are not in this repo

The RPH report and enrichment export are weekly inputs containing real business data — vendor relationships, quantity-on-hand, pricing. They live in `data/` locally and are gitignored. Don't commit them, even by accident. If you need to share a sample with someone outside the team, generate a fake one with the same column shape.

## License

Internal Cheshire Horse project. Not licensed for redistribution.
