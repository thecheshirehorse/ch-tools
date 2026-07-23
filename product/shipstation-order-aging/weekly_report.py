#!/usr/bin/env python3
"""
ShipStation Weekly Report
=========================
One-click companion to shipstation_fulfillment_dashboard.py. Reads the
ShipStation API key/secret from config.json (gitignored, never committed),
regenerates fulfillment_dashboard.html using the same fetch/build logic as
the interactive tool, and opens it so it's ready to attach to an email.

No email credentials are stored anywhere — whoever runs this sends the
report from their own already-logged-in email client.

Usage:
    python weekly_report.py
"""

import json
import os
import webbrowser
from datetime import datetime, timedelta

import shipstation_fulfillment_dashboard as dash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")


def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        config = json.load(f)
    missing = [
        k for k in ("shipstation_api_key", "shipstation_api_secret")
        if not config.get(k) or "PASTE_" in str(config.get(k))
    ]
    if missing:
        raise ValueError(f"config.json is missing/unfilled fields: {', '.join(missing)}")
    return config


def build_dashboard_html(config):
    api_key = config["shipstation_api_key"]
    api_secret = config["shipstation_api_secret"]
    sla_hours = config.get("sla_hours", 24)
    weeks = config.get("weeks", 1)

    print("Fetching warehouses and tags...")
    warehouses = dash.fetch_warehouses(api_key, api_secret)
    tag_catalog = {
        t["tagId"]: {"name": t.get("name") or f"Tag {t['tagId']}", "color": t.get("color") or "#999999"}
        for t in dash.fetch_tags(api_key, api_secret)
    }

    open_orders = []
    for status_val in dash.OPEN_STATUSES:
        def cb(n, total_pages, page, s=status_val):
            print(f"  Fetching open orders ({s})... {n} so far (page {page}/{total_pages})")
        open_orders.extend(dash.fetch_orders(api_key, api_secret, {"orderStatus": status_val}, progress_cb=cb))

    date_end = datetime.utcnow()
    date_start = date_end - timedelta(weeks=weeks)

    def cb2(n, total_pages, page):
        print(f"  Fetching shipment history... {n} orders so far (page {page}/{total_pages})")

    shipped_orders = dash.fetch_orders(api_key, api_secret, {
        "orderStatus": "shipped",
        "orderDateStart": date_start.strftime("%Y-%m-%d"),
        "orderDateEnd": date_end.strftime("%Y-%m-%d"),
    }, progress_cb=cb2)

    print("Building dashboard...")

    snapshot = dash.build_snapshot(open_orders, warehouses, sla_hours)
    history = dash.build_trend(shipped_orders, warehouses, sla_hours)

    payload = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "sla_hours": sla_hours,
        "weeks": weeks,
        "snapshot": snapshot,
        "history": history,
        "bucket_labels": [lb for lb, _, _ in dash.AGING_BUCKETS],
        "bucket_ranges": [[lo, hi] for _, lo, hi in dash.AGING_BUCKETS],
        "tag_catalog": tag_catalog,
    }

    html = dash.DASHBOARD_TEMPLATE.replace("__CHARTJS_JS__", dash.CHARTJS_JS).replace("__DATA_JSON__", json.dumps(payload))
    out_path = os.path.join(BASE_DIR, "fulfillment_dashboard.html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    return out_path, snapshot, len(open_orders), len(shipped_orders)


def main():
    config = load_config()
    html_path, snapshot, n_open, n_shipped = build_dashboard_html(config)
    print(f"[{datetime.now().isoformat()}] Report built: {html_path} "
          f"({n_open} open orders, {snapshot['total_open']} in snapshot, "
          f"{len(snapshot['breach_list'])} past SLA, {n_shipped} shipped orders analyzed).")
    if os.environ.get("CI"):
        return
    print("Attach this file to an email yourself to share it.")
    webbrowser.open(html_path)


if __name__ == "__main__":
    main()
