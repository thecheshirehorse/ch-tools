# Mailing List Cleaner

- This folder contains a browser-based HTML tool `clean_mailing_list.html` that performs mailing list cleaning client-side.

What the HTML does
- Accepts a CSV file (drag & drop via the file chooser) with columns including: `Customer Number`, `Customer Name`, `Address 1`, `Address 2`, `Email Address`.
- Runs the same cleaning steps as the Python script: remove blank rows, remove duplicate rows, remove rows with configured keywords/streets in Address 1, remove employee-tagged rows, strip certain name tags, move Address 2 into Address 1 when Address 1 is blank, clear Address 2 for PO Boxes, and deduplicate by Customer Number preferring rows with email.
- Shows a preview (first 100 rows) and allows downloading the cleaned CSV.

How to use
1. Open `clean_mailing_list.html` in a modern browser (double-click or open via your browser). No server required — it's pure client-side.
2. Click the file chooser and select your `mailing_list.csv` file.
3. Click Process. After it finishes you'll see the starting and final row counts and a preview.
4. Click Download Cleaned CSV to save `mailing_list_cleaned.csv`.

Notes and limitations
- The HTML CSV parser is a simple comma-split parser and assumes no embedded commas or quoted fields containing newlines. If your CSV contains complex quoted fields, open it in a spreadsheet and export a simplified CSV first, or use the original Python script which uses pandas and handles full CSV quoting.
- The filter keywords and patterns are defined near the top of `clean_mailing_list.html`. Edit them inline if you need different values.
- The HTML tool keeps all processing in your browser — no data is uploaded anywhere.
