from __future__ import annotations

from decimal import Decimal

from app.contracts.models import IndexContribution, ReviewState, TenantProfile
from app.contracts.wire import typed_projection_coverage_to_wire
from app.pipeline.boq_checks import check_boq_table
from app.pipeline.fact import FactExtractor
from app.pipeline.payment_schedule import project_payment_schedule
from app.pipeline.table import TablePipeline, TableProcessingLimits


def _rows(headers: list[str], values: list[list[str | None]]) -> list[dict]:
    rows = []
    for row_index, cells in enumerate(values):
        cell_citations = {
            str(column_index): {
                "node_id": f"table-row-{row_index}",
                "page_revision_id": f"page-{row_index // 2 + 1}",
                "source_file_id": "synthetic-annex",
                "page": row_index // 2 + 1,
                "text_span": str(value),
            }
            for column_index, value in enumerate(cells)
            if value not in (None, "")
        }
        rows.append(
            {"row_index": row_index, "cells": cells, "cell_citations": cell_citations}
        )
    return rows


def test_payment_schedule_keeps_each_milestone_trigger_and_cell_citation():
    headers = ["Đợt", "Tỷ lệ", "Mốc thanh toán", "Thời hạn", "Điều kiện", "Căn cứ"]
    rows = _rows(
        headers,
        [
            ["M1", "10%", "Tạm ứng", "05 ngày", "Sau ký", "Hợp đồng"],
            ["M2", "30%", "Giao vật tư", "10 ngày", "Biên bản giao hàng", "Điều 4"],
            ["M3", "25%", "Lắp đặt", "07 ngày", "Nghiệm thu lắp đặt", "Điều 5"],
            ["M4", "25%", "Bàn giao", "05 ngày", "Nghiệm thu bàn giao", "Điều 6"],
            ["M5", "10%", "Quyết toán", "15 ngày", "Hồ sơ quyết toán", "Điều 7"],
        ],
    )

    projection = project_payment_schedule("payments", headers, rows, source_role="annex")

    assert projection is not None
    assert projection.review_state == ReviewState.PASS
    assert [item.milestone_id for item in projection.milestones] == ["M1", "M2", "M3", "M4", "M5"]
    assert [Decimal(item.percent) for item in projection.milestones] == [10, 30, 25, 25, 10]
    assert projection.milestones[1].trigger == "Biên bản giao hàng"
    assert projection.milestones[1].deadline == "10 ngày"
    assert projection.milestones[1].citation.page_revision_id == "page-1"
    assert set(projection.milestones[1].cell_citations) == {"0", "1", "2", "3", "4", "5"}
    assert projection.raw_rows[1] == rows[1]["cells"]


def test_schedule_with_missing_row_is_partial_and_keeps_total_unknown():
    headers = ["Đợt", "Tỷ lệ", "Mốc thanh toán", "Thời hạn", "Điều kiện"]
    rows = _rows(headers, [["M1", "20%", "Tạm ứng", "", "Sau ký"], ["M2", "", "Bàn giao", "", ""]])

    projection = project_payment_schedule("payments", headers, rows, source_role="annex")

    assert projection is not None
    assert projection.review_state == ReviewState.NEEDS_REVIEW
    assert projection.total_percent is None
    assert projection.coverage.complete is False
    assert projection.coverage.reason


def test_boq_computes_line_amounts_subtotal_tax_and_total_without_double_counting_summary_rows():
    headers = ["STT", "Hạng mục", "Số lượng", "Đơn giá VND", "Thành tiền VND"]
    rows = _rows(
        headers,
        [
            ["1", "Thiết bị A", "2", "100", "200"],
            ["2", "Thiết bị B", "3", "50", "150"],
            ["", "Cộng", "", "", "350"],
            ["", "VAT 8%", "", "", "28"],
            ["", "Tổng cộng", "", "", "378"],
        ],
    )

    result = check_boq_table("boq", headers, rows, source_role="annex")

    assert result.review_state == ReviewState.PASS
    assert result.line_count == 2
    assert result.computed_line_sum == "350"
    assert result.stated_subtotal == "350"
    assert result.tax_amount == "28"
    assert result.grand_total == "378"
    assert result.currency == "VND"
    assert len(result.citations) >= 5


def test_boq_mismatch_or_missing_currency_stays_reviewable():
    headers = ["Hạng mục", "Số lượng", "Đơn giá", "Thành tiền"]
    rows = _rows(headers, [["Hạng mục A", "2", "100", "250"], ["Cộng", "", "", "250"]])

    result = check_boq_table("boq", headers, rows, source_role="annex")

    assert result.review_state == ReviewState.NEEDS_REVIEW
    assert result.computed_line_sum == "250"
    assert result.issues
    assert result.currency is None


def test_table_and_numeric_limits_return_partial_coverage_before_large_decimal_work():
    headers = ["Hạng mục", "Số lượng", "Đơn giá VND", "Thành tiền VND"]
    huge_rows = _rows(headers, [["A", "9" * 129, "1", "9" * 129]])

    result = check_boq_table("large", headers, huge_rows, max_rows=1, max_cells=8, max_numeric_chars=128)

    assert result.review_state == ReviewState.NEEDS_REVIEW
    assert result.coverage.complete is False
    assert result.coverage.reason
    assert result.computed_line_sum is None


def test_typed_projection_wire_is_optional_and_preserves_old_coverage_shape():
    old_coverage = {"n_facts": 0, "n_findings": 0}
    assert typed_projection_coverage_to_wire(old_coverage, [], [], lambda _citation: "unused") == old_coverage

    contribution = IndexContribution(
        extraction_version=1,
        proposed_index_version="idx_1",
        coverage=old_coverage,
    )
    assert contribution.publish == "propose"

    headers = ["Đợt", "Tỷ lệ", "Mốc thanh toán"]
    schedule = project_payment_schedule(
        "payments", headers,
        _rows(headers, [["M1", "100%", "Nghiệm thu"]]), source_role="annex",
    )
    registered = {}
    def register(citation):
        key = f"c{len(registered) + 1}"
        registered[key] = citation
        return key

    typed = typed_projection_coverage_to_wire(old_coverage, [schedule], [], register)
    milestone = typed["typed_table_projections"]["payment_schedules"][0]["milestones"][0]
    assert len(milestone["citation_ids"]) == 1
    assert set(milestone["cell_citation_ids"]) == {"0", "1", "2"}
    assert len(registered) == 4


def test_pipeline_fetches_only_bounded_rows_and_reports_partial_schedule():
    class Gateway:
        requested_end = None

        def call(self, tool, _envelope, **kwargs):
            if tool == "get_table_meta":
                return {
                    "header": ["Đợt", "Tỷ lệ", "Mốc thanh toán"], "n_rows": 4, "n_cols": 3,
                    "continuation": False, "header_row_indices": [], "source_role": "annex",
                }
            self.requested_end = kwargs["end"]
            return _rows(
                ["Đợt", "Tỷ lệ", "Mốc thanh toán"],
                [["M1", "25%", "Tạm ứng"], ["M2", "25%", "Giao hàng"]][:kwargs["end"]],
            )

    gateway = Gateway()
    result = TablePipeline(
        gateway, limits=TableProcessingLimits(max_rows=3, max_cells=9, max_operations=9)
    ).extract_with_projection(None, "payments")

    assert gateway.requested_end == 3
    assert result.payment_schedule is not None
    assert result.payment_schedule.review_state == ReviewState.NEEDS_REVIEW
    assert result.payment_schedule.coverage.complete is False
    assert result.payment_schedule.total_percent is None


def test_fact_normalizer_does_not_send_oversized_ocr_value_to_llm():
    class LLM:
        called = False

        def configured(self):
            return True

        def complete_json(self, *_args, **_kwargs):
            self.called = True
            raise AssertionError("oversized raw value must not reach the LLM")

    llm = LLM()
    extractor = FactExtractor(gateway=None, llm=llm)
    normalized, provenance = extractor._normalize("9" * 4097, "context", TenantProfile(version=1))

    assert normalized is None
    assert provenance == "L0"
    assert llm.called is False
