from __future__ import annotations

from pathlib import Path

from app.contracts.models import (
    AuthContext,
    Citation,
    LifecycleState,
    PageSnapshot,
    StructuralNode,
    TableSnapshot,
    TenantProfile,
    ToolEnvelope,
    VersionPins,
)
from app.tools.store import DossierRecord
from fixtures.catalog import CasePack, all_cases, load_case

TENANT = "tenant_a"
DOSSIER = "dossier_001"
PINS = VersionPins(
    manifest_version=2,
    source_snapshot_digest="sha256:aaa",
    tenant_profile_version=5,
    policy_version=2,
    ocr_run_version=3,
    reconstruction_version=2,
    extraction_version=7,
    index_version="idx_14",
)
PROFILE = TenantProfile(
    version=5,
    aliases={"Công ty ABC": ["ABC Co.", "ABC"]},
    field_keys=["contract_value", "party_a"],
)


def envelope(permissions: list[str] | None = None, actor: str = "user_001", acl: int = 12) -> ToolEnvelope:
    return ToolEnvelope(
        auth=AuthContext(
            actor_id=actor,
            tenant_id=TENANT,
            dossier_id=DOSSIER,
            acl_revision=acl,
            permissions=permissions or ["READ_CONTENT"],
            lifecycle=LifecycleState.ACTIVE,
        ),
        pins=PINS.model_copy(),
    )


def mock_record(*, lifecycle: LifecycleState = LifecycleState.ACTIVE, missing_table_cell: bool = True) -> DossierRecord:
    pages = [
        PageSnapshot(
            page_revision_id="page_1_rev_1",
            page_number=1,
            quality="OK",
            coverage=0.99,
            source_block_ids=["p1_b1"],
            text="Bên A: Công ty ABC. Giá trị hợp đồng: 1.000.000.000 VND.",
        )
    ]
    nodes = [
        StructuralNode(
            node_id="sec_1",
            type="SECTION",
            raw_label="Điều 1",
            order=1,
            has_children=True,
            text="Điều 1. Bên tham gia",
            page_range=[1],
            page_revision_id="page_1_rev_1",
        ),
        StructuralNode(
            node_id="field_party",
            type="FIELD",
            raw_label="Bên A",
            parent_id="sec_1",
            order=1,
            text="Bên A: Công ty ABC",
            page_range=[1],
            page_revision_id="page_1_rev_1",
            bbox=[10, 10, 200, 30],
            structured_key="party_a",
            structured_value="Công ty ABC",
        ),
        StructuralNode(
            node_id="field_value",
            type="FIELD",
            raw_label="Giá trị",
            parent_id="sec_1",
            order=2,
            text="Giá trị hợp đồng: 1.000.000.000 VND",
            page_range=[1],
            page_revision_id="page_1_rev_1",
            bbox=[10, 40, 300, 60],
            structured_key="contract_value",
            structured_value="1.000.000.000 VND",
        ),
        StructuralNode(
            node_id="clause_5_3",
            type="CLAUSE",
            raw_label="Điều 5.3",
            parent_id="sec_1",
            order=3,
            text="Điều 5.3. Bên A thanh toán trong 15 ngày kể từ ngày nghiệm thu.",
            page_range=[1],
            page_revision_id="page_1_rev_1",
            bbox=[10, 70, 400, 110],
        ),
        StructuralNode(
            node_id="unnum_1",
            type="UNNUMBERED_BLOCK",
            raw_label="(unnumbered)",
            order=4,
            text="Phụ lục không đánh số: điều khoản bảo mật.",
            page_range=[1],
            page_revision_id="page_1_rev_1",
        ),
        StructuralNode(
            node_id="tbl_node",
            type="TABLE",
            raw_label="Bảng 1",
            order=5,
            text="Bảng thanh toán",
            page_range=[1],
            page_revision_id="page_1_rev_1",
        ),
    ]
    rows: list[list[str | None]] = [
        ["Q1", "100"],
        ["Q2", "200"],
        ["Q3", None if missing_table_cell else "150"],
        ["Q4", "50"],
    ]
    cit = Citation(
        node_id="tbl_node",
        page_revision_id="page_1_rev_1",
        bbox=[0, 0, 1, 1],
        text_span="100",
    )
    tables = [
        TableSnapshot(
            table_id="table_1",
            title="Payments",
            header=["period", "amount"],
            rows=rows,
            continuation=False,
            node_id="tbl_node",
            page_revision_id="page_1_rev_1",
            cell_citations={"0:1": cit},
        )
    ]
    return DossierRecord(
        tenant_id=TENANT,
        dossier_id=DOSSIER,
        lifecycle=lifecycle,
        pins=PINS.model_copy(),
        pages=pages,
        nodes=nodes,
        tables=tables,
        profile=PROFILE,
        acl_revision=12,
        permissions_by_actor={"user_001": ["READ_CONTENT"]},
        case_id="DEFAULT",
    )


def fixtures_dir() -> Path:
    return Path(__file__).resolve().parent


__all__ = [
    "CasePack",
    "all_cases",
    "load_case",
    "envelope",
    "mock_record",
    "fixtures_dir",
]
