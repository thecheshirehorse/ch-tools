"""
Pull Shipping-tab metrics for the Website Metrics dashboard from ShipStation.

Computes the 7 SHIPPING_FIELDS values (ordersShipped, orderSales,
shippingCollected, shippingCost, insuranceCost, weightShippedOz,
itemsShipped) for one or more calendar months, by joining ShipStation's
/shipments (for shipDate, weight, shipmentCost, insuranceCost, voided) with
/orders (for orderTotal, shippingAmount, items, storeId) via v1 API.

Reuses the ShipStation v1 API key/secret already configured for the RPH/
order-aging tool at product/shipstation-order-aging/config.json.

Scoping, validated against the already-known March 2026 numbers in
index.html's SEED_DATA:
  - Filtered to storeId 221388 ("SFCC Production" / Salesforce Commerce
    Cloud = cheshirehorse.com). The same ShipStation account also handles
    a Swanzey in-store channel and two unrelated businesses (Crafty Ponies
    USA, Prichard Supply) sharing the account -- those must be excluded or
    every number is inflated ~5-8%.
  - Excludes voided shipments (a purchased-then-voided label isn't a real
    outbound shipment).
  - Excludes orders tagged "In-Store PickUp" (tag 75027) or "In-Store
    Pickup Never Picked up" (tag 69330). Cheshire Horse selects FedEx as
    the carrier for these even though nothing actually ships, which adds a
    real (fake) shipmentCost with zero offsetting shippingAmount -- as of
    June 2026 this was 155 of 1,454 "orders shipped" (10.7%) and $1,654.56
    of the month's $22,060.92 shippingCost (7.5%), overstating shipping
    loss. ShipStation's tagId filter on /orders doesn't work (same
    silent-ignore behavior as its date filters), so this is applied
    client-side against each order's tagIds array.

Accuracy after that scoping fix (validated against March 2026, which was
manually entered from ShipStation's Reports UI feature -- confirmed to have
no API equivalent in v1 or v2, so this is the closest automatable match):
  - shippingCollected, shippingCost, weightShippedOz, itemsShipped: match
    within ~0.05% (functionally exact).
  - ordersShipped, orderSales: best-effort, ran about 1-2% high in the
    March validation and the exact discrepancy wasn't identified (tried
    orderTotal, amountPaid, and orderTotal-minus-tax-and-shipping as
    candidates for orderSales; none matched precisely). Spot-check these
    two after import.

Usage:
    python pull_shipping_metrics.py 2026-04 2026-05 2026-06
    python pull_shipping_metrics.py 2026-04   # single month

Prints the computed values as JSON (one object per month, keyed by
"YYYY-MM") for review -- it does NOT write to index.html. Pipe the
reviewed output into merge_shipping_metrics.py to actually splice it in.
"""

import base64
import calendar
import json
import sys
import time
from pathlib import Path

import requests

CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / "product" / "shipstation-order-aging" / "config.json"
API_BASE = "https://ssapi.shipstation.com"
WEBSITE_STORE_ID = 221388  # "SFCC Production" (Salesforce Commerce Cloud) = cheshirehorse.com
ISPU_TAG_IDS = {75027, 69330}  # "In-Store PickUp", "In-Store Pickup Never Picked up"


def load_credentials():
    if not CONFIG_PATH.exists():
        raise SystemExit(
            f"Missing {CONFIG_PATH}. This script reuses the ShipStation v1 credentials "
            "already configured for the order-aging tool -- set that up first."
        )
    cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    return cfg["shipstation_api_key"], cfg["shipstation_api_secret"]


def make_session(api_key, api_secret):
    creds = base64.b64encode(f"{api_key}:{api_secret}".encode()).decode()
    session = requests.Session()
    session.headers.update({"Authorization": f"Basic {creds}", "Content-Type": "application/json"})
    return session


def ss_get(session, path, params=None):
    for _ in range(6):
        r = session.get(API_BASE + path, params=params, timeout=30)
        if r.status_code == 429:
            wait = int(r.headers.get("X-Rate-Limit-Reset", 5)) + 1
            time.sleep(wait)
            continue
        r.raise_for_status()
        return r.json()
    raise RuntimeError("rate limited too many times")


def fetch_all(session, path, params_base, list_key):
    page = 1
    out = []
    while True:
        params = dict(params_base)
        params["page"] = page
        params["pageSize"] = 500
        data = ss_get(session, path, params)
        out.extend(data[list_key])
        if page >= data["pages"]:
            break
        page += 1
        time.sleep(0.25)
    return out


def month_bounds(month_str):
    year, month = (int(x) for x in month_str.split("-"))
    last_day = calendar.monthrange(year, month)[1]
    return f"{year:04d}-{month:02d}-01", f"{year:04d}-{month:02d}-{last_day:02d}"


def pull_month(session, month_str):
    start, end = month_bounds(month_str)

    shipments = fetch_all(session, "/shipments", {"shipDateStart": start, "shipDateEnd": end}, "shipments")
    non_voided = [s for s in shipments if not s.get("voided")]

    # orders are looked up by a window wider than the ship-date range, since an
    # order can be placed several days before it actually ships
    order_window_start, _ = month_bounds(month_str)
    order_window_end, _ = month_bounds(month_str)
    # widen by ~2 weeks on each side (string math would be wrong across month/year
    # boundaries, so just walk via the datetime module)
    from datetime import datetime, timedelta

    start_dt = datetime.strptime(start, "%Y-%m-%d") - timedelta(days=14)
    end_dt = datetime.strptime(end, "%Y-%m-%d") + timedelta(days=14)
    orders = fetch_all(
        session, "/orders",
        {"orderDateStart": start_dt.strftime("%Y-%m-%d"), "orderDateEnd": end_dt.strftime("%Y-%m-%d")},
        "orders",
    )
    orders_by_id = {o["orderId"]: o for o in orders}

    n = 0
    sum_order_total = sum_shipping_amount = 0.0
    sum_shipment_cost = sum_insurance_cost = sum_weight = 0.0
    sum_items_qty = 0
    unmatched = 0

    for s in non_voided:
        o = orders_by_id.get(s["orderId"])
        if not o or o.get("advancedOptions", {}).get("storeId") != WEBSITE_STORE_ID:
            if not o:
                unmatched += 1
            continue
        if ISPU_TAG_IDS.intersection(o.get("tagIds") or []):
            continue
        n += 1
        sum_shipment_cost += s.get("shipmentCost") or 0.0
        sum_insurance_cost += s.get("insuranceCost") or 0.0
        w = s.get("weight") or {}
        if w.get("units") == "ounces":
            sum_weight += w.get("value") or 0.0
        elif w.get("units") == "pounds":
            sum_weight += (w.get("value") or 0.0) * 16
        sum_order_total += o.get("orderTotal") or 0.0
        sum_shipping_amount += o.get("shippingAmount") or 0.0
        sum_items_qty += sum((it.get("quantity") or 0) for it in (o.get("items") or []))

    return {
        "ordersShipped": n,
        "orderSales": round(sum_order_total, 2),
        "shippingCollected": round(sum_shipping_amount, 2),
        "shippingCost": round(sum_shipment_cost, 2),
        "insuranceCost": round(sum_insurance_cost, 2),
        "weightShippedOz": round(sum_weight),
        "itemsShipped": sum_items_qty,
    }, unmatched, len(non_voided)


def main():
    months = sys.argv[1:]
    if not months:
        print(__doc__)
        sys.exit(1)

    api_key, api_secret = load_credentials()
    session = make_session(api_key, api_secret)

    result = {}
    for month_str in months:
        print(f"Pulling {month_str}...", file=sys.stderr)
        values, unmatched, non_voided_count = pull_month(session, month_str)
        if unmatched:
            print(
                f"  note: {unmatched}/{non_voided_count} non-voided shipments had no matching "
                "order in the fetch window (unlikely to affect totals materially)", file=sys.stderr
            )
        result[month_str] = values
        print(f"  {json.dumps(values)}", file=sys.stderr)

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
