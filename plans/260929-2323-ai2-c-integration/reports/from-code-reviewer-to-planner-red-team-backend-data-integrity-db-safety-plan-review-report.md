# Red-team review: AI2-C integration plan

- **Artifact:** `plans/260929-2323-ai2-c-integration/` (`plan.md`, phase files, `plan-graph.yaml`, research and sizing artifacts)
- **Date:** 2026-09-30 · **Role:** hs-red-teamer (advisory only; no plan or code changes)
- **Personas (3):** P-B Backend data-integrity reviewer · P-D database/schema safety reviewer · P-O operations/release reviewer
- **Scope:** adversarial review of implementation and acceptance gates in C. Existing human decisions (HC-C1..C4, VD-C1..C8) remain authoritative and are not treated as agent approvals.
- **Verdict:** **REVISE before P3 / release.** Two high-impact correctness gaps remain: stale attempts can rewind the Backend query digest after being rejected, and the planned retry cleanup can delete citations shared with other extractors. Neither is covered by the stated tests.

## Findings

| ID | Severity | Persona | Evidence | Scenario | Required plan fix |
|---|---|---|---|---|---|
| RT-C-01 | High | P-B | `phases/phase-3-backend-ai2-e2e.md:37,39-41,57` | Two retries overlap. Attempt 3 persists first; attempt 2 finishes later. F3.2 says the lower attempt is ignored, but F3.3 still updates `dossier.metadata_json["ai2_snapshot_digest"]` from that stale report. The read model remains at attempt 3 while queries are pinned to attempt 2's digest, so current evidence can become unavailable or inconsistent. E5 only tests sequential retry and will not expose the stale completion. | Make persistence return whether the attempt was accepted plus the canonical persisted attempt/digest, and update dossier snapshot identity only from that accepted/current result (ideally in the same transaction). Add a concurrency test that completes N+1 before N and asserts both result JSON and dossier digest remain at N+1. Keep the existing conflict behavior for equal attempts. |
| RT-C-02 | High | P-D | `phases/phase-3-backend-ai2-e2e.md:34,108-110`; `backend/src/contract_intelligence/extraction/infrastructure/persistence/orm.py:174-194` | On supersede, facts may be scoped by `FactORM.extractor`, but `CitationORM` has no `run_id`, extractor, or other provenance column. Deleting citations for all documents in the run can therefore remove citations still referenced by non-AI2 facts or other runs. The plan acknowledges a discriminator probe at step 1(c), but the acceptance tests do not require preserving shared/non-AI2 citations, and the proposed deletion is destructive. | Preserve the human stop gate, and make it an explicit hard prerequisite: if citation ownership cannot be proven, do not perform supersede or continue 3a. Require a data-safe design (for example, delete only citations proven unreferenced after removing the exact AI2 facts, with FK/reference checks, or add explicit provenance via an approved migration). Add a test with AI2 and non-AI2 facts sharing a document/citation and assert the non-AI2 citation survives retry. Do not infer ownership from document membership alone. |

## Review notes

- I found no basis to bypass the ADR-14 Architecture Lead gate or the Backend/mentor approvals. The findings concern runtime invariants that those approvals do not themselves test.
- Phase 2's transactional job/record requirement and phase 4's hold-out/release approvals were not flagged here; this report is limited to the two actionable, high-impact C integration gaps above.

## Red-team checklist

- [x] Used three relevant personas.
- [x] Each finding cites plan/code file lines and gives a concrete failure scenario.
- [x] Each finding includes a specific plan-level fix and missing test.
- [x] Preserved human decision gates; no implementation or plan edits made.
