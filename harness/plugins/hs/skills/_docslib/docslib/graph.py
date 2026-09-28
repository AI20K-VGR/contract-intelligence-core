"""Graph: validate invariant (port build_modules.py + frontmatter/graph mới) + generate view.

validate(model)        → structural invariant (đếm/đi-graph, KHÔNG phán nội dung)
generate_views()       → reuse-matrix.md + <mod>.reused-by.md (ra out_dir, KHÔNG vào docs/)
generate_showcase_data → MOD_M4 / PTNT_LAYERS / PTNT_CLUSTERS / PART_MODREF (*.js cho showcase)
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import yaml_io

from . import frontmatter as fm
from . import capabilities as cap
from .derived import is_derived_output
from .index import Model

# ---- hằng số -------------------------------------------------
AXES = {"ingestion", "extraction", "decision", "orchestration", "posting"}
BANDS_ORDER_DEFAULT = [
    ("ingest", "Thu thập", "Ingest"), ("extract", "Bóc tách", "Extract"),
    ("decide", "Quyết định", "Decide"), ("orchestrate", "Điều phối (Spine)", "Orchestrate (Spine)"),
    ("write", "Ghi sổ", "Write"), ("assist", "Trợ lý", "Assist"), ("data", "Dữ liệu", "Data"),
]
PART_LAYERS = fm.PART_LAYERS  # SSOT ở frontmatter.py (DA5) — tránh lệch enum
GUARD_BOUNDARY_MAX_LINES = 15
BOUNDARY_CANONICAL = "responsibility-boundary.md"
_MIN_DUP_LEN = 20
GEN_BANNER = "<!-- GENERATED — nguồn: docs/_index/modules.yaml + frontmatter. Đừng sửa tay. -->"
JS_BANNER = ("/* GENERATED — nguồn: docs/_index/ + frontmatter. Đừng sửa tay.\n"
             "   parts = PTNT engine · config_parts = PTSP config. */")


def _bands_def(model: Model):
    """`bands:` taxonomy — ưu tiên `_index/bands.yaml` (model.bands), fallback legacy showcase."""
    return model.bands.get("bands") or model.showcase.get("bands")


def _bands_order(model: Model):
    bands = _bands_def(model)
    if bands:
        # Bỏ qua entry không phải dict hoặc thiếu id (phòng thủ)
        return [(b.get("id"), b.get("vi", b.get("id")), b.get("en", b.get("id")))
                for b in bands if isinstance(b, dict) and b.get("id")]
    return BANDS_ORDER_DEFAULT


def _cluster_names(model: Model) -> dict:
    """bid → (cluster_vi, cluster_en) từ bands.yaml (cũ là CLUSTER_NAMES)."""
    out = {}
    for b in (_bands_def(model) or []):
        if isinstance(b, dict) and b.get("id") and b.get("cluster_vi") and b.get("cluster_en"):
            out[b["id"]] = (b["cluster_vi"], b["cluster_en"])
    return out


# ---- validate -------------------------------------------------------------
def _substantive_lines(text):
    return {s for s in (l.strip() for l in text.splitlines())
            if len(s) > _MIN_DUP_LEN and not s.startswith("#")}


def _readme_guard(model: Model, findings):
    bpath = model.docs_root / "architecture" / BOUNDARY_CANONICAL
    bset = _substantive_lines(bpath.read_text(encoding="utf-8")) if bpath.is_file() else set()
    for m in model.modules:
        rp = model.docs_root / m.dir / "README.md"
        rel = f"{m.dir}/README.md"
        if not rp.is_file():
            findings.error("mandatory-doc-missing", rel, f"module {m.id}: thiếu README.md")
            continue
        text = rp.read_text(encoding="utf-8")
        if bset:
            dup = len(_substantive_lines(text) & bset)
            if dup > GUARD_BOUNDARY_MAX_LINES:
                findings.error("readme-copies-boundary", rel,
                               f"README trùng {dup} dòng nguyên-văn với {BOUNDARY_CANONICAL} "
                               f"> {GUARD_BOUNDARY_MAX_LINES} — giữ tóm tắt + link, đừng copy")
        if BOUNDARY_CANONICAL not in text:
            findings.warn("readme-missing-canonical-link", rel,
                          f"README thiếu link canonical → {BOUNDARY_CANONICAL}")


def validate(model: Model, findings, *, frontmatter_check=True) -> None:
    """Toàn bộ invariant structural. Push vào findings (error chặn, warn = gap)."""
    docs_root = model.docs_root
    ids = model.module_ids

    # 1) frontmatter mỗi doc + id uniqueness + parent/provenance resolve
    if frontmatter_check:
        seen_ids = {}
        for d in model.docs:
            fm.validate(d, findings)
            if d.id:
                seen_ids.setdefault(d.id, []).append(d.rel)
        for _id, paths in seen_ids.items():
            if len(paths) > 1:
                findings.error("duplicate-id", paths[0], f"id `{_id}` trùng ở: {', '.join(paths)}")
        all_ids = set(seen_ids)
        for d in model.docs:
            par = d.meta.get("parent")
            if par and par not in all_ids:
                findings.error("dangling-parent", d.rel, f"parent `{par}` không tồn tại")
            # Phòng thủ: provenance có thể là str hoặc list — chuẩn hoá về list
            prov_list = d.meta.get("provenance") or []
            if not isinstance(prov_list, list):
                prov_list = [prov_list]
            for prov in prov_list:
                if not (docs_root / prov).exists():
                    findings.warn("dangling-provenance", d.rel, f"provenance không thấy: `{prov}`")

    # 2) parts
    for pid, p in model.parts.items():
        if not isinstance(p, dict):
            findings.error("part-shape-bad", str(pid), f"part `{pid}` không phải dict — bỏ qua")
            continue
        if p.get("home") not in ids:
            findings.error("part-bad-home", pid, f"part `{pid}`: home lạ → {p.get('home')}")
        at = p.get("at", "")
        at_path = docs_root / at
        try:
            inside = at_path.resolve().is_relative_to(docs_root.resolve())
        except (OSError, ValueError):
            inside = False
        if at and not inside:
            findings.error("part-at-escape", pid, f"part `{pid}`: at thoát docs-root → {at}")
        elif not at_path.is_file():
            findings.error("part-missing-file", pid, f"part `{pid}`: at thiếu file → {at}")
        if "layer" in p and p["layer"] not in PART_LAYERS:
            findings.error("part-bad-layer", pid, f"part `{pid}`: layer lạ → {p['layer']}")

    # 3) links
    for ln in model.links:
        if not isinstance(ln, dict):
            findings.error("link-shape-bad", str(ln), "link entry không phải dict — bỏ qua")
            continue
        if ln.get("from") not in ids:
            findings.error("link-bad-from", str(ln), f"link from lạ → {ln.get('from')}")
        if ln.get("uses") not in model.parts:
            findings.error("link-dangling", str(ln),
                           f"link gãy: {ln.get('from')} → part '{ln.get('uses')}' không tồn tại")

    # 4) module intrinsic (axis) + display (band)
    for m in model.modules:
        if m.axis and m.axis not in AXES:
            findings.error("module-bad-axis", m.id, f"axis lạ → {m.axis} (∈ {sorted(AXES)})")
        bands = {b[0] for b in _bands_order(model)}
        if not m.band:
            findings.error("module-missing-band", m.id,
                           f"thiếu band (taxonomy ở _index/bands.yaml; legacy: showcase.yaml) (∈ {sorted(bands)})")
        elif m.band not in bands:
            findings.error("module-bad-band", m.id, f"band lạ → {m.band} (∈ {sorted(bands)})")

    # 5) config_parts (PTSP)
    for cid, c in model.config_parts.items():
        if not isinstance(c, dict):
            findings.error("configpart-shape-bad", str(cid), f"config_part `{cid}` không phải dict — bỏ qua")
            continue
        if c.get("home") not in ids:
            findings.error("configpart-bad-home", cid, f"config_part `{cid}`: home lạ → {c.get('home')}")
        if c.get("owner") != "PTSP":
            findings.error("configpart-bad-owner", cid, f"config_part `{cid}`: owner phải PTSP → {c.get('owner')}")
        if not c.get("vi") or not c.get("en"):
            findings.error("configpart-missing-bilingual", cid, f"config_part `{cid}`: thiếu vi/en")

    # 6) safety
    for sfy in model.safety:
        if not isinstance(sfy, dict):
            findings.error("safety-shape-bad", str(sfy), "safety entry không phải dict — bỏ qua")
            continue
        if not sfy.get("id"):
            findings.error("safety-missing-id", str(sfy), "safety thiếu id")
        for anc in (sfy.get("anchors", "") or "").split():
            if anc not in model.parts:
                findings.error("safety-bad-anchor", sfy.get("id", "?"),
                               f"anchor lạ → {anc} (phải là part thật)")

    # 7) foundations
    for f in model.foundations:
        if not isinstance(f, dict):
            findings.error("foundation-shape-bad", str(f), "foundation entry không phải dict — bỏ qua")
            continue
        if not f.get("id"):
            findings.error("foundation-missing-id", str(f), "foundation thiếu id")
        anc = f.get("anchor")
        if anc and anc != "infra" and anc not in model.parts:
            findings.error("foundation-bad-anchor", f.get("id", "?"),
                           f"anchor lạ → {anc} (part thật hoặc 'infra')")

    # 8) capability-driven required-set
    for m in model.modules:
        cap.check_module(docs_root / m.dir, m.dir, m.capabilities, findings)

    # 9) README guard (DRY vs boundary)
    _readme_guard(model, findings)


# ---- generate views -------------------------------------------------------
def generate_views(model: Model, out_dir: str | Path) -> list[str]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    parts, links = model.parts, model.links
    order = {m.id: m.order for m in model.modules}
    home_of = {pid: p["home"] for pid, p in parts.items()}
    consumers = {}
    for ln in links:
        consumers.setdefault(ln["uses"], []).append((ln["from"], ln.get("why", "")))
    reused = sorted({ln["uses"] for ln in links}, key=lambda p: (order.get(home_of.get(p), 0), p))
    reusers = sorted({ln["from"] for ln in links}, key=lambda m: order.get(m, 0))
    written = []

    head = "| Part | Nhà | " + " | ".join(reusers) + " |"
    sep = "|---|---|" + "|".join([":-:"] * len(reusers)) + "|"
    rows = [head, sep]
    for p in reused:
        froms = {f for f, _ in consumers.get(p, [])}
        cells = ["✓" if r in froms else "" for r in reusers]
        rows.append(f"| `{p}` | {home_of.get(p, '?')} | " + " | ".join(cells) + " |")
    grid = "\n".join(rows)
    edges = ["| From | Uses (part) | Nhà | Vì sao |", "|---|---|---|---|"]
    for ln in sorted(links, key=lambda l: (order.get(l["from"], 0), l["uses"])):
        edges.append(f"| {ln['from']} | `{ln['uses']}` | {home_of.get(ln['uses'], '?')} | {ln.get('why','')} |")
    edge_tbl = "\n".join(edges)
    spine = [pid for pid, p in parts.items() if p.get("universal_spine")]
    spine_note = ("\n> **Universal spine:** " + ", ".join(f"`{s}` ({home_of.get(s, '?')})" for s in spine)
                  + " — mọi recipe đi qua.\n") if spine else ""
    stats = (f"- module: **{len(model.modules)}** · part: **{len(parts)}** · "
             f"part reuse: **{len(reused)}** · cạnh: **{len(links)}**")
    matrix = (f"# Reuse matrix (FAP modules)\n\n{GEN_BANNER}\n\n{stats}\n{spine_note}\n"
              f"## Lưới reuse\n\n{grid}\n\n## Cạnh reuse (logical → physical)\n\n{edge_tbl}\n")
    (out_dir / "reuse-matrix.md").write_text(matrix, encoding="utf-8")
    written.append("reuse-matrix.md")

    owned = {}
    for pid, p in parts.items():
        owned.setdefault(p["home"], []).append(pid)
    for m in model.modules:
        lines = []
        for pid in sorted(owned.get(m.id, [])):
            consz = consumers.get(pid, [])
            if parts[pid].get("universal_spine"):
                lines.append(f"- `{pid}` — **universal spine**, mọi recipe đi qua.")
            elif consz:
                who = ", ".join(f"{f} ({w})" if w else f for f, w in
                                sorted(consz, key=lambda c: order.get(c[0], 0)))
                lines.append(f"- `{pid}` ← {who}")
        if not lines:
            continue
        body = (f"# {m.id.upper()} — reused by\n\n{GEN_BANNER}\n\n"
                f"> Đổi/bỏ part dưới = ảnh hưởng module liệt kê (xem reuse-matrix.md).\n\n"
                + "\n".join(lines) + "\n")
        (out_dir / f"{m.id}.reused-by.md").write_text(body, encoding="utf-8")
        written.append(f"{m.id}.reused-by.md")
    return written


# ---- generate showcase data (*.js) ----------------------------------------
def _mid(x):
    return x.upper()


_MOD_TOKEN = re.compile(r"\s*\(?\bMOD-\d+(?:/\d+)*\b\)?", re.IGNORECASE)


def _text_fix(model: Model) -> dict:
    """Map vá hiển thị note/why — presentation: ưu tiên `_present/*` (model.present), fallback legacy showcase."""
    tf = model.present.get("text_fix")
    if tf is None:
        tf = model.showcase.get("text_fix") or {}
    return {str(k): str(v) for k, v in tf.items()} if isinstance(tf, dict) else {}


def _scrub_mod(s, text_fix):
    s = (s or "").strip()
    if s in text_fix:
        return text_fix[s]
    return re.sub(r"\s{2,}", " ", _MOD_TOKEN.sub("", s)).strip(" /,")


def _js_file(path: Path, var, obj):
    path.write_text(JS_BANNER + f"\nvar {var} = " + json.dumps(obj, ensure_ascii=False, indent=2) + ";\n",
                    encoding="utf-8")


def generate_showcase_data(model: Model, out_dir: str | Path) -> list[str]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    parts, links = model.parts, model.links
    order = {m.id: m.order for m in model.modules}
    band_of = {m.id: m.band for m in model.modules}
    home_of = {pid: p["home"] for pid, p in parts.items()}
    text_fix = _text_fix(model)            # vá note/why từ data
    cluster_names = _cluster_names(model)  # tên cụm từ data
    written = []

    consumes, feeds = {}, {}
    for ln in links:
        frm, uses = ln["from"], ln["uses"]
        # Bỏ qua link nếu part không tìm thấy home (tránh KeyError khi _index méo)
        home = home_of.get(uses)
        if home is None:
            continue
        why = ln.get("why", "")
        consumes.setdefault(frm, []).append({"part": uses, "mod": _mid(home), "why": why})
        feeds.setdefault(home, []).append({"part": uses, "mod": _mid(frm), "why": why})
    cfg_by_home = {}
    for cid, c in model.config_parts.items():
        cfg_by_home.setdefault(c["home"], []).append({"id": cid, "vi": c.get("vi", ""), "en": c.get("en", "")})

    # MOD_M4
    m4 = {}
    for m in model.modules:
        eng = [pid for pid, p in parts.items() if p["home"] == m.id]
        m4[_mid(m.id)] = {"band": m.band, "parts": eng, "configParts": cfg_by_home.get(m.id, []),
                          "consumes": consumes.get(m.id, []), "feeds": feeds.get(m.id, [])}
    _js_file(out_dir / "module-m4-data.js", "MOD_M4", m4)
    written.append("module-m4-data.js")

    # PTNT_LAYERS
    bands_order = _bands_order(model)
    by_band = {}
    for m in model.modules:
        by_band.setdefault(m.band, []).append(m.id)
    bands = [{"id": bid, "vi": vi, "en": en,
              "mods": [_mid(x) for x in sorted(by_band.get(bid, []), key=lambda x: order.get(x, 0))]}
             for bid, vi, en in bands_order]
    l3 = [{"id": pid, "mod": _mid(p["home"])} for pid, p in parts.items() if p.get("layer") == "L3"]
    l4 = [{"id": pid, "mod": _mid(p["home"])} for pid, p in parts.items() if p.get("layer") == "L4"]
    founds = [{"id": f.get("id"), "provides": f.get("provides", "")} for f in model.foundations]
    saf = []
    for sfy in model.safety:
        ancs = (sfy.get("anchors", "") or "").split()
        mods, seen = [], set()
        for a in sorted(ancs, key=lambda a: order.get(home_of.get(a, ""), 0)):
            h = home_of.get(a)
            if h is None:
                continue  # anchor không tìm thấy trong parts → bỏ qua an toàn
            mm = _mid(h)
            if mm not in seen:
                seen.add(mm); mods.append(mm)
        saf.append({"id": sfy.get("id"), "vi": sfy.get("vi", ""), "en": sfy.get("en", ""),
                    "anchors": ancs, "mods": mods})
    _js_file(out_dir / "ptnt-layers-data.js", "PTNT_LAYERS",
             {"bands": bands, "l3": l3, "l4": l4, "foundations": founds, "safety": saf})
    written.append("ptnt-layers-data.js")

    # PTNT_CLUSTERS (MOD-FREE)
    cid_of = lambda b: "cl-" + (b or "?")
    clusters = []
    for bid, vi, en in bands_order:
        cparts = [pid for pid, p in parts.items() if band_of.get(p["home"]) == bid]
        cparts.sort(key=lambda pid: order.get(home_of.get(pid, ""), 0))
        nm = cluster_names.get(bid, (vi, en))
        clusters.append({"id": cid_of(bid), "band": bid, "vi": vi, "en": en,
                         "name_vi": nm[0], "name_en": nm[1],
                         "parts": [{"id": pid, "layer": parts[pid].get("layer", "L2"),
                                    "note": _scrub_mod(parts[pid].get("note", ""), text_fix),
                                    "universal": bool(parts[pid].get("universal_spine"))}
                                   for pid in cparts]})
    cl_edges = {}
    for ln in links:
        # Bỏ qua link nếu home/band không tìm thấy (tránh KeyError khi _index méo)
        h_uses = home_of.get(ln["uses"])
        if h_uses is None or band_of.get(h_uses) is None:
            continue
        if band_of.get(ln["from"]) is None:
            continue
        prod = cid_of(band_of[h_uses])
        cons = cid_of(band_of[ln["from"]])
        if prod == cons:
            continue
        key = (prod, cons)
        cl_edges.setdefault(key, {"from": prod, "to": cons, "vias": [], "why": _scrub_mod(ln.get("why", ""), text_fix)})
        if ln["uses"] not in cl_edges[key]["vias"]:
            cl_edges[key]["vias"].append(ln["uses"])
    cl_links = list(cl_edges.values())
    saf_cl = []
    for sfy in model.safety:
        ancs = (sfy.get("anchors", "") or "").split()
        cl, seen = [], set()
        for a in sorted(ancs, key=lambda a: order.get(home_of.get(a, ""), 0)):
            h = home_of.get(a)
            if h is None or band_of.get(h) is None:
                continue  # anchor không tìm thấy → bỏ qua an toàn
            c = cid_of(band_of[h])
            if c not in seen:
                seen.add(c); cl.append(c)
        saf_cl.append({"id": sfy.get("id"), "vi": sfy.get("vi", ""), "en": sfy.get("en", ""),
                       "anchors": ancs, "clusters": cl})
    _js_file(out_dir / "ptnt-clusters-data.js", "PTNT_CLUSTERS",
             {"clusters": clusters, "links": cl_links, "foundations": founds, "safety": saf_cl})
    written.append("ptnt-clusters-data.js")

    # PART_MODREF
    by_part = {}
    for ln in links:
        by_part.setdefault(ln["uses"], set()).add(ln["from"])
    ref = {}
    for pid, p in parts.items():
        cons = sorted(by_part.get(pid, ()), key=lambda mid: order.get(mid, 0))
        ref[pid] = {"owner": _mid(p["home"]), "consumers": [_mid(m) for m in cons],
                    "universal": bool(p.get("universal_spine"))}
    _js_file(out_dir / "part-modref-data.js", "PART_MODREF", ref)
    written.append("part-modref-data.js")
    return written


# ---- derive graph từ frontmatter (DA5 frontmatter-as-SSOT) -----------------
def _home_of_part_doc(model: Model, doc) -> str | None:
    """Module id sở hữu part doc = module có `dir` là tổ tiên dài nhất của `doc.rel`."""
    best = None
    rel = str(doc.rel).replace("\\", "/")
    for m in model.modules:
        prefix = m.dir.replace("\\", "/").rstrip("/") + "/"
        if rel.startswith(prefix) and (best is None or len(m.dir) > len(best.dir)):
            best = m
    return best.id if best else None


def derive_part_graph(model: Model) -> dict:
    """Sinh {parts, links} TỪ frontmatter part doc — graph 1-nguồn (leaf tự giữ fact).

    parts[id] = {home, at, owner, layer?, note?, universal_spine?}; links từ `reuses`
    (authored trên consumer part) → {from: home-của-consumer, uses: part, why}.
    """
    parts: dict = {}
    links: list = []

    def _emit_reuses(from_mod, reuses):
        if from_mod is None:
            return  # part/README ngoài mọi module dir → không emit link from:None (validate bắt part-bad-home)
        for r in (reuses or []):
            if isinstance(r, dict) and r.get("part"):
                links.append({"from": from_mod, "uses": r["part"], "why": r.get("why", "")})

    for d in model.docs:
        t = d.meta.get("type")
        if t == "part" and d.id:
            if d.id in parts:
                # graph chưa-validate: id trùng → last-wins âm thầm = mất part. Từ chối (như merge refuse-malformed).
                raise ValueError(f"derive: part id trùng `{d.id}` ({parts[d.id].get('at')} ↔ {d.rel}) — chạy validate trước")
            home = _home_of_part_doc(model, d)
            entry = {"home": home, "at": str(d.rel).replace("\\", "/")}
            if d.meta.get("owner"):
                entry["owner"] = d.meta["owner"]
            if d.meta.get("layer") is not None:
                entry["layer"] = d.meta["layer"]
            if d.meta.get("note") is not None:
                entry["note"] = d.meta["note"]
            if d.meta.get("universal_spine"):
                entry["universal_spine"] = True
            parts[d.id] = entry
            # part-level reuse: from = module sở hữu part này
            _emit_reuses(home, d.meta.get("reuses"))
        elif t == "module-readme" and d.id:
            # module-level reuse (khớp shape link thật from:<module> uses:<part>)
            _emit_reuses(d.id, d.meta.get("reuses"))
    return {"parts": parts, "links": links}


def derive_modules_yaml(model: Model, *, config_parts: dict | None = None) -> dict:
    """modules.yaml DERIVED: parts/links từ frontmatter + config_parts pass-through.

    config_parts KHÔNG có doc home (pure metadata) → giữ hand-authored, truyền vào hoặc
    lấy từ model.config_parts hiện có. Output KEEP-committed kèm banner GENERATED.
    """
    g = derive_part_graph(model)
    cp = model.config_parts if config_parts is None else config_parts
    out: dict = {"parts": g["parts"]}
    if cp:
        out["config_parts"] = cp
    out["links"] = g["links"]
    return out


# ---- gate: ép convention content⟂_index⟂_present⟂output (C6) ---------------
_PRESENTATION_KEYS = {"order", "sections", "pages", "partial", "category", "text_fix", "detail"}
# Bảng graph re-declare trong README: header có Part/From/Thành-phần + Uses/Nhà/Reuse/Tái-dùng.
# Heuristic (biết-không-đầy-đủ): mở rộng literal VN; strip code-fence trước khi search (tránh false-pos
# bảng-ví-dụ trong ``` ```).
_GRAPH_TABLE_RE = re.compile(
    r"\|[^\n|]*\b(part|from|thành phần|bộ phận)\b[^\n]*\|[^\n]*\b(uses|nhà|reuse|reused|tái dùng|tái sử dụng)\b",
    re.IGNORECASE)
_FENCE_RE = re.compile(r"```.*?```", re.DOTALL)


def _split_adopted(model: Model) -> bool:
    """Tree đã adopt convention mới = có bands.yaml | _present/ | playbook.yaml.

    Legacy (chỉ showcase.yaml) → KHÔNG ép (back-compat tới khi migrate)."""
    r = model.docs_root
    return ((r / "_index" / "bands.yaml").is_file()
            or (r / "_present").is_dir()
            or (r / "playbook.yaml").is_file())


def _safe_yaml(path: Path) -> dict:
    try:
        data = yaml_io.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml_io.YAMLError:
        return {}
    return data if isinstance(data, dict) else {}


def validate_clean_split(model: Model, findings) -> None:
    """Ép tách 4 lớp (C6). Chỉ chạy khi tree đã adopt convention mới."""
    if not _split_adopted(model):
        return
    root = model.docs_root

    # 1) output dẫn xuất nằm trong cây nguồn (phải gitignore + build ra out-dir)
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(root).as_posix()
        if is_derived_output(rel):
            findings.error("derived-committed", rel,
                           "output dẫn xuất commit trong cây nguồn — gitignore + build ra out-dir")

    # 2) presentation key trong _index/*.yaml (phải ở _present/)
    idx = root / "_index"
    if idx.is_dir():
        for y in sorted(idx.glob("*.yaml")):
            data = _safe_yaml(y)
            rel = y.relative_to(root).as_posix()
            for k in sorted(set(data) & _PRESENTATION_KEYS):
                findings.error("presentation-in-index", rel,
                               f"key trình bày `{k}` trong _index — chuyển sang _present/")
            for m in (data.get("modules") or []):
                if isinstance(m, dict) and "order" in m:
                    findings.error("presentation-in-index", rel,
                                   f"module `{m.get('id')}` mang `order` (presentation) trong _index — chuyển _present/")
                    break

    # 3) band/cluster (design taxonomy) trong _present/*.yaml (phải ở bands.yaml)
    pres = root / "_present"
    if pres.is_dir():
        for y in sorted(pres.glob("*.yaml")):
            data = _safe_yaml(y)
            rel = y.relative_to(root).as_posix()
            if "bands" in data or "cluster" in data:
                findings.error("band-in-present", rel,
                               "design taxonomy `bands`/`cluster` trong _present — chuyển sang _index/bands.yaml")
                continue
            for m in (data.get("modules") or []):
                if isinstance(m, dict) and ("band" in m or "cluster" in m):
                    findings.error("band-in-present", rel,
                                   f"module `{m.get('id')}` mang `band` (taxonomy) trong _present — chuyển bands.yaml")
                    break

    # 4) README re-declare graph (parts/reuse) — phải reference-only (link reuse-matrix)
    for m in model.modules:
        rp = root / m.dir / "README.md"
        if not rp.is_file():
            continue
        body = _FENCE_RE.sub("", rp.read_text(encoding="utf-8"))  # bỏ code-fence (bảng ví dụ không tính)
        if _GRAPH_TABLE_RE.search(body):
            findings.error("graph-redeclared-in-readme", f"{m.dir}/README.md",
                           "README re-declare graph (bảng part/reuse) — giữ reference-only, link reuse-matrix")
