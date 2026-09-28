# Edit mode — edit a diagram at the exact node (incremental edit)

Edits a `.drawio` file **that already has a hand-tuned layout** by targeting the exact `cell_id` instead of regenerating the whole XML. Engine: `scripts/edit_drawio.py` (stdlib + `defusedxml`) — the LLM generates ops, the script applies them **deterministically**, **fail-soft**, keeping the position of untargeted nodes unchanged.

Re-implementation of `applyDiagramOperations` (next-ai-draw-io, Apache-2.0 — see `NOTICE`).

## When to use

- The diagram already renders nicely, user drag-and-dropped it into position → they just want to change labels/styles/add/remove a few nodes. Regenerating the whole file **loses the layout**.
- Do NOT use when creating a new diagram from scratch (that's the regular Step 3 — hand-place / autolayout).

## Agent workflow (3 steps + mandatory validate)

```bash
# 1. Read the cell map: id + label + geometry across EVERY page
python3 scripts/edit_drawio.py diagram.drawio --list-cells

# 2. Generate ops.json targeting the correct cell_id (see contract below)

# 3. Apply ops, overwrite the file
python3 scripts/edit_drawio.py diagram.drawio --ops ops.json -o diagram.drawio
#    (read stderr: an "error: ..." line means the op failed, "warning: ..." is a non-fatal warning)

# 4. REQUIRED — validate the resulting XML
python3 scripts/validate.py diagram.drawio
```

`--list-cells` prints JSON `[{id, label, kind, page, x, y, w, h}]` for every vertex/edge (excludes id `0`/`1`). Use `page` to know which page a cell belongs to in a multi-page file.

`--ops -` reads ops from stdin instead of a file.

## Ops contract

Each op is an object in the JSON array:

| Field | Type | Required | Meaning |
|---|---|---|---|
| `operation` | `"update"` \| `"add"` \| `"delete"` | yes | operation type |
| `cell_id` | string | yes | target cell id (must match the `id` in `new_xml` for update/add) |
| `new_xml` | string (1 `<mxCell>`) | update/add | replacement / new fragment |

Full example:

```json
[
  { "operation": "update", "cell_id": "5",
    "new_xml": "<mxCell id=\"5\" value=\"New name\" style=\"rounded=1;\" vertex=\"1\" parent=\"1\"><mxGeometry x=\"100\" y=\"100\" width=\"120\" height=\"60\" as=\"geometry\"/></mxCell>" },
  { "operation": "add", "cell_id": "20",
    "new_xml": "<mxCell id=\"20\" value=\"New node\" vertex=\"1\" parent=\"1\"><mxGeometry x=\"400\" y=\"300\" width=\"120\" height=\"60\" as=\"geometry\"/></mxCell>" },
  { "operation": "delete", "cell_id": "8" }
]
```

Semantics:

- **update** — locates the cell by `cell_id` across the **entire tree** (every page, every depth — including cells nested inside containers), replaces it with `new_xml` under its **actual real parent**. `id` in the fragment must == `cell_id` (mismatch → op fails).
- **add** — adds a new cell; `cell_id` already exists → op fails. Appends to the `<root>` of the page containing `parent` (defaults to page-1). Fragment missing the `parent` attr → still applied + **warning** (cell may end up orphaned, won't render).
- **delete** — removes the cell from its real parent.

## Geometry rule (preserve layout)

Default is **preserve-geometry**: if the update's `new_xml` **is missing `<mxGeometry>`** or has empty geometry (missing both `x` and `y`), the engine **copies the old geometry** in + emits 1 warning — the whole point of edit mode: change content without the node jumping to `(0,0)`.

The `--faithful` flag disables this → replaces with the raw `new_xml`, next-ai style (missing geometry sends the node to `0,0`). Only use it when you **deliberately** want to reset the position.

## Fail-soft + exit code

- A failed op (id doesn't exist, malformed fragment, id mismatch, page has no `<root>`) → recorded in `errors[]`, **subsequent ops still run**. The engine never throws.
- Exit `0` if no op fails (warnings don't count as failures); `1` if ≥1 op fails (still writes the partial result from the successful ops).

## Safety

- The file + every `new_xml` fragment are parsed via `defusedxml` → billion-laughs / XXE attacks are blocked (op fails, no expansion, no crash).
- **Reserved guard**: any op touching `cell_id` `"0"` or `"1"` (hidden root / default layer) is
  **hard-rejected** — the page frame always stays intact.

## Note: the diff will be noisy (semantically lossless, NOT byte-preserving)

The engine reserializes the whole tree via `ElementTree.tostring` → may drop XML comments, normalize self-closing spacing, turn CDATA into escaped text, reorder attributes. draw.io parses it identically (semantically lossless), but `git diff` on the `.drawio` shows a wider footprint than the actual change — a deliberate trade-off to stay pure stdlib + deterministic.
