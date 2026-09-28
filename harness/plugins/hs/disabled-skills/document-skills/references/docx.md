# DOCX — create, edit, analyze (on-demand)

A `.docx` file is a ZIP of XML; three approaches by task.

## Decision tree

```
Need to read content?          -> Text extraction (pandoc / python-docx)
Create a new file from scratch? -> python-docx
Edit an existing file?
  |- Own file + simple edits   -> python-docx
  └- Someone else's / official document -> Redline workflow (raw OOXML)
```

## 1. Text extraction

```bash
# Read content + tracked changes
pandoc --track-changes=all path/to/file.docx -o output.md
# Options: accept | reject | all
```

Or using python-docx (no pandoc required):

```python
from docx import Document

doc = Document("file.docx")
text = "\n".join(p.text for p in doc.paragraphs)
```

### Raw XML (when comments, complex formatting, or media are needed)

`.docx` is a ZIP file. Unzip with the standard `zipfile` library, edit the XML with `lxml`, then zip back — no external script required:

```python
import zipfile, shutil
from lxml import etree

# Unpack all parts into a directory
with zipfile.ZipFile("file.docx") as z:
    z.extractall("unpacked/")

# Parse + edit main content
tree = etree.parse("unpacked/word/document.xml")
# ... operate on tree ...
tree.write("unpacked/word/document.xml", xml_declaration=True,
           encoding="UTF-8", standalone=True)
```

Key structure:
- `word/document.xml` — main content
- `word/comments.xml` — comments
- `word/media/` — embedded images/media
- Tracked changes: `<w:ins>` (inserted) / `<w:del>` (deleted)

## 2. Create a new file — python-docx

```python
from docx import Document
from docx.shared import Pt

doc = Document()
p = doc.add_paragraph()
run = p.add_run("Hello world")
run.bold = True
run.font.size = Pt(12)
doc.add_heading("Heading", level=1)
doc.save("output.docx")
```

Install: `pip install python-docx`

## 3. Edit an existing file — python-docx

```python
from docx import Document

doc = Document("existing.docx")
for p in doc.paragraphs:
    if "old phrase" in p.text:
        for run in p.runs:
            run.text = run.text.replace("old phrase", "new phrase")
doc.save("modified.docx")
```

Need tracked changes/XML features python-docx doesn't cover -> raw OOXML (unzip -> edit `word/document.xml` w/ lxml -> zip back, see section 1). XML editing rule — **only mark parts that actually changed**:
```python
# WRONG — replaces the entire sentence
'<w:del>...</w:del><w:ins>The term is 60 days.</w:ins>'

# CORRECT — keeps unchanged parts, only marks what changed
'<w:r rsid="..."><w:t>The term is </w:t></w:r>'
'<w:del><w:r><w:delText>30</w:delText></w:r></w:del>'
'<w:ins><w:r><w:t>60</w:t></w:r></w:ins>'
'<w:r rsid="..."><w:t> days.</w:t></w:r>'
```

## 4. Redline workflow (someone else's document / legal)

Use when: the file belongs to another party, or is a legal/academic/official document.

### Steps

1. **Convert to markdown** to read the content:
   ```bash
   pandoc --track-changes=all file.docx -o current.md
   ```

2. **Identify all changes needed** — group into batches of 3-10 changes:
   - By section: "Batch 1: Section 2", "Batch 2: Section 5"
   - By type: "Batch 1: dates", "Batch 2: signing party names"
   - **Do NOT use line numbers from the markdown** — they do not map to XML

3. **Unpack + read OOXML doc** (zipfile, no external script needed):
   ```python
   import zipfile
   with zipfile.ZipFile("file.docx") as z:
       z.extractall("unpacked/")
   ```
   Tracked changes need a consistent RSID (8 hex digits, e.g. `00AB12CD`); generate one value, reuse for all `<w:ins>`/`<w:del>` in the batch.

4. **Implement each batch**:
   - Grep `unpacked/word/document.xml` to find text in XML before each edit
   - Parse with `lxml.etree`, locate nodes by text, wrap with `<w:ins>`/`<w:del>`,
     write the XML file back
   - Line numbers shift after each write -> grep again for each batch

5. **Pack and verify** (zip back into correct OOXML structure):
   - Before zipping back, validate the edited tree against SKILL.md's OOXML safety net (catches malformed XML / broken relationships before the file goes corrupt):
     ```bash
     python3 ooxml/scripts/validate.py unpacked/ --original file.docx   # exit 0 = clean
     ```
   ```python
   import os, zipfile
   with zipfile.ZipFile("reviewed.docx", "w", zipfile.ZIP_DEFLATED) as z:
       for root, _, files in os.walk("unpacked/"):
           for name in files:
               full = os.path.join(root, name)
               z.write(full, os.path.relpath(full, "unpacked/"))
   ```
   ```bash
   pandoc --track-changes=all reviewed.docx -o verify.md
   grep "original phrase" verify.md   # must NOT be found
   grep "new phrase" verify.md        # must be found
   ```

## 5. Convert DOCX to images

```bash
# Step 1: DOCX -> PDF
soffice --headless --convert-to pdf document.docx

# Step 2: PDF -> JPEG (150 DPI)
pdftoppm -jpeg -r 150 document.pdf page
# Produces: page-1.jpg, page-2.jpg, ...

# Only convert pages 2-5:
pdftoppm -jpeg -r 150 -f 2 -l 5 document.pdf page
```

## Dependencies

| Tool | Install |
|---|---|
| python-docx | `pip install python-docx` |
| lxml | `pip install lxml` |
| pandoc | `sudo apt-get install pandoc` |
| LibreOffice | `sudo apt-get install libreoffice` |
| poppler | `sudo apt-get install poppler-utils` |
