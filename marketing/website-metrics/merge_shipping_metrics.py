"""
Merge pulled shipping-metrics months into index.html's SEED_DATA, leaving
every other month/tab untouched.

Unlike update_data.py (which replaces the whole SEED_DATA with a full
export from the page), this only updates data["shipping"][<month>] for the
months present in the input file -- meant to be used with
pull_shipping_metrics.py's output.

Usage:
    python pull_shipping_metrics.py 2026-04 2026-05 2026-06 > pulled.json
    python merge_shipping_metrics.py pulled.json
"""

import json
import re
import sys
from pathlib import Path

BEGIN_MARKER = "// BEGIN SEED_DATA"
END_MARKER = "// END SEED_DATA"


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)

    pulled = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    html_path = Path(__file__).parent / "index.html"
    html = html_path.read_text(encoding="utf-8")

    begin_idx = html.find(BEGIN_MARKER)
    end_idx = html.find(END_MARKER)
    if begin_idx == -1 or end_idx == -1:
        print(f"Could not find {BEGIN_MARKER} / {END_MARKER} markers in {html_path}")
        sys.exit(1)

    m = re.search(r"const SEED_DATA = ({.*});\n", html[begin_idx:end_idx], re.DOTALL)
    if not m:
        print("Could not parse the existing SEED_DATA block")
        sys.exit(1)
    data = json.loads(m.group(1))

    data.setdefault("shipping", {})
    for month, values in pulled.items():
        data["shipping"][month] = values
        print(f"set shipping[{month}] = {values}")

    block_start = html.index("\n", begin_idx) + 1
    new_block = "const SEED_DATA = " + json.dumps(data, indent=2) + ";\n"
    new_html = html[:block_start] + new_block + html[end_idx:]

    html_path.write_text(new_html, encoding="utf-8")
    print(f"\nUpdated {html_path}")


if __name__ == "__main__":
    main()
