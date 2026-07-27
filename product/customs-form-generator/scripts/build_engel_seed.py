"""
One-time (or occasional) derivation script: turns a confirmed HTSUS addendum
for an Engel invoice into data/engel_rules.json, the classification rules
file the tool ships with and keeps building on (see rules_store.py).

This does NOT read dollar amounts or PII off the invoice -- it only pairs
each line's item SKU with the HTSUS code/fiber/description-group group it
was confirmed under, which is reusable product-classification reference
data (the same kind of thing CLAUDE.md documents inline for the RPH tool's
classification cascade), not an operational transaction record.

Usage:
    python scripts/build_engel_seed.py "<path to the source invoice PDF>"

The GROUPS table below is transcribed from the confirmed "U.S. HTSUS
Classification Addendum" for Invoice 80176541 (23.07.2026) -- the addendum
groups invoice line *numbers* (not SKUs) by proposed HTSUS code, so this
script re-parses the invoice to recover each line's SKU, then joins on line
number.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from parsers.engel import parse  # noqa: E402


def expand_ranges(spec: str) -> set[str]:
    """'025-027, 047, 054' -> {'025','026','027','047','054'}"""
    out = set()
    for chunk in spec.split(","):
        chunk = chunk.strip()
        if "-" in chunk:
            a, b = chunk.split("-")
            for n in range(int(a), int(b) + 1):
                out.add(f"{n:03d}")
        else:
            out.add(f"{int(chunk):03d}")
    return out


# (htsus_code, description_group, fiber_content, line-number ranges)
GROUPS = [
    ("6103.31.00.00", "Children's hooded jackets; Hooded jackets", "100% virgin wool (fleece)",
     "025-027, 047, 054, 056-060, 062-063, 066-070"),
    ("6103.41.00.00", "Baby pants", "100% virgin wool (fleece)",
     "012, 014, 016, 018-019, 022, 024"),
    ("6104.31.00.00", "Hooded jackets", "100% virgin wool (fleece)",
     "048, 052-053"),
    ("6104.61.00.10", "Women's yoga pants", "Organic merino wool / organic silk (exact ratio not stated)",
     "204-206"),
    ("6107.19.00.00", "Children's leggings", "70% virgin wool / 30% silk",
     "156-160"),
    ("6108.29.90.00", "Ladies' briefs; Ladies' briefs / panties; Ladies' leggings", "70% virgin wool / 30% silk",
     "137-150"),
    ("6109.90.15.40", "Children's long-sleeve shirts; Ladies' long-sleeve shirts; Leisure / pajama tops",
     "70% virgin wool / 30% silk", "161-164, 179-187"),
    ("6109.90.80.20", "Ladies' tank tops", "70% virgin wool / 30% silk",
     "152-155"),
    ("6110.11.00.70", "Children's vests; Men's vests", "100% virgin wool (fleece)",
     "042-043, 131"),
    ("6110.11.00.80", "Children's vests; Ladies' vests", "100% virgin wool (fleece)",
     "040-041, 129-130"),
    ("6111.90.05.10", "Hooded jackets", "100% virgin wool (fleece)",
     "044-046, 049-051, 055, 061, 064-065"),
    ("6111.90.05.30",
     "Baby bodysuits; Baby bootees; Baby mittens; Baby pants; Hooded baby jackets; Hooded baby overalls",
     "100% virgin wool (fleece) / 70% virgin wool / 30% silk (varies by line -- see notes)",
     "010-011, 013, 015, 017, 020-021, 023, 082-128, 132-136, 151, 188-195"),
    ("6212.10.90.10", "Nursing bras", "92% organic cotton / 8% elastane",
     "001-006"),
    ("6212.10.90.40", "Sports bustiers / bras", "70% virgin wool / 28% silk / 2% elastane",
     "196-203"),
    ("6505.00.30.30", "Adult hats; Baby balaclavas; Baby bonnets; Baby hats",
     "100% virgin wool / 100% virgin wool (fleece) / 70% virgin wool / 30% silk (varies by line -- see notes)",
     "007-009, 028-039, 071-081, 165-178"),
]


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)
    pdf_path = sys.argv[1]

    _, items = parse(pdf_path)
    by_line = {it.line_no: it for it in items}

    line_to_group = {}
    for htsus, desc, fiber, ranges in GROUPS:
        for line_no in expand_ranges(ranges):
            line_to_group[line_no] = (htsus, desc, fiber)

    missing = set(by_line) - set(line_to_group)
    if missing:
        print(f"WARNING: {len(missing)} invoice lines have no group assignment: {sorted(missing)}")

    import datetime

    rules = {}
    for line_no, item in sorted(by_line.items()):
        group = line_to_group.get(line_no)
        if not group:
            continue
        htsus, desc, fiber = group
        rules[item.item_sku] = {
            "style_number": item.style_number,
            "description_group": desc,
            "fiber_content": fiber,
            "htsus_code": htsus,
            "updated_at": datetime.date.today().isoformat(),
        }

    out_path = Path(__file__).resolve().parent.parent / "data" / "engel_rules.json"
    out_path.write_text(json.dumps(rules, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {len(rules)} rules to {out_path}")


if __name__ == "__main__":
    main()
