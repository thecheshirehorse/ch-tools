# Setup

For someone (you in two months, or a coworker) opening this repo cold and trying to get it running.

## Requirements

- Python 3.10 or newer
- Ability to install pip packages
- A weekly RPH `.xls` file (legacy Excel format from Eagle/RPRO)
- A Cheshire-stores enrichment `.xlsx` file (export from Compass — see "Generating the enrichment file" below)

That's it. No database server, no API keys, no cloud infrastructure. Everything runs locally and writes to a SQLite file in the repo directory.

## First-time setup

```bash
git clone <repo-url>
cd rph-review
python -m venv .venv
source .venv/bin/activate         # Windows: .venv\Scripts\activate
pip install -r requirements.txt
mkdir -p data
```

## Each weekly run

```bash
# 1. Drop this week's two files into data/
#    The names don't matter — you'll reference them on the command line.
#    Conventional naming:
#      data/RPH_MM-DD-YY.xls
#      data/cheshire-enrichment.xlsx

# 2. Run the tool
source .venv/bin/activate
python rph_review.py data/RPH_05-07-26.xls data/cheshire-enrichment.xlsx

# 3. Open http://localhost:5057 in a browser
# 4. Review the queue, set class rules, approve/skip items
# 5. Click "Export Batch CSV" — file lands in the repo root as
#    RPH_approved_YYYY-MM-DD.csv
# 6. Stop the server with Ctrl+C
```

The exported CSV is what gets uploaded to Salesforce manually for now. Tier 2 will replace this step with a direct API push.

## Generating the enrichment file

The enrichment file is a Compass query export with these columns, filtered to stores 3 and 5 only:

- Item Number
- Item Description
- Vendor Name
- Vendor Code
- Department Code & Name
- Class Code & Name
- Quantity on Hand
- Store Closeout?
- Date Added
- List Price
- Retail Price
- UPC Code
- MFG Part #

Save as `.xlsx`. The file is large (~80k rows, ~8MB) and changes weekly as inventory shifts. It's worth automating this export if Compass supports scheduled queries; check with whoever set up the existing Klaviyo integration.

## Class rules

Decisions persist to `rules.db` (SQLite, in the repo root, gitignored). The schema:

```sql
CREATE TABLE class_rules (
  class_code TEXT PRIMARY KEY,
  kind TEXT NOT NULL,            -- 'upload' or 'skip'
  set_at TEXT NOT NULL,          -- ISO timestamp
  note TEXT                      -- human-readable label
);
```

To inspect:

```bash
sqlite3 rules.db "SELECT * FROM class_rules ORDER BY class_code"
```

To wipe and start over:

```bash
rm rules.db
```

The 5/7 baseline rules (always upload): C03 English Fittings, C07 English Saddle Pads, C12 Western Tack, C50 Feed, C55 Grooming Supplies, C58 Pet Supplies.

## Troubleshooting

**`ModuleNotFoundError: No module named 'xlrd'`** — Run `pip install -r requirements.txt` again. The legacy `.xls` format needs `xlrd` specifically; `openpyxl` only handles `.xlsx`.

**Port 5057 in use** — Pass `--port 5058` (or any free port) on the command line.

**Enrichment file has different columns than expected** — Compare against the column list above. If Compass changed something, the join in `load_and_classify()` will silently drop fields. Check the bucket counts on startup; if they look wrong, that's the first place to look.

**RPH has 0 unique SKUs after dedup** — The dedup is on `Item Number`. If the column got renamed in a new RPH format, this will collapse to 0. Inspect with `pandas.read_excel(path, engine='xlrd').columns`.

## When you're ready to extend

Tier 2 will add a publish step — pushing approved items directly to Salesforce via OCAPI rather than exporting CSV. Before starting that work, two open questions need answers (see `docs/PROJECT_BRIEF.md` for context):

1. Where do product images come from?
2. Does the existing Klaviyo OCAPI client have product-write scope, or does a new client need to be provisioned?
