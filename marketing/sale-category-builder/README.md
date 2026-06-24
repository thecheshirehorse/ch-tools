# LP Sale Category Builder

A no-install browser tool for combining SFCC category exports into discount-tier spreadsheets for Logical Position.

## Background

Salesforce Commerce Cloud doesn't allow multi-select across child categories when exporting products — each sub-category has to be exported individually. This tool eliminates the manual work of combining those exports, filtering bad rows, and organizing everything into the correctly structured xlsx files LP expects.

## Usage

Open `index.html` (or via the [ch-tools dashboard](https://github.com/caitlinsc/ch-tools)) in any browser. No installation, no server, no internet connection required.

### Steps

1. **Export your categories from SFCC** — one export per sub-category, with `Online = Y` selected. CSV or xlsx both work.

2. **Drop all the files into the tool at once** — or click to browse. All your exports for a given sale can be loaded in a single drag.

3. **Assign each file a discount tier and sheet name**
   - The tier selector is color-coded: green = 10%, blue = 15%, purple = 20%
   - The sheet name is pre-filled from the filename — edit it to match the tab name LP expects (e.g. `tack`, `horse_clothing`, `gifts`, `closeouts`)
   - Sheet names are capped at 31 characters (Excel limit)
   - Multiple files assigned the same tier + sheet name will be merged into one tab

4. **Check the summary panel** — shows how many sheets and rows are queued per tier

5. **Export** — click the button for each tier you need, or **Export All Tiers** to download everything at once. Files are named `10__off.xlsx`, `15__off.xlsx`, `20__off.xlsx`.

## Filtering

Rows where `onlineFlag__default` is `false`, `n`, `no`, or `0` are automatically removed before export. This handles the SFCC quirk where Online=Y exports sometimes still include offline products.

## Output Format

Each exported xlsx contains one sheet per assigned sheet name. Columns are always output in this order, matching the format LP receives:

| Column | Description |
|---|---|
| `ID` | Salesforce product ID |
| `brand` | Brand name |
| `name__default` | Product display name |
| `onlineFlag__default` | Online status (all `true` after filtering) |
| `variants` | Semicolon-separated variant SKUs |
| `variationGroups` | Variation group IDs |
| `productSets` | Product set IDs |

## Notes

- Discount levels are determined by the marketing team and programmed into the SF campaign and promotions separately — this tool only handles building the export files
- The tool runs entirely in the browser; no data is uploaded anywhere
- Tested with SFCC product export CSVs and xlsx files
