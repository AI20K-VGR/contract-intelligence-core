---
phase: 2
title: "Evidence Pipeline"
status: pending
plan: 260923-1023-ai2-completion-release
created: 2026-09-23
harness_version: 6.3.0
harness_kit_digest: 672de2e098c3cb8451018791788f1052b1b812ccec08a1f124191bd8bbc04ebd
harness_schema_version: 1.0
---

# Phase 2 — Evidence Pipeline

## Overview

Đóng các đường tạo evidence: clause/table/fact/event/context/party và mọi
substantive claim trong free-form answer phải trỏ về
snapshot immutable và citation kiểm tra được. Tập trung vào table liên trang,
claimed geometry, node repair, embedded annex và hai file độc lập; không biến
heuristic thành kết luận pháp lý.

## Context links

- `docs/ai2/AI2-06-implementation-gap.vi.md:23-36,46-82`
- `docs/ai2/AI2-13-contract-context-and-independent-samples.vi.md`
- `docs/ai2/AI2-14-party-count-full-flow.vi.md`
- `ai-service/app/pipeline/citations.py:10-145`
- `ai-service/app/pipeline/contract_context.py:39-334`
- `ai-service/app/pipeline/contract_events.py:39-115`
- `ai-service/app/pipeline/table.py`
- `ai-service/app/pipeline/outline.py`
- `ai-service/app/pipeline/compare.py`
- `ai-service/app/pipeline/fact.py`
- `ai-service/app/pipeline/result_structure.py`
- `ai-service/app/reasoning/query.py`
- `ai-service/app/reasoning/stack.py`
- `ai-service/app/reasoning/relations.py`
- `ai-service/app/reasoning/fact_link.py:108-327`
- `ai-service/app/reasoning/ask_assemble.py:15-436`
- `ai-service/app/reasoning/l0_rules.py:487-540`
- `ai-service/app/reasoning/l3_ground.py:86-251`

## Files

**Modify:** `ai-service/app/pipeline/citations.py`, `grounding.py`, `table.py`,
`outline.py`, `contract_context.py`, `contract_events.py`; `ai-service/app/reasoning/
fact_link.py`, `ask_assemble.py`, `l0_rules.py`, `l3_ground.py`; và
`ai-service/app/contracts/models.py`.

**Also inspect/modify only when tests require:** `ai-service/app/pipeline/compare.py`,
`fact.py`, `result_structure.py`; `ai-service/app/reasoning/query.py`, `stack.py`,
`relations.py`.

Các file reasoning trong danh sách là điểm đọc/kiểm tra trước. Chỉ sửa chúng khi
targeted test chứng minh gap; không refactor đồng loạt chỉ vì chúng xuất hiện trong
đường gọi.

**Create or extend tests:** `ai-service/tests/test_citations.py`,
`test_compare.py`, `test_contract_context.py`, `test_ai2_hardening.py`,
`test_input_coverage.py`, `test_structure_reconstruction.py`.

## Tests Before (regression coverage written BEFORE refactoring)

- [ ] Khóa exact-span/page/table/cell citation trong `test_citations.py` và
  `test_ai2_hardening.py`.
- [ ] Khóa independent two-document, embedded annex, event và party questions tại
  `test_contract_context.py:24-148`.
- [ ] Khóa table missing≠zero, continuation và malformed row behavior; test xanh là
  regression lock.

## Implement

1. Duy trì một resolver authoritative cho page/node/table/cell; xác nhận page
   revision, digest, text span và source scope trước khi `VALID`.
2. Duyệt table continuation/sparse/claimed geometry: ô không có line/span hoặc
   geometry `CLAIMED` giữ raw value nhưng tạo issue/`NEEDS_REVIEW`.
3. Bảo toàn node hierarchy và active-node repair; không dùng preview node làm điều
   kiện substring duy nhất khi citation đúng page source.
4. Fact/event/context/party chỉ assemble từ evidence cùng scope; role mention không
   đủ để khẳng định pháp nhân/MST.
5. Với `relation_policy=INDEPENDENT`, không candidate/finding cross-document;
   body–annex cùng snapshot chỉ tạo `PART_LINK` khi có link text/citation.
6. Mọi uncertainty đi qua `EvidenceIssue`, review item hoặc safe state; không bịa
   value thiếu, ngày hiệu lực, header kế thừa hay legal winner.

7. Với producer profile hiện tại, kiểm tra table ở `pages[*].tables` thay vì chỉ
   nhìn root; `doc-001` có 1 nested table, `doc-002` có 3 nested tables và 2
   continuity records. `word_count=0` trên `SCANNED_OCR` không được biến thành
   kết luận “không có text”.

8. Chuẩn hóa structure tree với `parent_id`, `order`, `page_range`, source scope,
   body/annex role và table/clause membership; giữ node `PARTIAL`/`FAILED` thay vì
   bịa node còn thiếu.

9. Chạy fact extraction theo type profile và phát candidate comparison theo
   `item_key + scope + subject/condition/validity`; giữ hai phía evidence, relation
   graph và không chạy precedence/legal-winner engine.

10. Mở rộng free-form Q&A từ `classify_ask`/`QueryRouter`: pin tenant+dossier+
    selected members, retrieve bounded evidence, cho phép câu hỏi quan hệ nhiều
    bước nhưng L3 phải ground mọi claim. Chỉ được trả `ANSWERED` khi mọi substantive
    claim có citation usable và `grounded=true`; citation invalid/stale, thiếu source
    hoặc query ngoài scope phải trả safe state. Source text/metadata từ snapshot chỉ là
    untrusted data, không được đổi system/developer policy, tool allowlist, scope hay
    output state.
11. Chuẩn hóa answer contract thành `claims[]`; mỗi claim phải có citation ID và
    citation resolver phải kiểm tra node/page/revision/scope/quote hash. Marker kiểu
    `citations: required` không đủ để coi answer grounded.

## Tests After (new behavior)

- [ ] Test table continuation thiếu header, sparse cells, claimed cell bbox và page
  failure; raw evidence còn nguyên và issue có citation.
- [ ] Test duplicate/missing node parent, invalid page revision, stale citation và
  line/span mismatch; assert `UNVERIFIED`/`NEEDS_REVIEW`.
- [ ] Test party count: có MST gắn role thì đếm entity duy nhất; chỉ có Bên A/B/C
  thì trả role count + `NEEDS_REVIEW`; không trộn hai document.
- [ ] Test event/context findings có source citation, còn thiếu evidence thì không
  tạo candidate finding giả.
- [ ] Test invariant `ANSWERED => grounded=true => claim-level citation usable`; case
  `ANSWERED` nhưng `grounded=false` hoặc citation invalid phải bị hạ state.
- [ ] Test prompt injection nằm trong clause/table/metadata không thể thay đổi policy,
  gọi tool, nới scope hoặc biến text thành authoritative instruction.
- [ ] Test citation claim-level với page/node/table/cell, revision, scope và quote/span
  hash; thiếu một claim citation hoặc citation stale/invalid phải hạ state.
- [ ] Test raw UTF-8, NFC/NFD, smart quote, zero-width/control chars và round-trip
  report; normalized match không được sửa raw source/citation quote.
- [ ] Replay chính xác hai file ngoài repo đã nêu trong plan; không copy chúng vào
  repo và không claim pass nếu file không còn tại path.

## Additional tests after (contract wave)

- [ ] Test profile-specific fields cho cả sáu loại wave đầu; unknown type/field
  giữ raw/evidence và không bị ép vào profile khác.
- [ ] Test tree parent/order/scope và body–annex relation edges; relation thiếu
  target trả `CONTEXT_GAP`/`NEEDS_REVIEW`.
- [ ] Test free-form question lookup/compare/cascade/field question với query
  trong một dossier; query khác dossier bị chặn hoặc trả `INSUFFICIENT_EVIDENCE`.

## Regression Gate

`Set-Location ai-service; .venv\Scripts\python.exe -m pytest tests/test_citations.py tests/test_compare.py tests/test_contract_context.py tests/test_ai2_hardening.py tests/test_input_coverage.py tests/test_structure_reconstruction.py -q --basetemp ..\tmp\ai2-phase2-basetemp`

## Post artifact

Ghi `plans/260923-1023-ai2-completion-release/artifacts/verification-P2.json`
với exact commands, số test, topology table/continuity assertions, citation
resolver checks, evidence issue counts và verdict. Replay Downloads là conditional:
file thiếu thì ghi `NOT_RUN`; fixture deterministic vẫn phải chạy.

## Success

- [ ] Không có fact/finding/event trả `VALID` khi citation resolver không verify.
- [ ] Hai input độc lập trả `cross_document_findings=[]`; `doc-002` vẫn có annex
  inventory/continuity trong đúng snapshot.
- [ ] Case không chắc chắn được surface qua issue/state, không bị bỏ hay chắc hóa.

## Risks

Siết citation có thể giảm số câu trả lời `ANSWERED`; đó là trade-off an toàn. Không
giảm gate để giữ tỷ lệ answered; tách coverage khỏi accuracy trong report.
