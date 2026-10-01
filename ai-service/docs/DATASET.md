# Dataset and annotation contract

Target: 30 authorized samples (8 text-layer PDFs, 8 clean scanned PDFs, 8 degraded scans, 6 hard cases). Cover Vietnamese, English and bilingual documents; tables, annexes, seals, signatures, small fonts, skew, blur, low contrast, JPEG artifacts and scanner noise. Keep original files immutable. Label source families so generated variants from one contract are not mistaken for independent documents.

`data/manifest.example.csv` is a template, not included test data. Required columns are `sample_id,file_path`; optional columns are `source,language,input_type,quality,has_table,has_annex,has_seal,has_signature,is_bilingual,degradation,dpi,ground_truth_text,ground_truth_bbox,ground_truth_critical_fields,notes`. Unknown columns are rejected. Boolean strings must be valid booleans. Empty optional values use defaults. IDs must be unique, safe ASCII identifiers. Use UTF-8 CSV and quote paths/notes containing commas.

Manifest input_type is a dataset label; actual classification is saved separately in page evidence and `detected_input_types`. Manifest dpi describes source/degradation DPI. Rendering uses `render.dpi` consistently across experiments (default 300), so a 150-DPI degraded PDF will be upsampled without recovering lost detail.

Relative paths resolve from `--root` (default current working directory), not the manifest's parent. Absolute paths are allowed. Existing `dataset/` documents can be referenced without copying or renaming. Do not include confidential metadata in the example manifest.

## Text

Create UTF-8 files in `data/ground_truth/text/`. Preserve diacritics, case and punctuation; use the intended reading order with newline between lines and form feed U+000C between pages. Normalize the annotation convention across annotators; avoid unintentional terminal newline. Never use native extraction as unquestioned ground truth. Have a human review important numeric fields and ambiguous Vietnamese marks.

## Critical fields

Example annotation structure (illustrative only):

```json
[
  {"type":"MONEY","value":"100000000","raw_text":"100.000.000 đồng","page":1},
  {"type":"DATE","value":"2026-09-15","raw_text":"15/09/2026","page":1},
  {"type":"TAX_CODE","value":"0123456789","raw_text":"0123456789","page":2}
]
```

Save under `data/ground_truth/critical_fields/` and set `ground_truth_critical_fields`. Page numbers start at 1. Omit `page` only for document-wide matching. Empty array means no annotated fields. Current numeric normalization follows Vietnamese conventions; review English number formatting explicitly.

## Bounding boxes

```json
[
  {"page":1,"level":"line","bbox":{"x1":0.1,"y1":0.2,"x2":0.8,"y2":0.25}},
  {"page":1,"level":"word","bbox":{"x1":0.1,"y1":0.2,"x2":0.2,"y2":0.25}}
]
```

Save under `data/ground_truth/bbox/`. Draw on the displayed page after PDF rotation, using normalized coordinates. Annotate word/line levels independently. Clause geometry is not required.

## Generated samples

Generator renders source pages at 300 DPI, then independently applies rotation ±2/±5 degrees, three Gaussian blur strengths, motion blur, low contrast, light/dark brightness, JPEG qualities 70/50/30, Gaussian noise, salt-and-pepper noise, and resolution 300/200/150 DPI. Seeds derive from the requested seed, page and variant. Output is lossless-wrapped image-only PDF plus manifest and `generation.json` with source hashes, per-variant seeds, dimensions and transforms.

Generated ground-truth paths stay blank until reviewed. Reuse the correct source page's text only after checking annotation suitability. Apply the recorded transform to all bbox corners and renormalize against output dimensions if adapting geometry. Generated variants share a source and must not inflate independent-sample claims.
