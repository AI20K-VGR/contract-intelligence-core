# Red-team review: security, failure mode, maintainer, operator

## Verdict

**REVISE-BEFORE-APPROVAL** unless the dispositions below remain explicit in `plan.md` and the named tests are added during cook. This report is evidence-bounded; it does not approve the plan.

## Pre-mortem lenses

- **Technical:** nested result persistence and restart reconciliation can duplicate or drop records under crash/lease races; covered by phases 2 and 5 replay/digest tests.
- **UX:** a user can be stuck on a static citation, hidden annex, or false `ANSWERED`; covered by phase 3 state DTO and phase 4 dynamic viewer/gap states.
- **Adoption:** reviewers will distrust the new queue if it changes a finding locally without revision/audit; phase 4 keeps canonical action/version behavior.
- **Organizational:** Backend, AI2 and FE owners must agree on one result DTO and ACL seam; plan dependencies and phase gates make the contract handoff explicit.
- **External:** Keycloak/vector/LLM/optional dependencies can be absent or change; phase 3 policy matrix and phase 6 `NOT_RUN` classification prevent false PASS.
- **Security:** removing mock registration is insufficient if same-tenant ACL or another prefix bypasses authorization; phase 1 route enumeration and ACL matrix cover both.

## Findings and dispositions

| ID | Severity | Failure scenario | Evidence / repro | Disposition |
|---|---|---|---|---|
| RT-1 | C | A second mock mutation path remains reachable under a different prefix after the main route is fixed. | `backend/src/contract_intelligence/main.py:325-332`; enumerate `app.routes` and POST every review/approve path without `Authorization`. | Accept in Phase 1: route table test must assert canonical resolution and auth on every mutation prefix. |
| RT-2 | C | Same-tenant users read or mutate an unshared dossier because tenant equality is treated as ACL. | `plans/reports/ai1-ai2-be-fe-full-review-20260925.md:84-88`; same-tenant different-user fixture with no share. | Accept in Phase 1: one ACL matrix is called by query, search, citation/finding read and mutation. |
| RT-3 | C | Nested `context_findings`, coverage or annex links are still dropped while top-level facts/findings pass. | `backend/src/contract_intelligence/shared/ai/persistence.py:667-799`; `docs/contracts/ai2.be.processing.result.v1.schema.json:64-78`. | Accept in Phase 2: round-trip full nested fixture and compare IDs/counts/provenance. |
| RT-4 | H | Job reports `SUCCEEDED` and UI turns green although the read model is empty. | Review table in `plans/reports/ai1-ai2-be-fe-full-review-20260925.md:68-76`. | Accept in Phase 2: separate execution status from evidence-ready predicate and metrics. |
| RT-5 | H | “Semantic fallback” calls LLM or fabricates an answer without citation. | `backend/src/contract_intelligence/shared/ai/canonical_processing.py:348-355`; `ai-service/app/reasoning/l0_rules.py:227-237`. | Accept in Phase 3: lexical/vector/LLM order, policy matrix, `used_llm` and citation validation tests. |
| RT-6 | C | FE overwrites server `BLOCKED`/`NEEDS_REVIEW` with `ANSWERED` because answer/hits are present. | `backend/src/contract_intelligence/contract/interfaces/api/routers/contract_router.py:617-622,710-717`; `frontend/src/api/ai2.ts:152-161`. | Accept in phases 3–4: discriminated DTO and all four state render tests. |
| RT-7 | H | Citation navigates to a real page but the wrong body/annex document. | `frontend/src/pages/CitationSplitViewPage.tsx:168-223`; `frontend/src/pages/DossierStructurePage.tsx:351-355`. | Accept in Phase 4: source scope keys and body/annex selector tests. |
| RT-8 | H | Finding queue shows facts but hides events/evidence gaps, recreating the original blind spot. | Review report `:27-38`; wire fields `ai-service/app/contracts/wire.py:248-347`. | Accept in phases 2 and 4: persist and render context/evidence/trace/coverage fixture. |
| RT-9 | H | Restart hydration submits the same snapshot twice or skips a confirmed manifest. | `backend/src/contract_intelligence/worker.py:65,401-417`; restart simulation command in Phase 5. | Accept in Phase 5: digest, idempotency, lease receipt and crash-after-submit tests. |
| RT-10 | H | Legacy separation breaks compatibility fixtures or leaves `AI_SERVICE_MODE=stub` as production default. | `docker-compose.yml:323-327`; `backend/src/contract_intelligence/shared/ai/client.py:323,407-415`. | Accept in Phase 5: canonical default, explicit opt-in compatibility, no canonical OCR call. |
| RT-11 | H | Offline tests are reported as authenticated E2E PASS without a Keycloak token. | Review report `plans/reports/ai1-ai2-be-fe-full-review-20260925.md:129-138`. | Accept in Phase 6: `PASS` requires token/stack evidence; otherwise record `NOT_RUN`. |

## Goodhart check

The plan does not use a single count as proof: record counts are paired with provenance round-trip, state semantics, ACL denial, idempotency and UI behavior. A team cannot make “facts/chunks persisted” green by inserting ungrounded rows because citation validation and evidence-ready gates remain required.

## Approval impact

All findings are accepted and assigned to phases; none is silently deferred. The plan remains `status: pending`; human review must still decide approval.
