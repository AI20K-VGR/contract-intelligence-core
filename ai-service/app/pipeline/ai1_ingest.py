"""Mock AI1: one or more PDFs → snapshots + tree. AI2 never receives PDF bytes."""

from __future__ import annotations

import hashlib
import io
import re
from uuid import uuid4

from app.contracts.models import SourceFile, TableSnapshot, ToolEnvelope
from app.pipeline.structure import is_structural_heading
from app.tools.store import DossierRecord
from fixtures.catalog import PROFILE_V5, make_envelope, make_node, make_page, make_pins, make_record


def digest_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()[:32]


def ingest_files(
    items: list[tuple[str, bytes, str]],
) -> tuple[DossierRecord, ToolEnvelope, dict, dict[str, bytes]]:
    """items: (filename, data, role body|annex). Returns record, envelope, meta, blobs."""
    if not items:
        raise ValueError("no files")
    dossier_id = f"d_{uuid4().hex[:10]}"
    combined = b"".join(d for _, d, _ in items)
    pins = make_pins(source_snapshot_digest=digest_bytes(combined), ocr_run_version=1, reconstruction_version=1)
    pages = []
    nodes: list = []
    tables: list[TableSnapshot] = []
    source_files: list[SourceFile] = []
    blobs: dict[str, bytes] = {}
    page_no = 1
    order = 0
    field_i = 1
    clause_i = 1
    engines: list[str] = []

    for idx, (filename, data, role) in enumerate(items):
        file_id = f"src_{idx}_{uuid4().hex[:6]}"
        texts, engine = extract_page_texts(filename, data)
        engines.append(engine)
        n_pages = max(1, len(texts))
        source_files.append(
            SourceFile(
                file_id=file_id,
                filename=filename,
                role="annex" if role == "annex" else "body",
                digest=digest_bytes(data),
                n_pages=n_pages,
            )
        )
        blobs[file_id] = data
        label = "Hợp đồng" if role != "annex" else f"Phụ lục — {filename}"
        root_id = f"file_{file_id}"
        start = page_no
        nodes.append(
            make_node(
                root_id,
                "SECTION",
                label,
                filename,
                order=order,
                page=start,
                has_children=True,
                page_range=list(range(start, start + n_pages)),
                source_file_id=file_id,
                page_in_file=1,
            )
        )
        order += 1
        added = 0
        last_party = None
        parent = section = root_id
        for local, text in enumerate(texts, start=1):
            quality = "EMPTY" if not text.strip() else ("LOW" if len(text.strip()) < 40 else "OK")
            page_text = text[:8000]
            line_texts = {
                f"{file_id}_p{local}_line{line_no}": line
                for line_no, line in enumerate(page_text.splitlines(), start=1)
            }
            line_ids = list(line_texts)
            pages.append(
                make_page(
                    page_no,
                    page_text,
                    quality=quality,
                    source_file_id=file_id,
                    page_in_file=local,
                    page_revision_id=f"{file_id}_p{local}_rev1",
                    line_texts=line_texts,
                    source_hash=digest_bytes(data),
                )
            )
            ns, ts, order, field_i, clause_i, parent, section, last_party = _parse_page(
                text,
                page_no=page_no,
                local=local,
                file_id=file_id,
                root_id=root_id,
                parent=parent,
                section=section,
                order=order,
                field_i=field_i,
                clause_i=clause_i,
                last_party=last_party,
                source_line_ids=line_ids,
            )
            nodes.extend(ns)
            tables.extend(ts)
            added += len(ns)
            page_no += 1
        if added == 0:
            blob = texts[0][:500] if texts else filename
            nodes.append(
                make_node(
                    f"body_{file_id}",
                    "UNNUMBERED_BLOCK",
                    "Nội dung",
                    blob,
                    parent_id=root_id,
                    order=order,
                    page=start,
                    source_file_id=file_id,
                    page_in_file=1,
                    source_line_ids=line_ids,
                )
            )
            order += 1

    rec = make_record(
        case_id="UPLOAD",
        dossier=dossier_id,
        pages=pages,
        nodes=nodes,
        tables=tables,
        pins=pins,
        profile=PROFILE_V5,
        source_files=source_files,
    )
    env = make_envelope(dossier=dossier_id, pins=pins)
    meta = {
        "engine": ",".join(engines),
        "n_pages": len(pages),
        "n_nodes": len(nodes),
        "n_tables": len(tables),
        "n_files": len(source_files),
        "digest": pins.source_snapshot_digest,
        "note": "AI1 lấy chữ sẵn trong tệp. AI2 không nhận byte PDF. Tô sáng trên PDF gốc.",
        "files": [f.model_dump() for f in source_files],
    }
    return rec, env, meta, blobs


def ingest_upload(filename: str, data: bytes):
    role = "annex" if _looks_annex(filename) else "body"
    rec, env, meta, blobs = ingest_files([(filename, data, role)])
    meta["filename"] = filename
    return rec, env, meta, blobs


def extract_page_texts(filename: str, data: bytes) -> tuple[list[str], str]:
    name = filename.lower()
    if name.endswith(".pdf"):
        try:
            from pypdf import PdfReader

            reader = PdfReader(io.BytesIO(data))
            texts = [(p.extract_text() or "").strip() for p in reader.pages]
            if not texts:
                texts = [""]
            return texts, "pdf_native"
        except Exception:
            return [_chunk_fallback(data)], "pdf_unreadable"
    text = data.decode("utf-8", errors="replace")
    parts = [p.strip() for p in re.split(r"\n\s*---+\s*\n|\f", text) if p.strip()]
    if len(parts) <= 1:
        parts = _paginate(text, 1600)
    return parts or [text[:1600] or filename], "text"


def _looks_annex(filename: str) -> bool:
    n = filename.lower()
    return "phu" in n or "annex" in n or "pl" in n or "phụ" in n


def _paginate(text: str, size: int) -> list[str]:
    chunks = []
    rest = text.strip()
    while rest:
        chunks.append(rest[:size])
        rest = rest[size:]
    return chunks or [""]


def _chunk_fallback(data: bytes) -> str:
    try:
        return data.decode("latin-1")[:4000]
    except Exception:
        return ""


def _parse_page(
    text: str,
    *,
    page_no: int,
    local: int,
    file_id: str,
    root_id: str,
    parent: str,
    section: str,
    order: int,
    field_i: int,
    clause_i: int,
    last_party: str | None = None,
    source_line_ids: list[str] | None = None,
):
    nodes = []
    tables: list[TableSnapshot] = []
    for line in text.splitlines():
        s = re.sub(r"^[#>\-\*]+\s*", "", line).strip()
        if not s or len(s) < 4:
            continue
        low_line = s.lower()
        kw = dict(
            source_file_id=file_id,
            page_in_file=local,
            page_revision_id=f"{file_id}_p{local}_rev1",
            source_line_ids=list(source_line_ids or []),
        )
        # A page line may contain several parties and tax IDs, for example:
        # "Bên A: ... MST ... Bên B: ... MST ...".  Do not use one
        # re.search() result for the whole line: that silently drops every
        # occurrence after the first one and assigns both MSTs to one party.
        # Only a declaration marker is a party declaration.  Mentions such as
        # "Bên A thanh toán..." remain clause text and must not become a
        # second party name or MST candidate.
        party_matches = list(re.finditer(r"\bBên\s+([ABCY])\b(?=\s*(?:[:—–-]))", s, re.I))
        if party_matches:
            last_party = party_matches[-1].group(1).upper()
        mst_matches = list(
            re.finditer(
                r"\bMST[:\s]+(\d{8,14})\b|Mã số thuế[^0-9]{0,24}(\d{8,14})",
                s,
                re.I,
            )
        )
        # A discrepancy line may mention the role before its tax ID without
        # using a declaration separator, for example "Bên A được ghi: ...
        # MST ...".  Use it only when the same line contains an MST; ordinary
        # clause mentions such as "Bên A thanh toán" must not switch context.
        if not party_matches and mst_matches:
            role_mentions = list(re.finditer(r"\bBên\s+([ABCY])\b", s, re.I))
            if role_mentions:
                last_party = role_mentions[-1].group(1).upper()

        # Party declarations commonly live inside Điều 1. The declaration
        # marker (colon/em dash) already distinguishes them from role mentions
        # in ordinary clauses, so do not suppress them merely because the
        # current structural parent is a clause.
        if not str(parent or "").startswith("cl_") or party_matches:
            for party_index, ben in enumerate(party_matches):
                letter = ben.group(1).upper()
                segment_end = party_matches[party_index + 1].start() if party_index + 1 < len(party_matches) else len(s)
                segment = s[ben.start() : segment_end]
                name_m = re.search(r"(Công ty[^.\n]{2,80})", segment, re.I)
                name = name_m.group(1) if name_m else segment[:80]
                name = re.sub(r"\s*MST[:\s]*\d{8,14}.*", "", name, flags=re.I).strip(" :;,.\t")[:80]
                nodes.append(
                    make_node(
                        f"field_party_{field_i}",
                        "FIELD",
                        f"Bên {letter}",
                        segment[:400],
                        parent_id=parent,
                        order=order,
                        page=page_no,
                    structured_key=f"party_{letter.lower()}",
                        structured_value=name,
                        **kw,
                    )
                )
                field_i += 1
                order += 1

        for mst in mst_matches:
            preceding_parties = [p for p in party_matches if p.start() <= mst.start()]
            letter = preceding_parties[-1].group(1).upper() if preceding_parties else (last_party or "")
            if "nhà cung cấp" in low_line or "danh mục" in low_line:
                mst_key = "mst_supplier"
            elif letter in {"A", "B", "C", "Y"}:
                mst_key = f"mst_party_{letter.lower()}"
            else:
                mst_key = "mst_seller"
            value = next(group for group in mst.groups() if group)
            nodes.append(
                make_node(
                    f"field_mst_{field_i}",
                    "FIELD",
                    "MST nhà cung cấp" if mst_key == "mst_supplier" else ("MST" + (f" Bên {letter}" if letter else "")),
                    mst.group(0),
                    parent_id=parent,
                    order=order,
                    page=page_no,
                    structured_key=mst_key,
                    structured_value=value,
                    **kw,
                )
            )
            field_i += 1
            order += 1
        item_m = (
            re.search(r"\bItem\s+([A-Za-z0-9]+)\s*:", s, re.I)
            or re.search(r"hạng mục\s+([A-Za-z0-9]+)", s, re.I)
            or re.search(r"sửa\s+([A-Za-z0-9]+)\s+thành", s, re.I)
            or re.match(r"^([A-Z])\s*:\s*\d", s)
        )
        fee_m = re.search(r"Phí\s+([A-Za-z0-9]+)\s*:", s, re.I)
        money_m = re.search(r"(\d[\d.\s]*)\s*(VND|USD|%)", s, re.I)
        if item_m and money_m:
            key = item_m.group(1)
            nodes.append(
                make_node(
                    f"field_item_{field_i}",
                    "FIELD",
                    f"Item {key}",
                    s[:400],
                    parent_id=parent,
                    order=order,
                    page=page_no,
                    structured_key=f"item:{key}",
                    structured_value=re.sub(r"\D", "", money_m.group(1)),
                    **kw,
                )
            )
            field_i += 1
            order += 1
            continue
        if fee_m and money_m:
            key = fee_m.group(1)
            nodes.append(
                make_node(
                    f"field_fee_{field_i}",
                    "FIELD",
                    f"Phí {key}",
                    s[:400],
                    parent_id=parent,
                    order=order,
                    page=page_no,
                    structured_key=f"scope:{key}",
                    structured_value=money_m.group(0).replace(" ", ""),
                    **kw,
                )
            )
            field_i += 1
            order += 1
            continue
        spec = _money_field_spec(s)
        if spec:
            key, val = spec
            nodes.append(
                make_node(
                    f"field_amt_{field_i}",
                    "FIELD",
                    key.split(":", 1)[-1],
                    s[:400],
                    parent_id=parent,
                    order=order,
                    page=page_no,
                    structured_key=key,
                    structured_value=val,
                    **kw,
                )
            )
            field_i += 1
            order += 1
            _append_text(nodes, parent, s)
            continue
        is_section_heading = bool(
            is_structural_heading(s)
            and (
                re.match(r"^(PHẦN|Phần|CHƯƠNG|Chương|MỤC|Mục)\s+\d+", s)
                or re.match(r"^(Phụ lục|PHỤ LỤC)\s+\d+\s*(?:[-–—:]|$)", s, re.I)
            )
        )
        if is_section_heading and not re.match(r"^(Điều|ĐIỀU|Article|Khoản|KHOẢN|Điểm|ĐIỂM)\b", s, re.I):
            nid = f"sec_{order}"
            nodes.append(make_node(nid, "SECTION", s[:80], s[:800], parent_id=root_id, order=order, page=page_no, has_children=True, **kw))
            section = parent = nid
            order += 1
            continue
        if re.match(r"^(Phụ lục|PHỤ LỤC)\s+\S+", s, re.I):
            nid = f"pl_{order}"
            nodes.append(make_node(nid, "SECTION", s[:80], s[:800], parent_id=root_id, order=order, page=page_no, has_children=True, **kw))
            section = parent = nid
            order += 1
            continue
        if re.match(r"^(Điều|ĐIỀU|Article)\s+[\d.]+", s, re.I):
            nid = f"cl_{clause_i}"
            nodes.append(make_node(nid, "CLAUSE", s[:80], s[:1200], parent_id=section, order=order, page=page_no, **kw))
            parent = nid
            clause_i += 1
            order += 1
            continue
        annex_cite = re.search(r"(phụ lục|phu luc)\s+(\d+)", s, re.I)
        if annex_cite and not re.match(r"^(Phụ lục|PHỤ LỤC)\s+", s, re.I):
            _append_text(nodes, parent, s)
            nodes.append(
                make_node(
                    f"field_ref_{field_i}",
                    "FIELD",
                    "Viện dẫn phụ lục",
                    s[:400],
                    parent_id=parent,
                    order=order,
                    page=page_no,
                    structured_key="annex_ref",
                    structured_value=f"Phụ lục {annex_cite.group(2)}",
                    **kw,
                )
            )
            field_i += 1
            order += 1
            continue
        _append_text(nodes, parent, s)
    if "|" in text and text.count("|") >= 4:
        tid = f"tbl_p{page_no}"
        rows = [[c.strip() for c in ln.split("|") if c.strip()][:4] for ln in text.splitlines() if "|" in ln][:8]
        if rows:
            width = max(len(r) for r in rows)
            header = [f"cột {i+1}" for i in range(width)]
            padded = [r + [None] * (width - len(r)) for r in rows]
            kw = dict(
                source_file_id=file_id,
                page_in_file=local,
                page_revision_id=f"{file_id}_p{local}_rev1",
                source_line_ids=list(source_line_ids or []),
            )
            nodes.append(make_node(tid, "TABLE", f"Bảng trang {page_no}", " ".join(header), parent_id=parent, order=order, page=page_no, **kw))
            tables.append(TableSnapshot(table_id=tid, title=f"Bảng p{page_no}", header=header, rows=padded, node_id=tid))
            order += 1
    return nodes, tables, order, field_i, clause_i, parent, section, last_party


def _append_text(nodes: list, parent_id: str | None, line: str) -> None:
    if not parent_id or not line:
        return
    owner = next((n for n in nodes if n.node_id == parent_id), None)
    if owner is None or owner.type not in {"CLAUSE", "SECTION", "UNNUMBERED_BLOCK"}:
        return
    extra = "\n" + line
    owner.text = ((owner.text or "") + extra)[:4000]


def _money_field_spec(s: str) -> tuple[str, str] | None:
    low = s.lower()
    if re.search(r"phạt|%/ngày|%/ngay", low):
        m = re.search(r"(\d+,\d+|\d+\.\d+|\d+)\s*%", s)
        if m:
            return _penalty_key(low), m.group(0).replace(" ", "")
    if re.search(r"giá hợp đồng|giá trị hợp đồng|giá trị nêu|giá trị\s*:|bảng tóm tắt", low):
        m = re.search(r"(\d{1,3}(?:\.\d{3})+|\d{7,})\s*VND", s, re.I)
        if m:
            return "item:contract_value", re.sub(r"\D", "", m.group(1))
    m = re.search(r"(\d+)\s*USD", s, re.I)
    if m and re.search(r"đơn giá|don gia|usd/bộ|usd/bo|thiết bị nhập", low):
        return "item:price_usd", m.group(1)
    return None


def _penalty_key(low: str) -> str:
    if "xây lắp" in low or "xay lap" in low:
        return "item:penalty_construction"
    if "thiết bị" in low or "thiet bi" in low:
        return "item:penalty_equipment"
    if "dưới 10" in low or "duoi 10" in low:
        return "item:penalty_lt10"
    if "từ 10" in low or "tu 10" in low:
        return "item:penalty_gte10"
    return "item:penalty_general"
