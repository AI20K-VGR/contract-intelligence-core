---
phase: 2
task: ST-045
title: "Extract facts/findings có citation + pair body–annex"
status: pending
plan: 260924-2201-260924-ai2-epic11-gap-closure
created: 2026-09-24
harness_version: 6.3.0
harness_kit_digest: 672de2e098c3cb8451018791788f1052b1b812ccec08a1f124191bd8bbc04ebd
harness_schema_version: 1.0
---

# Phase 2 — ST-045: Facts/findings + body–annex

## Mục tiêu

Đóng riêng ST-045: typed fact giữ raw/normalized/context/citation/provenance và body–annex pairing theo source role/context/relation. Mỗi finding có đúng một `model_disposition`, không tạo legal winner. Đây là commit bằng chứng C2.

## Files / ownership

- **AI2:** `ai-service/app/pipeline/fact.py`, `ai-service/app/pipeline/candidate.py`, `ai-service/app/pipeline/compare.py`, `ai-service/app/pipeline/idp.py`, relevant wire/models.
- **Tests:** fact/citation/compare tests; tạo `ai-service/tests/test_st045_facts_findings.py` nếu thiếu coverage.
- **Backend verification:** chỉ kiểm tra canonical result mapping/persistence cần cho facts/findings; không nối query trong commit này.

## TDD

- **RED:** missing raw/normalized/context/citation, invalid citation, body–annex thiếu context/relation, duplicate/missing `model_disposition`, attempted legal winner.
- **Implement:** bổ sung validation/fixture/adapter mapping tối thiểu trên pipeline hiện tại; không đổi safe disposition semantics.
- **GREEN:** targeted ST-045 suite và ST-044 regression.

## Success / evidence

- [ ] Fact có raw + normalized + context/subject + citation/provenance.
- [ ] Body–annex pairing chỉ xảy ra khi context/relation đủ; thiếu evidence trả state an toàn.
- [ ] Mỗi finding có đúng một disposition; không có legal winner.
- [ ] Tạo `verification-ST-045.json` gồm commands, test count, exit code, citation evidence.
- [ ] Commit duy nhất của task: `feat(ai2): complete ST-045`; kiểm tra `git show --stat --check <C2>`.

## Lệnh kiểm tra

```powershell
cd ai-service
$env:PYTHONPATH=(Get-Location).Path
.\.venv\Scripts\python.exe -m pytest -q tests/test_compare.py tests/test_citations.py tests/test_st045_facts_findings.py tests/test_processing_wire_contract.py
```

## Rollback

`git revert <C2>` rồi chạy lại C1 regression; không gộp thay đổi ST-046/ST-047.
