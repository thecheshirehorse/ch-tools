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

This does a WHOLESALE REPLACE of the entire dataset -- not a merge. If the
browser you exported from had an older SEED_DATA baked in (e.g. a tab left
open since before someone else updated index.html), the export silently
reflects that stale baseline for anything you didn't personally edit in
that tab, and running this script will blow away whatever was newer. The
page's own "Export data" always stamps meta.seededOn with *today's* date
regardless of how old the underlying numbers actually are, so that field
can't be trusted to catch this -- which is exactly how the shipping
history got reverted to pre-ISPU-fix numbers once already. To catch it
before it happens again, this script prints a before/after summary (line
counts and shipping cost/order totals) and asks for confirmation before
writing anything.

Usage:
    python update_data.py <exported-data.json>
"""
import json
import sys
from pathlib import Path

BEGIN_MARKER = "// BEGIN SEED_DATA"
END_MARKER = "// END SEED_DATA"


def shipping_summary(shipping):
    months = len(shipping)
    orders = sum(v.get("ordersShipped") or 0 for v in shipping.values())
    cost = sum(v.get("shippingCost") or 0 for v in shipping.values())
    return months, orders, cost


def main():
    if len(sys.argv) != 2:
        print("Usage: python update_data.py <exported-data.json>")
        sys.exit(1)

    export_path = Path(sys.argv[1])
    html_path = Path(__file__).parent / "index.html"

    new_data = json.loads(export_path.read_text(encoding="utf-8"))
    html = html_path.read_text(encoding="utf-8")

    begin_idx = html.find(BEGIN_MARKER)
    end_idx = html.find(END_MARKER)
    if begin_idx == -1 or end_idx == -1 or end_idx < begin_idx:
        print(f"Could not find {BEGIN_MARKER} / {END_MARKER} markers in {html_path}")
        sys.exit(1)

    block_start = html.index("\n", begin_idx) + 1
    current_block = html[block_start:end_idx]
    try:
        current_data = json.loads(current_block.split("const SEED_DATA = ", 1)[1].rstrip().rstrip(";"))
    except (IndexError, ValueError, json.JSONDecodeError):
        current_data = None

    if current_data is not None:
        cur_months, cur_orders, cur_cost = shipping_summary(current_data.get("shipping", {}))
        new_months, new_orders, new_cost = shipping_summary(new_data.get("shipping", {}))
        cur_rev = sum(len(v) for v in current_data.get("revenue", {}).values())
        new_rev = sum(len(v) for v in new_data.get("revenue", {}).values())

        print("Currently committed  -> shipping: %d months, %d orders, $%.2f total cost | revenue entries: %d"
              % (cur_months, cur_orders, cur_cost, cur_rev))
        print("This export would set -> shipping: %d months, %d orders, $%.2f total cost | revenue entries: %d"
              % (new_months, new_orders, new_cost, new_rev))

        cost_delta_pct = ((new_cost - cur_cost) / cur_cost * 100) if cur_cost else 0
        if new_months < cur_months or new_rev < cur_rev or abs(cost_delta_pct) > 3:
            print()
            print("WARNING: this looks like it would REMOVE data or shift shipping cost by "
                  f"{cost_delta_pct:+.1f}% -- if you didn't intend that big a change, this export "
                  "probably came from a browser tab with a stale/older baseline. Double-check before proceeding.")
        print()
        if input("Apply this export to index.html? [y/N] ").strip().lower() not in ("y", "yes"):
            print("Aborted -- nothing written.")
            sys.exit(1)

    new_block = "const SEED_DATA = " + json.dumps(new_data, indent=2) + ";\n"
    new_html = html[:block_start] + new_block + html[end_idx:]

    html_path.write_text(new_html, encoding="utf-8")
    print(f"Updated {html_path} from {export_path}")
    print("Next: review the diff, then `git add`, `git commit`, and push.")


if __name__ == "__main__":
    main()
