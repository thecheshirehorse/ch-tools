"""Groups classified line items into the HTSUS addendum summary table."""

from itertools import groupby


def compress_line_ranges(line_nos: list[str]) -> str:
    """['025','026','027','047'] -> '025-027, 047'"""
    nums = sorted(int(n) for n in line_nos)
    if not nums:
        return ""
    ranges = []
    start = prev = nums[0]
    for n in nums[1:]:
        if n == prev + 1:
            prev = n
            continue
        ranges.append((start, prev))
        start = prev = n
    ranges.append((start, prev))

    width = max(len(n) for n in line_nos)
    parts = []
    for a, b in ranges:
        if a == b:
            parts.append(f"{a:0{width}d}")
        else:
            parts.append(f"{a:0{width}d}-{b:0{width}d}")
    return ", ".join(parts)


def group_by_htsus(items: list) -> list[dict]:
    """Build the addendum summary rows: one per distinct HTSUS code, sorted by code.
    Lines with no htsus_code yet (unclassified) are grouped under "" and should be
    reviewed before generating a final addendum."""
    keyed = sorted(items, key=lambda it: (it.htsus_code or "￿", it.line_no))
    rows = []
    for htsus_code, group in groupby(keyed, key=lambda it: it.htsus_code):
        group = list(group)
        desc_groups = []
        for d in (it.description_group for it in group):
            if d and d not in desc_groups:
                desc_groups.append(d)
        fibers = []
        for f in (it.fiber_content for it in group):
            if f and f not in fibers:
                fibers.append(f)
        vendor_codes = sorted({it.customs_code_vendor for it in group if it.customs_code_vendor})
        rows.append(
            {
                "htsus_code": htsus_code,
                "line_ranges": compress_line_ranges([it.line_no for it in group]),
                "description_group": "; ".join(desc_groups),
                "fiber_content": "; ".join(fibers),
                "qty": sum(it.qty for it in group),
                "value": round(sum(it.net_total for it in group), 2),
                "vendor_customs_codes": ", ".join(vendor_codes),
                "line_count": len(group),
                "needs_review": not htsus_code,
            }
        )
    return rows


def totals_reconcile(rows: list[dict], expected_subtotal: float, tolerance: float = 0.05) -> tuple[bool, float]:
    grouped_total = round(sum(r["value"] for r in rows), 2)
    ok = abs(grouped_total - expected_subtotal) <= tolerance
    return ok, grouped_total
