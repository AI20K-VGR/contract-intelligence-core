---
phase: 1
title: "Pair Same Snapshot"
status: done
plan: 260927-0345-ai2-same-snapshot-compare
created: 2026-09-27
harness_version: 0.0.0-dev
harness_kit_digest: 
harness_schema_version: 1.0
---

# Phase 1 — Pair Same Snapshot

## Goal
Khoá hành vi: body và annex cùng `item_key` trong một snapshot, giá đã chuẩn hoá
khác nhau → `COMPARABLE_DIFFERENCE` + **hai citation**, reason nói "không kết
luận bên nào thắng" — **kể cả khi thân KHÔNG có chữ "Phụ lục"**. Phụ thuộc: không
có (chạy đầu).

## Đã đọc code (evidence, đã re-grep)
- `_pairing_allowed` gate trên **cùng file**, không trên chữ "Phụ lục":
  `if not left_file or not right_file or left_file == right_file: return True`
  (`ai-service/app/pipeline/compare.py:152-157`). Same-snapshot ⇒ cùng
  `source_file_id` ⇒ đã ghép cặp.
- `_pair_two_sources` ghép body↔annex khi `_pairing_allowed` (`compare.py:113-121`);
  `_missing_pairing_evidence` chỉ chặn khi cross-file thiếu relation (`compare.py:160-186`).
- `_pair` → `COMPARABLE_DIFFERENCE` khi hai money khác nhau, reason "không kết
  luận bên nào thắng" (`compare.py:334-344`); `_is_identity_fact` loại party
  (`compare.py:89-94`).
- `item_key = "contract_value"` được đặt khi `sk in {"contract_value", ...}`
  (`ai-service/app/pipeline/fact.py:44-45`); `source_role="annex"` khi tổ tiên
  chứa "phụ lục" (`fact.py:35-36`) — độc lập với chữ ở thân.
- Mẫu integration: `test_body_and_annex_totals_conflict_without_a_winner`
  (`ai-service/tests/test_related_mocks.py:55-81`) dùng `adapt_snapshot` +
  `run_idp`, body 1000000000 / annex 1200000000 — **nhưng thân CÓ** "Chi tiết
  theo Phụ lục 01". Case mới bỏ đúng dòng đó.

**Kết luận:** same-file ĐÃ ghép cặp ⇒ phase này là **characterization lock**.
Probe trước; chỉ sửa code nếu probe cho đỏ.

## Files
- **Create** `ai-service/tests/test_same_snapshot_pair.py` — test khoá (dùng
  `adapt_snapshot`/`run_idp` như `test_related_mocks.py`).
- **Modify (chỉ khi probe đỏ)** `ai-service/app/pipeline/compare.py` — sửa tối
  thiểu để cùng-snapshot ghép cặp; **KHÔNG** nới nhánh cross-file của
  `_pairing_allowed`.

## Red test name
`test_body_annex_pair_without_annex_mention_still_differs_no_winner`
(trong `tests/test_same_snapshot_pair.py`): hai page cùng snapshot, thân
"1.1. Tổng giá trị hợp đồng là 1.000.000.000 đồng." (KHÔNG có dòng "Phụ lục"),
annex "PHỤ LỤC 01 - BẢNG GIÁ" + "Tổng giá trị hợp đồng là 1.200.000.000 đồng."

## Green behavior (assert)
- `job.contribution.candidates` có ≥1 item `item_key == "contract_value"`,
  `disposition == Disposition.COMPARABLE_DIFFERENCE`.
- Candidate có đúng hai citation: `len(evidence_left) == 1 and len(evidence_right) == 1`.
- `"không kết luận bên nào thắng" in reason`.
- **Lock case chỉ-có-CONTEXT_GAP:** cùng scenario, `contract_context.findings`
  có `kind == "CONTEXT_GAP"` cho annex (thân không dẫn chiếu) — assert cặp
  candidate VẪN tồn tại song song (không bị gap thay thế). Đây là điểm nối sang
  Phase 2.
- Probe-first: cook chạy test trước. Nếu xanh ngay → ghi commit message "lock:
  same-file already pairs (compare.py:152)". Nếu đỏ → sửa tối thiểu `compare.py`,
  giữ nguyên nhánh cross-file.

## Do-not
- KHÔNG nới `_pairing_allowed` cho cross-file (không đụng dòng
  `compare.py:158` return trên `relation_pairs`).
- KHÔNG bịa câu dẫn chiếu; KHÔNG chọn bên thắng; KHÔNG dùng embedding.
- KHÔNG sửa `record.nodes`, không chạm sáu profile, không bật egress.

## Success
- [ ] `cd ai-service && uv run pytest tests/test_same_snapshot_pair.py` xanh.
- [ ] Regression `tests/test_compare.py tests/test_related_mocks.py` xanh.
- [ ] Nếu không có đỏ, plan/commit ghi rõ đây là lock (không sửa code).

## Risks
- Xanh-ngay bị nhầm là fail-first → mitigation: probe-first + khai lock rõ ràng.
