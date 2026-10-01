"""Adapter for the OCR-lab snapshot shape emitted by the current AI1 runs.

The OCR-lab producer uses the name ``ai1.snapshot.v1`` but its payload is a
different, deliberately richer shape than the canonical AI2 contract.  This
module consumes that shape without fabricating canonical fields or discarding
root-level structure and continuity evidence.
"""

from __future__ import annotations

import hashlib
import re
from collections import Counter, defaultdict
from typing import Any, Mapping

from app.contracts.models import (
    AuthContext,
    Citation,
    HandoffIssue,
    LifecycleState,
    PageSnapshot,
    ReviewState,
    SourceFile,
    StructuralNode,
    TableCell,
    TableCoverage,
    TableSnapshot,
    TenantProfile,
    ToolEnvelope,
    VersionPins,
)
from app.pipeline.ai1_snapshot_adapter import SnapshotAdapterResult, SnapshotContractError, fold_for_match
from app.pipeline.citations import CitationResolver, quote_digest
from app.tools.store import DossierRecord


_SUPPORTED_NODE_TYPES = {"ARTICLE", "CLAUSE", "POINT", "UNMARKED"}
_GEOMETRY = {"MEASURED", "DERIVED", "CLAIMED", "ABSENT", "UNKNOWN"}


def is_ocr_lab_snapshot(payload: Mapping[str, Any]) -> bool:
    """Return true only for the observed OCR-lab producer shape."""

    return (
        payload.get("schema_version") == "ai1.snapshot.v1"
        and isinstance(payload.get("filename"), str)
        and isinstance(payload.get("document_role"), str)
        and isinstance(payload.get("input_type"), str)
        and isinstance(payload.get("engine"), Mapping)
        and isinstance(payload.get("nodes"), list)
        and "table_continuity" in payload
    )


def adapt_ocr_lab_snapshot(
    snapshot: Mapping[str, Any],
    *,
    tenant_id: str = "tenant_a",
    actor_id: str = "user_001",
    profile: TenantProfile | None = None,
    acl_revision: int = 1,
    scope_id: str | None = None,
) -> SnapshotAdapterResult:
    """Adapt one OCR-lab JSON snapshot into the existing AI2 runtime model."""

    if not isinstance(snapshot, Mapping):
        raise SnapshotContractError("OCR-lab snapshot must be an object")
    required = ("schema_version", "snapshot_id", "source_digest", "dossier_id", "document_id", "pages", "nodes")
    missing = [name for name in required if name not in snapshot]
    if missing:
        raise SnapshotContractError(
            f"OCR-lab snapshot missing required fields: {', '.join(missing)}",
            code="OCR_LAB_INPUT_INVALID",
        )
    if snapshot.get("schema_version") != "ai1.snapshot.v1":
        raise SnapshotContractError("schema_version must be ai1.snapshot.v1", code="OCR_LAB_INPUT_INVALID")
    pages_in = snapshot.get("pages")
    nodes_in = snapshot.get("nodes")
    if not isinstance(pages_in, list) or not pages_in:
        raise SnapshotContractError("pages must be a non-empty array", code="OCR_LAB_INPUT_INVALID")
    if not isinstance(nodes_in, list):
        raise SnapshotContractError("nodes must be an array", code="OCR_LAB_INPUT_INVALID")

    raw_digest = str(snapshot.get("source_digest"))
    digest = _normalize_digest(raw_digest)
    profile = profile or TenantProfile(version=1)
    document_id = str(snapshot["document_id"])
    original_dossier_id = str(snapshot["dossier_id"])
    effective_dossier_id = scope_id or original_dossier_id
    snapshot_id = str(snapshot["snapshot_id"])
    source_role = str(snapshot.get("document_role") or "")
    input_type = str(snapshot.get("input_type") or "")
    engine = snapshot.get("engine")
    engine_name = str(engine.get("name") or "") if isinstance(engine, Mapping) else str(engine or "")
    engine_version = str(engine.get("version") or "") if isinstance(engine, Mapping) else None
    pages: list[PageSnapshot] = []
    issues: list[HandoffIssue] = []
    page_by_number: dict[int, PageSnapshot] = {}
    line_by_id: dict[str, tuple[PageSnapshot, Mapping[str, Any]]] = {}

    try:
        expected_page_count = int(snapshot.get("page_count")) if snapshot.get("page_count") is not None else None
    except (TypeError, ValueError):
        expected_page_count = None
        issues.append(_issue("PAGE_COUNT_INVALID", "page_count is not an integer", document_id, stage="INPUT"))
    if expected_page_count is not None and expected_page_count != len(pages_in):
        issues.append(_issue(
            "PAGE_COUNT_MISMATCH",
            f"page_count={expected_page_count}, received={len(pages_in)}",
            document_id,
            stage="INPUT",
        ))

    for index, raw_page in enumerate(pages_in, start=1):
        if not isinstance(raw_page, Mapping):
            raise SnapshotContractError(f"page {index} must be an object", code="OCR_LAB_INPUT_INVALID")
        page_number = _positive_int(raw_page.get("page_number"), f"page {index} page_number")
        if page_number in page_by_number:
            raise SnapshotContractError(f"duplicate page_number={page_number}", code="OCR_LAB_INPUT_INVALID")
        raw_lines = raw_page.get("lines") if isinstance(raw_page.get("lines"), list) else []
        page_text = str(raw_page.get("text") or "")
        line_texts: dict[str, str] = {}
        line_bboxes: dict[str, list[float]] = {}
        source_block_ids: list[str] = []
        page_revision_id = f"{snapshot_id}:p{page_number}"
        for line_index, raw_line in enumerate(raw_lines, start=1):
            if not isinstance(raw_line, Mapping):
                issues.append(_issue("LINE_INVALID", f"page {page_number} line {line_index} is not an object", document_id))
                continue
            line_id = str(raw_line.get("line_id") or f"{document_id}:p{page_number}:l{line_index:03d}")
            if line_id in line_by_id:
                raise SnapshotContractError(f"duplicate line_id={line_id}", code="OCR_LAB_INPUT_INVALID")
            line_texts[line_id] = str(raw_line.get("text") or "")
            bbox = _bbox(raw_line.get("bbox_normalized"))
            if raw_line.get("bbox_normalized") is not None and not bbox:
                issues.append(_issue("BBOX_INVALID", f"line {line_id} has invalid normalized bbox", document_id, location=line_id))
            if bbox:
                line_bboxes[line_id] = bbox
            source_block_ids.append(line_id)
            # The page is not in page_by_number until after construction, so
            # keep a temporary record and attach it below.
            line_by_id[line_id] = (None, raw_line)  # type: ignore[assignment]

        status = str(raw_page.get("status") or "PARTIAL").upper()
        quality = _quality(status, page_text, raw_lines, raw_page.get("error"))
        table_status = str(raw_page.get("table_status") or "UNKNOWN").upper()
        try:
            coverage = TableCoverage(table_status)
        except ValueError:
            coverage = TableCoverage.DETECTED if raw_page.get("tables") else TableCoverage.UNKNOWN
            issues.append(_issue("TABLE_STATUS_UNKNOWN", f"page {page_number}: {table_status}", document_id))
        if coverage == TableCoverage.DETECTED and not raw_page.get("tables"):
            issues.append(_issue("TABLE_STRUCTURE_UNAVAILABLE", f"page {page_number}: table detected without table payload", document_id))
        if isinstance(raw_page.get("words"), list) and not raw_page.get("words") and raw_lines:
            issues.append(_issue(
                "WORD_GEOMETRY_UNAVAILABLE",
                f"page {page_number}: lines exist but words[] is empty",
                document_id,
                location=page_revision_id,
            ))
        analysis_text = _analysis_view(page_text)
        page = PageSnapshot(
            page_revision_id=page_revision_id,
            page_number=page_number,
            quality=quality,
            coverage=0.0 if quality in {"FAILED", "EMPTY"} else 1.0,
            rotation=int(raw_page.get("rotation_degrees") or 0),
            source_block_ids=source_block_ids,
            text=page_text,
            source_file_id=document_id,
            page_in_file=page_number,
            table_coverage=coverage,
            width=_optional_int(raw_page.get("source_page_width")),
            height=_optional_int(raw_page.get("source_page_height")),
            image_key=str(raw_page.get("page_image_ref")) if raw_page.get("page_image_ref") else None,
            line_texts=line_texts,
            line_bboxes=line_bboxes,
            source_hash=digest,
            analysis_text=analysis_text if analysis_text != page_text else None,
            analysis_line_texts={line_id: _analysis_view(text) for line_id, text in line_texts.items()},
        )
        pages.append(page)
        page_by_number[page_number] = page
        for line_id, raw_line in list(line_by_id.items()):
            if raw_line[0] is None:
                line_by_id[line_id] = (page, raw_line[1])

    pages.sort(key=lambda item: item.page_number)
    if [page.page_number for page in pages] != list(range(1, len(pages) + 1)):
        issues.append(_issue("PAGE_SEQUENCE_GAP", "page numbers are not contiguous from 1", document_id, stage="INPUT"))

    line_lookup = {line_id: (page, raw_line) for line_id, (page, raw_line) in line_by_id.items()}
    nodes, node_issues = _adapt_nodes(nodes_in, document_id, page_by_number, line_lookup, source_role)
    issues.extend(node_issues)
    tables, table_nodes, table_issues = _adapt_tables(snapshot, document_id, pages, digest, source_role)
    issues.extend(table_issues)
    nodes.extend(table_nodes)

    source_file = SourceFile(
        file_id=document_id,
        filename=str(snapshot.get("filename") or f"ai1:{document_id}"),
        # Legacy routing only understands body/annex.  Raw contract role is
        # retained separately and independent batch mode prevents comparison.
        role=source_role if source_role in {"body", "annex"} else "body",
        digest=digest,
        n_pages=len(pages),
        document_role=source_role or None,
        input_type=input_type or None,
        engine=engine_name or None,
        raw_digest=raw_digest,
    )
    pins = VersionPins(
        manifest_version=1,
        source_snapshot_digest=digest,
        source_digest=digest,
        snapshot_digest=digest,
        tenant_profile_version=profile.version,
        policy_version=1,
        ocr_run_version=1,
        reconstruction_version=1,
        extraction_version=1,
    )
    record = DossierRecord(
        tenant_id=tenant_id,
        dossier_id=effective_dossier_id,
        lifecycle=LifecycleState.ACTIVE,
        pins=pins,
        pages=pages,
        nodes=nodes,
        tables=tables,
        profile=profile,
        acl_revision=acl_revision,
        permissions_by_actor={actor_id: ["READ_CONTENT"]},
        source_files=[source_file],
        case_id="AI1-OCR-LAB",
        handoff_issues=issues,
    )
    envelope = ToolEnvelope(
        auth=AuthContext(
            actor_id=actor_id,
            tenant_id=tenant_id,
            dossier_id=effective_dossier_id,
            acl_revision=acl_revision,
            permissions=["READ_CONTENT"],
        ),
        pins=pins.model_copy(),
    )
    return SnapshotAdapterResult(
        record=record,
        envelope=envelope,
        meta={
            "source": "ai1.snapshot.v1",
            "adapter": "ocr-lab",
            "snapshot_id": snapshot_id,
            "document_id": document_id,
            "dossier_id": original_dossier_id,
            "effective_dossier_id": effective_dossier_id,
            "filename": source_file.filename,
            "document_role": source_role,
            "input_type": input_type,
            "engine": engine_name,
            "engine_version": engine_version,
            "raw_source_digest": raw_digest,
            "n_pages": len(pages),
            "n_nodes": len(nodes),
            "n_tables": len(tables),
            "n_handoff_issues": len(issues),
            "table_continuity": snapshot.get("table_continuity") or [],
        },
    )


def _adapt_nodes(
    raw_nodes: list[Any],
    document_id: str,
    pages: Mapping[int, PageSnapshot],
    lines: Mapping[str, tuple[PageSnapshot, Mapping[str, Any]]],
    source_role: str,
) -> tuple[list[StructuralNode], list[HandoffIssue]]:
    raw_ids = [str(item.get("node_id")) for item in raw_nodes if isinstance(item, Mapping)]
    counts = Counter(raw_ids)
    issues: list[HandoffIssue] = []
    for raw_id, count in counts.items():
        if raw_id and count > 1:
            issues.append(_issue(
                "STRUCTURE_DUPLICATE_NODE_ID",
                f"node_id={raw_id} occurs {count} times; occurrence IDs were generated",
                document_id,
                location=raw_id,
                stage="STRUCTURE",
            ))
    occurrences: defaultdict[str, int] = defaultdict(int)
    unique_internal: dict[str, str] = {}
    for raw_id, count in counts.items():
        if count == 1:
            unique_internal[raw_id] = raw_id
    out: list[StructuralNode] = []
    for order, item in enumerate(raw_nodes):
        if not isinstance(item, Mapping):
            issues.append(_issue("NODE_INVALID", f"node index {order} is not an object", document_id, stage="STRUCTURE"))
            continue
        raw_id = str(item.get("node_id") or f"node-{order + 1}")
        occurrences[raw_id] += 1
        internal_id = raw_id if counts[raw_id] == 1 else f"{raw_id}#occ{occurrences[raw_id]}"
        raw_type = str(item.get("type") or "UNMARKED").upper()
        if raw_type not in _SUPPORTED_NODE_TYPES:
            issues.append(_issue("NODE_TYPE_UNKNOWN", f"node {raw_id}: {raw_type}", document_id, location=raw_id, stage="STRUCTURE"))
        canonical_type = {"ARTICLE": "SECTION", "CLAUSE": "CLAUSE", "POINT": "CLAUSE", "UNMARKED": "UNNUMBERED_BLOCK"}.get(raw_type, "UNNUMBERED_BLOCK")
        page_start = _optional_int(item.get("page_start")) or 1
        page_end = _optional_int(item.get("page_end")) or page_start
        page_range = list(range(page_start, page_end + 1)) if page_end >= page_start else [page_start]
        valid_pages = [page_no for page_no in page_range if page_no in pages]
        if len(valid_pages) != len(page_range):
            issues.append(_issue("NODE_PAGE_REFERENCE_INVALID", f"node {raw_id} references pages outside snapshot", document_id, location=raw_id, stage="STRUCTURE"))
        line_ids = [str(value) for value in (item.get("line_ids") or [])]
        unknown_lines = sorted(set(line_ids) - set(lines))
        if unknown_lines:
            issues.append(_issue("NODE_LINE_REFERENCE_INVALID", f"node {raw_id} unknown line_ids={unknown_lines}", document_id, location=raw_id, stage="STRUCTURE"))
        node_text = "\n".join(str(lines[line_id][1].get("text") or "") for line_id in line_ids if line_id in lines)
        first_page = pages.get(valid_pages[0] if valid_pages else page_start)
        parent_raw = str(item.get("parent_id")) if item.get("parent_id") is not None else None
        parent_id = unique_internal.get(parent_raw or "")
        if parent_raw and parent_raw not in unique_internal:
            issues.append(_issue(
                "AMBIGUOUS_PARENT_REFERENCE",
                f"node {raw_id} parent_id={parent_raw} is duplicated or unavailable; parent not attached",
                document_id,
                location=raw_id,
                stage="STRUCTURE",
            ))
        raw_label = str(item.get("label_raw") or item.get("label_normalized") or raw_id)
        out.append(
            StructuralNode(
                node_id=internal_id,
                source_node_id=raw_id,
                type=canonical_type,
                raw_label=raw_label,
                parent_id=parent_id,
                order=order,
                status="CONFIRMED" if not unknown_lines and valid_pages else "PARTIAL",
                text=node_text,
                page_range=valid_pages or [page_start],
                page_revision_id=first_page.page_revision_id if first_page else None,
                bbox=_bbox(item.get("bbox_normalized")),
                source_file_id=document_id,
                page_in_file=page_start,
                provenance="AI1",
                structure_level="SECTION" if canonical_type == "SECTION" else "BLOCK",
                scope_id=source_role or None,
                source_line_ids=line_ids,
            )
        )
    return out, issues


def _adapt_tables(
    snapshot: Mapping[str, Any],
    document_id: str,
    pages: list[PageSnapshot],
    digest: str,
    source_role: str,
) -> tuple[list[TableSnapshot], list[StructuralNode], list[HandoffIssue]]:
    tables: list[TableSnapshot] = []
    nodes: list[StructuralNode] = []
    issues: list[HandoffIssue] = []
    page_by_number = {page.page_number: page for page in pages}
    embedded_annex_pages = _embedded_annex_pages(snapshot)
    raw_table_entries: list[tuple[int, Mapping[str, Any]]] = []
    for page in snapshot.get("pages") or []:
        if not isinstance(page, Mapping):
            continue
        page_number = _optional_int(page.get("page_number")) or 0
        for raw_table in page.get("tables") or []:
            if isinstance(raw_table, Mapping):
                raw_table_entries.append((page_number, raw_table))

    logical_by_index: dict[int, str] = {}
    for index, (page_number, raw_table) in enumerate(raw_table_entries):
        table_id = str(raw_table.get("table_id") or f"{document_id}:table:{page_number}:{index}")
        header = [str(value) for value in (raw_table.get("header") or [])]
        logical_id = f"logical-table:{document_id}:{index}"
        if index:
            previous_page, previous = raw_table_entries[index - 1]
            previous_header = [str(value) for value in (previous.get("header") or [])]
            if page_number == previous_page + 1 and _header_key(header) == _header_key(previous_header):
                logical_id = logical_by_index[index - 1]
        logical_by_index[index] = logical_id
        page = page_by_number.get(page_number)
        if page is None:
            issues.append(_issue("TABLE_PAGE_REFERENCE_INVALID", f"table {table_id} references page {page_number}", document_id, location=table_id, stage="TABLE"))
            continue
        cells: list[TableCell] = []
        rows: list[list[str | None]] = []
        for row_index, raw_row in enumerate(raw_table.get("rows") or []):
            if not isinstance(raw_row, Mapping):
                issues.append(_issue("TABLE_ROW_INVALID", f"table {table_id} row {row_index} is not an object", document_id, location=table_id, stage="TABLE"))
                continue
            row_cells = raw_row.get("cells") if isinstance(raw_row.get("cells"), list) else []
            row_values: list[str | None] = []
            for column_index, raw_cell in enumerate(row_cells):
                if not isinstance(raw_cell, Mapping):
                    row_values.append(None)
                    continue
                text = str(raw_cell.get("text") or "")
                row_values.append(text)
                bbox = _bbox(raw_cell.get("bbox_normalized"))
                geometry = str(raw_cell.get("geometry_provenance") or "UNKNOWN").upper()
                if geometry not in _GEOMETRY:
                    geometry = "UNKNOWN"
                cells.append(
                    TableCell(
                        cell_id=str(raw_cell.get("cell_id") or f"{table_id}:r{row_index}:c{column_index}"),
                        row_index=row_index,
                        column_index=column_index,
                        text=text,
                        bbox=bbox,
                        line_ids=[],
                        geometry_provenance=geometry,
                    )
                )
            rows.append(row_values)
        node_id = f"table-node:{table_id}"
        citations: dict[str, Citation] = {}
        for cell in cells:
            citation = Citation(
                citation_id=f"table:{table_id}:{cell.row_index}:{cell.column_index}",
                node_id=node_id,
                page_revision_id=page.page_revision_id,
                bbox=cell.bbox,
                text_span=cell.text,
                source_file_id=document_id,
                page=page_number,
                page_range=[page_number],
                source_hash=digest,
                quote_sha256=quote_digest(cell.text),
                geometry_available=bool(cell.bbox),
                table_id=table_id,
                cell_id=cell.cell_id,
                geometry_source=cell.geometry_provenance,
                precision="MEASURED" if cell.geometry_provenance == "MEASURED" else "CLAIMED",
            )
            citation.validation_status = CitationResolver([page], []).verify(citation).status
            citations[f"{cell.row_index}:{cell.column_index}"] = citation
        table_role = (
            "annex"
            if page_number in embedded_annex_pages
            else (source_role if source_role in {"body", "annex"} else None)
        )
        table = TableSnapshot(
            table_id=table_id,
            title="",
            header=header,
            rows=rows,
            continuation=index > 0 and logical_id == logical_by_index.get(index - 1),
            node_id=node_id,
            page_revision_id=page.page_revision_id,
            cell_citations=citations,
            cells=cells,
            # Promote an explicit embedded PHỤ LỤC heading to the comparison
            # scope for table facts. This does not merge independent files;
            # it only labels pages inside this one snapshot.
            source_role=table_role,
            section_scope=logical_id,
            logical_table_id=logical_id,
            geometry_provenance=str(raw_table.get("geometry_provenance") or "UNKNOWN").upper(),
        )
        tables.append(table)
        nodes.append(
            StructuralNode(
                node_id=node_id,
                source_node_id=table_id,
                type="TABLE",
                raw_label=table_id,
                order=10_000 + index,
                text="\n".join(" | ".join(value or "" for value in row) for row in rows),
                page_range=[page_number],
                page_revision_id=page.page_revision_id,
                bbox=_bbox(raw_table.get("bbox_normalized")),
                source_file_id=document_id,
                page_in_file=page_number,
                provenance="AI1",
                structure_level="TABLE",
                scope_id=source_role or None,
            )
        )
        non_empty_cells = sum(bool(cell.text.strip()) for cell in cells)
        if not cells or not any(cell.text.strip() for cell in cells) or (
            cells and non_empty_cells / len(cells) < 0.25
        ):
            issues.append(_issue("TABLE_INCOMPLETE_OR_EMPTY", f"table {table_id} has insufficient non-empty cell values", document_id, location=table_id, stage="TABLE"))

    for continuity in snapshot.get("table_continuity") or []:
        if not isinstance(continuity, Mapping):
            continue
        decision = str(continuity.get("decision") or "").upper()
        from_id = str(continuity.get("from_table_id") or "")
        to_id = str(continuity.get("to_table_id") or "")
        from_table = next((table for table in tables if table.table_id == from_id), None)
        to_table = next((table for table in tables if table.table_id == to_id), None)
        if from_table and to_table and from_table.logical_table_id == to_table.logical_table_id and decision == "SPLIT":
            from_table.continuity_decision = decision
            from_table.continuity_confidence = _optional_float(continuity.get("confidence"))
            to_table.header_source_table_id = from_table.table_id
            to_table.continuity_decision = decision
            to_table.continuity_confidence = _optional_float(continuity.get("confidence"))
            issues.append(_issue(
                "TABLE_CONTINUITY_CONFLICT",
                f"AI1 decision SPLIT conflicts with compatible adjacent table evidence: {from_id} -> {to_id}",
                document_id,
                location=f"{from_id}->{to_id}",
                stage="TABLE",
            ))
    return tables, nodes, issues


def _embedded_annex_pages(snapshot: Mapping[str, Any]) -> dict[int, str]:
    """Return page -> annex number for explicit in-snapshot headings."""

    markers: list[tuple[int, str]] = []
    for raw_page in snapshot.get("pages") or []:
        if not isinstance(raw_page, Mapping):
            continue
        page_number = _optional_int(raw_page.get("page_number")) or 0
        for line in raw_page.get("lines") or []:
            text = str(line.get("text") or "") if isinstance(line, Mapping) else str(line or "")
            match = re.match(r"^\s*phu luc\s+0*([0-9]+)\b", fold_for_match(text))
            if match:
                markers.append((page_number, match.group(1)))
                break
    markers.sort()
    out: dict[int, str] = {}
    for index, (start, number) in enumerate(markers):
        end = markers[index + 1][0] - 1 if index + 1 < len(markers) else max(
            (_optional_int(page.get("page_number")) or 0 for page in snapshot.get("pages") or []),
            default=start,
        )
        for page_number in range(start, end + 1):
            out[page_number] = number
    return out


def _normalize_digest(value: str) -> str:
    digest = value.removeprefix("sha256:").lower()
    if not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise SnapshotContractError("source_digest must be sha256:<64 hex> or 64 hex", code="OCR_LAB_DIGEST_INVALID")
    return f"sha256:{digest}"


def _quality(status: str, text: str, lines: list[Any], error: Any) -> str:
    if status == "FAILED" or error:
        return "FAILED"
    if status == "PARTIAL":
        return "LOW"
    if not text.strip() and not lines:
        return "EMPTY"
    return "OK"


def _analysis_view(value: str) -> str:
    """Repair only obvious UTF-8-as-legacy mojibake; otherwise return raw."""

    if not value:
        return value
    marker_count = sum(value.count(marker) for marker in ("Ã", "Â", "â", "ð", "�", "»"))
    if marker_count == 0:
        return value
    try:
        candidate = value.encode("cp1252").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return value
    candidate_markers = sum(candidate.count(marker) for marker in ("Ã", "Â", "â", "ð", "�", "»"))
    return candidate if candidate_markers < marker_count else value


def _header_key(values: list[str]) -> tuple[str, ...]:
    return tuple(re.sub(r"\s+", " ", value.casefold()).strip() for value in values)


def _bbox(value: Any) -> list[float]:
    if not isinstance(value, list) or len(value) != 4:
        return []
    try:
        result = [float(item) for item in value]
    except (TypeError, ValueError):
        return []
    if not all(0 <= item <= 1 for item in result) or result[2] <= result[0] or result[3] <= result[1]:
        return []
    return result


def _positive_int(value: Any, name: str) -> int:
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise SnapshotContractError(f"{name} must be an integer", code="OCR_LAB_INPUT_INVALID") from exc
    if result < 1:
        raise SnapshotContractError(f"{name} must be >= 1", code="OCR_LAB_INPUT_INVALID")
    return result


def _optional_int(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _optional_float(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _issue(
    code: str,
    message: str,
    document_id: str,
    *,
    stage: str = "INPUT",
    location: str | None = None,
    review_state: ReviewState = ReviewState.NEEDS_REVIEW,
) -> HandoffIssue:
    token = hashlib.sha256(f"{document_id}:{stage}:{code}:{location or message}".encode("utf-8")).hexdigest()[:16]
    return HandoffIssue(
        code=code,
        message=message,
        review_state=review_state,
        error_id=f"err:{token}",
        stage=stage,
        document_id=document_id,
        location=location,
    )
