"""Dossiers for the contract-graph builder (P3): a body file and an annex file whose clauses
amend the body ("Sửa đổi điểm c khoản 1 Điều 3 như sau: …").

Every node is one or more page lines, pages carry ``source_hash`` and ``line_texts`` so node
citations verify as ``VALID`` the same way OCR-lab snapshots do. Facts are optional input
facts (``record.facts``) for the pairing / implicit-substitution tests.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from app.contracts.models import (
    Citation,
    Fact,
    LifecycleState,
    PageSnapshot,
    SourceFile,
    StructuralNode,
)
from app.pipeline.citations import quote_digest
from app.tools.store import DossierRecord
from fixtures import DOSSIER, PINS, PROFILE, TENANT

BODY = "f-body"
ANNEX = "f-annex"


@dataclass(frozen=True)
class Spec:
    node_id: str
    label: str
    text: str
    parent: str | None = None
    type: str = "CLAUSE"
    level: str = "BLOCK"


@dataclass(frozen=True)
class FactSpec:
    fact_id: str
    node_id: str
    item_key: str
    value: str


BODY_NODES = [
    Spec("b_d3", "Điều 3", "Thanh toán"),
    Spec("b_d3k1", "1.", "Thanh toán theo các đợt sau:", "b_d3"),
    Spec("b_d3k1a", "a)", "Đợt 1 tạm ứng 30% giá trị hợp đồng.", "b_d3k1"),
    Spec("b_d3k1c", "c)", "Đợt 3 thanh toán phần còn lại.", "b_d3k1"),
    Spec("b_d5", "Điều 5", "Giao hàng"),
    Spec("b_d5k2", "2.", "Đơn giá giao hàng là 100.000 đồng/tấn.", "b_d5"),
    Spec("b_d7", "Điều 7", "Nghiệm thu"),
    Spec("b_d7k2", "2.", "Bên A nghiệm thu trong 05 ngày.", "b_d7"),
    Spec("b_d7k3", "3.", "Biên bản nghiệm thu do hai bên ký.", "b_d7"),
    Spec("b_d18", "Điều 18", "Tạm ứng"),
    Spec("b_d18k5", "5.", "Mức tạm ứng do các bên thỏa thuận.", "b_d18"),
]

# RT-06: rights / scope sentences in the body, not under any operation unit
BODY_RIGHTS = Spec(
    "b_d8",
    "Điều 8",
    "Bên A có quyền từ chối nghiệm thu theo khoản 2 Điều 7.\n"
    "Điều 5 không áp dụng đối với lô hàng 2.",
)

ANNEX_NODES = [
    Spec("a_pl", "Phụ lục 01", "Sửa đổi, bổ sung Hợp đồng", type="SECTION", level="ANNEX"),
    Spec(
        "a1",
        "1.",
        "Sửa đổi điểm c khoản 1 Điều 3 như sau:\n“c) Đợt 3 thanh toán 70% giá trị hợp đồng.”",
        "a_pl",
    ),
    Spec(
        "a2",
        "2.",
        "Bổ sung khoản 4 vào sau khoản 3 Điều 7 như sau:\n“4. Bên B bàn giao hồ sơ hoàn công.”",
        "a_pl",
    ),
    Spec("a3", "3.", "Điều 5 không áp dụng đối với lô hàng 2.", "a_pl"),
    Spec("a4", "4.", "Bãi bỏ Điều 9.", "a_pl"),
    Spec("a5", "5.", "Bên B có trách nhiệm sửa chữa hàng lỗi theo Điều 7.", "a_pl"),
    Spec("a6", "6.", "Giá được điều chỉnh theo chỉ số CPI tại Điều 4.", "a_pl"),
    Spec(
        "a7",
        "7.",
        "Điều chỉnh khoản 2 Điều 5 như sau:\nĐơn giá giao hàng là 120.000 đồng/tấn.",
        "a_pl",
    ),
    Spec(
        "a8", "8.", "Thay đổi Điều 7 của Hợp đồng như sau:\nBên A nghiệm thu trong 03 ngày.", "a_pl"
    ),
    Spec(
        "a9",
        "9.",
        "Khoản 2 Điều 5 được thay bằng nội dung sau:\nĐơn giá giao hàng là 120.000 đồng/tấn.",
        "a_pl",
    ),
    Spec(
        "a10",
        "10.",
        "Bổ sung khoản 5a vào sau khoản 5 Điều 18 như sau:\n“5a. Tạm ứng không quá 50%.”",
        "a_pl",
    ),
    Spec("a11", "11.", "Bên A có quyền từ chối nghiệm thu theo khoản 2 Điều 7.", "a_pl"),
]

# fact pair Điều 5 khoản 2 (body) ↔ annex item 7: different files, so compare.py only pairs
# them when a relation unlocks (a7, b_d5k2); the legacy graph only links a7 → Điều 5.
UNLOCK_FACTS = [
    FactSpec("fact-body-don-gia", "b_d5k2", "don_gia", "100000"),
    FactSpec("fact-annex-don-gia", "a7", "don_gia", "120000"),
]

# RT-12 dossier: operations whose targets hold no fact of the annex fact's item
NO_UNLOCK_ANNEX = [
    Spec("a_pl", "Phụ lục 01", "Sửa đổi, bổ sung Hợp đồng", type="SECTION", level="ANNEX"),
    Spec(
        "a1",
        "1.",
        "Sửa đổi điểm c khoản 1 Điều 3 như sau:\n“c) Đợt 3 thanh toán 70% giá trị hợp đồng.”",
        "a_pl",
    ),
    Spec("a4", "4.", "Bãi bỏ Điều 9.", "a_pl"),
    Spec("a12", "12.", "Tạm ứng theo tiến độ: 40%.", "a_pl"),
]
NO_UNLOCK_FACTS = [
    FactSpec("fact-body-tam-ung", "b_d3k1a", "tam_ung", "30%"),
    FactSpec("fact-annex-tam-ung", "a12", "tam_ung", "40%"),
]


def graph_record(*, body_rights: bool = False, facts: bool = True) -> DossierRecord:
    """Body + annex with every explicit operation of the P3 scenario matrix."""

    body = [*BODY_NODES, *([BODY_RIGHTS] if body_rights else [])]
    return dossier(
        [(BODY, "body", body), (ANNEX, "annex", ANNEX_NODES)], UNLOCK_FACTS if facts else []
    )


def no_unlock_record() -> DossierRecord:
    """Edges exist, yet none of them joins the two nodes of a cross-file fact pair."""

    return dossier([(BODY, "body", BODY_NODES), (ANNEX, "annex", NO_UNLOCK_ANNEX)], NO_UNLOCK_FACTS)


def implicit_record(
    *,
    annex_text: str = "Thay đổi số lượng hàng hóa theo bảng dưới đây.",
    body_facts: list[FactSpec] | None = None,
    annex_facts: list[FactSpec] | None = None,
    annex_extra: list[Spec] | None = None,
) -> DossierRecord:
    """Annex without addresses; its facts meet body facts only through ``item_key``."""

    body = [
        Spec("b_d2", "Điều 2", "Hàng hóa"),
        Spec("b_d2k1", "1.", "Số lượng thép cuộn: 100 tấn.", "b_d2"),
        Spec("b_d2k2", "2.", "Số lượng thép tấm: 50 tấn.", "b_d2"),
        *BODY_NODES,
    ]
    annex = [
        Spec("x_pl", "Phụ lục 02", annex_text, type="SECTION", level="ANNEX"),
        Spec("x1", "1.", "Số lượng thép cuộn: 120 tấn.", "x_pl"),
        *(annex_extra or []),
    ]
    facts = [
        *(
            body_facts
            if body_facts is not None
            else [FactSpec("fb1", "b_d2k1", "so_luong_thep_cuon", "100")]
        ),
        *(
            annex_facts
            if annex_facts is not None
            else [FactSpec("fa1", "x1", "so_luong_thep_cuon", "120")]
        ),
    ]
    return dossier([(BODY, "body", body), (ANNEX, "annex", annex)], facts)


def dossier(files: list[tuple[str, str, list[Spec]]], facts: list[FactSpec]) -> DossierRecord:
    pages: list[PageSnapshot] = []
    nodes: list[StructuralNode] = []
    sources: list[SourceFile] = []
    order = 0
    for page_number, (file_id, role, specs) in enumerate(files, start=1):
        revision = f"{file_id}:p1"
        lines: dict[str, str] = {}
        for spec in specs:
            text_lines = spec.text.split("\n")
            ids = []
            for i, line in enumerate(text_lines):
                line_id = f"{spec.node_id}:l{i}"
                head = f"{spec.label}. " if spec.label.startswith("Điều") else f"{spec.label} "
                lines[line_id] = (head + line) if i == 0 else line
                ids.append(line_id)
            order += 1
            nodes.append(
                StructuralNode(
                    node_id=spec.node_id,
                    type=spec.type,
                    raw_label=spec.label,
                    parent_id=spec.parent,
                    order=order,
                    text=spec.text,
                    page_range=[page_number],
                    page_revision_id=revision,
                    source_file_id=file_id,
                    page_in_file=1,
                    structure_level=spec.level,
                    source_line_ids=ids,
                )
            )
        text = "\n".join(lines.values())
        pages.append(
            PageSnapshot(
                page_revision_id=revision,
                page_number=page_number,
                text=text,
                source_file_id=file_id,
                page_in_file=1,
                line_texts=lines,
                source_hash="sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest(),
            )
        )
        sources.append(SourceFile(file_id=file_id, filename=f"{file_id}.pdf", role=role, n_pages=1))
    by_id = {node.node_id: node for node in nodes}
    page_of = {page.page_revision_id: page for page in pages}
    return DossierRecord(
        tenant_id=TENANT,
        dossier_id=DOSSIER,
        lifecycle=LifecycleState.ACTIVE,
        pins=PINS.model_copy(),
        pages=pages,
        nodes=nodes,
        tables=[],
        profile=PROFILE,
        acl_revision=12,
        permissions_by_actor={"user_001": ["READ_CONTENT"]},
        source_files=sources,
        facts=[_fact(spec, by_id[spec.node_id], page_of, files) for spec in facts],
        case_id="CONTRACT-GRAPH",
    )


def _fact(spec: FactSpec, node: StructuralNode, pages: dict, files) -> Fact:
    page = pages[node.page_revision_id]
    role = next(role for file_id, role, _ in files if file_id == node.source_file_id)
    span = node.text.split("\n")[0]
    start = page.text.find(span)
    return Fact(
        fact_id=spec.fact_id,
        raw_value=spec.value,
        normalized_value=spec.value,
        subject=spec.item_key,
        item_key=spec.item_key,
        scope=spec.item_key,
        source_role=role,
        citation=Citation(
            node_id=node.node_id,
            page_revision_id=node.page_revision_id,
            text_span=span,
            source_file_id=node.source_file_id,
            page=page.page_number,
            page_range=[page.page_number],
            line_ids=list(node.source_line_ids[:1]),
            char_start=start,
            char_end=start + len(span),
            source_hash=page.source_hash,
            quote_sha256=quote_digest(span),
        ),
        provenance="L0",
    )
