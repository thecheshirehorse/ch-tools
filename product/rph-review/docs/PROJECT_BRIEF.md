# Salesforce Product Upload Automation — Project Brief

**Status:** Concept validated against live data 5/7/26. Working prototype runs end-to-end. Code lives at https://github.com/caitlinsc/rph-review (private). Next phase is hardening + Salesforce write integration.

**Last worked on:** May 8, 2026

---

## When you come back, start here

The concept tool works. You ran it against today's RPH and approved 110 of 215 SKUs in a single review session, with 30% of those approvals coming from class rules you set during the session. Six "always upload" rules are now persisted in `rules.db` and will pre-classify those classes automatically next week.

The next concrete actions, in priority order:

1. **Run it again next Thursday on the 5/14 RPH.** This is the cheapest, highest-information next step. The hypothesis to test: with 6 rules pre-loaded, the manual-review pile should shrink from 156 → roughly 120, and the approved batch should still feel correct. If yes, the class-rule mechanism is proven and we can start tagging "always skip" rules aggressively to drive the queue down further.

2. **Image handling decision.** Still untouched and now the biggest gap. Where do product images come from when you upload manually today? (vendor portal, Eagle, shared drive, internal DAM?) Required before the tool can write to Salesforce. ~30 min conversation with whoever else does product creation.

3. **OCAPI access.** Find out from whoever set up the Klaviyo OCAPI integration whether the existing client credentials have product-write scope, or whether a new client is needed. ~15 min conversation. This unblocks the publish step.

4. **Confirm with the team:** are the lettered stores (A, B, D, E, F, G) physical inventory or accounting entities? Today's run didn't need this answer (the Cheshire-filtered enrichment dodged it), but it'll matter once we start tagging "always skip" rules and want to be sure we're not skipping items the lettered stores carry uniquely.

5. **Long-description and category-mapping fields.** Today's RPH has SKU + description + price. Salesforce needs more (long description, category tree, attributes). Decide where these come from for new uploads — pulled from Eagle, hand-typed, or vendor data sheets.

Once 2 and 3 are answered, the next conversation can move from "concept" to "Tier 2 pipeline that writes to staging Salesforce."

---

## What the 5/7/26 concept run proved

Run details: 232 RPH rows / 215 unique SKUs from `RPH_05-07-26.xls`, joined against a Cheshire-stores-only enrichment export (78,510 SKUs known to stores 3 or 5).

### Classification cascade — final bucket counts

| Bucket | Count | Action | Outcome |
|---|---|---|---|
| Drop · Closeout | 2 | Auto-drop | Worked |
| Drop · Coupon (dept H1/H2) | 47 | Auto-drop | Worked |
| Drop · Delivery (dept 80) | 1 | Auto-drop | Worked |
| Auto · C20 Special Order | 9 | Auto-upload | Worked, all 9 stayed in approved batch |
| Review · Class rule needed | 156 | Manual | Reviewed in one session |

Final approved batch: **110 of 215 (51%)** — 9 from C20 auto, 33 from class rules set during session, 68 manually approved.

### What this confirmed

- **C20 = always upload is correct.** All 9 C20 items survived review without override. Promote from "soft signal" to "hard rule."
- **Class-level rules are the right scaling mechanism.** A single rule on class C58 (Pet Supplies) auto-approved 26 items in one shot — almost an entire MY FAMILY USA shipment.
- **Department code H1/H2 cleanly identifies coupons.** All 47 dropped items were genuine coupons, no false positives.
- **The approved batch is dept-clean.** All 110 approvals fall in depts 30–34 (Feed, Tack, Clothing, Supplies, Gifts). Nothing from lumber/hardware/plumbing snuck through. Strong validation that the cascade plus a human in the loop produces a safe batch.
- **A single-screen review UI is enough.** No round-trips to Eagle, Compass, or Monday during review — all needed fields fit on one page.

### What this disproved or revised

- **The "BLANK vendor = coupon" assumption from the old brief is wrong.** Today's run had 49 BLANK-vendor items spanning multiple non-coupon departments (lumber, hardware, etc.). The dept H1/H2 rule reliably catches actual coupons; vendor name is not a useful signal.
- **The "Cheshire stores only" filter on the original RPH is leaky.** Today's RPH included items in classes like 011 (KD SPRUCE / FIR FRAMING LUMBER) — implying store 3 or 5 has some framing-lumber SKUs on the books. Worth a 5-minute look in Eagle to understand whether that's real (a fence-supply line item, say) or a data quirk. Doesn't block the tool either way.

### Rules persisted to `rules.db`

Six "always upload" class rules are now saved and will pre-classify next week's RPH:

| Class | Name |
|---|---|
| C03 | ENGLISH FITTINGS |
| C07 | ENGLISH SADDLE PADS |
| C12 | WESTERN TACK |
| C50 | FEED |
| C55 | GROOMING SUPPLIES |
| C58 | PET SUPPLIES |

No "always skip" rules persisted yet — they'd accelerate next week's review further. Worth adding ones for the most common Hamshaw-only classes (framing lumber, drywall screws, etc.) on the next pass.

---

## Architecture (current state)

A local Python tool that runs from VS Code. Three layers, two are built:

### ✅ Built

**Data layer.** Reads RPH .xls + Cheshire enrichment .xlsx, joins on Item Number, deduplicates multi-UPC items.

**Classification layer.** Applies the rule cascade (closeout → coupon → delivery → C20 → class rule → manual). Persists class rules to local SQLite. Loads them on each run.

**Review UI.** Local Flask web app on localhost. Single-screen layout: queue on the left, item detail in the middle, class rule library + publish bar on the right. Keyboard shortcuts for fast review. CSV export for the approved batch.

### 🟡 Not yet built

**Publish layer.** Currently exports a CSV. Tier 2 = pushes to Salesforce via OCAPI Data API directly. Blocked on (a) image source decision and (b) OCAPI client credential scope.

**Monday integration.** Currently nothing flows back to the Monday board. Not blocking — Monday would just mirror what's in the CSV. Worth doing once Tier 2 ships.

---

## Open questions / things to figure out before Tier 2

| Question | Why it matters | Status |
|---|---|---|
| Image source | Required for actual product creation | **NOW BLOCKING** — was deferred, can't defer further |
| OCAPI client scope | Determines publish path (API vs XML import) | **NOW BLOCKING** — ~15 min conversation |
| Long description & category mapping | Salesforce needs more than RPH provides | Not yet specced |
| Lettered stores (A, B, D, E, F, G) | Affects "always skip" rule design | Open, not blocking |
| Store 5 catalog policy | Are Saratoga-only items on the site? | Defaulted to "yes," still works |
| Booking orders (PO data) | Future buyer commitments | Compass has it, not yet pulled |

---

## Files in this handoff folder

- `PROJECT_BRIEF.md` — this document (5/7/26 update)
- `analysis_findings.md` — original 4/30 data analysis (still valid for context)
- `RPH_04-30-26.xls` — original test report
- `RPH_05-07-26.xls` — today's report
- `Export237.xlsx`, `Export60.xlsx` — original 4/30 enrichment tests
- `vendor-class-department-by-store2.xlsx` — today's Cheshire enrichment (the format that worked)
- `RPH_approved_2026-05-07.csv` — today's approved batch (110 SKUs)
- `rph_review.py` — the runnable concept tool
- `RPH_Review_Concept.html` — self-contained demo (5/7 data baked in)
- `rules.db` — persisted class rules (6 entries)
- `concept_README.md` — how to run the tool
