"""
Parser for Engel GmbH (Pfullingen, Germany) commercial invoices.

Calibrated against a real 17-page / 206-line sample invoice (No. 80176541,
23.07.2026). Engel's invoice is a fairly regular repeating block per line
item, three physical text lines each:

    NNN <description...> <color/size...> <size> <qty> pcs. <unit price> <tax%> <net total>
    [optional wrapped word(s) of the description]
    Item No. <sku> RRP <rrp>
    Customs Code <code> Country of Origin <country> Weight <kg> kg

Fiber content isn't printed per line -- Engel prints a composition key at
the bottom of the invoice keyed by item-number prefix ("Articles start with
57/58... are made of 100% wool (fleece)", etc.). That key is encoded here
as a *display-only* fallback; it is not precise enough on its own to pick
an HTSUS code (see README) -- actual classification comes from the rules
database, keyed on the exact item SKU.
"""

import re

from models import InvoiceHeader, LineItem

ITEM_LINE_RE = re.compile(
    r"^(\d{3})\s+(.+?)\s+(\d+)\s+pcs\.\s+([\d.,]+)\s+(\d+)\s+([\d.,]+)\s*$"
)
ITEM_NO_RE = re.compile(r"^Item No\.\s+(\S+)\s+RRP\s+([\d.,]+)\s*$")
CUSTOMS_RE = re.compile(
    r"^Customs Code\s+(\d+)\s+Country of Origin\s+(\S+)\s+Weight\s+([\d.,]+)\s*kg\s*$"
)

BOILERPLATE_PREFIXES = (
    "#VGCS#",
    "Invoice",
    "Document No.",
    "Description",
    "ENGEL GmbH",
    "Wörthstra",
    "Geschäftsführung",
    "Amtsgericht",
    "BW Bank",
    "GLS Bank",
    "KSK Reutlingen",
    "Postbank",
    "T +49",
    "F +49",
    "info@engel",
    "www.engel",
)
DOC_HEADER_ROW_RE = re.compile(r"^\d+\s+\d{2}\.\d{2}\.\d{4}\s+\d+/\d+\s*$")

PREFIX_FIBER_KEY = [
    (("40", "42"), "100% virgin wool"),
    (("50", "52", "55"), "100% virgin wool (terry)"),
    (("57", "58"), "100% virgin wool (fleece)"),
    (("70", "72", "77", "79"), "70% virgin wool / 30% silk"),
    (("80",), "100% cotton"),
    (("81",), "95% cotton / 5% elastane"),
    (("84",), "100% cotton (terry)"),
    (("86", "87"), "100% cotton"),
]
PREFIX_FIBER_KEY_LONG = [
    ("M150", "70% virgin wool / 28% silk / 2% elastane (men's)"),
    ("M200", "70% virgin wool / 28% silk / 2% elastane (men's)"),
    ("W150", "70% virgin wool / 28% silk / 2% elastane (women's)"),
    ("W200", "70% virgin wool / 28% silk / 2% elastane (women's)"),
    ("U200", "70% virgin wool / 28% silk / 2% elastane (unisex)"),
]
STYLE_FIBER_EXCEPTIONS = {
    "365030": "100% cotton",
    "364150": "92% cotton / 8% elastane",
    "364160": "95% cotton / 5% elastane",
}


def fiber_from_style(style_number: str) -> str:
    """Best-effort fiber guess from Engel's printed item-number key. Display hint only."""
    if style_number in STYLE_FIBER_EXCEPTIONS:
        return STYLE_FIBER_EXCEPTIONS[style_number]
    for prefix, fiber in PREFIX_FIBER_KEY_LONG:
        if style_number.startswith(prefix):
            return fiber
    for prefixes, fiber in PREFIX_FIBER_KEY:
        if style_number[:2] in prefixes:
            return fiber
    return ""


def _is_boilerplate(line: str) -> bool:
    if DOC_HEADER_ROW_RE.match(line):
        return True
    return any(line.startswith(p) for p in BOILERPLATE_PREFIXES)


def _to_float(s: str) -> float:
    return float(s.replace(".", "").replace(",", "."))


def _parse_lines(full_text: str) -> list[LineItem]:
    lines = [ln.strip() for ln in full_text.splitlines()]
    items: list[LineItem] = []
    current = None  # dict of in-progress fields
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        m = ITEM_LINE_RE.match(line)
        if m:
            line_no, blob, qty, unit_price, tax_pct, net_total = m.groups()
            blob_parts = blob.rsplit(" ", 1)
            if len(blob_parts) == 2:
                description, size = blob_parts
            else:
                description, size = blob, ""
            current = {
                "line_no": line_no,
                "description": description,
                "size": size,
                "qty": int(qty),
                "unit_price": _to_float(unit_price),
                "tax_pct": _to_float(tax_pct),
                "net_total": _to_float(net_total),
            }
            i += 1
            continue

        m = ITEM_NO_RE.match(line)
        if m and current is not None:
            sku, rrp = m.groups()
            current["item_sku"] = sku
            current["style_number"] = sku.split("-")[0]
            current["rrp"] = float(rrp)  # RRP uses plain dot-decimal, unlike the rest of the invoice
            i += 1
            continue

        m = CUSTOMS_RE.match(line)
        if m and current is not None:
            code, country, weight = m.groups()
            current["customs_code_vendor"] = code
            current["country_of_origin"] = country
            current["weight_kg"] = _to_float(weight)
            items.append(LineItem(**current))
            current = None
            i += 1
            continue

        if current is not None and "item_sku" not in current and line and not _is_boilerplate(line):
            # a wrapped word/phrase of the description, e.g. "BEST"
            current["description"] = (current["description"] + " " + line).strip()
            i += 1
            continue

        i += 1

    return items


def _grab_after_label(lines: list[str], label: str) -> str:
    for idx, ln in enumerate(lines):
        if ln.strip() == label:
            for nxt in lines[idx + 1 : idx + 3]:
                nxt = nxt.strip()
                if nxt:
                    return nxt
            return ""
        if ln.strip().startswith(label) and ln.strip() != label:
            return ln.strip()[len(label) :].strip()
    return ""


def _parse_header(full_text: str, items: list[LineItem]) -> InvoiceHeader:
    lines = full_text.splitlines()
    header = InvoiceHeader(vendor="engel", importer_ein="02-0350695")

    m2 = re.search(r"(\d{7,9})\s+(\d{2}\.\d{2}\.\d{4})\s+\d+/\d+", full_text)
    if m2:
        header.document_no, header.document_date = m2.group(1), m2.group(2)

    # "Customer No. Our Tax ID No." header line, with values on a later line
    # ("11936 DE146477427") once a same-line address wraps in between.
    m = re.search(r"(\d+)\s+(DE[\d]+)", full_text)
    if m:
        header.customer_no = m.group(1)

    m = re.search(r"Currency:\s*([A-Z]{3})", full_text)
    if m:
        header.currency = m.group(1)

    m = re.search(r"Country of Origin\s+(\S+)", full_text)
    if m:
        header.country_of_origin = m.group(1)

    # Anchor the totals block on "Quantity ... Subtotal ..." (the summary table on
    # the last page) rather than searching the whole doc, since "Quantity" is also
    # a column header repeated on every item-list page.
    totals_block = ""
    tm = re.search(r"Quantity\s+([\d.,]+)\s*\n\s*Subtotal\s+([\d.,]+)", full_text)
    if tm:
        header.quantity_total, header.subtotal = tm.group(1), tm.group(2)
        totals_block = full_text[tm.start() : tm.start() + 2000]

    def find_amount(label: str) -> str:
        m = re.search(re.escape(label) + r"\s*\n?\s*([\d.,]+)", totals_block)
        return m.group(1) if m else ""

    dm = re.search(r"Discount\s*\((\d+)%\)\s*\n?\s*([\d.,]+)", totals_block)
    if dm:
        header.discount_pct, header.discount_amount = dm.group(1), dm.group(2)
    header.additional_expenses = find_amount("Additional Expenses")
    header.net_total_amount = find_amount("Net Total Amount")
    header.tax_amount = find_amount("Tax Amount")
    header.total_amount = find_amount("Total Amount")

    m = re.search(r"Shipment Type\s*\n?\s*(\S+)", totals_block)
    if m:
        header.shipment_type = m.group(1)
    m = re.search(r"Payment Terms\s*\n?\s*([^\n]+)", totals_block)
    if m:
        header.payment_terms = m.group(1).strip()

    note_lines = [
        ln.strip()
        for ln in lines
        if ln.strip().startswith("Articles start with") or ln.strip().startswith("Article ")
    ]
    header.notes = note_lines

    return header


def parse(pdf_path: str) -> tuple[InvoiceHeader, list[LineItem]]:
    import pdfplumber

    with pdfplumber.open(pdf_path) as pdf:
        full_text = "\n".join(page.extract_text() or "" for page in pdf.pages)

    items = _parse_lines(full_text)
    header = _parse_header(full_text, items)
    return header, items
