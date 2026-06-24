# Cheshire Horse — Rewards Account Creator

A local desktop tool that transforms Google Form customer registration data into Epicor Eagle POS-ready CSV files for batch customer import.

## What It Does

Cashiers fill out a Google Form when customers sign up for a rewards account. This tool takes that form data, formats it to Eagle's exact specifications, auto-assigns customer numbers, and generates two CSV files:

1. **Customer Import CSV** — for Eagle's Customer Import Designer (customer records)
2. **Contacts Import CSV** — for Eagle's Customer Contacts Import (email addresses)

All data stays local. Nothing goes to the cloud.

## Setup

### Requirements

- **Python 3.8+** — [Download here](https://www.python.org/downloads/). Check **"Add Python to PATH"** during install.
- **Flask** — Installed automatically on first run.

### Installation

1. Download or clone this repo
2. Double-click **`start_eagle_import.bat`**
3. The app opens in your browser at `http://localhost:5000`

That's it. Flask installs itself on first launch if needed.

## Usage

### Step 1: Import Data

Paste data directly from Google Sheets (tab-separated) or upload a CSV export. The tool auto-detects the format and matches columns by header name — column order doesn't matter.

Accepts two input formats:
- **Raw Google Form responses** — First Name, Last Name as separate columns
- **Pre-formatted Eagle export** — Customer Name combined, customer numbers already assigned

### Step 2: Review

Verify all customers in a table view. Edit any field inline or remove entries before exporting. All Eagle formatting is applied automatically:

- Names uppercased
- Sort Name generated as `QQ` + last name (max 10 chars)
- Zip codes padded with leading zeros
- Phone numbers stripped to digits only
- Dates formatted as `mm/dd/yy` (Eagle rejects `mm/dd/yyyy`)
- All fields truncated to Eagle's max character limits

### Step 3: Export

Download both CSV files with one click each:

- **Customer Import CSV** → Open in Eagle's Customer Import Designer, load your saved map, verify, import
- **Contacts Import CSV** → Save to `C:\3apps\temp\`, open Customer Contacts Import Setup in Eagle, select file, import

**Always run the Customer Import before the Contacts Import** — customers must exist in Eagle before contacts can be added.

## Customer Number Assignment

Numbers auto-increment per store and persist between sessions:

| Store | Location | Prefix | Example |
|-------|----------|--------|---------|
| Store 3 | Swanzey, NH | `*9` | `*98051`, `*98052`, `*98053`... |
| Store 5 | Saratoga, NY | `*5` | `*58085`, `*58086`, `*58087`... |

Click the counter boxes in the header bar to manually adjust starting numbers if they get out of sync with Eagle.

## Eagle Import Designer Map

The Customer Import CSV has 14 columns mapped to these positions:

| Position | Eagle Field |
|----------|------------|
| 1 | Customer Number |
| 2 | Customer Name |
| 3 | Sort Name |
| 4 | Address 1 |
| 5 | Address 2 |
| 6 | City |
| 7 | State |
| 8 | Zip Code |
| 9 | Phone |
| 10 | Category Plan |
| 11 | Store Opened |
| 12 | Date Account Opened |
| 13 | Birthdate |
| 14 | User Code 4 |

### Constants (set in Eagle Map Field, not in CSV)

| Eagle Field | Value |
|------------|-------|
| Credit Limit | 1 |
| Terms Code | C |
| Taxable | Y |
| User Code 2 | 1 |
| Balance Method | O |
| Charge Allowed | N |
| Std Sell Price | R |
| Finance Charges | Y |
| Transfer to Store | N |
| Print Statements | N |
| Check Allowed | Y |
| Credit A/R Only | N |
| Keep Dept. History | N |
| Print Invoices | N |
| PO Required | N |

## Data Storage

All data is stored in `cheshire_eagle_data.json` in the same folder as `app.py`. This file contains:

- Next customer numbers for each store
- Current queue of customers waiting to be exported
- Import history log

Back up this file by copying it. Restore by replacing it.

**⚠️ This file contains real customer PII (names, addresses, phone numbers) once the tool has been used.** The copy currently committed in this repo is not empty — it has live customer records in its batch history. Treat it the same as any other customer data export: don't commit real customer data to a shared/public repo. Consider adding `cheshire_eagle_data.json` to `.gitignore` and keeping backups somewhere access-controlled instead.

## Known stray files

- A duplicate `index.html` exists at the top level of this folder, identical to `templates/index.html` (the one Flask actually serves). Safe to delete the top-level copy.
- `__pycache__/app.cpython-312.pyc` is a compiled Python cache artifact and shouldn't be committed — safe to delete and add `__pycache__/` to `.gitignore`.

## Google Form Setup

The Google Form ("The Cheshire Horse Rewards Application v2") collects:

| Field | Required |
|-------|----------|
| Store Account Opened In (3 or 5) | Yes |
| First Name | Yes |
| Last Name | Yes |
| Street Address | Yes |
| Apt/Suite/Unit | No |
| City | Yes |
| State (dropdown) | Yes |
| Zip Code | Yes |
| Phone Number (10 digits) | Yes |
| Email Address | No |
| Email updates & coupons? (Yes/No) | Yes |
| Date of Birth | No |

## File Structure

```
cheshire-eagle-import/
├── app.py                      # Flask app + all business logic
├── templates/
│   └── index.html              # Web UI (single page)
├── cheshire_eagle_data.json    # Persistent data (auto-created)
├── start_eagle_import.bat      # Windows launcher (double-click)
└── README.md
```

## Troubleshooting

**"Python is not recognized"** — Reinstall Python from python.org and check **"Add Python to PATH"** during install. Restart Command Prompt after.

**Port 5000 already in use** — Another app is using port 5000. Close it, or edit `app.py` and change `port=5000` to another port like `port=5050`.

**Customer numbers out of sync with Eagle** — Click the counter boxes in the header to manually set the next numbers to match what Eagle expects.

**Zip codes losing leading zeros** — This tool handles it automatically. If you see `3431` instead of `03431` in the CSV, the input data lost the zeros before reaching the tool. The tool pads all zips to 5 digits.

**Dates rejected by Eagle** — Eagle requires `mm/dd/yy` (2-digit year). The tool converts automatically, but if you manually enter dates, use that format.
