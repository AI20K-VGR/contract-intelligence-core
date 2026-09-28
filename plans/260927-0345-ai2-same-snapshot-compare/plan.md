---
id: 260927-0345-ai2-same-snapshot-compare
title: "Ghep cap gia tri trong cung snapshot khi than khong nhac phu luc"
status: pending
mode: hard
tdd: true
branch: TBD
created: 2026-09-27
author: user:dungskbg2004@gmail.com
decisions: [DEC-1]
phases:
  - phases/phase-1-pair-same-snapshot.md
  - phases/phase-2-gap-as-note.md
harness_version: 0.0.0-dev
harness_kit_digest: 
harness_schema_version: 1.0
---

# Plan: Ghep cap gia tri trong cung snapshot khi than khong nhac phu luc

> hs:cook ĐỌC file này làm hợp đồng. Evidence dạng `file:line` đã re-grep tại
> thời điểm viết plan. Tag `[ASSUMED]` / `[OBSERVED]` gắn rõ trên claim hành vi.

## Tổng quan
Cùng một `item_key` trong một snapshot bất biến thì AI2 phải hiện **cặp hai
nguồn + hai citation**, kể cả khi thân hợp đồng không viết chữ "Phụ lục 01".
Thiếu chữ dẫn chiếu chỉ là **chú thích quan hệ chưa xác nhận (UNCONFIRMED)**,
không phải lý do xoá cặp. Scope thật rất hẹp (YAGNI): chỉ khoá hành vi ghép cặp
same-snapshot ở `compare.py` và hạ `CONTEXT_GAP` từ tín hiệu-đứng-một-mình xuống
chú-thích-kèm-cặp ở `contract_context.py`. Không bịa câu dẫn chiếu, không chọn
bên thắng, không đụng embedding/LLM.

**Phát hiện load-bearing (đã re-grep):** đường ghép cặp trong `compare.py` KHÔNG
gate trên chữ "Phụ lục" ở thân — nó gate trên **cùng file**. `_pairing_allowed`
trả `True` khi `left_file == right_file` hoặc thiếu file id (`compare.py:152`).
Trong một snapshot, body và annex chung `source_file_id` ⇒ đã ghép cặp sẵn. Bằng
chứng: unit test `test_two_sources_same_context_only` ghép body/annex
`contract_value` khác giá (1000000000 vs 1100000000) → `COMPARABLE_DIFFERENCE`
(`tests/test_compare.py:72`), và integration `test_body_and_annex_totals_conflict_without_a_winner`
(`tests/test_related_mocks.py:55`) — nhưng test này thân CÓ chữ "Chi tiết theo
Phụ lục 01". Chữ "Phụ lục" ở thân chỉ đổi `PART_LINK` ↔ `CONTEXT_GAP` trong
`contract_context.py`, KHÔNG đổi cặp candidate. Hệ quả: Phase 1 phần lớn là
**khoá đặc tả (characterization lock)**, hành vi thay đổi thật nằm ở Phase 2.

## Quyết định đã khoá
- **DEC-1** (`docs/decisions.md:1`): cùng `item_key` trong một snapshot bất biến
  thì hiện cặp + hai citation. Thiếu chữ "Phụ lục N" ở thân là chú thích quan hệ
  chưa xác nhận, KHÔNG xoá cặp. Không bịa câu dẫn chiếu. Không chọn bên thắng.
  Không dùng embedding để quyết định quan hệ.
- Nguồn: `plans/reports/ai2-five-slice-brainstorm-260927.md` (lát 1, hướng B).

## Ràng buộc (constraint-scan)
- Zone: `ai-service/app/pipeline/**` (code) + `ai-service/tests/**` (test) là
  vùng làm việc. Không đụng file harness (`.cursor/**`, `harness/**`).
- **Không hạ cổng citation** (`_pairing_allowed` cross-file vẫn cần
  `relation_pairs`, `compare.py:152-157`): same-snapshot pass là do cùng file,
  KHÔNG được nới path cross-file.
- Giữ bất biến "không chọn bên thắng": mọi reason đi qua
  `_two_source_reason` (`compare.py:213`) và phải chứa câu không kết luận.

## Features
- Cặp same-snapshot không phụ thuộc chữ dẫn chiếu: body↔annex cùng `item_key`,
  giá khác → `COMPARABLE_DIFFERENCE` + hai citation, dù thân không nhắc phụ lục.
- Chú thích quan hệ chưa xác nhận: khi thiếu dẫn chiếu, `CONTEXT_GAP` đi kèm cặp
  như note UNCONFIRMED, không thay thế cặp, không bịa câu "theo Phụ lục 01".

## Phases
| # | Theme | Phụ thuộc | Cỡ |
|---|---|---|---|
| 1 | Pair Same Snapshot | — | S (khoá đặc tả; sửa chỉ khi probe đỏ) |
| 2 | Gap As Note | P1 | S |

## Out of scope
Sáu profile hợp đồng; egress/LLM; viết lại `record.nodes`; pgvector/embedding;
`legal_winner`; self-hashing citation; chọn MST đúng. Không nới cổng citation
cross-file. Không bịa câu dẫn chiếu vào page text.

## Acceptance (toàn plan)
- [ ] Mỗi phase red→green TDD; nếu probe cho thấy đã xanh sẵn thì ghi rõ là
  **characterization lock** (không giả vờ đỏ).
- [ ] `cd ai-service && uv run pytest tests/test_same_snapshot_pair.py tests/test_gap_as_note.py tests/test_related_mocks.py tests/test_compare.py tests/test_ec_silent_pass.py` — xanh.
- [ ] Không có finding nào chọn bên thắng; không có page text bị chèn câu bịa.
- [ ] Cổng citation cross-file không bị nới (giá trị `_pairing_allowed` cross-file giữ nguyên).

## Rollback
Mỗi phase commit riêng. Hoàn tác: `git revert <sha>` từng phase; chạy lại lệnh
acceptance ở trên để xác nhận suite về trạng thái trước.

## Risks
| Rủi ro | K×I | Mitigation |
|---|---|---|
| Phase 1 xanh-ngay (đã ghép sẵn) làm "red-first" giả | High×Low | Probe trước: cook viết test, chạy, nếu xanh thì khai là lock + chuyển đỏ thật sang case chỉ-có-CONTEXT_GAP; không sửa code nếu không có đỏ. |
| Sửa `contract_context.py` vô tình bỏ cặp | Low×High | Test Phase 2 assert cả candidate/CONTEXT_CONFLICT lẫn note tồn tại đồng thời. |
| Nới cổng citation khi "cho qua same-snapshot" | Low×High | Không đụng nhánh cross-file của `_pairing_allowed`; test giữ giá trị cross-file. |
