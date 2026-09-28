# PPTX — create, edit, analyze PowerPoint (on-demand)

A `.pptx` file is a ZIP of XML. Primary library: **python-pptx** (read/create/edit). Raw XML needed (animations, comments, parts python-pptx doesn't cover) -> unzip w/ standard `zipfile`, edit w/ `lxml`, zip back (same as docx.md). No external script needed.

## Decision tree

```
Read content?                    -> python-pptx (text) or raw XML
Create without a template?       -> python-pptx build slides directly
Create from an HTML layout?      -> scripts/html2pptx.js (see scripts/html2pptx.md)
Edit an existing file?           -> python-pptx (load -> edit shape -> save)
Create from an existing template? -> open template with python-pptx, edit placeholders
Need slide images?               -> convert to JPEG (LibreOffice + poppler)
```

## 1. Read content — python-pptx

```python
from pptx import Presentation

prs = Presentation("file.pptx")
for i, slide in enumerate(prs.slides):
    print(f"--- Slide {i} ---")
    for shape in slide.shapes:
        if shape.has_text_frame:
            for para in shape.text_frame.paragraphs:
                print("".join(run.text for run in para.runs))
    # Speaker notes
    if slide.has_notes_slide:
        print("NOTES:", slide.notes_slide.notes_text_frame.text)
```

### Raw XML (comments, animations, formatting not exposed by python-pptx)

`.pptx` is a ZIP. Unzip with `zipfile`, read/edit XML with `lxml`, zip back:

```python
import zipfile
from lxml import etree

with zipfile.ZipFile("file.pptx") as z:
    z.extractall("unpacked/")

tree = etree.parse("unpacked/ppt/slides/slide1.xml")
# ... operate on tree ...
tree.write("unpacked/ppt/slides/slide1.xml",
           xml_declaration=True, encoding="UTF-8", standalone=True)
```

Key structure after unzipping:
- `ppt/presentation.xml` — metadata, slide list
- `ppt/slides/slide{N}.xml` — content of each slide (1-indexed)
- `ppt/notesSlides/notesSlide{N}.xml` — speaker notes
- `ppt/theme/theme1.xml` — colors, fonts
- `ppt/media/` — images and media

Before packing back, validate the edited tree against SKILL.md's OOXML safety net (catches malformed XML / broken relationships before the file goes corrupt):

```bash
python3 ooxml/scripts/validate.py unpacked/ --original file.pptx   # exit 0 = clean
```

Pack back into the correct OOXML structure (preserve relative paths):

```python
import os, zipfile
with zipfile.ZipFile("output.pptx", "w", zipfile.ZIP_DEFLATED) as z:
    for root, _, files in os.walk("unpacked/"):
        for name in files:
            full = os.path.join(root, name)
            z.write(full, os.path.relpath(full, "unpacked/"))
```

## 2. Create from scratch — python-pptx

Build slides directly using layout + shape API, not via HTML.

Have an HTML layout instead (text/images/shapes/bullets already as markup)? Use `scripts/html2pptx.js` (see `scripts/html2pptx.md`) rather than hand-porting the layout to python-pptx calls.

```python
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN

prs = Presentation()                 # default 10x7.5"; 16:9 see below
prs.slide_width = Inches(13.333)     # 16:9 widescreen
prs.slide_height = Inches(7.5)

# Title slide (layout 0 = Title Slide)
slide = prs.slides.add_slide(prs.slide_layouts[0])
slide.shapes.title.text = "Slide title"
slide.placeholders[1].text = "Subtitle / context"

# Content slide (layout 5 = Title Only) + custom textbox
slide = prs.slides.add_slide(prs.slide_layouts[5])
slide.shapes.title.text = "Content"
box = slide.shapes.add_textbox(Inches(1), Inches(1.5), Inches(11), Inches(5))
tf = box.text_frame
tf.text = "First line"
p = tf.add_paragraph()
p.text = "Bullet point"
p.level = 1
run = tf.paragraphs[0].runs[0]
run.font.size = Pt(24)
run.font.bold = True
run.font.color.rgb = RGBColor(0xF4, 0xF6, 0xF6)
tf.paragraphs[0].alignment = PP_ALIGN.LEFT

prs.save("output.pptx")
```

### Design principles

- Pick a consistent palette for the content theme; ensure sufficient text/background contrast.
- Cross-platform safe fonts: Arial, Helvetica, Calibri, Times New Roman, Georgia, Verdana, Tahoma.
- Charts/tables slides: use **two-column** layout (40/60) or full-slide; do NOT stack a chart below text in a single narrow column.

### Charts, tables, and native images (python-pptx)

```python
from pptx.util import Inches
from pptx.chart.data import CategoryChartData
from pptx.enum.chart import XL_CHART_TYPE

# Table
rows, cols = 3, 2
tbl = slide.shapes.add_table(rows, cols, Inches(1), Inches(2),
                             Inches(6), Inches(2)).table
tbl.cell(0, 0).text = "Quarter"
tbl.cell(0, 1).text = "Revenue"

# Chart (clustered column)
data = CategoryChartData()
data.categories = ["Q1", "Q2", "Q3"]
data.add_series("2026", (10.5, 14.2, 9.8))
slide.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED,
                       Inches(7), Inches(2), Inches(5), Inches(3.5), data)

# Image
slide.shapes.add_picture("logo.png", Inches(0.5), Inches(0.5),
                         height=Inches(1))
```

Validate by rendering to images (section 5) and check: clipped text, overlaps, poor contrast -> fix code -> regenerate.

## 3. Edit an existing file — python-pptx

```python
from pptx import Presentation

prs = Presentation("existing.pptx")
for slide in prs.slides:
    for shape in slide.shapes:
        if not shape.has_text_frame:
            continue
        for para in shape.text_frame.paragraphs:
            for run in para.runs:
                if "old phrase" in run.text:
                    run.text = run.text.replace("old phrase", "new phrase")
prs.save("output.pptx")
```

Edit run-by-run to preserve formatting; avoid assigning `shape.text_frame.text = ...` — erases all existing runs/formatting. XML parts python-pptx doesn't cover (animations, transitions) -> raw XML from section 1.

## 4. Create from an existing template — python-pptx

Open the template directly with python-pptx; slide layouts and theme are preserved.

### Step 1 — Inspect the template

```python
from pptx import Presentation
prs = Presentation("template.pptx")
for i, layout in enumerate(prs.slide_layouts):
    print(i, layout.name, [ph.placeholder_format.idx for ph in layout.placeholders])
```

### Step 2 — Inventory shapes on each slide

```python
for si, slide in enumerate(prs.slides):
    for shape in slide.shapes:
        kind = "ph" if shape.is_placeholder else shape.shape_type
        txt = shape.text_frame.text[:40] if shape.has_text_frame else ""
        print(f"slide {si} | id {shape.shape_id} | {kind} | {txt!r}")
```

### Step 3 — Fill placeholders / replace text

```python
slide = prs.slides[0]
# By placeholder idx (more stable than position)
slide.placeholders[0].text = "New title"
slide.placeholders[1].text = "New content"
prs.save("output.pptx")
```

Notes:
- Replace text run-by-run to preserve template colors/fonts (see section 3).
- Use `RGBColor(0xFF, 0x00, 0x00)` for RGB colors; theme colors via `MSO_THEME_COLOR` (`from pptx.enum.dml import MSO_THEME_COLOR`).
- To duplicate or reorder slides, operate on `prs.slides._sldIdLst` (the list of `<p:sldId>` elements in `presentation.xml`) via lxml — move/copy elements, then save.

## 5. Convert slides to images for inspection

python-pptx cannot render images. Use LibreOffice headless -> PDF -> JPEG:

```bash
soffice --headless --convert-to pdf presentation.pptx
pdftoppm -jpeg -r 150 presentation.pdf slide
# Produces: slide-1.jpg, slide-2.jpg, ...

# Pages 2-5 only
pdftoppm -jpeg -r 150 -f 2 -l 5 presentation.pdf slide
```

Combine into a thumbnail grid (optional) with ImageMagick `montage`:

```bash
montage slide-*.jpg -tile 4x -geometry +4+4 thumbnails.png
```

## Dependencies

| Tool | Install |
|---|---|
| python-pptx | `pip install python-pptx` |
| lxml | `pip install lxml` |
| LibreOffice | `sudo apt-get install libreoffice` |
| poppler | `sudo apt-get install poppler-utils` |
| ImageMagick | `sudo apt-get install imagemagick` (montage, optional) |
