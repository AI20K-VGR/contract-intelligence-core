---
phase: 4
title: "Structured Contract Analysis"
status: pending
plan: 260924-2352-ai2-ui-completion
created: 2026-09-24
---

# Phase 4 — Structured Contract Analysis

## Mục tiêu

Hoàn thiện theo hai deliverable có gate riêng: (A) các view đã có API/DTO thật gồm structure, facts/fields, tables và review spots; (B) semantic coverage bounded cho nghĩa vụ, điều kiện, phạt, thời hạn, thanh toán, ngoại lệ, relations/comparison/risk chỉ khi endpoint/fixture chứng minh đủ. Không mở rộng thành một hệ thống phân tích mới trong cùng phase.

## Files

- **Modify:** `frontend/src/pages/DossierReviewPage.tsx` và các components analysis/risk/structure hiện có.
- **Modify as needed:** `frontend/src/api/structure.ts` và API clients cho facts, tables, review spots, relations/comparison.
- **Modify as needed:** `ai-service/app/reasoning/l0_rules.py`, `l1_retrieval.py`, `ask_assemble.py` và contract profile/query fixtures.
- **Contract discovery:** nếu relations/comparison/risk chưa có endpoint hoặc DTO ổn định, ghi `BLOCKED_BY_CONTRACT` trong artifact phase và chỉ ship phần A; không dùng mock để đóng gate.
- **Add:** structured result components, evidence-linked row model, fixtures cho multi-document/annex, penalty/obligation/no-evidence/conflict cases.

## TDD

- **RED:** tests cho field answer có citation; comparison khác unit/currency trả `NOT_COMPARABLE`; body/annex khác scope không merge; penalty/obligation không có structured key trả safe state hoặc bounded text hits có citation; unrelated dossier không leak.
- **Implement:** render facts/tree/relations/comparison/risk từ API; bổ sung key aliases/routing và bounded fallback retrieval; giữ `NEEDS_REVIEW`/`INSUFFICIENT_EVIDENCE`.
- **GREEN:** AI2 reasoning tests và frontend rendering tests; kiểm tra citation trên từng row/card.
- **Regression:** AI2 offline release suite, backend search/structure tests, frontend build/lint.

## Success

- [ ] Người dùng xem được các vấn đề hợp đồng, không chỉ party info, từ các nhóm dữ liệu trên.
- [ ] Mỗi fact/finding/risk/comparison row có source hoặc safe state; không có text paragraph “có vẻ đúng” không nguồn.
- [ ] Tab clause/risk không còn placeholder; scope document/annex và conflict state hiển thị rõ.

## Risks

Semantic coverage của producer có thể thấp hơn UI mong muốn. Mitigation: tách “retrieved text evidence” khỏi “verified structured fact”, hiển thị confidence/review state, bổ sung fixture trước khi mở rộng query aliases.
