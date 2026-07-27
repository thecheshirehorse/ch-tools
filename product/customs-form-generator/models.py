"""Vendor-agnostic data shapes shared by every parser and the classification/output code."""

from dataclasses import dataclass, field


@dataclass
class InvoiceHeader:
    vendor: str = ""
    document_no: str = ""
    document_date: str = ""
    customer_no: str = ""
    currency: str = ""
    importer_name: str = "The Cheshire Horse"
    importer_ein: str = "02-0350695"
    country_of_origin: str = ""
    quantity_total: str = ""
    subtotal: str = ""
    discount_pct: str = ""
    discount_amount: str = ""
    additional_expenses: str = ""
    net_total_amount: str = ""
    tax_amount: str = ""
    total_amount: str = ""
    shipment_type: str = ""
    payment_terms: str = ""
    notes: list = field(default_factory=list)


@dataclass
class LineItem:
    line_no: str
    description: str
    size: str
    qty: int
    unit_price: float
    tax_pct: float
    net_total: float
    item_sku: str
    style_number: str
    rrp: float
    customs_code_vendor: str
    country_of_origin: str
    weight_kg: float
    # filled in later by the classification/lookup step
    htsus_code: str = ""
    fiber_content: str = ""
    description_group: str = ""
    match_source: str = ""  # "exact" | "style-hint" | "" (unmatched)
