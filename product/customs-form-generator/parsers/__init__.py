"""
Vendor-specific invoice parsers.

Each parser turns a vendor's commercial-invoice PDF into a common
(InvoiceHeader, [LineItem]) shape that the rest of the app works with.
Invoice layouts differ vendor to vendor, so each vendor gets its own
parser calibrated against real sample invoices -- there is no generic
"parse any PDF" fallback, because a wrong guess here is a compliance
document, not a cosmetic bug.

To add a new vendor:
  1. Get at least one real sample invoice PDF from them.
  2. Write parsers/<vendor_slug>.py exposing parse(pdf_path) -> (InvoiceHeader, [LineItem]),
     following the pattern in engel.py.
  3. Register it in VENDORS below.
"""

from . import engel

VENDORS = {
    "engel": {
        "label": "Engel GmbH (Germany)",
        "parser": engel,
        "available": True,
    },
    "janus": {
        "label": "Janus (Norway)",
        "parser": None,
        "available": False,
    },
    "ruskovilla": {
        "label": "Ruskovilla (Finland)",
        "parser": None,
        "available": False,
    },
}
