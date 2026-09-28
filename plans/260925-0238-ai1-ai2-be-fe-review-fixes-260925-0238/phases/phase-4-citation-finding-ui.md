---
phase: 4
title: "Citation Finding UI"
status: pending
plan: 260925-0238-ai1-ai2-be-fe-review-fixes-260925-0238
created: 2026-09-25
---

# Phase 4 — Citation Finding UI

## Overview

Thay citation compare/split static bằng viewer theo dossier/document/source citation thật, đồng thời đưa context findings, evidence issues, events/trace, coverage và finding actions vào Dossier Review. UI chỉ render dữ liệu đã scope/ACL và state từ Backend; annex là một document scope có selector.

Dependencies: phases 1–3. Không tạo mock data mới trong live path.

## Files

- Modify: `frontend/src/pages/DossierReviewPage.tsx`, `frontend/src/components/DossierSearchResults.tsx`, `frontend/src/pages/CitationComparePage.tsx`, `frontend/src/pages/CitationSplitViewPage.tsx`, `frontend/src/pages/DossierStructurePage.tsx`, `frontend/src/api/ai2.ts` and finding/review API module.
- Create: `frontend/src/components/ContextFindingsPanel.tsx`, `frontend/src/components/DynamicCitationViewer.tsx`, `frontend/src/components/FindingQueue.tsx`, `frontend/tests/dynamic-citation-viewer.test.tsx`, `frontend/tests/context-findings-panel.test.tsx`, `frontend/tests/finding-queue.test.tsx`.
- Create/modify Backend citation/finding DTO only if a failing contract test proves the existing read endpoint lacks source resolution; add `backend/tests/unit/test_citation_source_scope.py` with it.
- Modify: `frontend/tests/dossier-search-results.test.tsx`, `frontend/tests/review-actions.test.ts`, `frontend/tests/ai2-contract.test.ts`.

## Tests Before (RED)

- [ ] Search click passes `dossier_id`, `document_id`, citation ID and location; pages no longer render hard-coded `#DOS-2024-884`/`v3.2`.
- [ ] Body and annex citations open selected source file/page/line/bbox; a citation from another document is not silently rejected or mis-opened.
- [ ] A fixture with context finding, event, evidence issue, coverage and zero facts/findings renders the gap/context panel.
- [ ] Finding queue renders severity, two-sided evidence, review action, base-version conflict and revision audit; save is not a `setTimeout`.
- [ ] Run `npm --prefix frontend test -- --run dynamic-citation-viewer.test.tsx context-findings-panel.test.tsx finding-queue.test.ts`; tests fail against current static pages.

## Implement

1. Define citation/finding view models from Phase 3 DTO and normalize locatability/source scope at the API boundary.
2. Replace hard-coded pages with route/query state keyed by dossier + document + citation; add body/annex selector and unresolved/error states.
3. Add context/evidence/coverage/trace panels without hiding facts/findings.
4. Wire finding actions to canonical review API with severity, two-sided evidence, `base_version`, 409 handling and revision audit; remove fake local success.
5. Guard live route against `sampleSearchQuery`, `splitCitations` and static dossier constants; fixtures remain test-only.
6. Preserve keyboard focus and state labels; unresolved citations are not verified-source links.

## Tests After (GREEN)

- [ ] Real body/annex locations open with correct scope and unresolved warning.
- [ ] Context/evidence panel shows counts and reason codes even with zero facts/findings.
- [ ] Success, unauthorized/error and stale-version 409 render server results without fabricated local success.
- [ ] Static-data guard passes for the live review route.

## Regression Gate

`npm --prefix frontend test -- --run`; `npm --prefix frontend run build`; `npm --prefix frontend run lint`; `npm --prefix frontend run format:check`; and, when Backend DTO/route changes, `python -m pytest backend/tests/unit/test_citation_source_scope.py backend/tests/unit/test_review_router.py -q --basetemp tmp/plan-ai2-p4-backend`.

## Success / Acceptance

- [ ] No hard-coded dossier/version/citation remains in live compare/split paths.
- [ ] User sees facts/findings plus context findings, evidence issues, coverage/trace and AI2 state.
- [ ] Body/annex citation opens correct source scope; unresolved/partial is a gap, not a verified link.
- [ ] Finding actions use Backend ACL/RBAC/version and show revision/audit.

## Risks

- Multiple panels can cache stale results; query keys include dossier/document/generation and invalidate after action.
- Source-resolution endpoint may be incomplete; add only the minimal proven DTO seam, not a new document system.
- Fixtures can hide static runtime behavior; retain negative import/content scan for live routes.

## Rollback

Use a feature flag to return to the prior page only with an explicit legacy/static limitation label; never call it a verified evidence viewer. Revert the UI/API change set independently of persisted evidence/audit.
