#!/usr/bin/env python3
"""
Cheshire Horse - Rewards Account Creator
Local desktop app for importing Google Form customer data into Epicor Eagle POS.
Includes pipeline tracker for PSM (Pet Store Marketer) workflow.
"""

import os
import json
import csv
import io
import re
import webbrowser
import threading
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_file

app = Flask(__name__)

DATA_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(DATA_DIR, "cheshire_eagle_data.json")

INITIAL_DATA = {
    "nextNumbers": {"store3": 8051, "store5": 8085},
    "queue": [],
    "batches": [],
}

STAGES = [
    {"id": "eagle", "label": "Import to Eagle", "color": "#2d5a27"},
    {"id": "psm_waiting", "label": "Waiting for PSM Sync", "color": "#b8860b"},
    {"id": "psm_action", "label": "Add Interests & Points", "color": "#1a4a7a"},
    {"id": "complete", "label": "Complete", "color": "#666"},
]

# --- Data Persistence ---

def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r') as f:
                data = json.load(f)
            for key in INITIAL_DATA:
                if key not in data:
                    data[key] = INITIAL_DATA[key]
            return data
        except (json.JSONDecodeError, IOError):
            pass
    return json.loads(json.dumps(INITIAL_DATA))

def save_data(data):
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=2)

# --- Formatting ---

def fmt_date(d):
    if not d or str(d).strip() == "":
        return ""
    d = str(d).strip()
    if re.match(r'^\d{1,2}/\d{1,2}/\d{2}$', d):
        parts = d.split('/')
        return f"{parts[0].zfill(2)}/{parts[1].zfill(2)}/{parts[2]}"
    if re.match(r'^\d{1,2}/\d{1,2}/\d{4}$', d):
        parts = d.split('/')
        return f"{parts[0].zfill(2)}/{parts[1].zfill(2)}/{parts[2][2:]}"
    if re.match(r'^\d{4}-\d{1,2}-\d{1,2}', d):
        parts = d[:10].split('-')
        return f"{parts[1].zfill(2)}/{parts[2].zfill(2)}/{parts[0][2:]}"
    for fmt in ('%m/%d/%Y %H:%M:%S', '%m/%d/%Y', '%Y-%m-%d', '%m/%d/%y'):
        try:
            dt = datetime.strptime(d, fmt)
            return dt.strftime('%m/%d/%y')
        except ValueError:
            continue
    return ""

def fmt_today():
    return datetime.now().strftime('%m/%d/%y')

def pad_zip(z):
    return re.sub(r'\D', '', str(z)).zfill(5)[:5]

def clean_phone(p):
    return re.sub(r'\D', '', str(p))[:12]

def truncate(s, n):
    return str(s).upper()[:n] if s else ""

# --- Parsing ---

def parse_csv_data(text):
    lines = text.strip().replace('\r\n', '\n').replace('\r', '\n').split('\n')
    lines = [l for l in lines if l.strip()]
    if len(lines) < 2:
        return []
    is_tab = '\t' in lines[0]
    if is_tab:
        headers = [h.strip() for h in lines[0].split('\t')]
        rows = []
        for line in lines[1:]:
            values = [v.strip() for v in line.split('\t')]
            rows.append(dict(zip(headers, values)))
    else:
        reader = csv.DictReader(io.StringIO(text))
        rows = list(reader)
    return rows

def find_field(row, *fragments):
    for key in row:
        kl = key.lower()
        for frag in fragments:
            if frag.lower() in kl:
                val = row[key]
                if val and str(val).strip():
                    return str(val).strip()
    return ""

def find_exact(row, name):
    clean = re.sub(r'[^a-z0-9]', '', name.lower())
    for key in row:
        if re.sub(r'[^a-z0-9]', '', key.lower()) == clean:
            val = row[key]
            if val and str(val).strip():
                return str(val).strip()
    return ""

def parse_row(row):
    first = find_exact(row, "firstname") or find_field(row, "first name")
    last = find_exact(row, "lastname") or find_field(row, "last name")
    if not first and not last:
        cn = find_exact(row, "customername") or find_field(row, "customer name")
        if cn:
            parts = cn.strip().split()
            first = parts[0] if parts else ""
            last = " ".join(parts[1:]) if len(parts) > 1 else ""
    if not first and not last:
        return None

    store = find_field(row, "store account") or find_exact(row, "storeopened") or find_field(row, "store opened") or "3"
    store = re.sub(r'\D', '', str(store)) or "3"

    return {
        "store": store,
        "firstName": first,
        "lastName": last,
        "address1": find_exact(row, "streetaddress") or find_field(row, "street address") or find_exact(row, "address1") or find_field(row, "address 1") or "",
        "address2": find_field(row, "apt") or find_exact(row, "address2") or find_field(row, "address 2") or "",
        "city": find_field(row, "city") or "",
        "state": find_field(row, "state") or "",
        "zip": find_field(row, "zip") or "",
        "phone": find_field(row, "phone number") or find_field(row, "phone") or "",
        "email": find_field(row, "email address") or "",
        "emailUpdates": find_field(row, "updates and coupons") or find_field(row, "email updates") or "Yes",
        "dob": find_field(row, "date of birth") or find_exact(row, "birthdate") or "",
        "existingCustNum": find_exact(row, "customernumber") or find_field(row, "customer number") or "",
        "categoryPlan": find_exact(row, "categoryplan") or find_field(row, "category plan") or "",
        "dateOpened": find_exact(row, "dateaccountopened") or find_field(row, "date account opened") or "",
        "interests": find_field(row, "interests") or "",
        "invoice": find_field(row, "invoice") or "",
        "notes": find_field(row, "notes") or find_field(row, "comments") or "",
    }

def build_customer(raw, cust_num):
    store = raw["store"]
    return {
        "customerNumber": cust_num,
        "customerName": truncate(f"{raw['firstName']} {raw['lastName']}", 30),
        "sortName": truncate(f"QQ{raw['lastName']}", 10),
        "address1": truncate(raw["address1"], 30),
        "address2": truncate(raw["address2"], 30),
        "city": truncate(raw["city"], 15),
        "state": truncate(raw["state"], 2),
        "zip": pad_zip(raw["zip"]),
        "phone": clean_phone(raw["phone"]),
        "categoryPlan": raw["categoryPlan"] or ("SALE" if store == "3" else "SALE5"),
        "storeOpened": store,
        "dateAccountOpened": raw["dateOpened"] or fmt_today(),
        "birthdate": fmt_date(raw["dob"]) if raw["dob"] else "",
        "userCode4": store,
        "email": raw.get("email", ""),
        "emailUpdates": raw.get("emailUpdates", "Yes"),
        "contactName": truncate(f"{raw['firstName']} {raw['lastName']}", 20),
        "firstName": raw["firstName"],
        "lastName": raw["lastName"],
        "interests": raw.get("interests", ""),
        "invoice": raw.get("invoice", ""),
        "notes": raw.get("notes", ""),
    }

# --- CSV Generation ---

def gen_customer_csv(customers):
    h = "Customer Number,Customer Name,Sort Name,Address 1,Address 2,City,State,Zip Code,Phone,Category Plan,Store Opened,Date Account Opened,Birthdate,User Code 4"
    lines = [h] + [",".join([c["customerNumber"],c["customerName"],c["sortName"],c["address1"],c["address2"],c["city"],c["state"],c["zip"],c["phone"],c["categoryPlan"],c["storeOpened"],c["dateAccountOpened"],c["birthdate"],c["userCode4"]]) for c in customers]
    return "\r\n".join(lines) + "\r\n"

def gen_contacts_csv(customers):
    lines = []
    for c in customers:
        if not c.get("email"):
            continue
        oo = "Y" if c.get("emailUpdates") == "No" else "N"
        lines.append(",".join([c["customerNumber"],"0",c["contactName"],"Y","","","","",c["email"],"","","","","Y",oo,"",""]))
    return "\r\n".join(lines) + "\r\n"

# --- Routes ---

@app.route('/')
def index():
    return render_template('index.html', stages=STAGES)

@app.route('/api/data')
def get_data():
    return jsonify(load_data())

@app.route('/api/import', methods=['POST'])
def import_data():
    data = load_data()
    rows = parse_csv_data(request.json.get('text', ''))
    if not rows:
        return jsonify({"added": 0, "skipped": 0})
    nums = data["nextNumbers"]
    added = skipped = 0
    for row in rows:
        p = parse_row(row)
        if not p:
            skipped += 1
            continue
        if p["existingCustNum"]:
            cn = p["existingCustNum"]
        else:
            sk = "store5" if p["store"] == "5" else "store3"
            pfx = "*5" if p["store"] == "5" else "*9"
            cn = f"{pfx}{nums[sk]}"
            nums[sk] += 1
        data["queue"].append(build_customer(p, cn))
        added += 1
    data["nextNumbers"] = nums
    save_data(data)
    return jsonify({"added": added, "skipped": skipped})

@app.route('/api/queue/<int:idx>', methods=['DELETE'])
def delete_queue(idx):
    data = load_data()
    if 0 <= idx < len(data["queue"]):
        data["queue"].pop(idx)
        save_data(data)
    return jsonify({"ok": True})

@app.route('/api/queue/<int:idx>', methods=['PUT'])
def update_queue(idx):
    data = load_data()
    if 0 <= idx < len(data["queue"]):
        u = request.json
        c = data["queue"][idx]
        first = u.get("firstName", c.get("firstName", ""))
        last = u.get("lastName", c.get("lastName", ""))
        c["customerName"] = truncate(f"{first} {last}", 30)
        c["sortName"] = truncate(f"QQ{last}", 10)
        c["contactName"] = truncate(f"{first} {last}", 20)
        for k in ["address1","address2","city","state","zip","phone","email","interests","invoice","notes"]:
            if k in u:
                c[k] = u[k]
        if "dob" in u:
            c["birthdate"] = fmt_date(u["dob"])
        c["firstName"] = first
        c["lastName"] = last
        c["address1"] = truncate(c["address1"], 30)
        c["address2"] = truncate(c["address2"], 30)
        c["city"] = truncate(c["city"], 15)
        c["state"] = truncate(c["state"], 2)
        c["zip"] = pad_zip(c["zip"])
        c["phone"] = clean_phone(c["phone"])
        data["queue"][idx] = c
        save_data(data)
    return jsonify({"ok": True})

@app.route('/api/queue/clear', methods=['POST'])
def clear_queue():
    """Discard the entire queue without creating a batch or reserving numbers"""
    data = load_data()
    data["queue"] = []
    save_data(data)
    return jsonify({"ok": True})

@app.route('/api/queue/to-batch', methods=['POST'])
def queue_to_batch():
    """Move current queue into a new batch in the pipeline"""
    data = load_data()
    if not data["queue"]:
        return jsonify({"error": "Queue is empty"})
    batch = {
        "id": datetime.now().strftime("%Y%m%d_%H%M%S"),
        "date": datetime.now().strftime("%m/%d/%y"),
        "stage": "eagle",
        "customers": data["queue"],
        "customerCount": len(data["queue"]),
    }
    data["batches"].append(batch)
    data["queue"] = []
    save_data(data)
    return jsonify({"ok": True, "batchId": batch["id"]})

@app.route('/api/batches/<batch_id>/advance', methods=['POST'])
def advance_batch(batch_id):
    data = load_data()
    stage_ids = [s["id"] for s in STAGES]
    for b in data["batches"]:
        if b["id"] == batch_id:
            idx = stage_ids.index(b["stage"])
            if idx < len(stage_ids) - 1:
                b["stage"] = stage_ids[idx + 1]
            save_data(data)
            return jsonify({"ok": True, "newStage": b["stage"]})
    return jsonify({"error": "Batch not found"}), 404

@app.route('/api/batches/<batch_id>/move', methods=['POST'])
def move_batch(batch_id):
    data = load_data()
    target = request.json.get("stage")
    for b in data["batches"]:
        if b["id"] == batch_id:
            b["stage"] = target
            save_data(data)
            return jsonify({"ok": True})
    return jsonify({"error": "Batch not found"}), 404

@app.route('/api/batches/<batch_id>', methods=['DELETE'])
def delete_batch(batch_id):
    data = load_data()
    data["batches"] = [b for b in data["batches"] if b["id"] != batch_id]
    save_data(data)
    return jsonify({"ok": True})

@app.route('/api/batches/<batch_id>/customer/<int:cidx>/done', methods=['POST'])
def toggle_customer_done(batch_id, cidx):
    data = load_data()
    for b in data["batches"]:
        if b["id"] == batch_id:
            if 0 <= cidx < len(b["customers"]):
                b["customers"][cidx]["psmDone"] = not b["customers"][cidx].get("psmDone", False)
                save_data(data)
                return jsonify({"ok": True, "done": b["customers"][cidx]["psmDone"]})
    return jsonify({"error": "Not found"}), 404

@app.route('/api/numbers', methods=['PUT'])
def set_numbers():
    data = load_data()
    n = request.json
    if "store3" in n: data["nextNumbers"]["store3"] = int(n["store3"])
    if "store5" in n: data["nextNumbers"]["store5"] = int(n["store5"])
    save_data(data)
    return jsonify(data["nextNumbers"])

@app.route('/api/export/customers')
def export_customers():
    data = load_data()
    return send_file(io.BytesIO(gen_customer_csv(data["queue"]).encode()), mimetype='text/csv', as_attachment=True, download_name='customer_import.csv')

@app.route('/api/export/contacts')
def export_contacts():
    data = load_data()
    return send_file(io.BytesIO(gen_contacts_csv(data["queue"]).encode()), mimetype='text/csv', as_attachment=True, download_name='contacts_import.csv')

@app.route('/api/export/customers/preview')
def preview_customers():
    return gen_customer_csv(load_data()["queue"]), 200, {'Content-Type': 'text/plain'}

@app.route('/api/export/contacts/preview')
def preview_contacts():
    return gen_contacts_csv(load_data()["queue"]), 200, {'Content-Type': 'text/plain'}

def open_browser():
    webbrowser.open('http://localhost:5000')

if __name__ == '__main__':
    print(f"\n  Cheshire Horse - Rewards Account Creator")
    print(f"  Data file: {DATA_FILE}")
    print(f"  Open http://localhost:5000 in your browser\n")
    threading.Timer(1.5, open_browser).start()
    app.run(host='127.0.0.1', port=5000, debug=False)
