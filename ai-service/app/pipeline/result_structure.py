"""Derived hierarchy for result v0.1; never rewrites the raw AI1 nodes."""
import re
from collections import defaultdict

from app.contracts.models import HandoffIssue, ReviewState, StructuralNode
from app.pipeline.table_headers import fold


def enrich_result_structure(record):
    grouped = defaultdict(list)
    for node in record.nodes:
        grouped[node.source_file_id].append(node.model_copy(deep=True))
    tables = {t.node_id: t for t in record.tables}
    active = []
    for file_id, nodes in grouped.items():
        root_id = f"ai2-root:{file_id}"
        file_role = next((s.role for s in record.source_files if s.file_id == file_id), "body")
        root = StructuralNode(node_id=root_id, type="SECTION", raw_label="Phụ lục" if file_role == "annex" else "Hợp đồng",
                              text="", structure_level="DOCUMENT", source_file_id=file_id,
                              scope_id=root_id, is_synthetic=True, provenance="AI2_REPAIRED")
        active.append(root)
        scope = root_id
        clause = None
        sections = {}
        previous_table = None
        emitted = {root_id: root}
        page_axes = {}
        for page in record.pages:
            if page.source_file_id != file_id:
                continue
            boxes = list(page.line_bboxes.values())
            vertical = sum(b[3] - b[1] > 3 * (b[2] - b[0]) for b in boxes) > len(boxes) / 2
            page_axes[page.page_number] = 0 if vertical else 1
            if vertical and page.rotation == 0:
                record.handoff_issues.append(HandoffIssue(code="ORIENTATION_METADATA_REVIEW",
                    message=f"page {page.page_number}: vertical line geometry with rotation=0; verify source rendering",
                    review_state=ReviewState.NEEDS_REVIEW))
        def position(node):
            page = node.page_range[0] if node.page_range else 0
            return (page, node.bbox[page_axes.get(page, 1)] if node.bbox else 0, node.order)
        for order, node in enumerate(sorted(nodes, key=position), 1):
            node.order = len(active) + order
            heading = re.match(r"^phu luc\s+0*(\d+)(?:\s*[-:–—(]|\s*$)", fold(node.raw_label))
            if heading:
                key = heading.group(1)
                existing = sections.get(key)
                if existing:
                    node.parent_id = existing
                    scope = existing
                else:
                    node.type = "SECTION"
                    node.structure_level = "ANNEX"
                    node.parent_id = root_id
                    scope = node.node_id
                    sections[key] = scope
                clause = None
            else:
                declared_parent = emitted.get(node.parent_id)
                if declared_parent is None or declared_parent.scope_id != scope:
                    node.parent_id = scope if node.type in {"CLAUSE", "TABLE", "FIELD"} else clause or scope
                if node.type == "CLAUSE":
                    clause = node.node_id
            node.scope_id = scope
            node.provenance = "AI2_REPAIRED"
            active.append(node)
            emitted[node.node_id] = node
            table = tables.get(node.node_id)
            if table is None:
                continue
            table.source_role = "annex" if scope != root_id else next((s.role for s in record.source_files if s.file_id == file_id), "body")
            table.section_scope = scope
            if not any(table.header) and previous_table is not None:
                prior, prior_node = previous_table
                if (prior.section_scope == scope and len(prior.header) == len(table.header)
                        and any(prior.header) and node.page_range[0] == prior_node.page_range[0] + 1):
                    table.header = list(prior.header)
                    table.header_source_table_id = prior.table_id
                    table.continuation = True
                    node.status = "PARTIAL"
                    record.handoff_issues.append(HandoffIssue(code="TABLE_CONTINUATION_REVIEW",
                        message=f"table {table.table_id}: candidate continuation of {prior.table_id}; header inherited, rows remain separate",
                        review_state=ReviewState.NEEDS_REVIEW))
            previous_table = (table, node)
    record.active_nodes = active
    scopes = {node.node_id: node.scope_id for node in active}
    for fact in record.facts:
        scope = scopes.get(fact.citation.node_id)
        if scope and not scope.startswith("ai2-root:"):
            fact.source_role = "annex"
            fact.validity = scope
