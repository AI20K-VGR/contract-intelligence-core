# Research report — AI2 completion scope and acceptance evidence

Ngày: 2026-09-23  
Plan: `260923-1023-ai2-completion-release`

## Câu hỏi

AI2 còn cần hoàn thiện gì để có thể đưa vào một release gate đáng tin cậy trên hai
OCR-lab snapshots người dùng vừa cung cấp, và phần nào phải giữ ngoài scope?

## Bổ sung từ hai producer JSON hiện tại [OBSERVED 2026-09-23]

- Cả hai payload khai báo `schema_version=ai1.snapshot.v1` nhưng shape thực tế
  là producer profile `ai1.snapshot.v1/ocr-lab`, không phải canonical backend
  snapshot. Root có `pages`, `nodes` và `table_continuity`; table thật nằm dưới
  `pages[*].tables`, cell dưới `rows[*].cells`.
- `doc-001`: `TEXT_LAYER`, 8 pages, 69 root nodes, 358 lines, 3633 words, 1
  nested table, 0 continuity records; root node geometry `DERIVED`.
- `doc-002`: `SCANNED_OCR`, 4 pages, 7 root nodes, 48 lines, 0 words, 3 nested
  tables, 2 continuity records; table geometry `MEASURED` nhưng một số cell
  geometry `CLAIMED`.
- Hai payload cùng `dossier_id=dossier-001` nhưng khác `document_id` và digest;
  `relation_policy=INDEPENDENT` là bất biến của acceptance replay.

## Nguồn độc lập và phát hiện

### 1. Contract/docs — ownership và ranh giới

- `docs/contracts/AI1-AI2-CONTRACT.vi.md` và các schema dưới `docs/contracts/`
  xác định `ai1.snapshot.v1` là payload AI1–AI2; result envelope cũ không được
  dùng làm canonical snapshot.
- `docs/ai2/AI2-06-implementation-gap.vi.md:23-36,46-82,132-145` đánh dấu
  handoff end-to-end, table continuation, review persistence, vector production,
  OCR và BE ACL/lifecycle là các mức `Partial`, `Mock` hoặc `Ngoài AI2`.
- `docs/ai2/AI2-03-detailed-design.vi.md:158-168,305-353,383` yêu cầu citation
  restore/verification, safe state khi thiếu evidence, bounded processing và report
  có `n`/denominator; không được suy ra MVP readiness chỉ từ JSON hợp lệ.

**Kết luận từ nguồn 1:** completion trong plan phải là contract/evidence/runtime/
release gate của `ai-service`; không âm thầm kéo BE production, OCR provider,
pgvector hoặc UI HITL vào cùng thay đổi.

### 2. Runtime code — đường chạy thật

- `ai-service/app/ai2/v1/__init__.py:11-80` có public API v1 gồm `process_files`,
  adapter-only `process_payloads` và full `process_payloads_full`.
- `ai-service/app/pipeline/ai2_batch.py:39-201` ép `relation_policy=INDEPENDENT`,
  chạy từng payload độc lập, giữ lỗi theo document và luôn phát hành
  `cross_document_findings=[]` ở batch model.
- `ai-service/app/pipeline/contract_context.py:39-205` và
  `contract_events.py:39-115` tạo context/event có citation; `idp.py:64-238`
  xử lý egress/budget/citation/review state.
- `ai-service/app/pipeline/ai1_snapshot_adapter.py:258-372` phân biệt canonical
  snapshot, OCR-lab input và legacy result; `contracts/wire.py:18-146` validate
  request membership và wire model.

**Probe [OBSERVED 2026-09-23]:** chạy:

`Set-Location ai-service; .venv\Scripts\python.exe scripts/run_ai2_ai1_files.py --input "C:\Users\dungs\Downloads\ocr-run-20260922-093747-doc-001.json" --input "C:\Users\dungs\Downloads\ocr-run-20260922-095540-doc-002.json" --strict --output artifacts/ai2-two-input-replay-20260923.json`

Kết quả machine report `ai-service/artifacts/ai2-two-input-replay-20260923.json`:

- `overall_review_state=NEEDS_REVIEW`, `dossier_id=dossier-001`,
  `relation_policy=INDEPENDENT`, `batch_issues=0`, `cross_document_findings=0`,
  `documents=2`.
- `doc-001`: `SUCCEEDED + NEEDS_REVIEW`, 126 events, 0 facts, 2 evidence issues.
- `doc-002`: `SUCCEEDED + NEEDS_REVIEW`, 34 facts, 20 events, 1 context finding,
  6 evidence issues.

**Kết luận từ nguồn 2:** hai input đã chạy được qua cùng batch path và không bị trộn
ở cấp batch; acceptance còn phải kiểm tra sâu annex/continuity/citation và lý do
`NEEDS_REVIEW`, không được đổi overall state thành PASS chỉ vì exit code `0`.

### 3. Tests/CI — bằng chứng regression và giới hạn đo

- `ai-service/tests/test_contract_context.py:24-148` khóa embedded annex,
  independent files, events, party questions và citation state.
- `ai-service/tests/test_processing_wire_contract.py:110-313` khóa request/result
  schema, idempotency API, retry, egress denial và citation failure.
- `ai-service/tests/test_job_store.py:23-133` khóa tenant-scoped idempotency,
  lease claim, terminal persistence và cross-dossier rejection.
- `.github/workflows/ai-service.yml` chỉ là offline gate: synthetic PDF, pytest
  `not live` và contract registry; không chứng minh live provider hoặc Linux runner
  từ một lần chạy local.

**Probe [OBSERVED 2026-09-23]:**

`Set-Location ai-service; .venv\Scripts\python.exe -m pytest -q -m "not live" --basetemp ..\tmp\plan-ai2-basetemp-20260923`

đạt `198 passed, 6 deselected, 2 warnings, RC=0`. Cùng suite không chỉ định
`--basetemp` có `6 errors` do `WinError 5` khi pytest quét
`C:\Users\dungs\AppData\Local\Temp\pytest-of-dungs`; lỗi đó là môi trường temp,
không phải test assertion. Vì vậy mọi gate plan phải pin basetemp writable hoặc
được chạy trên CI runner sạch.

**Kết luận từ nguồn 3:** test coverage hiện đủ làm baseline mạnh cho plan, nhưng
phải ghi rõ denominator/path và tách offline gate khỏi live/accuracy claims.

## Open questions

1. Có được phép dùng hai absolute paths Downloads trong CI/release không? Hiện
   chúng là user-provided local inputs; plan chỉ dùng khi có mặt, không commit chúng.
2. Khi không có credential live, release decision là `defer/not-run`, không phải
   pass; cần human xác nhận release posture sau khi plan được duyệt.
3. Nếu muốn production end-to-end, cần plan riêng cho BE ACL/lifecycle, OCR
   provider reliability, persistent review audit và process isolation.

## Ranked conclusion

1. **P0 — Giữ một plan hard bốn phase:** contract boundary → evidence correctness
   → bounded runtime → release verification. Đây là đường ngắn nhất vì bốn phase
   dùng cùng model/corpus và có dependency tuần tự.
2. **P1 — Dùng hai JSON Downloads làm acceptance replay tùy điều kiện:** chúng là
   bằng chứng integration thật, nhưng không thay thế deterministic fixtures và
   không được commit/được xem là sample production đại diện.
3. **P2 — Tách live/production platform thành follow-up:** không dùng rate limit,
   thiếu credential hoặc absence của UI/BE production để nới safety gate trong plan.
