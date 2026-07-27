"""
Regenerates the EMBEDDED_RULES block in index.html from data/*_rules.json.

index.html is a self-contained, browser-only tool (no Python/Flask, so your
boss can just open it) -- it can't read data/*_rules.json off disk at
runtime the way the old server-side version did, especially when opened as
a local file:// page rather than through GitHub Pages. So the JSON files
stay the single source of truth (git-tracked, human-diffable, editable
without touching HTML), and this script bakes their current contents into
index.html as a JS object literal.

Run this after data/*_rules.json changes (e.g. after merging in a
"classification updates" file someone downloaded from the tool):

    python scripts/embed_rules.py

Then commit both the updated data/*_rules.json and the regenerated
index.html together.
"""

import json
import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
INDEX_HTML = BASE_DIR / "index.html"
DATA_DIR = BASE_DIR / "data"

START_MARKER = "// EMBEDDED_RULES_START"
END_MARKER = "// EMBEDDED_RULES_END"

SNAKE_TO_CAMEL = {
    "style_number": "styleNumber",
    "description_group": "descriptionGroup",
    "fiber_content": "fiberContent",
    "htsus_code": "htsusCode",
    "updated_at": "updatedAt",
}


def to_camel_rule(rule: dict) -> dict:
    return {SNAKE_TO_CAMEL.get(k, k): v for k, v in rule.items()}


def main():
    embedded = {}
    for path in sorted(DATA_DIR.glob("*_rules.json")):
        vendor = path.name[: -len("_rules.json")]
        rules = json.loads(path.read_text(encoding="utf-8"))
        embedded[vendor] = {sku: to_camel_rule(rule) for sku, rule in rules.items()}
        print(f"  {vendor}: {len(rules)} rules from {path.name}")

    html = INDEX_HTML.read_text(encoding="utf-8")
    if START_MARKER not in html or END_MARKER not in html:
        raise SystemExit(f"Could not find {START_MARKER}/{END_MARKER} markers in {INDEX_HTML}")

    before, rest = html.split(START_MARKER, 1)
    _, after = rest.split(END_MARKER, 1)

    payload = json.dumps(embedded, indent=2, ensure_ascii=False, sort_keys=True)
    new_block = f"{START_MARKER}\nconst EMBEDDED_RULES = {payload};\n{END_MARKER}"

    INDEX_HTML.write_text(before + new_block + after, encoding="utf-8")
    total = sum(len(v) for v in embedded.values())
    print(f"Wrote {total} total rules across {len(embedded)} vendor(s) into {INDEX_HTML.name}")


if __name__ == "__main__":
    main()
