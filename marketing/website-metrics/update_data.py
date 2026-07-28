"""Publish an exported Website Metrics dataset into index.html.

The dashboard (index.html) keeps its baseline dataset inline as a JS
constant so it works when opened directly from disk (no server, no
fetch). Shipping-tab numbers are pulled live via the page's "Import
from ShipStation" button (see ssPullMonth() in index.html, ported from
pull_shipping_metrics.py); Revenue/Site Visits/Search Console are still
entered by hand in the page, since those come from Eagle/GA/Klaviyo/GSC
dashboards ShipStation has no visibility into.

Either way, edits stay local to whatever browser made them (in
localStorage) until someone runs this script: use the page's "Export
data" button to download a JSON snapshot of the current numbers, then
run this script to splice that file into index.html between the
SEED_DATA marker comments. Commit the updated index.html so everyone
else's copy shows the new numbers.

Usage:
    python update_data.py <exported-data.json>
"""
import json
import sys
from pathlib import Path

BEGIN_MARKER = "// BEGIN SEED_DATA"
END_MARKER = "// END SEED_DATA"


def main():
    if len(sys.argv) != 2:
        print("Usage: python update_data.py <exported-data.json>")
        sys.exit(1)

    export_path = Path(sys.argv[1])
    html_path = Path(__file__).parent / "index.html"

    data = json.loads(export_path.read_text(encoding="utf-8"))
    html = html_path.read_text(encoding="utf-8")

    begin_idx = html.find(BEGIN_MARKER)
    end_idx = html.find(END_MARKER)
    if begin_idx == -1 or end_idx == -1 or end_idx < begin_idx:
        print(f"Could not find {BEGIN_MARKER} / {END_MARKER} markers in {html_path}")
        sys.exit(1)

    block_start = html.index("\n", begin_idx) + 1
    new_block = "const SEED_DATA = " + json.dumps(data, indent=2) + ";\n"
    new_html = html[:block_start] + new_block + html[end_idx:]

    html_path.write_text(new_html, encoding="utf-8")
    print(f"Updated {html_path} from {export_path}")
    print("Next: review the diff, then `git add`, `git commit`, and push.")


if __name__ == "__main__":
    main()
