# XLSX — analyze, create, edit spreadsheets (on-demand)

## Decision tree

```
Read / analyze data?             -> pandas
Create new or edit with formulas? -> openpyxl
Need computed formula values?    -> LibreOffice headless convert (see section 4)
Financial model?                 -> see "Financial model standards"
```

## Required principles

1. **Use Excel formulas, do not hardcode values computed in Python**:
   ```python
   # WRONG
   sheet['B10'] = df['Sales'].sum()   # hardcoded 5000

   # CORRECT
   sheet['B10'] = '=SUM(B2:B9)'       # Excel computes it
   ```

2. **Zero formula errors** — after creating or editing: recompute with LibreOffice headless (section 4), fix all `#REF!`, `#DIV/0!`, `#VALUE!`, `#N/A`, `#NAME?` before delivering.

3. **Preserve the existing template format when updating a file** — don't impose new conventions on a file with its own patterns.

## 1. Read and analyze — pandas

```python
import pandas as pd

# Read
df = pd.read_excel('file.xlsx')                          # first sheet
all_sheets = pd.read_excel('file.xlsx', sheet_name=None) # all sheets -> dict

# Explore
df.head()
df.info()
df.describe()

# Write back
df.to_excel('output.xlsx', index=False)
```

Pandas tips:
- Specify dtype to avoid inference errors: `pd.read_excel('f.xlsx', dtype={'id': str})`
- Large files: `usecols=['A', 'C', 'E']` to load only needed columns
- Dates: `parse_dates=['date_column']`

## 2. Create new — openpyxl

```python
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment

wb = Workbook()
sheet = wb.active

# Data + formula
sheet['A1'] = 'Revenue'
sheet['B1'] = '=SUM(B2:B9)'

# Formatting
sheet['A1'].font = Font(bold=True, color='FF0000')
sheet['A1'].fill = PatternFill('solid', start_color='FFFF00')
sheet['A1'].alignment = Alignment(horizontal='center')
sheet.column_dimensions['A'].width = 20

wb.save('output.xlsx')
```

## 3. Edit an existing file — openpyxl

```python
from openpyxl import load_workbook

wb = load_workbook('existing.xlsx')        # preserves formulas (default)
# wb = load_workbook('f.xlsx', data_only=True)  # reads values only, do NOT save back

sheet = wb.active

# Edit cells
sheet['A1'] = 'New value'
sheet.insert_rows(2)
sheet.delete_cols(3)

# Add sheet
ws2 = wb.create_sheet('SheetName')
ws2['A1'] = 'Data'

wb.save('modified.xlsx')
```

**Warning**: Loading with `data_only=True` then saving -> formulas are permanently lost.

## 4. Recalculate formulas (required when using formulas)

**Known limitation**: openpyxl does **not** recalculate formulas. Writing `=SUM(B2:B9)` leaves only the formula string; the cached value stays empty until an Excel engine recalculates. So `load_workbook(data_only=True)` on a freshly created file returns `None` for those cells.

To force recalculation and load cached values, use LibreOffice headless to convert the file through itself (round-trip through the LibreOffice calculation engine):

```bash
# Round-trip so LibreOffice recalculates and writes cached values into the file
soffice --headless --calc --convert-to xlsx --outdir computed/ output.xlsx
# Result: computed/output.xlsx — all formula cells now have cached values
```

Then check for formula errors with openpyxl (reading cached values):

```python
from openpyxl import load_workbook

wb = load_workbook("computed/output.xlsx", data_only=True)
ERRORS = {"#REF!", "#DIV/0!", "#VALUE!", "#N/A", "#NAME?", "#NULL!", "#NUM!"}
found = []
for ws in wb.worksheets:
    for row in ws.iter_rows():
        for cell in row:
            if isinstance(cell.value, str) and cell.value in ERRORS:
                found.append(f"{ws.title}!{cell.coordinate}: {cell.value}")
print(found or "Zero formula errors")
```

If `found` is not empty -> fix the source formulas and recompute until it is empty.

If LibreOffice is unavailable: openpyxl still writes the correct formula string, Excel will calculate it on open — but you **cannot** verify values/errors in this environment. State that limitation to the user instead of assuming verification was done.

## 5. Financial model standards

### Color coding (industry standard — apply when no custom template exists)

| Color | Meaning |
|---|---|
| Blue (0,0,255) | Hardcoded input — numbers the user changes |
| Black (0,0,0) | All formulas and calculations |
| Green (0,128,0) | Link from another worksheet in the same workbook |
| Red (255,0,0) | Link from an external file |
| Yellow background (255,255,0) | Key assumption requiring attention |

### Number formatting

| Type | Format |
|---|---|
| Year | Text string: "2024" |
| Currency | `$#,##0` — always include unit in header: "Revenue ($mm)" |
| Zero | Use format `$#,##0;($#,##0);-` to show "-" instead of "0" |
| Percentage | `0.0%` |
| Multiple | `0.0x` |
| Negative numbers | Use parentheses `(123)`, not a minus sign `-123` |

### Formula construction

```python
# WRONG — hardcode growth rate
sheet['C5'] = 0.15

# CORRECT — cell reference
sheet['C5'] = '=(C4-C2)/C2'
```

- Place ALL assumptions (growth rate, margin, multiple...) in dedicated assumption cells, use cell references in formulas.
- Document hardcoded values: `"Source: Bloomberg, 8/15/2025, AAPL US Equity"`

### Verification checklist

```
[ ] Test 2-3 sample cell references before building the full model
[ ] Confirm Excel column mapping (column 64 = BL, not BK)
[ ] Row offset: Excel is 1-indexed (DataFrame row 5 = Excel row 6)
[ ] Handle NaN: pd.notna() before using as denominator
[ ] Cross-sheet reference: correct format Sheet1!A1
```

## 6. Library selection guide

| Task | Library |
|---|---|
| Data analysis, bulk operations, simple export | pandas |
| Formulas, complex formatting, Excel-specific | openpyxl |
| Recalculate formulas after creating or editing | LibreOffice headless convert (section 4) |

## Dependencies

| Tool | Install |
|---|---|
| pandas | `pip install pandas openpyxl` |
| openpyxl | `pip install openpyxl` |
| LibreOffice | `sudo apt-get install libreoffice` (formula recompute, section 4) |
