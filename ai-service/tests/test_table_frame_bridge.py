from app.contracts.models import (
    Citation,
    PaymentMilestoneProjection,
    PaymentScheduleProjection,
    ReviewState,
    TableProjectionCoverage,
    TableSnapshot,
)
from app.pipeline.table_frame_bridge import payment_schedule_frames


def _schedule() -> PaymentScheduleProjection:
    citation = Citation(
        node_id="table-1",
        page_revision_id="page-1",
        source_file_id="doc-1",
        text_span="Đợt 1 30% sau nghiệm thu",
        validation_status="VALID",
    )
    return PaymentScheduleProjection(
        table_id="table-1",
        source_role="annex",
        milestones=[PaymentMilestoneProjection(
            milestone_id="Đợt 1",
            raw_label="Đợt 1",
            raw_percent="30%",
            percent="30",
            event="Nghiệm thu",
            trigger="Sau nghiệm thu",
            deadline="07 ngày làm việc",
            raw_cells=["Đợt 1", "30%", "Sau nghiệm thu", "07 ngày làm việc"],
            citation=citation,
            cell_citations={"0": citation},
        )],
        review_state=ReviewState.PASS,
        coverage=TableProjectionCoverage(
            complete=True, source_rows=1, processed_rows=1, source_cells=4,
            processed_cells=4, page_count=1,
        ),
    )


def test_payment_schedule_projection_becomes_grounded_frame_with_row_citation():
    table = TableSnapshot(
        table_id="table-1",
        title="Lịch thanh toán phí dịch vụ",
        header=["Đợt", "Tỷ lệ", "Điều kiện", "Thời hạn"],
        rows=[["Đợt 1", "30%", "Sau nghiệm thu", "07 ngày làm việc"]],
        node_id="table-node-1",
        page_revision_id="page-1",
    )

    frames = payment_schedule_frames(
        _schedule(),
        table=table,
        profile="SALES",
        dossier_id="dos-1",
        document_id="doc-1",
        snapshot_id="snap-1",
    )

    assert len(frames) == 1
    frame = frames[0]
    assert frame.get("amount").value == "30" or str(frame.get("amount").value) == "30"
    assert frame.get("unit").value == "percent"
    assert frame.get("deadline").value == "07"
    assert frame.get("deadline_unit").value == "business-day"
    assert frame.get("object_scope").state == "GROUNDED"
    assert frame.evidence[0].source_ref == "table-1:row:Đợt 1"


def test_header_aliases_and_multiline_header_are_conservative():
    from app.pipeline.table_headers import identify_header

    header, indices = identify_header([
        ["STT", "Mô tả công việc", "Đơn giá", "Thành tiền"],
        ["", "(hạng mục)", "(VND)", "(VND)"],
        ["1", "Thi công", "100", "100"],
    ])

    assert header == ["STT", "Mô tả công việc", "Đơn giá", "Thành tiền"]
    assert indices == [0, 1]


def test_semantic_extension_consumes_typed_schedule_projection():
    from test_frame_job import semantic_record

    from app.pipeline.frame_context import build_semantic_extension
    from app.pipeline.runtime import ProcessingRuntime

    record = semantic_record()
    node = record.nodes[0]
    record.tables = [record.tables[0].model_copy(update={
        "table_id": "table-1",
        "node_id": node.node_id,
        "title": "Lịch thanh toán",
        "header": ["Đợt", "Tỷ lệ", "Điều kiện", "Thời hạn"],
    })]
    record.payment_schedules = [_schedule()]

    extension = build_semantic_extension(
        record, ProcessingRuntime(), bounds=record.semantic_profile.context_bounds,
    )

    table_frames = [
        frame for frame in extension.frames
        if frame.evidence[0].source_ref.startswith("table-1:row:")
    ]
    assert len(table_frames) == 1
    assert table_frames[0].slots["amount"].value == "30"
    assert table_frames[0].slots["deadline_unit"].value == "business-day"
    assert extension.coverage.frames == len(extension.frames)
