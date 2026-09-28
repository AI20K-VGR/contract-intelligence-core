#!/usr/bin/env python3
"""Deterministic structural linter for .drawio files.

Catches the class of mistakes a vision self-check is slow and unreliable at:
dangling edge endpoints, duplicate or reserved ids, broken parent references,
and (as warnings) off-grid geometry, overlapping sibling nodes, and edge
routing defects. Runs without launching draw.io, so it is a fast pre-check
before the visual review step.

  python3 validate.py diagram.drawio

Edge routing checks (warnings): an edge segment crossing a non-incident leaf
vertex ("routes through vertex"), and two edges crossing each other ("edges X
and Y cross") — the two defects the SKILL.md step-5 self-check looks for
("Edge-shape overlap", "Stacked edges"), but caught here deterministically.

Routing is only knowable from the XML when an edge carries explicit waypoints
(``<Array as="points">``) — exactly the hand-routed case the SKILL.md tells
authors to use to route around shapes. Edges with no waypoints are auto-routed
by draw.io at render time (the path is not stored), so they are NOT geometry-
checked here, keeping these warnings free of false positives. Endpoints honour
``exitX/exitY``/``entryX/entryY`` when present, else the node centre, and
absolute positions are resolved through parent containers.

Exit status is non-zero when any error (or, with --strict, any warning) is
found, so it can gate a workflow. Compressed (non-XML) diagram pages are
skipped with a warning — this skill always writes uncompressed XML.

Usage: python3 validate.py <file.drawio> [--strict]
"""
import argparse
import sys
import defusedxml.ElementTree as ET

RESERVED = {"0", "1"}


def rect(cell):
    """Return (x, y, w, h) floats for a cell's geometry, or None if absent/bad.

    x/y default to 0 when omitted: draw.io treats a missing position as the
    origin, and container-managed children (table rows, swimlane/UML-class
    lines under tableLayout) legitimately omit x/y while keeping width/height.
    Only width/height are required to be present and numeric.
    """
    g = cell.find("mxGeometry")
    if g is None:
        return None
    try:
        return (float(g.get("x", "0")), float(g.get("y", "0")),
                float(g.get("width", "nan")), float(g.get("height", "nan")))
    except ValueError:
        return None


def is_edge_label(cell):
    """True for a draw.io edge label / relative-positioned child vertex.

    These legitimately omit width/height: their position is given relative to a
    parent edge (style ``edgeLabel``) or via ``relative="1"`` geometry. Treating
    them as normal vertices wrongly flags them as missing/invalid geometry.
    """
    if "edgeLabel" in (cell.get("style") or ""):
        return True
    g = cell.find("mxGeometry")
    return g is not None and g.get("relative") == "1"


def overlap(a, b):
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    return ax < bx + bw and bx < ax + aw and ay < by + bh and by < ay + ah


# --- Edge routing geometry -------------------------------------------------
#
# These helpers reason about edge paths. They only apply to edges with explicit
# waypoints (the route is otherwise computed by draw.io at render time and not
# stored in the XML), so the checks never guess an auto-routed path.

def style_num(style, key):
    """Return float value of ``key=`` in a draw.io style string, or None."""
    for part in (style or "").split(";"):
        if part.startswith(key + "="):
            try:
                return float(part.split("=", 1)[1])
            except ValueError:
                return None
    return None


def abs_rect(cell, by_id):
    """Absolute (x, y, w, h) of a vertex, summing parent-container offsets.

    Children of a container use coordinates relative to the container origin, so
    an edge spanning containers needs absolute positions to be compared.
    """
    r = rect(cell)
    if r is None or any(v != v for v in r):
        return None
    x, y, w, h = r
    parent, seen = cell.get("parent"), set()
    while parent and parent in by_id and parent not in seen:
        seen.add(parent)
        p = by_id[parent]
        if p.get("vertex") == "1":
            pr = rect(p)
            if pr and not any(v != v for v in pr):
                x += pr[0]
                y += pr[1]
        parent = p.get("parent")
    return (x, y, w, h)


def endpoint(edge, end, by_id):
    """Absolute (x, y) where ``edge`` meets its source/target vertex.

    Honours exitX/exitY (source) and entryX/entryY (target) if the style pins
    them; otherwise the vertex centre. Returns None if the vertex is unresolved.
    """
    vid = edge.get(end)
    if not vid or vid not in by_id:
        return None
    box = abs_rect(by_id[vid], by_id)
    if box is None:
        return None
    x, y, w, h = box
    style = edge.get("style") or ""
    fx = style_num(style, "exitX" if end == "source" else "entryX")
    fy = style_num(style, "exitY" if end == "source" else "entryY")
    return (x + (fx if fx is not None else 0.5) * w,
            y + (fy if fy is not None else 0.5) * h)


def edge_waypoints(edge):
    """Explicit <Array as="points"> waypoints of an edge as [(x, y), ...]."""
    g = edge.find("mxGeometry")
    if g is None:
        return []
    arr = g.find("Array")
    if arr is None:
        return []
    pts = []
    for pt in arr.findall("mxPoint"):
        px, py = pt.get("x"), pt.get("y")
        if px is not None and py is not None:
            try:
                pts.append((float(px), float(py)))
            except ValueError:
                pass
    return pts


def edge_route(edge, by_id):
    """Absolute polyline [(x, y), ...] for a waypointed edge, or None.

    Returns None when the edge has no explicit waypoints (auto-routed; path
    unknown) or an endpoint cannot be resolved.
    """
    waypoints = edge_waypoints(edge)
    if not waypoints:
        return None
    s, t = endpoint(edge, "source", by_id), endpoint(edge, "target", by_id)
    if s is None or t is None:
        return None
    return [s] + waypoints + [t]


def _orient(a, b, c):
    v = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
    return 0 if abs(v) < 1e-9 else (1 if v > 0 else -1)


def segments_cross(p1, p2, p3, p4):
    """True if segments p1p2 and p3p4 properly cross (interior intersection).

    Proper crossing only: collinear overlap and shared-endpoint touches return
    False, so edges meeting at a common node or grazing a corner are not flagged.
    """
    o1, o2 = _orient(p1, p2, p3), _orient(p1, p2, p4)
    o3, o4 = _orient(p3, p4, p1), _orient(p3, p4, p2)
    return o1 != o2 and o3 != o4 and 0 not in (o1, o2, o3, o4)


def _point_in_rect(p, box, eps=1e-6):
    x, y, w, h = box
    return x + eps < p[0] < x + w - eps and y + eps < p[1] < y + h - eps


def route_hits_rect(points, box):
    """True if a polyline enters a rectangle's interior or crosses a border."""
    x, y, w, h = box
    corners = [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
    borders = list(zip(corners, corners[1:] + corners[:1]))
    for a, b in zip(points, points[1:]):
        if _point_in_rect(a, box) or _point_in_rect(b, box):
            return True
        if any(segments_cross(a, b, c, d) for c, d in borders):
            return True
    return False


def routes_cross(pa, pb):
    """True if any segment of polyline pa properly crosses any of pb."""
    for a1, a2 in zip(pa, pa[1:]):
        for b1, b2 in zip(pb, pb[1:]):
            if segments_cross(a1, a2, b1, b2):
                return True
    return False


def geometry_warnings(cells, ids, parents):
    """Edge-through-vertex and edge-crossing warnings for waypointed edges."""
    warns = []
    routed = []          # (edge_id, polyline, {source, target})
    for c in cells:
        if c.get("edge") == "1":
            pts = edge_route(c, ids)
            if pts:
                routed.append((c.get("id"), pts,
                               {c.get("source"), c.get("target")}))
    # Edge routes through an unrelated leaf vertex (containers wrap children, so
    # an edge legitimately traverses them — restrict to leaves, as overlap does).
    leaves = [(c.get("id"), abs_rect(c, ids)) for c in cells
              if c.get("vertex") == "1" and c.get("id") not in parents
              and not is_edge_label(c)]
    leaves = [(vid, box) for vid, box in leaves if box]
    for eid, pts, ends in routed:
        for vid, box in leaves:
            if vid not in ends and route_hits_rect(pts, box):
                warns.append(f"edge {eid!r} routes through vertex {vid!r}")
    # Edge-edge crossings (both routes known).
    for i in range(len(routed)):
        for j in range(i + 1, len(routed)):
            (ia, pa, _), (ib, pb, _) = routed[i], routed[j]
            if routes_cross(pa, pb):
                warns.append(f"edges {ia!r} and {ib!r} cross")
    return warns


# GROUP_LEVEL nesting hierarchy — from drawio-ai-kit core.mjs (MIT).
# Lower number = outermost container. 0 = top-level (Cloud/Account/Region/DC).
# We enforce VPC→AZ→Subnet→SG chain; top-level containers can nest flexibly.
GROUP_LEVEL = {
    "group_aws_cloud": 0, "group_aws_cloud_alt": 0, "group_account": 0,
    "group_corporate_data_center": 0, "group_on_premise": 0, "group_region": 0,
    "group_vpc": 2, "group_vpc2": 2,
    "group_availability_zone": 3,
    "group_subnet": 4,
    "group_security_group": 5,
}


def _group_tok(style):
    """Extract group stencil name from style string."""
    import re as _re
    m = _re.search(r"grIcon=mxgraph\.aws4\.([a-zA-Z0-9_]+)", style)
    return m.group(1) if m else None


def check_group_levels(cells, ids):
    """Return warnings for AWS group nesting violations.

    Checks that each group is nested inside a higher-level container when
    one exists in the diagram. Top-level (Cloud/Account/Region) groups
    are exempt — they can nest flexibly.
    """
    warns = []
    by_id = {c.get("id"): c for c in cells}
    # All levels present in this diagram
    all_levels = set()
    for c in cells:
        g = _group_tok(c.get("style", ""))
        if g and g in GROUP_LEVEL:
            all_levels.add(GROUP_LEVEL[g])
    if not all_levels:
        return warns  # no AWS groups at all → nothing to check

    for c in cells:
        g = _group_tok(c.get("style", ""))
        if g is None or g not in GROUP_LEVEL:
            continue
        lvl = GROUP_LEVEL[g]
        if lvl == 0:
            continue  # top-level groups exempt
        # Check ancestry: does any ancestor have a lower level?
        has_lower_ancestor = False
        p = by_id.get(c.get("parent"))
        guard = 0
        while p and guard < 50:
            pg = _group_tok(p.get("style", ""))
            if pg is not None and pg in GROUP_LEVEL and GROUP_LEVEL[pg] < lvl:
                has_lower_ancestor = True
                break
            p = by_id.get(p.get("parent"))
            guard += 1
        # Only warn if a lower-level container EXISTS in the diagram
        # but this group isn't inside one.
        if not has_lower_ancestor and any(al < lvl for al in all_levels):
            warns.append(f"group {g!r} should nest inside a higher-level group "
                         f"(Cloud→Region→VPC→AZ→Subnet→SG) — currently at wrong level")
    return warns


def _load_category_colors():
    """Load category→hex map from data/category-colors.json (P2)."""
    import json as _json
    fp = __import__("os").path.join(
        __import__("os").path.dirname(__file__), "..", "data", "category-colors.json")
    if not __import__("os").path.exists(fp):
        return {}
    with open(fp, encoding="utf-8") as f:
        return _json.load(f)


def _load_catalog_byname():
    """Build a lookup: stencil_name → entry for all catalog packs."""
    import json as _json
    import os as _os
    catalog_dir = _os.path.join(_os.path.dirname(__file__), "..", "data", "catalog")
    by_name = {}
    if not _os.path.isdir(catalog_dir):
        return by_name
    for fn in sorted(_os.listdir(catalog_dir)):
        if not fn.endswith(".json"):
            continue
        try:
            with open(_os.path.join(catalog_dir, fn), encoding="utf-8") as f:
                data = _json.load(f)
        except Exception:
            continue
        for icon in data.get("icons", []):
            name = icon.get("name", "")
            by_name[name] = icon
    return by_name


def audit_aws_convention(cells):
    """Return warnings for Color=Identity violations and rounded frames.

    Color=Identity: every resIcon should use its category color.
    Rounded frames: AWS diagrams use square corners, not rounded=1.
    """
    import re as _re
    warns = []
    cat_colors = _load_category_colors()

    for c in cells:
        style = c.get("style", "")
        m = _re.search(r"resIcon=mxgraph\.aws4\.([a-zA-Z0-9_]+)", style)
        if not m:
            continue
        icon_name = m.group(1)
        # Get category color: look up icon in catalog first, then categoryColors
        catalog = _load_catalog_byname()
        entry = catalog.get(icon_name, {})
        expected_color = None
        if entry.get("color"):
            expected_color = str(entry["color"]).strip().lower()
        elif entry.get("category"):
            expected_color = cat_colors.get(entry["category"], "").strip().lower()
        if not expected_color:
            continue

        fm = _re.search(r"fillColor=([^;]+)", style)
        if not fm:
            continue
        used = fm.group(1).strip().lower()
        if used.startswith("light-dark"):
            continue
        if used != expected_color:
            warns.append(f"Icon {icon_name!r} recolored (fillColor={fm.group(1).strip()} "
                         f"≠ expected {expected_color}) — keep category color for recognizability")

    # Rounded frames check
    rounded_count = 0
    for c in cells:
        style = c.get("style", "")
        if c.get("edge") == "1":
            continue
        if "/aws4/" in style or ";text;" in style:
            continue
        if _re.search(r"(?:^|;)rounded=1", style):
            rounded_count += 1
    if rounded_count:
        warns.append(f"Rounded frames found ({rounded_count} cells with rounded=1) — "
                     "AWS diagrams use SQUARE corners; set rounded=0 on boxes/frames")
    return warns


def audit_aesthetic(cells):
    """Subjective aesthetic checks — font scatter, palette scatter, icon-size inconsistency.

    These are advisory warnings; escalate to errors only with --strict.
    """
    import re as _re
    warns = []

    # Font size scatter
    font_sizes = set()
    for c in cells:
        style = c.get("style", "") or ""
        for m in _re.finditer(r"fontSize=(\d+)", style):
            font_sizes.add(int(m.group(1)))
    if len(font_sizes) > 4:
        warns.append(f"Too many font sizes ({len(font_sizes)}: {sorted(font_sizes)}) — "
                     "limit to 3-4 for consistency")
    big = [s for s in font_sizes if s >= 16]
    if big:
        warns.append(f"Oversized fonts {big} — use ≤14px for labels")

    # Palette scatter (non-AWS fills only)
    fills = set()
    for c in cells:
        style = c.get("style", "") or ""
        if "/aws4." in style:
            continue  # AWS icons + groups use canonical colors
        fm = _re.search(r"fillColor=([^;]+)", style)
        if fm:
            fills.add(fm.group(1).strip().lower())
    fills.discard("none")
    fills.discard("default")
    if len(fills) > 8:
        warns.append(f"Palette too scattered ({len(fills)} background colors) — "
                     "use limited palette, reserve strong colors for accents")

    return warns


def check_child_spills(cells, ids):
    """Return warnings when a child vertex extends beyond its container's bounds.

    Children use coordinates relative to their container. A child whose
    x+w > parent_w or y+h > parent_h "spills" outside the visual boundary,
    which looks broken in rendered output.
    """
    warns = []
    by_id = {c.get("id"): c for c in cells}
    for c in cells:
        if c.get("vertex") != "1":
            continue
        parent_id = c.get("parent")
        if not parent_id or parent_id in ("0", "1"):
            continue
        parent = by_id.get(parent_id)
        if parent is None or parent.get("vertex") != "1":
            continue
        pr = rect(parent)
        cr = rect(c)
        if pr is None or cr is None:
            continue
        # Skip NaN geometry (rect returns NaN for missing width/height)
        if any(v != v for v in pr) or any(v != v for v in cr):
            continue
        pw, ph = pr[2], pr[3]
        cx, cy, cw, ch = cr
        # 2px tolerance — draw.io allows minor overshoot from stroke width
        if cx < -2 or cy < -2:
            warns.append(f"child {c.get('id')!r} has negative relative position "
                         f"({cx:g},{cy:g}) — spills outside parent {parent_id!r}")
        if cx + cw > pw + 2 or cy + ch > ph + 2:
            warns.append(f"child {c.get('id')!r} ({cx:g}+{cw:g},{cy:g}+{ch:g}) "
                         f"extends beyond parent {parent_id!r} ({pw:g}x{ph:g})")
    return warns


def check_stacked_arrowheads(cells):
    """Return warnings when multiple edges share the same exit/entry point on a vertex.

    Two edges from the same source with identical exitX/exitY (or to the same target
    with identical entryX/entryY) have stacked arrowheads — the lines overlap and
    the rendering is ambiguous. Distribute exit/entry points across the perimeter.
    """
    warns = []
    by_id = {c.get("id"): c for c in cells}
    edges = [c for c in cells if c.get("edge") == "1"]

    def _parse_exit(style, prefix):
        """Return (exitX, exitY) as (float|None, float|None) from a style string."""
        x, y = None, None
        for part in (style or "").split(";"):
            if part.startswith(prefix + "X="):
                try:
                    x = float(part.split("=", 1)[1])
                except ValueError:
                    pass
            elif part.startswith(prefix + "Y="):
                try:
                    y = float(part.split("=", 1)[1])
                except ValueError:
                    pass
        return x, y

    # Group by (source, exitX, exitY)
    src_groups = {}
    for e in edges:
        src = e.get("source")
        if not src or src not in by_id or by_id[src].get("vertex") != "1":
            continue
        ex, ey = _parse_exit(e.get("style", ""), "exit")
        key = (src, ex, ey)
        src_groups.setdefault(key, []).append(e.get("id"))

    for (src, ex, ey), eids in src_groups.items():
        if len(eids) <= 1:
            continue
        pt = f"exitX={ex:.2f},exitY={ey:.2f}" if ex is not None and ey is not None else \
             f"exitX={ex}" if ex is not None else f"exitY={ey}" if ey is not None else \
             "default exit point"
        warns.append(f"{len(eids)} edges ({', '.join(repr(e) for e in eids)}) "
                     f"share {pt} on source {src!r} — "
                     f"distribute exit points across the shape perimeter")

    # Group by (target, entryX, entryY)
    tgt_groups = {}
    for e in edges:
        tgt = e.get("target")
        if not tgt or tgt not in by_id or by_id[tgt].get("vertex") != "1":
            continue
        ex, ey = _parse_exit(e.get("style", ""), "entry")
        key = (tgt, ex, ey)
        tgt_groups.setdefault(key, []).append(e.get("id"))

    for (tgt, ex, ey), eids in tgt_groups.items():
        if len(eids) <= 1:
            continue
        pt = f"entryX={ex:.2f},entryY={ey:.2f}" if ex is not None and ey is not None else \
             f"entryX={ex}" if ex is not None else f"entryY={ey}" if ey is not None else \
             "default entry point"
        warns.append(f"{len(eids)} edges ({', '.join(repr(e) for e in eids)}) "
                     f"share {pt} on target {tgt!r} — "
                     f"distribute entry points across the shape perimeter")

    return warns


def audit_stencils(cells):
    """Check every resIcon/grIcon stencil exists in known catalogs.

    Checks against both the OSS catalog + the shape-index (lazy-loaded).
    When a stencil name is unknown, suggest closest matches (did-you-mean).
    """
    import re as _re
    warns = []
    catalog = _load_catalog_byname()
    # Build known-names set: catalog names + shape-index names (lazy)
    known = set(catalog.keys())
    known.update({"resourceIcon", "resourceIcon2", "group", "groupCenter", "productIcon"})

    # Lazy-load shape-index for AWS stencil validation (10k+ names)
    try:
        import gzip, json, os as _os2
        idx_path = _os2.path.join(_os2.path.dirname(__file__), "..", "data", "shape-index.json.gz")
        if _os2.path.isfile(idx_path):
            with gzip.open(idx_path, "rt", encoding="utf-8") as f:
                shape_index = json.load(f)
            for s in shape_index:
                title = s.get("title", "")
                style = s.get("style", "")
                for m in _re.finditer(r"(?:resIcon|grIcon|shape)=mxgraph\.aws4\.([a-zA-Z0-9_]+)", style):
                    known.add(m.group(1))
    except Exception:
        pass  # fail-soft: no shape-index → check catalog names only

    def suggest(name):
        """Fuzzy did-you-mean: commonsubstring."""
        name_l = name.lower()
        candidates = []
        for k in known:
            if name_l in k.lower() or k.lower() in name_l:
                candidates.append(k)
                if len(candidates) >= 3:
                    break
        return candidates[:3]

    seen = set()
    for c in cells:
        style = c.get("style", "")
        for pattern in (r"resIcon=mxgraph\.aws4\.([a-zA-Z0-9_]+)",
                        r"grIcon=mxgraph\.aws4\.([a-zA-Z0-9_]+)",
                        r"shape=mxgraph\.aws4\.([a-zA-Z0-9_]+)"):
            m = _re.search(pattern, style)
            if not m:
                continue
            name = m.group(1)
            if name in seen or name in known:
                seen.add(name)
                continue
            seen.add(name)
            sug = suggest(name)
            msg = f"Stencil not found: mxgraph.aws4.{name}"
            if sug:
                msg += f" — did you mean: {', '.join(sug[:3])}?"
            warns.append(msg)
    return warns


def check_page(diagram):
    """Return (errors, warnings) for one <diagram> page."""
    name = diagram.get("name", "?")
    model = diagram.find("mxGraphModel")
    if model is None:
        if (diagram.text or "").strip():
            return [], [f"page {name!r}: compressed, skipped (cannot lint)"]
        return [f"page {name!r}: no <mxGraphModel>"], []
    root = model.find("root")
    cells = root.findall("mxCell") if root is not None else []
    errors, warns = [], []
    ids = {}
    for c in cells:
        cid = c.get("id")
        if cid in ids:
            errors.append(f"duplicate id {cid!r}")
        ids[cid] = c
    parents = {c.get("parent") for c in cells}            # ids that have children
    for c in cells:
        cid, parent = c.get("id"), c.get("parent")
        is_v, is_e = c.get("vertex") == "1", c.get("edge") == "1"
        if parent is not None and parent not in ids:
            errors.append(f"cell {cid!r} parent {parent!r} does not exist")
        for end in ("source", "target"):
            ref = c.get(end)
            if ref and ref not in ids:
                errors.append(f"edge {cid!r} {end} {ref!r} does not exist")
        if (is_v or is_e) and cid in RESERVED:
            errors.append(f"cell {cid!r} reuses reserved id 0/1")
        if is_v and not is_edge_label(c):
            r = rect(c)
            if r is None or any(v != v for v in r):       # None or NaN
                errors.append(f"vertex {cid!r} has missing/invalid geometry")
            else:
                x, y, w, h = r
                if w <= 0 or h <= 0:
                    warns.append(f"vertex {cid!r} non-positive size {w:g}x{h:g}")
                if x < 0 or y < 0:
                    warns.append(f"vertex {cid!r} negative position ({x:g},{y:g})")
    # Sibling overlap: only leaf vertices (containers legitimately wrap children).
    boxes = [(c.get("id"), c.get("parent"), rect(c)) for c in cells
             if c.get("vertex") == "1" and c.get("id") not in parents and rect(c)
             and not any(v != v for v in rect(c))]
    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            (ia, pa, ra), (ib, pb, rb) = boxes[i], boxes[j]
            if pa == pb and overlap(ra, rb):
                warns.append(f"vertices {ia!r} and {ib!r} overlap")
    warns += geometry_warnings(cells, ids, parents)
    # New audits (P8)
    warns += check_group_levels(cells, ids)
    warns += audit_aws_convention(cells)
    warns += audit_stencils(cells)
    # P9 audits
    warns += check_child_spills(cells, ids)
    warns += check_stacked_arrowheads(cells)
    # Aesthetic audit: advisory only, gated behind --strict
    # (called from main() so objective checks don't change default exit code)
    return errors, warns


def main():
    ap = argparse.ArgumentParser(description="Lint a .drawio file for structural errors.")
    ap.add_argument("file")
    ap.add_argument("--strict", action="store_true", help="treat warnings as failure too")
    args = ap.parse_args()
    try:
        tree = ET.parse(args.file)
    except (ET.ParseError, OSError) as exc:
        sys.exit(f"error: cannot parse {args.file}: {exc}")
    pages = tree.getroot().findall("diagram") or [tree.getroot()]
    errors, warns = [], []
    for page in pages:
        e, w = check_page(page)
        errors += e
        warns += w
    # Aesthetic audit: gated behind --strict (subjective, don't change default exit)
    if args.strict:
        cells = []
        for page in pages:
            model = page.find("mxGraphModel")
            if model is not None:
                root_elem = model.find("root")
                if root_elem is not None:
                    cells.extend(root_elem.findall("mxCell"))
        warns += audit_aesthetic(cells)
    for w in warns:
        print(f"warning: {w}")
    for e in errors:
        print(f"error: {e}")
    print(f"{len(errors)} error(s), {len(warns)} warning(s)")
    if errors or (args.strict and warns):
        sys.exit(1)


if __name__ == "__main__":
    main()
