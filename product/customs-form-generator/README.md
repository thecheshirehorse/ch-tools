# Customs Form Generator

Turns an overseas supplier's commercial invoice PDF into a draft **U.S.
HTSUS Classification Addendum** — the document format Cheshire Horse
previously built by hand (with Claude's help) for Engel GmbH shipments.

## Running it

Windows: double-click `start_customs_form_generator.bat`. It sets up a
virtual environment on first run, installs dependencies, and opens
`http://127.0.0.1:5061` in your browser.

Manual:
```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

## How it works

1. **Upload** the supplier's invoice PDF and pick the supplier.
2. The tool **parses** every line item (SKU, description, qty, price,
   weight, the supplier's own customs code) and looks up each SKU's
   **exact** item number against `data/<vendor>_rules.json`, a file of
   previously confirmed HTSUS classifications for that supplier.
3. You **review** the results. Matched lines are pre-filled from a past
   invoice; anything new is flagged for manual entry, with suggestions
   from sibling SKUs of the same style where available.
4. Saving writes your confirmed classifications back into
   `data/<vendor>_rules.json` and generates the printable **addendum**
   (group totals reconcile against the invoice subtotal automatically, so
   a missing/duplicated line is easy to catch before it goes to the
   broker).
5. **Commit and push** `data/<vendor>_rules.json` after a session where
   you classified anything new. That file is tracked in git specifically
   so the next person to `git pull` this repo — on any computer — gets
   the same classifications, instead of starting from scratch. The review
   page shows the exact `git` commands to run. If you skip this step, the
   tool still works fine, it just means the other computer will have to
   re-classify the same SKUs the next time they come up on an invoice.

## Why classification is keyed on the exact SKU, not the style

On the real sample Engel invoice, the *same style number* (e.g. a hooded
jacket sold across many sizes) was correctly split across three different
HTSUS headings depending on size — infant sizes fall under the babies'-
garments heading, larger child sizes fall under boys'/girls' headings.
A style-level shortcut would have silently mis-classified most of that
style's lines. So the tool never auto-applies a classification unless the
*exact* SKU has been confirmed before; for anything new, it only ever
*suggests* what sibling SKUs were classified as, for a human to confirm.

## Adding another supplier (e.g. Janus, Ruskovilla)

1. Get at least one real sample invoice PDF from them — invoice layouts
   differ enough between suppliers that a generic parser isn't reliable
   for a compliance document.
2. Write `parsers/<vendor_slug>.py` with a `parse(pdf_path) -> (InvoiceHeader, [LineItem])`
   function, following the pattern in `parsers/engel.py`.
3. Register it in `parsers/__init__.py`'s `VENDORS` dict.
4. Optionally pre-populate `data/<vendor_slug>_rules.json` from a
   confirmed classification for that supplier (see
   `scripts/build_engel_seed.py` for the pattern) so the tool is useful
   from the first upload.

## Data handling

- `data/<vendor>_rules.json` (SKU → HTSUS classification rules) **is**
  committed — it's reusable product-classification reference data (no
  PII, no pricing), and the whole point is that it travels with the repo
  between computers. See "Commit and push" above.
- `data/uploads/` (raw invoice PDFs) is **not** committed — real vendor
  and pricing data.
