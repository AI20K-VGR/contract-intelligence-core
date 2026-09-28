#!/usr/bin/env python3
"""Id-targeted incremental editor for .drawio files.

Re-implements next-ai-draw-io's ``applyDiagramOperations`` (DayuanJiang/
next-ai-draw-io, Apache-2.0) in stdlib + defusedxml: an LLM emits a list of
``{operation, cell_id, new_xml}`` ops, this script applies them deterministically
to the existing XML so a hand-tuned layout survives — instead of regenerating the
whole diagram. update / add / delete are keyed on ``cell_id`` over the WHOLE tree
(every <diagram> page, every nesting depth), not just page-1's root.

  python3 edit_drawio.py <file.drawio> --ops <ops.json|->  [-o out.drawio] [--faithful]
  python3 edit_drawio.py <file.drawio> --list-cells

Design notes (why it is shaped this way):
- ElementTree has no parent pointer, so a whole-tree parent map is built once and
  edits act on a cell's REAL parent (a nested container, not an assumed <root>).
- Parsing goes through defusedxml so a billion-laughs / XXE payload in the file or
  in any fragment is refused, never expanded.
- ``tostring`` drops the XML declaration and reserializes the whole tree (it
  normalizes self-closing spacing, turns CDATA into escaped text, may reorder
  attributes). The result is loss*less* semantically — draw.io parses it the same —
  but it is NOT byte-preserving; the declaration is re-prepended by hand.
- Fail-soft: every op is wrapped independently; a bad op records an error and the
  remaining ops still run. The engine never raises on user input.
"""
import argparse
import json
import sys

import defusedxml.ElementTree as DET
from defusedxml.common import DefusedXmlException
import xml.etree.ElementTree as STD_ET
from dataclasses import dataclass, field
from xml.etree.ElementTree import ParseError

RESERVED = {"0", "1"}  # mxGraphModel's invisible root (0) and default layer (1)


@dataclass
class ApplyResult:
    """Outcome of applying ops. ``errors`` carries both hard errors ("error: …")
    and non-fatal warnings ("warning: …"); the CLI exit code counts only the
    former (a warning, e.g. preserved geometry, is not a failure)."""
    result: str
    errors: list = field(default_factory=list)


# --- Parsing helpers -------------------------------------------------------

def _parse_document(xml):
    """Parse a full .drawio document safely. Raises on malformed/entity input."""
    return DET.fromstring(xml)


def _parse_fragment(new_xml):
    """Parse a single mxCell fragment safely; returns the Element.

    Raises ParseError / DefusedXmlException on malformed or entity-bearing input,
    which the caller turns into a per-op error (fail-soft).
    """
    if not isinstance(new_xml, str) or not new_xml.strip():
        raise ParseError("empty fragment")
    return DET.fromstring(new_xml)


def _build_parent_map(root):
    """Map every element to its parent across the whole tree (all pages/depths).

    ElementTree exposes no parent pointer; this single pass is what lets delete/
    update act on a cell's true parent rather than assuming a child of <root>.
    """
    return {child: parent for parent in root.iter() for child in parent}


def _index_cells(root):
    """id -> mxCell Element over the entire tree (every page, every depth)."""
    return {c.get("id"): c for c in root.iter("mxCell")}


def _all_roots(root):
    """Every <root> element (one per mxGraphModel page), in document order."""
    return list(root.iter("root"))


# --- Geometry gate (RT-S1) -------------------------------------------------

def _geometry_incomplete(frag):
    """True when the fragment's geometry cannot place the node.

    Triggers when <mxGeometry> is absent, or present but missing both x and y
    (the empty ``<mxGeometry/>`` case) — either way the node would snap to 0,0
    and lose its hand-placed position, so the old geometry should be preserved.
    """
    g = frag.find("mxGeometry")
    if g is None:
        return True
    return g.get("x") is None and g.get("y") is None


def _copy_geometry(old_cell, frag):
    """Copy the old cell's <mxGeometry> into the fragment (drop any partial one)."""
    old_g = old_cell.find("mxGeometry")
    if old_g is None:
        return False
    existing = frag.find("mxGeometry")
    if existing is not None:
        frag.remove(existing)
    frag.append(STD_ET.fromstring(STD_ET.tostring(old_g, encoding="unicode")))
    return True


# --- Serialization ---------------------------------------------------------

def _serialize(root):
    """Reserialize the tree and re-prepend the XML declaration ``tostring`` drops.

    Deterministic: no time/random; attribute order follows insertion order.
    """
    body = STD_ET.tostring(root, encoding="unicode")
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + body


# --- Operations ------------------------------------------------------------

def _op_update(cell_id, new_xml, idx, pmap, faithful, errors):
    cell = idx.get(cell_id)
    if cell is None:
        errors.append(f"error: update {cell_id!r}: cell not found")
        return
    frag = _parse_fragment(new_xml)
    if frag.get("id") != cell_id:
        errors.append(f"error: update {cell_id!r}: fragment id {frag.get('id')!r} mismatch")
        return
    if not faithful and _geometry_incomplete(frag):
        if _copy_geometry(cell, frag):
            errors.append(f"warning: update {cell_id!r}: geometry missing, preserved old position")
    parent = pmap.get(cell)
    if parent is None:
        errors.append(f"error: update {cell_id!r}: no parent (orphan/no <root>)")
        return
    pos = list(parent).index(cell)
    parent.remove(cell)
    parent.insert(pos, frag)


def _op_add(cell_id, new_xml, idx, roots, pmap, errors):
    if cell_id in idx:
        errors.append(f"error: add {cell_id!r}: id already exists")
        return
    frag = _parse_fragment(new_xml)
    if frag.get("id") != cell_id:
        errors.append(f"error: add {cell_id!r}: fragment id {frag.get('id')!r} mismatch")
        return
    if not roots:
        errors.append(f"error: add {cell_id!r}: no <root> to append into")
        return
    parent_id = frag.get("parent")
    if parent_id is None:
        errors.append(f"warning: add {cell_id!r}: fragment has no parent attribute")
    # Append into the <root> of the page that owns the referenced parent; else page-1.
    target_root = roots[0]
    if parent_id and parent_id in idx:
        ancestor = idx[parent_id]
        while ancestor is not None and ancestor.tag != "root":
            ancestor = pmap.get(ancestor)
        if ancestor is not None:
            target_root = ancestor
    target_root.append(frag)


def _op_delete(cell_id, idx, pmap, errors):
    cell = idx.get(cell_id)
    if cell is None:
        errors.append(f"error: delete {cell_id!r}: cell not found")
        return
    parent = pmap.get(cell)
    if parent is None:
        errors.append(f"error: delete {cell_id!r}: no parent (no <root>)")
        return
    parent.remove(cell)


def apply_operations(xml, ops, *, faithful=False):
    """Apply ``ops`` to a .drawio document string, fail-soft + deterministic.

    Returns ApplyResult(result, errors). On a document-level parse failure the
    original ``xml`` is returned untouched (nothing is serialized, so no entity
    can have expanded). Each op is wrapped independently: a bad op appends an
    error and the rest still run.
    """
    errors = []
    try:
        root = _parse_document(xml)
    except (ParseError, DefusedXmlException, ValueError) as exc:
        return ApplyResult(result=xml, errors=[f"error: cannot parse document: {exc}"])

    for i, op in enumerate(ops):
        try:
            action = op.get("operation")
            cell_id = op.get("cell_id")
            new_xml = op.get("new_xml")
            if cell_id is None or not isinstance(cell_id, str):
                errors.append(f"error: op[{i}]: missing/invalid cell_id")
                continue
            if cell_id in RESERVED:
                errors.append(f"error: op[{i}] {action} {cell_id!r}: refuse reserved id 0/1")
                continue
            # Rebuild index + parent map each op: prior ops may have mutated the tree.
            idx = _index_cells(root)
            pmap = _build_parent_map(root)
            roots = _all_roots(root)
            if action == "update":
                if new_xml is None:
                    errors.append(f"error: op[{i}] update {cell_id!r}: new_xml required")
                    continue
                _op_update(cell_id, new_xml, idx, pmap, faithful, errors)
            elif action == "add":
                if new_xml is None:
                    errors.append(f"error: op[{i}] add {cell_id!r}: new_xml required")
                    continue
                _op_add(cell_id, new_xml, idx, roots, pmap, errors)
            elif action == "delete":
                _op_delete(cell_id, idx, pmap, errors)
            else:
                errors.append(f"error: op[{i}]: unknown operation {action!r}")
        except (ParseError, DefusedXmlException, ValueError) as exc:
            errors.append(f"error: op[{i}] {op.get('operation')} "
                          f"{op.get('cell_id')!r}: {exc}")

    return ApplyResult(result=_serialize(root), errors=errors)


# --- list-cells ------------------------------------------------------------

def list_cells(xml):
    """Return a flat id/label/geometry map for every vertex/edge on every page.

    Reserved ids 0/1 are skipped. Pages are numbered 1..N in document order, so
    an agent can target a cell on the right page.
    """
    root = _parse_document(xml)
    pages = root.findall("diagram") or [root]
    out = []
    for page_no, page in enumerate(pages, start=1):
        for c in page.iter("mxCell"):
            cid = c.get("id")
            if cid in RESERVED:
                continue
            is_edge = c.get("edge") == "1"
            is_vertex = c.get("vertex") == "1"
            if not (is_edge or is_vertex):
                continue
            g = c.find("mxGeometry")

            def _num(key):
                if g is None or g.get(key) is None:
                    return None
                try:
                    return float(g.get(key))
                except ValueError:
                    return None

            def _int(v):
                return int(v) if v is not None and v == int(v) else v

            out.append({
                "id": cid,
                "label": c.get("value") or "",
                "kind": "edge" if is_edge else "vertex",
                "page": page_no,
                "x": _int(_num("x")),
                "y": _int(_num("y")),
                "w": _int(_num("width")),
                "h": _int(_num("height")),
            })
    return out


# --- CLI -------------------------------------------------------------------

def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Apply id-targeted edits to a .drawio file, or list its cells.")
    ap.add_argument("file", help="path to the .drawio file")
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--ops", metavar="OPS",
                      help="ops JSON file, or '-' to read from stdin")
    mode.add_argument("--list-cells", action="store_true",
                      help="print id/label/geometry of every cell as JSON")
    ap.add_argument("-o", "--out", help="write result XML to this file (default: stdout)")
    ap.add_argument("--faithful", action="store_true",
                    help="replace geometry verbatim instead of preserving the old position")
    args = ap.parse_args(argv)

    try:
        with open(args.file, encoding="utf-8") as f:
            xml = f.read()
    except OSError as exc:
        print(f"error: cannot read {args.file}: {exc}", file=sys.stderr)
        return 1

    if args.list_cells:
        try:
            cells = list_cells(xml)
        except (ParseError, DefusedXmlException, ValueError) as exc:
            print(f"error: cannot parse {args.file}: {exc}", file=sys.stderr)
            return 1
        print(json.dumps(cells, ensure_ascii=False, indent=2))
        return 0

    # --ops path
    if args.ops == "-":
        raw = sys.stdin.read()
    else:
        try:
            with open(args.ops, encoding="utf-8") as f:
                raw = f.read()
        except OSError as exc:
            print(f"error: cannot read ops {args.ops}: {exc}", file=sys.stderr)
            return 1
    try:
        ops = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(f"error: invalid ops JSON: {exc}", file=sys.stderr)
        return 1
    if not isinstance(ops, list):
        print("error: ops must be a JSON array", file=sys.stderr)
        return 1

    res = apply_operations(xml, ops, faithful=args.faithful)
    for msg in res.errors:
        print(msg, file=sys.stderr)

    if args.out:
        try:
            with open(args.out, "w", encoding="utf-8") as f:
                f.write(res.result)
        except OSError as exc:
            print(f"error: cannot write {args.out}: {exc}", file=sys.stderr)
            return 1
    else:
        sys.stdout.write(res.result)

    hard_errors = [e for e in res.errors if e.startswith("error")]
    return 1 if hard_errors else 0


if __name__ == "__main__":
    sys.exit(main())
