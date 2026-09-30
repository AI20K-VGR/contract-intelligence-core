"""Render synthetic contracts into evidence-first AI1 snapshot JSON."""

from __future__ import annotations

import hashlib
import random
import re
import unicodedata
from dataclasses import dataclass
from datetime import date
from typing import Any

from evals.golden.catalog import ContractSpec, QuestionSpec

_NORMALIZED_DATE = date(2026, 1, 1).isoformat()


@dataclass(slots=True)
class _Line:
    line_id: str
    page_no: int
    raw_text: str
    is_gold: bool = False


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _amount(contract_id: str, question_index: int, variant_seed: int | None) -> int:
    base = 8_000_000 + int(contract_id[1:]) * 170_000 + question_index * 25_000
    if variant_seed is None:
        return base
    return base + random.Random(f"{variant_seed}:{contract_id}:{question_index}").randint(1, 900) * 1_000


def _vnd(value: int) -> str:
    return f"{value:,}".replace(",", ".")


def _source_lines(
    contract: ContractSpec,
    question: QuestionSpec,
    question_index: int,
    variant_seed: int | None,
    feature: str,
) -> tuple[list[list[str]], list[tuple[str, str]]]:
    """Return evidence groups and raw/normalized value pairs for a question."""

    base = _amount(contract.contract_id, question_index, variant_seed)
    title = contract.title
    tax_suffix = 1000 + int(contract.contract_id[1:]) * 10 + question_index
    amount_text = _vnd(base)
    if question_index == 1:
        line = f"Điều 2.1. Phí {title.lower()} áp dụng cho {feature}: {amount_text} VND mỗi kỳ."
        return [[line]], [(amount_text, str(base))]
    if question_index == 2:
        line = f"Điều 2.2. Thời điểm áp dụng {title.lower()}: 01/01/2026."
        return [[line]], [("01/01/2026", _NORMALIZED_DATE)]
    if question_index == 3:
        line = f"Điều 3.1. Bên B chịu trách nhiệm thực hiện {title.lower()} theo tiến độ đã thống nhất."
        return [[line]], [("Bên B chịu trách nhiệm", "Bên B chịu trách nhiệm")]
    if question_index == 4:
        return [
            [f"Chỉ tiêu thời hạn {title.lower()}: 30 ngày."],
            [f"Chỉ tiêu chi phí {title.lower()}: {amount_text} VND."],
        ], [("30 ngày", "30 ngày"), (amount_text, str(base))]
    if question_index == 5:
        revised = base + 1_250_000
        first = f"Hợp đồng chính ghi phí {title.lower()} là {amount_text} VND."
        second = f"Phụ lục sửa đổi ghi phí {title.lower()} là {_vnd(revised)} VND."
        return [[first], [second]], [(amount_text, str(base)), (_vnd(revised), str(revised))]
    if question_index == 6:
        names = ("Công ty Sao Biển Hư Cấu", "Công ty Mây Xanh Hư Cấu", "Công ty Gió Nam Hư Cấu")
        name = names[0] if variant_seed is None else names[variant_seed % len(names)]
        first = f"Bên A: {name}; mã số thuế 031{tax_suffix:07d}."
        second = f"Bên B: {name}; mã số thuế 040{tax_suffix + 1:07d}."
        return [[first], [second]], [(f"031{tax_suffix:07d}", f"031{tax_suffix:07d}")]
    if question_index == 7:
        first = "Phụ lục số 1 sửa điều khoản này, hiệu lực từ 01/03/2026 đến 31/08/2026."
        second = "Phụ lục số 2 tiếp tục sửa cùng điều khoản, hiệu lực từ 01/06/2026 đến 30/09/2026."
        return [[first], [second]], [("01/03/2026", "2026-03-01")]
    if question_index == 8:
        line = "Hồ sơ dẫn chiếu Phụ lục A để xác định nội dung chi tiết; phụ lục này không có trong bộ tài liệu."
        return [[line]], []
    if question_index == 9:
        line = f"Văn bản không nêu giá trị cụ thể cho {title.lower()} trong phạm vi điều khoản này."
        return [[line]], []
    if question_index == 11:
        other = base + 500_000
        first = f"Giá trị {title.lower()} tại kỳ 1 là {amount_text} VND."
        second = f"Giá trị {title.lower()} tại kỳ 2 là {_vnd(other)} VND."
        return [[first, second]], [(amount_text, str(base)), (_vnd(other), str(other))]
    if question_index == 12:
        line = f"Điều 8.2. Phạm vi và mức {title.lower()} được xác định tại khoản này."
        return [[line]], [("Điều 8.2", "Điều 8.2")]
    return [], []


def _bbox(line_index: int) -> list[float]:
    row = line_index % 36
    top = round(0.035 + row * 0.026, 4)
    return [0.08, top, 0.92, round(top + 0.02, 4)]


def _span(
    group: list[_Line],
    span_id: str,
    line_lookup: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    boxes = [line_lookup[line.line_id]["bbox"] for line in group]
    return {
        "span_id": span_id,
        "page_no": group[0].page_no,
        "line_ids": [line.line_id for line in group],
        "bbox": [
            round(min(box[0] for box in boxes), 4),
            round(min(box[1] for box in boxes), 4),
            round(max(box[2] for box in boxes), 4),
            round(max(box[3] for box in boxes), 4),
        ],
    }


def _table_page(contract_id: str, page_no: int) -> tuple[list[str], dict[str, Any]] | None:
    if contract_id == "G02" and page_no == 1:
        rows = [
            ("Thiết bị đo", "TB-01", "12", "8.250.000 VND"),
            ("Bộ điều khiển", "TB-02", "4", "16.500.000 VND"),
            ("Máy ghi dữ liệu", "TB-03", "3", "9.750.000 VND"),
        ]
    elif contract_id == "G05" and page_no in {16, 17}:
        start = 1 if page_no == 16 else 4
        rows = [
            (f"Hạng mục {index}", f"CT-{index:02d}", str(index * 12), f"{index * 4}.500.000 VND")
            for index in range(start, start + 3)
        ]
    else:
        return None

    texts = ["Bảng khối lượng: Hạng mục | Mã | Số lượng | Đơn giá"]
    texts.extend(" | ".join(row) for row in rows)
    lines = [f"{contract_id.lower()}-p{page_no:03d}-tbl-l{index:02d}" for index in range(1, len(texts) + 1)]
    cells = []
    for row_index, row in enumerate([("Hạng mục", "Mã", "Số lượng", "Đơn giá"), *rows]):
        for column_index, text in enumerate(row):
            cells.append(
                {
                    "cell_id": f"{contract_id.lower()}-p{page_no:03d}-c{row_index:02d}-{column_index:02d}",
                    "row_index": row_index,
                    "column_index": column_index,
                    "row_kind": "HEADER" if row_index == 0 else "DATA",
                    "text": text,
                    "line_ids": [lines[min(row_index, len(lines) - 1)]],
                    "bbox_fragments": [[0.08 + column_index * 0.21, 0.1 + row_index * 0.04, 0.28 + column_index * 0.21, 0.13 + row_index * 0.04]],
                }
            )
    return texts, {
        "table_id": f"{contract_id.lower()}-table-p{page_no:03d}",
        "logical_table_id": f"{contract_id.lower()}-quantity-table",
        "fragment_id": f"{contract_id.lower()}-fragment-p{page_no:03d}",
        "continuation": contract_id == "G05" and page_no == 17,
        "table_coverage": {"status": "DETECTED", "method": "synthetic-layout-v1"},
        "bbox": [0.08, 0.1, 0.92, 0.28],
        "geometry_status": "derived",
        "cells": cells,
    }


def _extra_lines(contract: ContractSpec) -> dict[int, list[str]]:
    extras: dict[int, list[str]] = {}
    if contract.contract_id == "G05":
        for index, page_no in enumerate((20, 27, 34, 41, 48), start=1):
            extras.setdefault(page_no, []).append(f"PHỤ LỤC {index}. Hạng mục thi công và khối lượng nghiệm thu.")
        extras.setdefault(10, []).append("Điều 12.3. Khối lượng được xác nhận theo bảng tại trang kế tiếp:")
        extras.setdefault(11, []).append("tiếp theo Điều 12.3: phần khối lượng còn lại được nghiệm thu cùng kỳ.")
    return extras


def render_contract(
    contract: ContractSpec,
    *,
    variant_seed: int | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Build one normalized snapshot and its construction-derived question labels."""

    snapshot_id = f"snapshot-{contract.contract_id.lower()}"
    if variant_seed is not None:
        snapshot_id += f"-v{variant_seed}"
    lines_by_page: dict[int, list[_Line]] = {page: [] for page in range(1, contract.page_count + 1)}
    gold_groups: dict[str, list[list[_Line]]] = {}
    question_values: dict[str, list[tuple[str, str]]] = {}

    for question_index, question in enumerate(contract.questions, start=1):
        feature = contract.features[(question_index - 1) % len(contract.features)]
        groups, values = _source_lines(
            contract, question, question_index, variant_seed, feature
        )
        gold_groups[question.question_id] = []
        question_values[question.question_id] = values
        page_no = min(contract.page_count, 1 + (question_index - 1) // 4)
        for group_index, group_texts in enumerate(groups, start=1):
            group_lines = []
            for line_index, text in enumerate(group_texts, start=1):
                line_id = f"{contract.contract_id.lower()}-q{question_index:02d}-s{group_index:02d}-l{line_index:02d}"
                line = _Line(line_id, page_no, unicodedata.normalize("NFC", text), True)
                lines_by_page[page_no].append(line)
                group_lines.append(line)
            gold_groups[question.question_id].append(group_lines)

    for page_no, texts in _extra_lines(contract).items():
        for index, text in enumerate(texts, start=1):
            line_id = f"{contract.contract_id.lower()}-p{page_no:03d}-extra-l{index:02d}"
            lines_by_page[page_no].append(_Line(line_id, page_no, unicodedata.normalize("NFC", text)))

    table_pages: dict[int, dict[str, Any]] = {}
    for page_no in range(1, contract.page_count + 1):
        table = _table_page(contract.contract_id, page_no)
        if table:
            texts, table_data = table
            table_pages[page_no] = table_data
            for index, text in enumerate(texts, start=1):
                line_id = f"{contract.contract_id.lower()}-p{page_no:03d}-tbl-l{index:02d}"
                lines_by_page[page_no].append(_Line(line_id, page_no, unicodedata.normalize("NFC", text)))

    page_objects = []
    page_line_lookup: dict[str, dict[str, Any]] = {}
    all_text = []
    for page_no, page_lines in lines_by_page.items():
        page_lines.sort(key=lambda line: line.line_id)
        while len(page_lines) < 36:
            filler_index = len(page_lines) + 1
            text = f"Nội dung mẫu trang {page_no}, dòng phụ {filler_index:02d}, không tạo thêm dữ kiện hợp đồng."
            page_lines.append(
                _Line(
                    f"{contract.contract_id.lower()}-p{page_no:03d}-f{filler_index:02d}",
                    page_no,
                    unicodedata.normalize("NFC", text),
                )
            )
        if len(page_lines) > 42:
            raise ValueError(f"rendered page exceeds 42 lines: {contract.contract_id} p{page_no}")

        if contract.contract_id == "G08":
            non_gold = [line for line in page_lines if not line.is_gold]
            for line in non_gold[::10]:
                decomposed = unicodedata.normalize("NFD", line.raw_text)
                line.raw_text = "".join(
                    char for char in decomposed if unicodedata.category(char) != "Mn"
                ).replace("đ", "d").replace("Đ", "D")
        if contract.contract_id == "G08" and page_no == 1 and variant_seed is None:
            page_lines[-1].raw_text = "Dòng OCR phụ: số tiền 1.250."
            if len(page_lines) < 42:
                page_lines.append(
                    _Line(
                        f"g08-p001-f{len(page_lines) + 1:02d}",
                        1,
                        "Dòng OCR phụ tiếp theo: 000 VND; không thuộc dữ kiện được hỏi.",
                    )
                )

        table_lines = table_pages.get(page_no)
        line_objects = []
        raw_texts = []
        for line_index, line in enumerate(page_lines):
            box = _bbox(line_index)
            item = {
                "line_id": line.line_id,
                "raw_text": unicodedata.normalize("NFC", line.raw_text),
                "bbox": box,
                "bbox_source": "derived",
                "geometry_status": "derived",
                "engine_confidence": 1.0,
                "words": [],
            }
            line_objects.append(item)
            page_line_lookup[line.line_id] = item
            raw_texts.append(item["raw_text"])
        page_text = "\n".join(raw_texts)
        all_text.append(page_text)
        revision_id = f"{snapshot_id}:p{page_no}:r1"
        page_objects.append(
            {
                "page_no": page_no,
                "page_revision_id": revision_id,
                "input_type": "SCANNED_OCR" if contract.contract_id == "G08" else "TEXT_LAYER",
                "status": "SUCCESS",
                "raw_text_digest": _sha256(page_text.encode("utf-8")),
                "transform": {"rotation_degrees": 0, "profile_version": "synthetic-layout-v1"},
                "quality": {"coverage_status": "COMPLETE", "ocr_confidence": 1.0, "signals": []},
                "table_coverage": table_lines["table_coverage"] if table_lines else {"status": "NOT_PRESENT", "method": "synthetic-layout-v1"},
                "lines": line_objects,
                "tables": [table_lines] if table_lines else [],
                "warnings": [],
            }
        )

    source_digest = _sha256("\n".join(all_text).encode("utf-8"))
    snapshot = {
        "schema_version": "ai1.snapshot.v1",
        "snapshot_id": snapshot_id,
        "dossier_id": f"dossier-{contract.contract_id.lower()}",
        "document_id": f"document-{contract.contract_id.lower()}",
        "run_id": f"run-{snapshot_id}",
        "source_digest": source_digest,
        "created_at": "2026-01-01T00:00:00Z",
        "execution": {
            "execution_manifest_id": "synthetic-golden-v1",
            "config_digest": _sha256(b"synthetic-golden-config-v1"),
            "policy_digest": _sha256(b"synthetic-golden-policy-v1"),
            "source_version_digest": source_digest,
            "replay": False,
        },
        "producer": {
            "engine_name": "synthetic-golden-renderer",
            "engine_version": "1.0.0",
            "code_image_digest": _sha256(b"synthetic-golden-renderer-v1"),
        },
        "language": {
            "declared_scope": "vi",
            "detected_profile": "vi",
            "detector": {"name": "fixed-synthetic-profile", "version": "1"},
        },
        "status": "SUCCESS",
        "pages": page_objects,
    }

    questions = []
    for question_index, question in enumerate(contract.questions, start=1):
        groups = gold_groups[question.question_id]
        required = [
            _span(group, f"{question.question_id}-R{index:02d}", page_line_lookup)
            for index, group in enumerate(groups, start=1)
        ]
        values = []
        value_pairs = question_values[question.question_id]
        for index, (raw, normalized) in enumerate(value_pairs, start=1):
            span = required[min(index - 1, len(required) - 1)]
            value_kind = (
                "date" if re.fullmatch(r"\d{2}/\d{2}/\d{4}", raw)
                else "identifier" if raw.isdigit() and len(raw) >= 10
                else "number" if normalized.isdigit()
                else "text"
            )
            values.append(
                {
                    "value_id": f"{question.question_id}-V{index:02d}",
                    "kind": value_kind,
                    "raw": raw,
                    "normalized": normalized,
                    "span_id": span["span_id"],
                }
            )
        if variant_seed is not None:
            prefix = random.Random(f"phrase:{variant_seed}:{question.question_id}").choice(
                ("Theo hồ sơ, ", "Căn cứ nội dung ghi nhận, ", "Xin xác định: ")
            )
            question_text = prefix + question.text
        else:
            question_text = question.text
        questions.append(
            {
                "question_id": question.question_id,
                "contract_id": contract.contract_id,
                "text": unicodedata.normalize("NFC", question_text),
                "kind": question.kind,
                "mutations": [mutation.kind for mutation in question.mutations],
                "expected_state": question.expected_state.value,
                "comparison": question.kind == "comparison",
                "required_spans": required,
                "acceptable_spans": [dict(span) for span in required],
                "gold_values": values,
            }
        )
    return snapshot, questions
