---
phase: 3
title: "Facts Findings"
status: pending
plan: 260924-2116-260924-ai2-epic11-completion
created: 2026-09-24
harness_version: 6.3.0
harness_kit_digest: 672de2e098c3cb8451018791788f1052b1b812ccec08a1f124191bd8bbc04ebd
harness_schema_version: 1.0
---

# Phase 3 — Facts, Findings & Index Proposal

## Overview

Đóng ST-045 và ST-047: extract fact typed như giá/ngày/bên/MST với raw, normalized, context, subject, citation và provenance; pair body–annex theo relation/context; tạo finding có đúng một `model_disposition`; đề xuất `IndexContribution` nhưng không publish active.

## Requirements

- Fact phải giữ raw/normalized/context/citation/source role; invalid citation không được đi tới `ANSWERED`.
- Pairing phải explainable qua context/relation và có safe outcome khi ambiguous.
- Mỗi finding có đúng một disposition; index proposal không được mutation active pointer.

## Implementation Steps

1. Viết RED fixtures cho normalization, citation, body–annex ambiguity, proposal gate và retry/duplicate result.
2. Giữ deterministic normalization trước model và validate citation sau extraction.
3. Cập nhật candidate pairing, finding disposition, wire mapping và proposal-only index.
4. Chạy phase 2 regression, assert active pointer không đổi sau retry/duplicate và ghi `verification-P3.json`.

## Files

**Modify:** `ai-service/app/pipeline/fact.py:13`, `ai-service/app/pipeline/candidate.py:7`, `ai-service/app/pipeline/compare.py`, `ai-service/app/pipeline/index.py:6`, `ai-service/app/pipeline/idp.py:39`, `ai-service/app/contracts/wire.py` và Backend result persistence mapping.

**Create/Modify tests:** `ai-service/tests/test_fact_*.py`, `test_compare.py`, `test_index*.py`, `test_citations.py`, canonical result fixtures; Backend persistence/review tests.

## TDD (Tests Before → Implement → Tests After → Regression Gate)

- **Tests-before (RED):** typed fact raw/normalized; currency/unit/date/MST normalization; missing citation; body-only/annex-only; context mismatch; explicit pair; ambiguous pair; exactly-one disposition; `propose` contribution; active pointer unchanged; egress/budget denial.
- **Implement:** giữ deterministic normalization trước model; validate citation sau extraction; candidate pairer dùng relation graph và context; map result sang canonical wire/backend; index store chỉ append proposal.
- **Tests-after:** `cd ai-service; $env:PYTHONPATH=(Get-Location).Path; .\.venv\Scripts\python.exe -m pytest -q tests/test_fact* tests/test_compare.py tests/test_citations.py tests/test_happy_ai2_contract.py`; chạy Backend persistence tests.
- **Regression gate:** phase 2 suite xanh; serialize/deserialize canonical result không mất citation/disposition/provenance.

## Success

- [ ] Mỗi fact có đủ raw/normalized/context/citation và source role.
- [ ] Mỗi finding có đúng một `model_disposition`; thiếu evidence không bị biến thành legal conclusion.
- [ ] Body–annex pair có lý do/context/reference có thể audit.
- [ ] `IndexContribution.publish == propose`; active index và active pointer không đổi.

## Risk Assessment

LLM có thể tạo fact có vẻ hợp lý nhưng citation sai. Mitigation: L0 normalization, citation gate bắt buộc, invalid evidence chuyển review/gap và test negative trên offset/span.
