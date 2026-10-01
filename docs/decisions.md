# Decision Register

---
id: DEC-1
status: active
date: 2026-09-27
actor: "user:dungskbg2004@gmail.com"
ts: "2026-09-26T20:46:56.614623+00:00"
affects: "ai-service/app/pipeline/compare.py"
---

## DEC-1 — So cap gia tri trong cung snapshot khi than khong nhac phu luc

Cung item_key trong mot snapshot bat bien thi hien cap va hai citation. Thieu chu dan chieu Phu luc N la chu thich quan he chua xac nhan, khong xoa cap. Khong bia cau dan chieu. Khong chon ben thang. Khong dung embedding de quyet dinh quan he. Nguon: plans/reports/ai2-five-slice-brainstorm-260927.md.

---
id: DEC-dungskbg2004-1
status: active
date: 2026-10-01
actor: "user:dungskbg2004@gmail.com"
ts: "2026-09-30T19:09:31.882458+00:00"
affects: "ai-service/app/pipeline/compare.py, ai-service/app/reasoning/relations.py, docs/ai2/AI2-15"
---

## DEC-dungskbg2004-1 — AI2 clause frame: amendment timeline is review-only; statutory-limit checks out of AI2 scope

User chose (brainstorm 2026-10-01): AI2 may build a value timeline from AMENDS edges with effective_from and propose an effective value, but always NEEDS_REVIEW; keeps AI2-15 s4 boundary (no LEGAL_WINNER). Checking clauses against statute (e.g. penalty cap) is not AI2's job.

---
id: DEC-dungskbg2004-2
status: superseded
date: 2026-10-01
actor: "user:dungskbg2004@gmail.com"
ts: "2026-09-30T19:09:32.235559+00:00"
affects: "plans/260929-2323-ai2-b-versioned-service, plans/260929-2323-ai2-c-integration, evals/golden/spec.py"
---

## DEC-dungskbg2004-2 — AI2 re-direction to clause frames: keep plan A as neutral baseline, rewrite B/C; architecture chosen only after key-normalization spike

User chose (brainstorm 2026-10-01): clause-frame (norm key + structured condition) is the new AI2 direction for all 6 profiles. Plan A golden/scorer stays to prove improvement. Option 1 Fact++ / 2 full Frame / 3 layered Frame decided by spike on ~30 clauses (synthetic + real anonymized): key precision >=95%, recall >=80% proposed gate.

---
id: DEC-dungskbg2004-3
status: active
date: 2026-10-01
actor: "user:dungskbg2004@gmail.com"
ts: "2026-10-01T00:30:30.845497+00:00"
affects: "evals/spikes/clause_key, plans/260929-2323-ai2-b-versioned-service, plans/260929-2323-ai2-c-integration"
supersedes: DEC-dungskbg2004-2
---

## DEC-dungskbg2004-3 — AI2 direction: clause key graph is the core; gates measured per dossier, not per pooled pair

User chose after hs:critique (2026-10-01, verdict BLOCKED advisory, plans/reports/ai2-clause-key-critique-report.md). Keeps from DEC-dungskbg2004-2: plan A stays the neutral baseline, plans B/C are rewritten around clause frames. Changes: (1) the clause key graph stays the AI2 core (user overrode the critique's PA-C-first recommendation); (2) the gate is measured on real anonymized dossiers (body+annex), not on pairs pooled across unrelated contracts: false-DUPLICATE = 0, wrong-definite-key rate <= threshold to be set, recall within a dossier, precision per disposition, n >= 120 pairs. Before B/C rewrite: fix critique blockers C-01 (DUPLICATE on None values) and C-02 (uncertainty turned into definite keys); PARAMETER/timeline (C-04) must be measured, not assumed. Compatible with DEC-dungskbg2004-1 and with the earlier same-snapshot value-pairing ruling.

---
id: DEC-dungskbg2004-4
status: active
date: 2026-10-01
actor: "user:dungskbg2004@gmail.com"
ts: "2026-10-01T00:52:59.752173+00:00"
affects: "evals/spikes/clause_key/mechanism.py"
---

## DEC-dungskbg2004-4 — AI2 key graph: scope/object is a comparison attribute in decide(), not part of the REMEDY key

User chose D3=B (2026-10-01; plans/reports/research-261001-0147-ai2-key-scope-and-lexicon-governance-report.md). REMEDY key stays (bearer, action, qualifier). Frames carry a scope span; decide() checks scope before comparing consequences: both scopes certain and different -> SCOPE_DIFFERS (shown, values not compared); one side scoped -> GENERAL_VS_SPECIFIC; scope present but not certainly normalized -> never DUPLICATE. Certain normalization = item_key match or a small closed per-profile list. Evidence: only 3/135 gold same-key pairs differ in scope; putting scope in the key would split ~67/135 pairs and turn scope-normalization errors into silently lost pairs.

---
id: DEC-dungskbg2004-5
status: active
date: 2026-10-01
actor: "user:dungskbg2004@gmail.com"
ts: "2026-10-01T00:53:01.473768+00:00"
affects: "evals/spikes/clause_key, docs/ai2/AI2-01-business-policy-perspective.vi.md, plans/260929-2323-ai2-b-versioned-service, plans/260929-2323-ai2-c-integration"
---

## DEC-dungskbg2004-5 — AI2 lexicon governance: G3 now - LLM proposes aliases, tenant lexicon editor approves, versioned per tenant

User chose D4=G3 now (2026-10-01; plans/reports/research-261001-0147-ai2-key-scope-and-lexicon-governance-report.md). Two loops: mechanism/global lexicon released by dev behind the per-dossier gate of DEC-dungskbg2004-3; alias loop per tenant. LLM only proposes aliases from UNMAPPED/backoff frames, choosing existing actions/qualifiers; a named tenant lexicon editor approves (no reviewer correction changes rules by itself, AI2-DOC-02-brd:78). Approved aliases live in tenant_profile_version; adding one creates a new run and keeps old results (AI2-01:30,38). Automatic checks before approval: no collision with another action's aliases, generic-verb stoplist, minimum length. Keys from tenant aliases carry method=TENANT_ALIAS and the wrong-key rate is tracked per alias source, with revocation above a threshold. Cross-tenant promotion only with tenant opt-in and only as abstract alias strings, never contract text (AI2-01:102, BR-A10). Open: who holds the editor role, the revocation threshold, the opt-in clause.
