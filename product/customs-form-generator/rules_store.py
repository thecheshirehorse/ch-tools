"""
Persisted HTSUS classification decisions, keyed on the exact vendor SKU.

Stored as one plain JSON file per vendor (data/<vendor>_rules.json),
**committed to git** -- unlike most "local state" in this repo, this file
is meant to travel with the repo between computers (Store 3, Store 5,
whoever runs this tool), because the whole point is that a classification
confirmed once doesn't need to be re-confirmed by someone else on a
different machine. After saving a review, commit and push this file so
other computers pick up the new classifications on their next `git pull`.

It contains no PII and no pricing -- just SKU -> HTSUS/fiber/description
mappings, the same kind of reference data CLAUDE.md documents inline for
other tools' classification rules.

Why SKU-level and not style-level: on the real Engel sample invoice, the
same style number (e.g. 575520, a hooded jacket sold in many sizes) was
classified under *three different* HTSUS headings depending on size --
infant sizes fell under the babies'-garments heading (6111) while larger
child sizes fell under boys'/girls' headings (6103/6104). A style-level
rule would have silently mis-classified two thirds of that style's lines.
So an exact SKU match is required to auto-fill a line; for an unmatched
SKU we only ever *suggest* what sibling SKUs of the same style were
classified as, for a human to pick from -- never apply it automatically.
"""

import datetime
import json
import tempfile
from pathlib import Path


def _path(data_dir: Path, vendor: str) -> Path:
    return data_dir / f"{vendor}_rules.json"


def load(data_dir: Path, vendor: str) -> dict:
    """item_sku -> {style_number, description_group, fiber_content, htsus_code, updated_at}"""
    p = _path(data_dir, vendor)
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def save(data_dir: Path, vendor: str, rules: dict) -> None:
    """Atomic-ish write: dump to a temp file in the same directory, then replace."""
    p = _path(data_dir, vendor)
    p.parent.mkdir(parents=True, exist_ok=True)
    # sorted by SKU so the committed diff is small and readable
    ordered = dict(sorted(rules.items()))
    fd, tmp_name = tempfile.mkstemp(dir=str(p.parent), prefix=f".{vendor}_rules_", suffix=".tmp")
    with open(fd, "w", encoding="utf-8") as f:
        json.dump(ordered, f, indent=2, ensure_ascii=False)
        f.write("\n")
    Path(tmp_name).replace(p)


def get_rule(data_dir: Path, vendor: str, item_sku: str):
    return load(data_dir, vendor).get(item_sku)


def get_style_hints(data_dir: Path, vendor: str, style_number: str):
    """Distinct classifications already on file for sibling SKUs of this style, most common first."""
    rules = load(data_dir, vendor)
    counts = {}
    for item_sku, rule in rules.items():
        if rule.get("style_number") != style_number:
            continue
        key = (rule.get("htsus_code", ""), rule.get("description_group", ""), rule.get("fiber_content", ""))
        counts[key] = counts.get(key, 0) + 1
    hints = [
        {"htsus_code": k[0], "description_group": k[1], "fiber_content": k[2], "n": n}
        for k, n in counts.items()
    ]
    hints.sort(key=lambda h: h["n"], reverse=True)
    return hints


def upsert_rule(
    data_dir: Path,
    vendor: str,
    item_sku: str,
    style_number: str,
    description_group: str,
    fiber_content: str,
    htsus_code: str,
) -> None:
    rules = load(data_dir, vendor)
    rules[item_sku] = {
        "style_number": style_number,
        "description_group": description_group,
        "fiber_content": fiber_content,
        "htsus_code": htsus_code,
        "updated_at": datetime.date.today().isoformat(),
    }
    save(data_dir, vendor, rules)


def apply_known_rules(data_dir: Path, vendor: str, items: list) -> None:
    """Fill in htsus_code/fiber_content/description_group for lines with an exact SKU match.
    Mutates the passed LineItem list in place; unmatched lines are left blank with match_source=""."""
    rules = load(data_dir, vendor)
    for item in items:
        rule = rules.get(item.item_sku)
        if rule:
            item.htsus_code = rule.get("htsus_code", "")
            item.fiber_content = rule.get("fiber_content", "") or ""
            item.description_group = rule.get("description_group", "") or ""
            item.match_source = "exact"
