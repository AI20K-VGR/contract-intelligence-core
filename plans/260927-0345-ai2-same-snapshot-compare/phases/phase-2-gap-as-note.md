---
phase: 2
title: "Gap As Note"
status: done
plan: 260927-0345-ai2-same-snapshot-compare
created: 2026-09-27
harness_version: 0.0.0-dev
harness_kit_digest: 
harness_schema_version: 1.0
---

# Phase 2 — Gap As Note

## Goal
Khi annex được phát hiện nhưng thân không nhắc số phụ lục, `CONTEXT_GAP` vẫn ở
lại NHƯNG **không được là tín hiệu duy nhất** nếu đang tồn tại một cặp giá trị.
Gap trở thành **chú thích quan hệ chưa xác nhận (UNCONFIRMED)** gắn với cặp; cặp
(candidate `COMPARABLE_DIFFERENCE` / `CONTEXT_CONFLICT`) vẫn còn. Không bịa câu
"theo Phụ lục 01" vào page text. Phụ thuộc: Phase 1.

## Đã đọc code (evidence, đã re-grep)
- `CONTEXT_GAP` phát khi annex không có `_body_annex_references`
  (`ai-service/app/pipeline/contract_context.py:135-147`), reason "chưa thấy
  tham chiếu rõ từ thân", `review_state=NEEDS_REVIEW`, `relation_type=None` —
  hiện là finding **đứng một mình**, không liên kết với cặp.
- `PART_LINK` là nhánh có dẫn chiếu (`contract_context.py:122-134`,
  `RelationType.REFERENCES`).
- `CONTEXT_CONFLICT` từ candidate khác `COMPARABLE_MATCH` khi hai nguồn ở hai part
  (`contract_context.py:191-214`) — đây là "cặp" ở tầng context.
- `_finding` seed metadata (`contract_context.py:359-382`) — chỗ gắn cờ
  `unconfirmed_relation`.

## Files
- **Create** `ai-service/tests/test_gap_as_note.py` — test RED.
- **Modify** `ai-service/app/pipeline/contract_context.py` — khi annex thiếu dẫn
  chiếu MÀ có cặp giá trị cùng `item_key`, đánh dấu `CONTEXT_GAP` là note
  UNCONFIRMED (thêm `metadata["relation"]="UNCONFIRMED"` + tham chiếu tới cặp);
  giữ nguyên finding cặp. Không sửa page/`record.nodes`.

## Red test name
`test_missing_annex_mention_is_unconfirmed_note_not_a_dropped_pair`
(trong `tests/test_gap_as_note.py`): cùng scenario Phase 1 (thân KHÔNG nhắc phụ
lục, body 1000000000 / annex 1200000000).

## Green behavior (assert)
- `findings` chứa CẢ HAI: một tín hiệu khác biệt (candidate
  `COMPARABLE_DIFFERENCE` HOẶC `kind == "CONTEXT_CONFLICT"`) VÀ một
  `kind == "CONTEXT_GAP"` cho annex.
- `CONTEXT_GAP` mang cờ UNCONFIRMED: `finding.metadata.get("relation") == "UNCONFIRMED"`
  (RED hiện tại: chưa có cờ → fail).
- Không có node/page nào bị chèn chuỗi "theo Phụ lục 01" / "Phụ lục 01": assert
  page text và `record.nodes` không đổi so với input (kiểu
  `after == before` như `tests/test_ec_silent_pass.py:22-27`).
- `review_state` tổng của job vẫn `NEEDS_REVIEW`.

## Do-not
- KHÔNG xoá/che cặp khi thêm note; gap chỉ là chú thích.
- KHÔNG bịa câu dẫn chiếu vào page text hay `raw_label`.
- KHÔNG chọn bên thắng; KHÔNG dùng embedding; KHÔNG đụng nhánh cross-file
  `compare.py`.

## Success
- [ ] `cd ai-service && uv run pytest tests/test_gap_as_note.py` red→green.
- [ ] Regression `tests/test_related_mocks.py tests/test_compare.py tests/test_ec_silent_pass.py` xanh.
- [ ] `test_padded_annex_heading_links_to_unpadded_body_reference` và
  `test_missing_annex_mention_stays_a_gap_and_does_not_invent_a_node`
  (`tests/test_related_mocks.py:84,103`) vẫn xanh — nhánh có dẫn chiếu và nhánh
  không-có-cặp không đổi.

## Risks
- Sửa contract_context bỏ sót giữ cặp → mitigation: assert đồng thời hai finding.
- Cờ UNCONFIRMED làm hỏng `PART_LINK` path → mitigation: chỉ gắn ở nhánh
  `CONTEXT_GAP` có cặp, giữ test padded-ref xanh.
