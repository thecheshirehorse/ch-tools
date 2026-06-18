"""
RPH Review — concept Flask app
================================

Reads:
  - The weekly RPH .xls export (legacy Excel)
  - A Cheshire enrichment .xlsx export filtered to stores 3 and 5
    (must contain: Item Number, Vendor Name, Department Code/Name,
     Class Code/Name, Quantity on Hand, Store Closeout?)

Applies the rule cascade (closeout > coupon > delivery > C20 > class rule
> manual review), spins up a local web UI for the review pile, and
writes an "approved" CSV when you're done.

Class-rule decisions persist to a local SQLite file (rules.db) so the
review queue shrinks each week as you tag classes.

Usage:
  pip install flask pandas openpyxl xlrd
  python rph_review.py path/to/RPH_05-07-26.xls path/to/cheshire-enrichment.xlsx
  # then open http://localhost:5057
"""

from __future__ import annotations

import argparse
import csv
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from flask import Flask, jsonify, request, send_file

# ---------------------------------------------------------------------------
# CLASSIFICATION
# ---------------------------------------------------------------------------

BUCKET_LABELS = {
    "drop_closeout": "Drop · Closeout",
    "drop_coupon": "Drop · Coupon",
    "drop_delivery": "Drop · Delivery/System",
    "auto_c20": "Auto · C20 Special Order",
    "review_class": "Review · Class rule needed",
    "review_no_enrich": "Review · No enrichment",
}


def classify_row(row: pd.Series) -> str:
    """Apply the rule cascade. Order matters."""
    if str(row.get("Store Closeout?", "")).strip().upper() == "Y":
        return "drop_closeout"
    dept = str(row.get("department_code", "")).strip()
    klass = str(row.get("class_code", "")).strip()
    if dept in ("H1", "H2"):
        return "drop_coupon"
    if dept == "80":
        return "drop_delivery"
    if klass == "C20":
        return "auto_c20"
    if pd.isna(row.get("department_code")):
        return "review_no_enrich"
    return "review_class"


def load_and_classify(rph_path: Path, enrich_path: Path) -> list[dict]:
    """Read both files, join, classify, return JSON-ready records."""
    rph = pd.read_excel(rph_path, engine="xlrd")
    enrich = pd.read_excel(enrich_path)

    # Normalize Item Number on both sides
    rph["Item Number"] = rph["Item Number"].astype(str).str.strip()
    enrich["Item Number"] = enrich["Item Number"].astype(str).str.strip()

    # Aggregate enrichment to one row per item, summing QOH/QOO across stores 3+5
    agg_dict = {
        "qoh_cheshire": ("Quantity on Hand", lambda s: s.fillna(0).sum()),
        "department_code": ("Department Code", "first"),
        "department_name": ("Department Name", "first"),
        "class_code": ("Class Code", "first"),
        "class_name": ("Class Name", "first"),
    }
    if "Quantity on Order" in enrich.columns:
        agg_dict["qoo_cheshire"] = ("Quantity on Order", lambda s: s.fillna(0).sum())
    agg = enrich.groupby("Item Number").agg(**agg_dict).reset_index()

    # Dedupe RPH (multi-UPC items show up twice)
    rph_dedup = rph.drop_duplicates("Item Number").copy()
    joined = rph_dedup.merge(agg, on="Item Number", how="left")
    joined["bucket"] = joined.apply(classify_row, axis=1)

    records = []
    for _, r in joined.iterrows():
        records.append(
            {
                "item": r["Item Number"],
                "desc": (str(r["Item Description"])[:80] if pd.notna(r["Item Description"]) else ""),
                "mfg_part": (str(r["MFG Part #"]).strip() if pd.notna(r["MFG Part #"]) else ""),
                "upc": (lambda v: str(int(float(v))) if pd.notna(v) and str(v).strip() not in ("", "0") and str(v).replace(".", "", 1).isdigit() else (str(v).strip() if pd.notna(v) and str(v).strip() not in ("", "0") else ""))(r["UPC Code"]),
                "vendor": (str(r["Vendor Name"]) if pd.notna(r["Vendor Name"]) else ""),
                "date_added": (str(r["Date Added"])[:10] if pd.notna(r["Date Added"]) else ""),
                "closeout": str(r.get("Store Closeout?", "")).strip().upper() == "Y",
                "list_price": float(r["List Price"]) if pd.notna(r["List Price"]) else 0.0,
                "retail_price": float(r["Retail Price"]) if pd.notna(r["Retail Price"]) else 0.0,
                "dept_code": (str(r.get("department_code", "")) if pd.notna(r.get("department_code")) else ""),
                "dept_name": (str(r.get("department_name", "")) if pd.notna(r.get("department_name")) else ""),
                "class_code": (str(r.get("class_code", "")) if pd.notna(r.get("class_code")) else ""),
                "class_name": (str(r.get("class_name", "")) if pd.notna(r.get("class_name")) else ""),
                "qoh_cheshire": float(r.get("qoh_cheshire", 0)) if pd.notna(r.get("qoh_cheshire")) else 0.0,
                "qoo_cheshire": float(r.get("qoo_cheshire", 0)) if pd.notna(r.get("qoo_cheshire")) else 0.0,
                "bucket": r["bucket"],
                "bucket_label": BUCKET_LABELS[r["bucket"]],
            }
        )

    # Sort: review first (clustered by class), then auto, then drops
    order = {
        "review_class": 0, "review_no_enrich": 1, "auto_c20": 2,
        "drop_coupon": 3, "drop_closeout": 4, "drop_delivery": 5,
    }
    records.sort(key=lambda r: (order[r["bucket"]], r.get("class_code", ""), r.get("item", "")))
    return records


# ---------------------------------------------------------------------------
# CLASS RULE PERSISTENCE
# ---------------------------------------------------------------------------

DB_PATH = Path(__file__).parent / "rules.db"


def init_db() -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS class_rules (
                class_code TEXT PRIMARY KEY,
                kind TEXT NOT NULL,
                set_at TEXT NOT NULL,
                note TEXT
            )"""
        )


def get_rules() -> dict[str, str]:
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute("SELECT class_code, kind FROM class_rules").fetchall()
    return {code: kind for code, kind in rows}


def set_rule(code: str, kind: str, note: str = "") -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO class_rules (class_code, kind, set_at, note) VALUES (?, ?, ?, ?)",
            (code, kind, datetime.now(timezone.utc).isoformat(), note),
        )


def remove_rule(code: str) -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM class_rules WHERE class_code = ?", (code,))


# ---------------------------------------------------------------------------
# FLASK APP
# ---------------------------------------------------------------------------

app = Flask(__name__)
RECORDS: list[dict] = []          # populated on startup
DECISIONS: dict[str, str] = {}    # item_number -> 'approve' | 'skip'


@app.route("/")
def index():
    """Serve the HTML with live state injected, replacing the baked-in demo data."""
    html_path = Path(__file__).parent / "index.html"
    if not html_path.exists():
        return "<h1>Place index.html next to this script.</h1>", 500

    html = html_path.read_text(encoding="utf-8")

    # Build the live initialization block. The JS will detect window.LIVE_MODE
    # and use these values instead of the embedded demo data.
    payload = {
        "records": RECORDS,
        "rules": get_rules(),
        "decisions": DECISIONS,
    }
    inject = (
        "<script>\n"
        "window.LIVE_MODE = true;\n"
        f"window.LIVE_STATE = {json.dumps(payload)};\n"
        "</script>\n"
    )

    # Insert the live state script just before the closing </head> so it runs
    # before the main script that reads window.RPH_DATA.
    html = html.replace("</head>", inject + "</head>", 1)
    return html


@app.route("/api/state")
def api_state():
    return jsonify({
        "records": RECORDS,
        "rules": get_rules(),
        "decisions": DECISIONS,
    })


@app.route("/api/decide", methods=["POST"])
def api_decide():
    data = request.json or {}
    item = data.get("item")
    decision = data.get("decision")  # 'approve' | 'skip' | None
    if decision is None:
        DECISIONS.pop(item, None)
    else:
        DECISIONS[item] = decision
    return jsonify({"ok": True})


@app.route("/api/rule", methods=["POST"])
def api_rule():
    data = request.json or {}
    code = data.get("class_code")
    kind = data.get("kind")  # 'upload' | 'skip' | None
    if kind is None:
        remove_rule(code)
    else:
        set_rule(code, kind)
    return jsonify({"ok": True, "rules": get_rules()})


@app.route("/api/export")
def api_export():
    """Stream out approved items as CSV."""
    rules = get_rules()
    approved = []
    for r in RECORDS:
        manual = DECISIONS.get(r["item"])
        if manual == "approve":
            r2 = {**r, "decision_source": "manual"}
            approved.append(r2)
        elif manual == "skip":
            continue
        elif r["bucket"] == "auto_c20":
            approved.append({**r, "decision_source": "auto_c20"})
        elif r["bucket"].startswith("review_") and r["class_code"] in rules and rules[r["class_code"]] == "upload":
            approved.append({**r, "decision_source": f"class_rule:{r['class_code']}"})

    out = Path(__file__).parent / f"RPH_approved_{datetime.now().strftime('%Y-%m-%d')}.csv"
    with out.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Item Number", "Description", "Vendor", "UPC", "MFG Part #",
                    "Department", "Class", "List Price", "Retail Price",
                    "QOH Cheshire", "Decision Source"])
        for r in approved:
            w.writerow([
                r["item"], r["desc"], r["vendor"], r["upc"], r["mfg_part"],
                f'{r["dept_code"]} {r["dept_name"]}',
                f'{r["class_code"]} {r["class_name"]}',
                r["list_price"], r["retail_price"], r["qoh_cheshire"],
                r["decision_source"],
            ])
    return send_file(out, as_attachment=True)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

READY = False   # True once files have been loaded via the picker


@app.route("/upload", methods=["GET"])
def upload_page():
    """File picker landing page shown when the app starts with no data loaded."""
    return """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>RPH Review — Load Files</title>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: #111827; color: #e5e7eb;
      min-height: 100vh; display: flex; align-items: center; justify-content: center;
    }
    .card {
      background: #1f2937; border: 1px solid #374151; border-radius: 12px;
      padding: 40px 48px; width: 480px; max-width: 95vw;
    }
    h1 { font-size: 1.4rem; font-weight: 600; color: #f9fafb; margin-bottom: 6px; }
    .subtitle { font-size: 0.875rem; color: #9ca3af; margin-bottom: 32px; }
    label { display: block; font-size: 0.875rem; font-weight: 500; color: #d1d5db; margin-bottom: 6px; }
    .file-row { margin-bottom: 20px; }
    input[type="file"] {
      display: block; width: 100%;
      background: #111827; border: 1px solid #374151; border-radius: 8px;
      color: #e5e7eb; padding: 10px 12px; font-size: 0.875rem; cursor: pointer;
    }
    input[type="file"]::file-selector-button {
      background: #374151; border: none; color: #e5e7eb;
      padding: 5px 12px; border-radius: 4px; margin-right: 10px; cursor: pointer;
    }
    .hint { font-size: 0.75rem; color: #6b7280; margin-top: 4px; }
    button[type="submit"] {
      width: 100%; margin-top: 12px; padding: 12px;
      background: #10b981; border: none; border-radius: 8px;
      color: #fff; font-size: 1rem; font-weight: 600; cursor: pointer;
      transition: background 0.15s;
    }
    button[type="submit"]:hover { background: #059669; }
    button[type="submit"]:disabled { background: #374151; color: #6b7280; cursor: not-allowed; }
    #status { margin-top: 16px; font-size: 0.875rem; color: #9ca3af; text-align: center; min-height: 20px; }
  </style>
</head>
<body>
  <div class="card">
    <h1>RPH Review Tool</h1>
    <p class="subtitle">Load this week's files to begin</p>
    <form id="loadForm">
      <div class="file-row">
        <label for="rph_file">RPH Export (.xls)</label>
        <input type="file" id="rph_file" name="rph_file" accept=".xls,.xlsx">
        <p class="hint">Weekly RPH export — e.g. RPH_06-04-26.xls</p>
      </div>
      <div class="file-row">
        <label for="enrich_file">Enrichment Export (.xlsx)</label>
        <input type="file" id="enrich_file" name="enrich_file" accept=".xls,.xlsx">
        <p class="hint">Compass enrichment export — e.g. RPH_Enrichment_06-04-26.xlsx</p>
      </div>
      <button type="submit" id="submitBtn">Load Files &amp; Start Review</button>
    </form>
    <div id="status"></div>
  </div>
  <script>
    document.getElementById('loadForm').addEventListener('submit', async (e) => {
      e.preventDefault();
      const rph = document.getElementById('rph_file').files[0];
      const enrich = document.getElementById('enrich_file').files[0];
      if (!rph || !enrich) { document.getElementById('status').textContent = 'Please select both files.'; return; }
      const btn = document.getElementById('submitBtn');
      btn.disabled = true; btn.textContent = 'Loading…';
      document.getElementById('status').textContent = 'Processing files, please wait…';
      const fd = new FormData();
      fd.append('rph_file', rph);
      fd.append('enrich_file', enrich);
      try {
        const res = await fetch('/api/load', { method: 'POST', body: fd });
        const data = await res.json();
        if (data.ok) {
          document.getElementById('status').textContent = `Loaded ${data.count} SKUs. Redirecting…`;
          window.location.href = '/';
        } else {
          document.getElementById('status').textContent = 'Error: ' + data.error;
          btn.disabled = false; btn.textContent = 'Load Files & Start Review';
        }
      } catch (err) {
        document.getElementById('status').textContent = 'Error: ' + err;
        btn.disabled = false; btn.textContent = 'Load Files & Start Review';
      }
    });
  </script>
</body>
</html>"""


@app.route("/api/load", methods=["POST"])
def api_load():
    """Accept uploaded files, classify, and populate RECORDS."""
    import tempfile, os
    global RECORDS, READY

    rph_file = request.files.get("rph_file")
    enrich_file = request.files.get("enrich_file")
    if not rph_file or not enrich_file:
        return jsonify({"ok": False, "error": "Both files required."})

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            rph_path = Path(tmpdir) / rph_file.filename
            enrich_path = Path(tmpdir) / enrich_file.filename
            rph_file.save(str(rph_path))
            enrich_file.save(str(enrich_path))
            RECORDS = load_and_classify(rph_path, enrich_path)
            READY = True
        return jsonify({"ok": True, "count": len(RECORDS)})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)})


# Redirect to picker if files haven't been loaded yet
_original_index = index.__wrapped__ if hasattr(index, '__wrapped__') else index

@app.before_request
def check_loaded():
    """Redirect to the file picker if data hasn't been loaded yet."""
    if request.path in ("/upload", "/api/load") or request.path.startswith("/static"):
        return None
    if not READY and not RECORDS:
        from flask import redirect
        return redirect("/upload")


def main() -> None:
    import webbrowser, threading, time

    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("rph", nargs="?", type=Path, help="Weekly RPH .xls export (optional — can upload via browser)")
    p.add_argument("enrichment", nargs="?", type=Path, help="Cheshire enrichment .xlsx (optional)")
    p.add_argument("--port", type=int, default=5057)
    args = p.parse_args()

    init_db()

    if args.rph and args.enrichment:
        # Classic command-line usage still works
        if not args.rph.exists():
            sys.exit(f"RPH file not found: {args.rph}")
        if not args.enrichment.exists():
            sys.exit(f"Enrichment file not found: {args.enrichment}")
        global RECORDS, READY
        RECORDS = load_and_classify(args.rph, args.enrichment)
        READY = True
        counts: dict[str, int] = {}
        for r in RECORDS:
            counts[r["bucket"]] = counts.get(r["bucket"], 0) + 1
        print(f"\n  Loaded {len(RECORDS)} unique SKUs from {args.rph.name}")
        for b, c in sorted(counts.items()):
            print(f"    {BUCKET_LABELS[b]:<35} {c:>4}")
        start_url = f"http://localhost:{args.port}"
    else:
        start_url = f"http://localhost:{args.port}/upload"

    print(f"\n  RPH Review Tool")
    print(f"  Opening http://localhost:{args.port}")
    print(f"  Press Ctrl+C to stop\n")

    def open_browser():
        time.sleep(1.2)
        webbrowser.open(start_url)

    threading.Thread(target=open_browser, daemon=True).start()
    app.run(host="127.0.0.1", port=args.port, debug=False)


if __name__ == "__main__":
    main()
