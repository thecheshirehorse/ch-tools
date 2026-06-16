# RPH Review — Concept Test (5/7/26)

A working concept of the Salesforce upload pipeline, built against today's
real RPH and a Cheshire-stores-only enrichment export. Run on 232 RPH
rows / 215 unique SKUs.

## What's here

**`RPH_Review_Concept.html`** — fully self-contained, double-clickable.
All 215 SKUs from today's RPH are baked in. Open it in a browser and you
can click through the actual review experience right now.

**`rph_review.py`** — the runnable Flask version. Reads live from your
RPH and enrichment files, persists class rules to a local SQLite DB, and
exports an approved-batch CSV.

## Bucket counts on today's RPH

| Bucket | Count | What it means |
|---|---|---|
| Drop · Closeout | 2 | Store Closeout flag = Y |
| Drop · Coupon | 47 | Department H1/H2 |
| Drop · Delivery/System | 1 | Department 80 |
| Auto · C20 Special Order | 9 | Buyer-flagged Cheshire |
| **Review · Class rule needed** | **156** | Need your eyes — for now |

The 156-item review pile is exactly the situation the project brief
predicted: without class-level rules, ~150 items end up in review per
week. Each "Always skip class X" decision you make collapses future
queues. Once 30–50 of the most common Hamshaw classes are tagged (KD
SPRUCE FRAMING LUMBER, DRYWALL SCREWS, MASONRY DRILL BITS, etc.), the
weekly review should drop to ~30 items.

## Try it

1. **Open `RPH_Review_Concept.html` in any browser.** Today's data is
   pre-loaded.
2. The first item should already be selected — `268J 2x6-8' KD SPRUCE
   J-GRADE`, class 011. Click "Always skip this class" in the dashed
   box at the bottom. Watch the review count drop and the class library
   on the right gain an entry.
3. Try the keyboard shortcuts: `A` approves, `S` skips, `↓`/`↑` navigate.
4. Click any of the bucket cells across the top to filter the queue.
5. Hit "Export Batch CSV" to download the approved set.

The HTML demo doesn't persist between page reloads — that's what the
Python version is for.

## Run the Flask version

```bash
pip install flask pandas openpyxl xlrd
python rph_review.py RPH_05-07-26.xls vendor-class-department-by-store2.xlsx
# open http://localhost:5057
```

Class rules persist to `rules.db` (SQLite, next to the script). Run it
again next week with new files and your existing rules apply
automatically.

## What this concept proves

- The rule cascade works on real data
- The class-rule library is the right scaling mechanism (one decision,
  permanent payoff)
- A single-screen review UI is enough — no need for Monday-board
  side-trips during review
- Today's RPH alone can drive a meaningful filter (50/215 = 23% drop rate
  before any human review)

## What it doesn't do yet

- Push to Salesforce via OCAPI — exports a CSV instead. Wiring this up
  is the Tier 2 step from the project brief.
- Pull image URLs (still an open question per the brief).
- Push to Monday board (Monday API integration is a separate next step).
- Handle the "no enrichment" / Hamshaw-only case — today's RPH had zero
  of these because the original RPH is already Cheshire-filtered.

## Open questions surfaced by this run

1. **Class 011 (KD SPRUCE / FIR FRAMING LUMBER) shows up in RPH** even
   though enrichment is filtered to stores 3 and 5. That means store 3 or
   5 has *some* framing-lumber SKUs on the books. Worth confirming
   whether that's real or a data quirk before "always skip" rules go in.

2. **`BLANK` vendor still appears** for 49 items, even though
   per-vendor rules in the brief assumed BLANK = coupons. In today's
   data, several BLANK-vendor items have non-coupon dept codes (lumber,
   hardware). The dept-code coupon rule (H1/H2) catches the real coupons
   correctly, so this isn't a bug — but the project brief's note about
   "BLANK = coupons" should be updated.

3. **The 9 C20 items**: take a quick look in the demo and confirm
   they all genuinely belong on the site. If yes, that confirms the
   "C20 = always upload" assumption from the brief.
