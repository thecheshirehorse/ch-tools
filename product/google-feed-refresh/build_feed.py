#!/usr/bin/env python3
"""
SFCC → Google Shopping Feed Builder

Merges a Salesforce Commerce Cloud catalog XML export and price book XML export
into a Google Shopping-compliant TSV for manual upload to Google Merchant Center.

Usage:
    python build_feed.py <catalog.xml> <pricebook.xml> [output.tsv]

Designed for: cheshirehorse.com (SFCC B2C Commerce)
"""

import xml.etree.ElementTree as ET
import csv
import re
import html
import sys
import os
import argparse
from collections import defaultdict

# ─── Site Configuration ──────────────────────────────────────────────────────

SITE_URL = "https://www.cheshirehorse.com"

# Image URL base path (hashless static URL — Google's crawler will resolve
# the real images from og:image tags on product pages within 24-72 hours)
IMAGE_BASE = "https://www.cheshirehorse.com/on/demandware.static/-/Sites-master-cheshirehorse/default/images/products"

# SFCC XML namespaces
NS_CAT = "{http://www.demandware.com/xml/impex/catalog/2006-10-31}"
NS_PB = "{http://www.demandware.com/xml/impex/pricebook/2006-10-31}"

# Price book IDs
LIST_PRICE_BOOK = "ch-list-prices"
SALE_PRICE_BOOKS = [
    "ch-consignment-demo-saddle-pricebook",
    "ch-closeout-pricebook",
]

# SFCC site ID (for site-specific flags)
SITE_ID = "CheshireHorse"


# ─── Helpers ─────────────────────────────────────────────────────────────────

def strip_html(text):
    """Remove HTML tags and decode entities."""
    if not text:
        return ""
    text = html.unescape(text)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    text = text.replace('\r', '').replace('\n', ' ')
    return text


def slugify(name):
    """Convert product name to URL slug."""
    s = name.lower()
    s = re.sub(r'[^a-z0-9]+', '-', s)
    s = s.strip('-')
    return s


def get_text(el, tag, ns=NS_CAT, lang="x-default"):
    """Get text from a localized element."""
    for child in el.findall(f"{ns}{tag}"):
        if child.get("{http://www.w3.org/XML/1998/namespace}lang") == lang:
            return child.text or ""
        if child.get("{http://www.w3.org/XML/1998/namespace}lang") is None and child.get("site-id") is None:
            return child.text or ""
    found = el.find(f"{ns}{tag}")
    if found is not None and found.get("site-id") is None:
        return found.text or ""
    return ""


def get_flag(el, tag, ns=NS_CAT):
    """Get boolean flag, preferring site-specific then generic."""
    for child in el.findall(f"{ns}{tag}"):
        if child.get("site-id") == SITE_ID:
            return child.text == "true"
    found = el.find(f"{ns}{tag}")
    if found is not None and found.get("site-id") is None:
        return found.text == "true"
    return False


def get_image_path(el, ns=NS_CAT):
    """Get the first large image path."""
    images = el.find(f"{ns}images")
    if images is None:
        return ""
    for ig in images.findall(f"{ns}image-group"):
        if ig.get("view-type") == "large":
            img = ig.find(f"{ns}image")
            if img is not None:
                return img.get("path", "")
    for ig in images.findall(f"{ns}image-group"):
        img = ig.find(f"{ns}image")
        if img is not None:
            return img.get("path", "")
    return ""


def get_custom_attr(el, attr_id, ns=NS_CAT):
    """Get a custom attribute value."""
    cas = el.find(f"{ns}custom-attributes")
    if cas is None:
        return ""
    for ca in cas.findall(f"{ns}custom-attribute"):
        if ca.get("attribute-id") == attr_id:
            values = ca.findall(f"{ns}value")
            if values:
                return values[0].text or ""
            return ca.text or ""
    return ""


def get_custom_attr_list(el, attr_id, ns=NS_CAT):
    """Get all values for a multi-value custom attribute."""
    cas = el.find(f"{ns}custom-attributes")
    if cas is None:
        return []
    for ca in cas.findall(f"{ns}custom-attribute"):
        if ca.get("attribute-id") == attr_id:
            values = ca.findall(f"{ns}value")
            if values:
                return [v.text for v in values if v.text]
            if ca.text:
                return [ca.text]
    return []


def get_variant_ids(el, ns=NS_CAT):
    """Get list of variant product IDs from a master product."""
    variations = el.find(f"{ns}variations")
    if variations is None:
        return []
    variants_el = variations.find(f"{ns}variants")
    if variants_el is None:
        return []
    return [v.get("product-id") for v in variants_el.findall(f"{ns}variant")]


def build_image_url(path):
    """Build full image URL from path."""
    if not path:
        return ""
    if path.startswith("/"):
        return f"{IMAGE_BASE}{path}"
    else:
        return f"{IMAGE_BASE}/{path}"


# ─── Shipping Surcharges (Zone B / mid-range) ────────────────────────────────
# Added to base shipping ($8 flat under $99, free over $99).
# Zone B is the middle ground — most customers are in the Northeast/mid-Atlantic.

OVERSIZE_SURCHARGE = {
    "Oversize Group 1": 6.50,
    "Oversize Group 2": 11.00,
    "Oversize Group 3": 15.50,
    "Oversize Group 4": 18.00,
    "Oversize Group 5": 27.50,
    "Oversize Group 6": 38.50,
    "Oversize Group 7": 55.00,
}

# Overweight surcharges by weight bracket (Zone B)
OVERWEIGHT_BRACKETS = [
    (5,   7.00),
    (10,  9.00),
    (15, 11.00),
    (20, 14.50),
    (25, 20.00),
    (30, 24.00),
    (35, 29.00),
    (40, 31.00),
    (45, 35.00),
    (50, 36.00),
    (55, 37.00),
    (60, 39.00),
    (65, 40.00),
    (70, 41.00),
]


def get_overweight_surcharge(weight_lbs):
    """Look up overweight surcharge by weight bracket."""
    if weight_lbs <= 0:
        return 0.00
    for max_weight, surcharge in OVERWEIGHT_BRACKETS:
        if weight_lbs <= max_weight:
            return surcharge
    # Over 70 lbs — no surcharge per ShipperHQ table (handled separately)
    return 0.00


# ─── Parsers ─────────────────────────────────────────────────────────────────

def parse_pricebooks(filepath):
    """Parse price book XML and return {pricebook_id: {product_id: price}}."""
    print("Parsing price books...")
    prices = {}
    context = ET.iterparse(filepath, events=("end",))
    current_pb_id = None

    for event, elem in context:
        tag = elem.tag.replace(NS_PB, "")

        if tag == "header":
            current_pb_id = elem.get("pricebook-id")
            if current_pb_id not in prices:
                prices[current_pb_id] = {}

        elif tag == "price-table" and current_pb_id:
            product_id = elem.get("product-id")
            amount_el = elem.find(f"{NS_PB}amount")
            if amount_el is not None and amount_el.text:
                try:
                    prices[current_pb_id][product_id] = float(amount_el.text)
                except ValueError:
                    pass
            elem.clear()

        elif tag == "pricebook":
            current_pb_id = None
            elem.clear()

    for pb_id, pb_prices in prices.items():
        print(f"  Price book '{pb_id}': {len(pb_prices)} entries")

    return prices


def parse_catalog(filepath):
    """Parse catalog XML using iterparse for memory efficiency."""
    print("Parsing catalog...")
    products = {}
    count = 0

    for event, elem in ET.iterparse(filepath, events=("end",)):
        if elem.tag != f"{NS_CAT}product":
            continue

        count += 1
        if count % 10000 == 0:
            print(f"  Processed {count} products...")

        pid = elem.get("product-id")
        if not pid:
            elem.clear()
            continue

        # Parse shipping weight
        ship_weight_str = get_custom_attr(elem, "shipWeight")
        try:
            ship_weight = float(ship_weight_str) if ship_weight_str else 0.0
        except ValueError:
            ship_weight = 0.0

        # Parse ShipperHQ shipping groups (multi-value)
        shipping_groups = get_custom_attr_list(elem, "shipperHQShippingGroups")

        product = {
            "id": pid,
            "name": get_text(elem, "display-name"),
            "short_desc": strip_html(get_text(elem, "short-description")),
            "long_desc": strip_html(get_text(elem, "long-description")),
            "brand": get_text(elem, "brand") or "",
            "upc": get_text(elem, "upc") or "",
            "online": get_flag(elem, "online-flag"),
            "available": get_flag(elem, "available-flag"),
            "image_path": get_image_path(elem),
            "variant_ids": get_variant_ids(elem),
            "color": (get_custom_attr(elem, "color")
                      or get_custom_attr(elem, "color_horse_clothing") or ""),
            "size": (get_custom_attr(elem, "size")
                     or get_custom_attr(elem, "size_footwear")
                     or get_custom_attr(elem, "size_apparel")
                     or get_custom_attr(elem, "size_horse_clothing") or ""),
            "manufacturer_sku": get_text(elem, "manufacturer-sku") or "",
            "ship_weight": ship_weight,
            "shipping_groups": shipping_groups,
        }

        cc = elem.find(f"{NS_CAT}classification-category")
        if cc is not None:
            product["category"] = cc.text or ""
        else:
            product["category"] = ""

        products[pid] = product
        elem.clear()

    print(f"  Total products parsed: {count}")
    return products


# ─── Feed Builder ────────────────────────────────────────────────────────────

def build_feed(catalog_file, pricebook_file, output_file):
    """Main feed generation logic."""

    # Parse inputs
    prices = parse_pricebooks(pricebook_file)
    list_prices = prices.get(LIST_PRICE_BOOK, {})
    sale_price_maps = [prices.get(pb, {}) for pb in SALE_PRICE_BOOKS]

    products = parse_catalog(catalog_file)

    # Build master → variant relationships
    master_of = {}
    for pid, prod in products.items():
        for vid in prod["variant_ids"]:
            master_of[vid] = pid

    masters = {pid for pid, prod in products.items() if prod["variant_ids"]}
    print(f"\nMasters: {len(masters)}")
    print(f"Variants: {len(master_of)}")
    print(f"Standalone products: {len(products) - len(masters) - len(master_of)}")

    # Build feed rows
    feed_rows = []
    skipped = defaultdict(int)

    for pid, prod in products.items():
        # Skip masters — we submit at variant level
        if pid in masters:
            skipped["is_master"] += 1
            continue

        master_id = master_of.get(pid)
        master = products.get(master_id) if master_id else None

        # Inherit from master where needed
        name = prod["name"] or (master["name"] if master else "")
        short_desc = prod["short_desc"] or (master["short_desc"] if master else "")
        brand = prod["brand"] or (master["brand"] if master else "")
        image_path = prod["image_path"] or (master["image_path"] if master else "")
        category = prod["category"] or (master["category"] if master else "")
        upc = prod["upc"]

        is_online = prod["online"]
        is_available = prod["available"]

        # Pricing: list price, then check sale price books
        list_price = list_prices.get(pid)
        if list_price is None and master_id:
            list_price = list_prices.get(master_id)

        sale_price = None
        for sp_map in sale_price_maps:
            sale_price = sp_map.get(pid)
            if sale_price:
                break
        if sale_price is None and master_id:
            for sp_map in sale_price_maps:
                sale_price = sp_map.get(master_id)
                if sale_price:
                    break

        # Validation
        if not name:
            skipped["no_name"] += 1
            continue
        if not is_online:
            skipped["not_online"] += 1
            continue
        if not is_available:
            skipped["not_available"] += 1
            continue
        if list_price is None and sale_price is None:
            skipped["no_price"] += 1
            continue
        if not image_path:
            skipped["no_image"] += 1
            continue

        effective_price = list_price if list_price is not None else sale_price
        effective_sale = sale_price if (sale_price and list_price and sale_price < list_price) else None

        # Description
        description = short_desc or name
        if len(description) > 5000:
            description = description[:4997] + "..."

        # Title with variant attributes
        title = name
        variant_attrs = []
        if prod["color"]:
            variant_attrs.append(prod["color"])
        if prod["size"]:
            variant_attrs.append(prod["size"])
        if variant_attrs:
            title = f"{name} - {' / '.join(variant_attrs)}"
        if len(title) > 150:
            title = title[:147] + "..."

        # Product URL
        url_pid = master_id or pid
        link = f"{SITE_URL}/p/{slugify(name)}/{url_pid}.html"

        # Image URL
        image_link = build_image_url(image_path)

        # GTIN
        gtin = upc if upc and upc != "0" else ""

        # Shipping: base rate + surcharges for overweight/oversize
        # Inherit shipping groups and weight from master if variant doesn't have them
        shipping_groups = prod["shipping_groups"] or (master["shipping_groups"] if master else [])
        ship_weight = prod["ship_weight"] or (master["ship_weight"] if master else 0.0)

        # Base shipping: free over $99, $8 flat rate under
        if effective_price >= 99:
            base_shipping = 0.00
        else:
            base_shipping = 8.00

        # Calculate surcharges — take the highest applicable one
        surcharge = 0.00
        for group in shipping_groups:
            if group in OVERSIZE_SURCHARGE:
                surcharge = max(surcharge, OVERSIZE_SURCHARGE[group])
            elif group == "Overweight" and ship_weight > 0:
                surcharge = max(surcharge, get_overweight_surcharge(ship_weight))

        total_shipping = base_shipping + surcharge
        shipping = f"US:::{total_shipping:.2f} USD"

        row = {
            "id": pid,
            "title": title,
            "description": description,
            "link": link,
            "image_link": image_link,
            "availability": "in_stock" if is_available else "out_of_stock",
            "price": f"{effective_price:.2f} USD",
            "sale_price": f"{effective_sale:.2f} USD" if effective_sale else "",
            "shipping": shipping,
            "brand": brand,
            "gtin": gtin,
            "mpn": prod["manufacturer_sku"] or pid,
            "condition": "new",
            "item_group_id": master_id if master_id else "",
            "color": prod["color"],
            "size": prod["size"],
            "product_type": category.replace("-", " > ").replace("_", " ") if category else "",
        }

        feed_rows.append(row)

    # Report
    print(f"\n=== Feed Summary ===")
    print(f"Total feed rows: {len(feed_rows)}")
    print(f"\nSkipped:")
    for reason, count in sorted(skipped.items(), key=lambda x: -x[1]):
        print(f"  {reason}: {count}")

    if not feed_rows:
        print("ERROR: No rows to write!")
        sys.exit(1)

    # Write TSV
    fieldnames = [
        "id", "title", "description", "link", "image_link",
        "availability", "price", "sale_price", "shipping", "brand", "gtin",
        "mpn", "condition", "item_group_id", "color", "size",
        "product_type"
    ]

    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        writer.writerows(feed_rows)

    size_mb = round(os.path.getsize(output_file) / 1024 / 1024, 1)
    print(f"\nFeed written to: {output_file}")
    print(f"File size: {size_mb} MB")


# ─── CLI ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Build a Google Shopping feed from SFCC catalog + price book exports."
    )
    parser.add_argument("catalog", help="Path to SFCC catalog XML export")
    parser.add_argument("pricebook", help="Path to SFCC price book XML export")
    parser.add_argument(
        "output",
        nargs="?",
        default="google_shopping_feed.tsv",
        help="Output TSV path (default: google_shopping_feed.tsv)"
    )
    args = parser.parse_args()

    build_feed(args.catalog, args.pricebook, args.output)
