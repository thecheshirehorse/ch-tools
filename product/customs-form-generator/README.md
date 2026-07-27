# Customs Form Generator

Turns an overseas supplier's commercial invoice PDF into a draft **U.S.
HTSUS Classification Addendum** — the document format Cheshire Horse
previously built by hand (with Claude's help) for Engel GmbH shipments.

**Runs entirely in the browser.** No Python, no install, no server —
just open `index.html`. All parsing happens client-side (via pdf.js);
nothing is uploaded anywhere.

## Running it

Open `product/customs-form-generator/index.html` directly in a browser
(double-click it, or use the "Customs Form Generator" card on the
dashboard). Works offline once the page and its one CDN script (pdf.js)
have loaded once.

## How it works

1. **Upload** the supplier's invoice PDF and pick the supplier.
2. The tool **parses** every line item (SKU, description, qty, price,
   weight, the supplier's own customs code) in-browser and looks up
   each SKU's **exact** item number against a built-in classification
   table for that supplier.
3. You **review** the results. Matched lines are pre-filled from a past
   invoice; anything new is flagged for manual entry, with suggestions
   from sibling SKUs of the same style where available.
4. Saving keeps your confirmed classifications in this browser's local
   storage (so re-uploading the same invoice, or a future one with the
   same SKUs, auto-fills on this computer) and generates the printable
   **addendum** — group totals reconcile against the invoice subtotal
   automatically, so a missing or duplicated line is easy to catch
   before it goes to the broker.
5. If you classified anything new, click **Download classification
   updates** on the addendum page. That downloads a small JSON file
   with just the new/changed SKUs — send it to whoever maintains this
   repo (Slack, email, whatever's easiest) so they can fold it into the
   shared rule set for every computer, not just yours.

## Why classification is keyed on the exact SKU, not the style

On the real sample Engel invoice, the *same style number* (e.g. a hooded
jacket sold across many sizes) was correctly split across three different
HTSUS headings depending on size — infant sizes fall under the babies'-
garments heading, larger child sizes fall under boys'/girls' headings.
A style-level shortcut would have silently mis-classified most of that
style's lines. So the tool never auto-applies a classification unless the
*exact* SKU has been confirmed before; for anything new, it only ever
*suggests* what sibling SKUs were classified as, for a human to confirm.

## Maintaining the shared classification rules

`data/<vendor>_rules.json` is the source of truth for the classification
table every computer starts with — one file per supplier, plain JSON,
committed to git. `index.html` can't read that file at runtime on its
own (it's a static page, often opened as a local file), so its contents
are baked into `index.html` as a JS object (look for `EMBEDDED_RULES`
near the top of the `<script>` block).

**This part still needs Python** (only for whoever maintains the repo —
not for anyone just using the tool):

1. Someone downloads a "classification updates" file from the tool (see
   step 5 above) and sends it to you.
2. Merge those entries into `data/<vendor>_rules.json` (by hand for a
   couple of SKUs, or write a quick script if it's a lot).
3. Regenerate the embedded block:
   ```
   python scripts/embed_rules.py
   ```
4. Commit and push both the updated `data/<vendor>_rules.json` and the
   regenerated `index.html`.
5. Anyone who reloads the page (or `git pull`s + reopens the file) now
   has the new classifications built in.

## Adding another supplier (e.g. Janus, Ruskovilla)

1. Get at least one real sample invoice PDF from them — invoice layouts
   differ enough between suppliers that a generic parser isn't reliable
   for a compliance document.
2. Add a parser object to the `PARSERS` map in `index.html`, following
   the pattern of `engelParser` (a `parse(arrayBuffer) -> {header, items}`
   function). The shared `extractPdfText()`/`clusterLines()` helpers
   handle turning the PDF into text; you're writing the regexes that
   turn that text into structured line items, calibrated against the
   real sample invoice.
3. Add the vendor to the `VENDORS` registry (`available: true`).
4. To seed it with an already-confirmed classification (e.g. a broker's
   addendum for that supplier's first invoice): use the tool itself —
   upload that invoice, classify every line against the confirmed
   addendum, save, then use **Download classification updates** to get
   a JSON file covering the whole invoice. Add it as
   `data/<vendor_slug>_rules.json` and run `python scripts/embed_rules.py`.

## Data handling

- `data/<vendor>_rules.json` (SKU → HTSUS classification rules) **is**
  committed — it's reusable product-classification reference data (no
  PII, no pricing).
- Uploaded invoice PDFs never leave the browser and are never written
  to disk by this tool.
