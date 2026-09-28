# PDF — extract, create, merge/split, fill forms (on-demand)

## Decision tree

```
Read text/tables?          -> pdfplumber (Python)
Create a new PDF?          -> reportlab (Python)
Merge / split / rotate?    -> pypdf or qpdf (CLI)
Fill a form?
  |- Has fillable fields   -> pypdf update_page_form_field_values
  └- No fields (scan/image)-> reportlab overlay + pypdf merge
OCR a scanned file?        -> pytesseract + pdf2image
```

## 1. Extract text and tables

### pypdf — basic reading

```python
from pypdf import PdfReader

reader = PdfReader("document.pdf")
print(f"Total pages: {len(reader.pages)}")

text = "".join(page.extract_text() for page in reader.pages)
```

### pdfplumber — text with layout + tables

```python
import pdfplumber

with pdfplumber.open("document.pdf") as pdf:
    for page in pdf.pages:
        print(page.extract_text())

# Extract tables -> pandas DataFrame
import pandas as pd

with pdfplumber.open("document.pdf") as pdf:
    all_tables = []
    for page in pdf.pages:
        for table in page.extract_tables():
            if table:
                df = pd.DataFrame(table[1:], columns=table[0])
                all_tables.append(df)

combined = pd.concat(all_tables, ignore_index=True)
combined.to_excel("extracted.xlsx", index=False)
```

### CLI — pdftotext (poppler)

```bash
pdftotext input.pdf output.txt          # basic
pdftotext -layout input.pdf output.txt  # preserve layout
pdftotext -f 1 -l 5 input.pdf out.txt  # pages 1-5 only
```

## 2. Create a new PDF — reportlab

```python
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

doc = SimpleDocTemplate("report.pdf", pagesize=letter)
styles = getSampleStyleSheet()
story = [
    Paragraph("Title", styles['Title']),
    Spacer(1, 12),
    Paragraph("Body paragraph text.", styles['Normal']),
]
doc.build(story)
```

## 3. Merge, split, rotate — pypdf

```python
from pypdf import PdfWriter, PdfReader

# Merge
writer = PdfWriter()
for path in ["a.pdf", "b.pdf"]:
    for page in PdfReader(path).pages:
        writer.add_page(page)
with open("merged.pdf", "wb") as f:
    writer.write(f)

# Split (1 file per page)
reader = PdfReader("input.pdf")
for i, page in enumerate(reader.pages):
    w = PdfWriter()
    w.add_page(page)
    with open(f"page_{i+1}.pdf", "wb") as f:
        w.write(f)

# Rotate
page = PdfReader("input.pdf").pages[0]
page.rotate(90)
```

### CLI — qpdf

```bash
# Merge
qpdf --empty --pages file1.pdf file2.pdf -- merged.pdf

# Split pages 1-5
qpdf input.pdf --pages . 1-5 -- pages1-5.pdf

# Rotate page 1 by 90 degrees
qpdf input.pdf output.pdf --rotate=+90:1

# Remove password
qpdf --password=SECRET --decrypt encrypted.pdf decrypted.pdf
```

## 4. OCR a scanned file

```python
# pip install pytesseract pdf2image
import pytesseract
from pdf2image import convert_from_path

images = convert_from_path('scanned.pdf')
text = ""
for i, img in enumerate(images):
    text += f"--- Page {i+1} ---\n"
    text += pytesseract.image_to_string(img, lang='vie+eng')
```

## 5. Fill a PDF form

### 5a. Form with fillable fields (AcroForm) — pypdf

```python
from pypdf import PdfReader, PdfWriter

reader = PdfReader("file.pdf")

# List existing fields (name + type) to know what to fill
fields = reader.get_fields()
for name, f in (fields or {}).items():
    print(name, f.get("/FT"), f.get("/V"))

# Fill values: text field uses a string, checkbox uses the export name ("/On"...)
writer = PdfWriter(clone_from=reader)
values = {
    "last_name": "Nguyen",
    "Checkbox12": "/On",
}
for page in writer.pages:
    writer.update_page_form_field_values(page, values)

# Keep values visible when opened (set NeedAppearances)
writer.set_need_appearances_writer(True)
with open("output.pdf", "wb") as f:
    writer.write(f)
```

If `get_fields()` returns `None` or empty -> file has no AcroForm, use 5b.

### 5b. Form without fillable fields (scan / image) — overlay

No fields to fill -> draw text at correct coordinates, merge over the original page. PDF uses bottom-left-origin coordinates; unit = points (72pt = 1 inch).

1. **Determine coordinates**: render the page to an image to locate the positions to fill.
   ```python
   from pdf2image import convert_from_path
   imgs = convert_from_path("file.pdf", dpi=150)
   imgs[0].save("page1.png")   # inspect pixels -> convert to points (point = px*72/dpi)
   ```
   Measure y from the image top, convert to bottom-left origin: `y_pdf = page_height_pt - y_top_pt`.

2. **Create the overlay layer with reportlab** (same page size as original):
   ```python
   from reportlab.pdfgen import canvas
   from pypdf import PdfReader

   page = PdfReader("file.pdf").pages[0]
   w, h = float(page.mediabox.width), float(page.mediabox.height)

   c = canvas.Canvas("overlay.pdf", pagesize=(w, h))
   c.setFont("Helvetica", 11)
   c.drawString(120, h - 90, "Nguyen")     # (x, y) bottom-left origin
   c.drawString(120, h - 130, "2026-06-15")
   c.save()
   ```

3. **Merge the overlay onto the original page** (section 6, watermark technique):
   ```python
   from pypdf import PdfReader, PdfWriter
   base = PdfReader("file.pdf")
   over = PdfReader("overlay.pdf").pages[0]
   writer = PdfWriter()
   base.pages[0].merge_page(over)
   for p in base.pages:
       writer.add_page(p)
   with open("output.pdf", "wb") as f:
       writer.write(f)
   ```

4. **Verify**: render `output.pdf` back to an image, check text lands in the correct blank space and does not overlap labels; adjust coordinates in step 2 and repeat if needed.

## 6. Other operations

```python
# Watermark
from pypdf import PdfReader, PdfWriter
watermark = PdfReader("watermark.pdf").pages[0]
reader = PdfReader("document.pdf")
writer = PdfWriter()
for page in reader.pages:
    page.merge_page(watermark)
    writer.add_page(page)
with open("watermarked.pdf", "wb") as f:
    writer.write(f)

# Set password
writer.encrypt("userpass", "ownerpass")

# Extract metadata
meta = PdfReader("document.pdf").metadata
print(meta.title, meta.author)

# Extract images (CLI)
pdfimages -j input.pdf output_prefix
```

## Dependencies

| Tool | Install |
|---|---|
| pypdf | `pip install pypdf` |
| pdfplumber | `pip install pdfplumber` |
| reportlab | `pip install reportlab` |
| pytesseract | `pip install pytesseract pdf2image` |
| poppler | `sudo apt-get install poppler-utils` |
| qpdf | `sudo apt-get install qpdf` |
