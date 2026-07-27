"""
Cheshire Horse - Customs Form Generator

Turns an overseas supplier's commercial invoice PDF into a proposed U.S.
HTSUS classification addendum, the same kind of document previously built
by hand (with Claude's help) for Engel GmbH invoices.

Single-user local tool: state for the invoice currently being worked on
lives in module-level globals, same pattern as the RPH Review tool. Only
one invoice is "in progress" at a time.

IMPORTANT: this tool proposes classifications for a human to review, the
same way the printed addendum itself says ("Final classification is
subject to review by the customs broker and U.S. Customs and Border
Protection"). It never files anything or talks to a broker automatically.
"""

import csv
import datetime
import io
import webbrowser
from pathlib import Path

from flask import Flask, redirect, render_template, request, send_file, url_for
from werkzeug.utils import secure_filename

import rules_store
from classification import group_by_htsus, totals_reconcile
from parsers import VENDORS

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

app = Flask(__name__)

# in-memory state for the invoice currently loaded (single user, single session)
STATE = {"vendor": None, "header": None, "items": None, "source_filename": None}


@app.route("/")
def index():
    vendors = {slug: v for slug, v in VENDORS.items()}
    return render_template("index.html", vendors=vendors)


@app.route("/upload", methods=["POST"])
def upload():
    vendor = request.form.get("vendor", "")
    vendor_info = VENDORS.get(vendor)
    if not vendor_info or not vendor_info["available"]:
        return "Unknown or not-yet-supported vendor.", 400

    f = request.files.get("invoice_pdf")
    if not f or not f.filename:
        return redirect(url_for("index"))

    filename = secure_filename(f.filename)
    saved_path = UPLOAD_DIR / filename
    f.save(saved_path)

    header, items = vendor_info["parser"].parse(str(saved_path))
    header.vendor = vendor
    rules_store.apply_known_rules(DATA_DIR, vendor, items)

    STATE["vendor"] = vendor
    STATE["header"] = header
    STATE["items"] = items
    STATE["source_filename"] = filename

    return redirect(url_for("review"))


@app.route("/review")
def review():
    if not STATE["items"]:
        return redirect(url_for("index"))
    items = STATE["items"]
    hints = {}
    for it in items:
        if it.match_source != "exact":
            hints[it.item_sku] = rules_store.get_style_hints(DATA_DIR, STATE["vendor"], it.style_number)
    unmatched = sum(1 for it in items if it.match_source != "exact")
    return render_template(
        "review.html",
        header=STATE["header"],
        items=items,
        hints=hints,
        unmatched=unmatched,
        total=len(items),
        source_filename=STATE["source_filename"],
    )


@app.route("/review/save", methods=["POST"])
def review_save():
    items = STATE["items"]
    if not items:
        return redirect(url_for("index"))

    for it in items:
        htsus = request.form.get(f"htsus_{it.line_no}", "").strip()
        desc = request.form.get(f"desc_{it.line_no}", "").strip()
        fiber = request.form.get(f"fiber_{it.line_no}", "").strip()
        it.htsus_code = htsus
        it.description_group = desc
        it.fiber_content = fiber
        if htsus:
            rules_store.upsert_rule(
                DATA_DIR, STATE["vendor"], it.item_sku, it.style_number, desc, fiber, htsus
            )

    return redirect(url_for("addendum"))


@app.route("/addendum")
def addendum():
    items = STATE["items"]
    header = STATE["header"]
    if not items:
        return redirect(url_for("index"))

    rows = group_by_htsus(items)
    expected = float((header.subtotal or "0").replace(".", "").replace(",", "."))
    reconciled, grouped_total = totals_reconcile(rows, expected)

    return render_template(
        "addendum.html",
        header=header,
        rows=rows,
        reconciled=reconciled,
        grouped_total=grouped_total,
        expected_subtotal=expected,
        prepared_date=datetime.date.today().strftime("%B %d, %Y"),
        vendor_label=VENDORS[STATE["vendor"]]["label"],
    )


@app.route("/addendum/export.csv")
def export_csv():
    items = STATE["items"]
    if not items:
        return redirect(url_for("index"))

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        [
            "Line No", "Item SKU", "Description", "Size", "Qty", "Unit Price", "Net Total",
            "Vendor Customs Code", "Country of Origin", "Weight (kg)",
            "Proposed HTSUS", "Description Group", "Fiber Content",
        ]
    )
    for it in items:
        writer.writerow(
            [
                it.line_no, it.item_sku, it.description, it.size, it.qty, it.unit_price, it.net_total,
                it.customs_code_vendor, it.country_of_origin, it.weight_kg,
                it.htsus_code, it.description_group, it.fiber_content,
            ]
        )
    buf.seek(0)
    return send_file(
        io.BytesIO(buf.getvalue().encode("utf-8")),
        mimetype="text/csv",
        as_attachment=True,
        download_name=f"customs-form-lines-{STATE['header'].document_no or 'export'}.csv",
    )


if __name__ == "__main__":
    webbrowser.open("http://127.0.0.1:5061")
    app.run(port=5061, debug=False)
