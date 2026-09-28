# Research: Tất cả các phần cần thiết để hoàn thiện AI2

**Mode**: depth
**Date**: 2026-09-23
**Sources reviewed**: 10 nguồn ngoài repo + code/docs/tests hiện tại  
**Delegation**: self-research; không spawn agent để giữ một evidence ledger thống nhất

## Central question

AI2 cần những capability, contract, safety gate, runtime control và evaluation artifact nào để
xử lý contract/annex nhiều loại một cách có thể kiểm chứng; phần nào repo đã có, phần nào mới là
thiết kế, và thứ tự hoàn thiện nào ít rủi ro nhất?

### Evaluation criteria

- Evidence integrity: raw source, citation, provenance, scope.
- Semantic coverage: structure, facts, relations, comparison, query.
- Extensibility: profile/version/annex extension.
- Safety: no guessing, no scope leakage, no legal winner, bounded execution.
- Verification: deterministic regression, human-reviewed golden set, release report.
- Operational fit: tenant isolation, idempotency, budget, egress, lease, observability.

### Boundary

Nghiên cứu chỉ bao phủ AI2 sau handoff AI1. Không nghiên cứu OCR provider, Backend production
queue/ACL/lifecycle, frontend HITL, production vector platform hoặc legal advice/precedence.

## Summary

AI2 nên được hoàn thiện như một **evidence-first semantic dossier system**: boundary → structure
and members → evidence/citation → profile facts → relations → comparison → bounded query.
Repo đã có nền tảng mạnh cho citation, safe state, comparison, relation graph, query stack,
runtime budget và tenant/idempotency; test offline hiện xanh `198 passed, 6 deselected` và
contract registry `OK (5 schemas)` [OBSERVED 2026-09-23].
Khoảng trống lớn nhất là profile registry theo loại hợp đồng, public contract thống nhất cho
member/scope/relation/profile, full free-form Q&A và evidence-aware evaluation. Không nên dùng
LLM/RAG để che các khoảng trống này.

## 1. Current baseline observed in repo

### 1.1 Existing foundation

| Area | Observed evidence | Interpretation |
|---|---|---|
| Review states | `ai-service/app/contracts/models.py:10-14` | Có `ANSWERED`, `NEEDS_REVIEW`, `INSUFFICIENT_EVIDENCE`, `BLOCKED`, `NOT_COMPARABLE`; đây là nền safe-state tốt |
| Citation model | `models.py:210-244`; `pipeline/citations.py`; `reasoning/l3_ground.py:18-225` | Có citation model, registry và re-validation node/page/table/cell |
| Facts/candidates | `models.py:435-470`; `pipeline/fact.py`; `pipeline/compare.py:42-405` | Có raw/normalized fact, candidate và two-sided evidence; cần gắn profile semantics ổn định |
| Structure | `pipeline/result_structure.py:1-87`; `pipeline/outline.py:9-227` | Có derived hierarchy, parent/order/scope, body/annex handling và node-first citation |
| Relations | `reasoning/relations.py:128-386` | Có `PARENT_OF`, `SAME_CLAUSE`, `REFERENCES`, `AMENDS`, `DEFINES`, `USES_DEFINED_TERM` và safe unresolved relation |
| Query | `reasoning/query.py:16-175`; `reasoning/stack.py:15-172` | Có typed intent, L0–L3 và `unscoped` safe state; free-form bounded route chưa đầy đủ |
| Tools/security | `tools/gateway.py:18-257`; `security/service_envelope.py` | Có allowlist, tenant/dossier lookup và tool-level checks |
| Runtime | `pipeline/runtime.py:18-89`; `pipeline/idp.py:39-168`; `tools/jobs.py:27-310` | Có budget, egress, timeout, lease, idempotency và persistence hooks |
| Vector | `reasoning/vector_recall.py:1-223` | Có optional recall, model/dimension/snapshot gates; vector chưa phải source of truth |
| Regression | command output 2026-09-23 | `198 passed, 6 deselected`; warning chỉ do pytest cache permission |
| Contract registry | `node scripts/check-contract-registry.mjs` | `Contract registry OK (5 schemas)` |

### 1.2 Gaps that matter for the requested AI2

1. **Type profile contract**: plan đã chỉ định registry cho sáu profile nhưng public schema/model
   cho `profile_type`, `profile_version`, `field_key`, type-specific extension và `UNMAPPED` chưa
   trở thành một contract hoàn chỉnh [repo: `plans/260923-1023-ai2-completion-release/phases/phase-1-contract-boundaries.md`].
2. **Public member/relation semantics**: `app/contracts/wire.py:67-77` hiện giới hạn wire relation
   ở `MEMBER_OF`/`ANNEX_OF`, trong khi internal graph có nhiều relation hơn; cần phân biệt
   membership relation với semantic relation, không dồn tất cả vào một enum.
3. **Dossier-wide structure**: structure repair đã tồn tại, nhưng acceptance cần bảo đảm tree
   đầy đủ cho contract + annex, không merge clause trùng số giữa các scope.
4. **Free-form query**: `query.py` có `unscoped`; `orchestrator.py:9-60` có plan-and-act bounded
   nhưng phải bắt buộc query envelope, selected members và L3 claim-level grounding trước khi
   coi là Q&A v1.
5. **Evaluation truth**: corpus người dùng gọi là 95, repo manifest hiện có 65 records; chưa có
   human-reviewed golden set. Đây là blocker cho accuracy claim, không phải blocker cho schema/
   citation/safety regression.
6. **Cross-cutting output**: cần một package/result contract nối facts, structure, relations,
   candidates, evidence issues, answer và trace mà không tạo các format song song.

## 2. Research findings by AI2 part

### 2.1 Handoff and canonical contract

**Required behavior**

- Validate producer profile, schema version, tenant, dossier, document/member identity, source
  digest, page/node/table topology, role relation and attempt/idempotency.
- Preserve raw snapshot immutably.
- Reject malformed payloads with stable codes; route incomplete but usable evidence to review state.
- Keep legacy adapter separate from canonical backend input.

**Why**

Contract extraction cannot be reliable if an output cannot identify which snapshot/member/page it
came from. JSON Schema recommends declaring `$schema` so dialect/tooling interpretation is fixed;
conditional subschemas can represent type-specific branches without making one giant union schema [1][2].

**Repo status**

`wire.py:111-144` already validates dossier members, unique IDs, one body and relation targets.
The next required step is extending this boundary for versioned contract profiles without leaking
internal metadata into the public root.

**Priority**: P0.

### 2.2 Contract-type profiles

**Required behavior**

Use a small shared core plus versioned type profiles:

- Core: parties, identifiers, dates, term, scope, value, currency, payment, delivery, acceptance,
  termination, governing references, source scope and review state.
- Wave profiles: `SALES`, `SUPPLY_SERVICE`, `LEASE`, `CONSTRUCTION_WORK`, `EMPLOYMENT`, `NDA`.
- Annex extensions: price, quantity, technical scope, schedule, SLA, payment, acceptance,
  amendment.
- Each field: `field_key`, aliases, value type, normalization rule, unit/currency policy, source
  scope, cardinality, evidence requirement, profile version.
- Unknown type/field: raw evidence + `UNMAPPED`/`NEEDS_REVIEW`; never force into a nearby profile.

**External finding**

CUAD contains 510 commercial contracts, 13,000+ expert-supervised labels and 41 clause types [7].
The lesson is not to copy CUAD's taxonomy; it is that contract field inventories require explicit
annotation policy and domain review. A universal field list without reviewed labels will create
false completeness.

**Repo status**

`fact.py:25-175` already normalizes through a tenant profile/aliases, but the contract-type
registry requested by the current plan is a separate capability and should not be hidden inside
tenant aliases.

**Priority**: P0 for registry/core; P1 for each profile vertical slice.

### 2.3 Structure tree and document membership

**Required behavior**

Represent:

```text
dossier
├── contract member
│   ├── body
│   ├── clause/section
│   └── table/field
└── annex member
    ├── annex heading
    ├── clause/section
    └── table/field
```

Every node needs stable identity, type, raw label, parent, order, page range, source member,
scope, provenance, status and citation anchors. Body and annex nodes with the same clause number
must remain separate.

**External finding**

ContractNLI uses document-level hypotheses plus evidence spans; 607 documents were annotated, many
documents exceed a 512-token model context, and evidence can be discontinuous. It reports that
negation by exception is difficult and that better evidence identification improves NLI [8].
This supports structure/context windows and multi-span citations instead of whole-document prompts.

**Repo status**

`result_structure.py` and `outline.py` already provide derived structure and citation location.
The missing acceptance is dossier-level completeness and explicit membership semantics for all
profile/annex outputs.

**Priority**: P0.

### 2.4 Citation, provenance and evidence gate

**Required behavior**

- Every fact, relation, candidate, event and answer claim points to page/node/line/table/cell
  evidence or is marked review/insufficient.
- Citation must resolve against the active snapshot and page revision.
- No generated geometry, line or span when upstream lacks it.
- Keep raw text, normalized value, source digest, extraction version and review state.
- Expose claim-level citations, not only one citation for an entire answer.

**External finding**

W3C PROV models provenance around entities, activities and agents and explicitly supports
reproducibility, versioning and derivation [3]. For contract QA, ContractNLI requires concise,
self-contained evidence spans for a decision [8].

**Repo status**

`l3_ground.py:24-84` re-resolves citations and marks validation status; `models.py:210-244`
stores citation metadata. This is one of the strongest existing foundations and should become the
authoritative gate used by every downstream output.

**Priority**: P0; do not relax this gate to improve answer rate.

### 2.5 Fact extraction and normalization

**Required behavior**

- Deterministic extraction first for dates, money, currency, quantity, units, identifiers, VAT,
  parties and explicit clause labels.
- Preserve `raw_value`; put parsed value in `normalized_value`.
- Carry subject, role, unit, currency, condition, validity, scope, field/profile key, provenance,
  citation and review state.
- Do not infer a missing effective date, quantity, currency conversion or party identity.
- Multiple plausible values stay as multiple candidates or `NEEDS_REVIEW`.

**External finding**

CUAD demonstrates the value of expert clause annotations [7]. ContractNLI shows that contract
entailment is harder than span identification, especially with exceptions/negation [8]. Therefore
normalization and extraction should be separable from legal interpretation.

**Repo status**

`Fact` exists at `models.py:435-461`; `fact.py` and `grounding.py` implement normalization and
grounding. The main gap is attaching contract profile semantics and preserving field-level scope
through every path.

**Priority**: P1 after structure/evidence spine.

### 2.6 Relation graph

**Required behavior**

Separate relation categories:

- Membership: contract/annex/document member.
- Structure: `PARENT_OF`, `SAME_CLAUSE`.
- Reference: `REFERENCES`, `DEFINES`, `USES_DEFINED_TERM`.
- Change candidate: `AMENDS`.
- Uncertainty: `CONTEXT_GAP`.

Each edge needs from/to node, relation type, support kind, source scope, citation and review state.
`ANNEX_OF` must only express membership when caller/evidence confirms it; semantic `AMENDS` is a
separate claim.

**External finding**

PROV emphasizes derivation and versioning as first-class provenance concepts [3]. ContractNLI's
evidence-span formulation also implies that a relation or inference cannot be trusted without
supporting spans [8].

**Repo status**

`relations.py:128-386` already builds internal graph edges. `wire.py:67-77` needs a clearer public
separation between member role relation and semantic graph relation.

**Priority**: P0 for structure/membership; P1 for semantic relation types.

### 2.7 Comparison and amendment candidate

**Required behavior**

Compare only compatible facts/clauses:

- `WITHIN_DOCUMENT`
- `CONTRACT_ANNEX`
- `ANNEX_ANNEX`

Pair by field key, subject/role, scope, unit/currency and validity. Output two-sided evidence,
disposition, comparison scope, review state and explanation. Different unit/currency/validity or
scope is `NOT_COMPARABLE`, not a conflict. Explicit “replace/amend/supplement” text may produce
`CANDIDATE_AMENDMENT`, never legal precedence.

**Repo status**

`compare.py:42-405` already contains these comparison scopes, `NOT_COMPARABLE`, two evidence sides
and `CANDIDATE_AMENDMENT`. The research priority is contract/profile integration and adversarial
tests, not rewriting comparison as an LLM task.

**Priority**: P1.

### 2.8 Retrieval and indexing

**Required behavior**

Route retrieval in this order:

```text
tenant/dossier/member authorization
→ exact/structured lookup
→ clause/table/field retrieval
→ optional semantic/vector recall
→ snapshot/profile/scope filter
→ citation re-validation
→ bounded reasoning
```

Vector recall is a candidate generator, never evidence by itself. Index keys must include snapshot
digest, member/scope, profile/extraction version and embedding model/version. Re-indexing must not
overwrite raw snapshot or silently reuse stale review.

**External finding**

RAG evaluation literature separates retrieval relevance from generation accuracy and faithfulness;
those dimensions must be measured separately [9]. OWASP notes that RAG does not fully mitigate
prompt injection [5].

**Repo status**

`vector_recall.py:92-223` already gates snapshot/model/dimension/egress/budget and returns trace.
`gateway.py:169-200` exposes structured/semantic search under tenant/dossier context. The remaining
work is selected-member filtering, profile/scope metadata and end-to-end retrieval metrics.

**Priority**: P1; semantic/vector is optional for v1.

### 2.9 Free-form Q&A and reasoning

**Required behavior**

Free-form means flexible language, not unlimited authority. Each request must carry:

```text
tenant_id → dossier_id → selected_member_ids → allowed evidence scope → query budget
```

The answer path should be:

1. classify intent and identify referenced members/clauses/fields;
2. retrieve exact/structured evidence;
3. traverse relation graph for multi-step questions;
4. use semantic recall only when deterministic retrieval is insufficient;
5. generate claim-level answer from bounded evidence;
6. re-resolve citations and assign `ANSWERED`, `NEEDS_REVIEW` or `INSUFFICIENT_EVIDENCE`.

**Repo status**

`FourLayerReasoner` exists at `stack.py:15-172`; `orchestrator.py:9-60` limits steps/replans and
uses allowlisted tools; `l3_ground.py` revalidates citations. `query.py:142` still classifies
unmatched questions as `unscoped`, so the missing capability is general bounded routing, not a
new free-form model.

**Security evidence**

OWASP states that RAG does not fully prevent prompt injection [5], excessive functionality and
permissions increase agency risk [4], and unbounded inference can cause denial of service or
financial loss [6]. Q&A should therefore remain read-only, allowlisted, budgeted and fail-closed.

**Priority**: P1 after semantic spine; no arbitrary tool, URL, filesystem or code execution.

### 2.10 Runtime, budget, egress and job lifecycle

**Required behavior**

- Separate processing, LLM and embedding budgets.
- Bound timeout, max calls, retries and context size.
- Check egress before provider call; fallback to deterministic partial result.
- Enforce tenant-scoped idempotency and dossier-scoped lease.
- Persist raw input, derived result and review overlay separately.
- Mark review stale when input/profile/extraction version changes.

**External finding**

OWASP classifies unbounded consumption as a risk involving DoS, denial of wallet and service
degradation [6]. NIST AI RMF requires safe failure beyond knowledge limits and documentation of
validity/reliability limits [10].

**Repo status**

`runtime.py`, `idp.py` and `jobs.py` already implement many controls. Research focus should be
contract tests proving these controls remain intact when adding profile and Q&A work.

**Priority**: P0 safety baseline; P1 hardening before release.

### 2.11 Security and tool governance

**Required behavior**

- Tool allowlist by operation, not generic arbitrary command.
- Every tool call re-checks tenant/dossier/member scope and version pins.
- Input document text is data, not instructions; prompt injection content must not alter policy.
- No write/publish action from AI2; review/publish remains an external gate.
- Record tool calls, rejected calls, provider policy, trace and review state.

**External finding**

OWASP recommends minimizing extension functionality/permissions, avoiding open-ended extensions,
using the user's authorization context and requiring approval for high-impact actions [4].

**Repo status**

`gateway.py:18-47` and `orchestrator.py:14-60` provide an allowlisted baseline. It must be
extended with selected-member authorization and a clear no-write contract.

**Priority**: P0 for read-only boundaries; P1 for adversarial prompt/tool tests.

### 2.12 Persistence, index contribution and review overlay

**Required behavior**

- Store source digest/version and derived package fingerprint.
- Keep raw snapshot, derived facts/relations/index contribution and human review separate.
- A rerun invalidates/stales prior review when relevant inputs change.
- Proposal/index contribution cannot become authoritative without external approval.

**Repo status**

`tools/persist.py:49-186` stores record state, facts, relation graph, citations and review flags;
`tools/jobs.py` covers job ownership. The gap is a single documented version/fingerprint policy for
profile changes, semantic extraction changes and Q&A cache invalidation.

**Priority**: P1.

### 2.13 Observability and traceability

**Required behavior**

Every processing/query trace should carry:

- request/job/attempt ID;
- tenant/dossier/member scope;
- source snapshot digest and profile/extraction/policy versions;
- route chosen, tools called, retrieval modes, candidate counts;
- citation validation result;
- budget/egress/provider status;
- final review state and reason.

OpenTelemetry defines traces, metrics, logs and baggage as signals and provides context propagation
across process boundaries [11][12]. AI2 does not need to adopt OpenTelemetry immediately, but its
internal `QueryTrace`/processing trace should preserve equivalent correlation fields.

**Priority**: P1 for release evidence; P2 for production exporter integration.

### 2.14 Evaluation, golden set and release gate

Evaluate separately:

| Layer | Metrics/evidence |
|---|---|
| Contract/wire | schema validation, semantic rejection, unknown field, identity/digest/membership |
| Structure | node coverage, parent/order/scope accuracy, annex membership, table continuity |
| Citation | resolve rate, page/node/line/table/cell correctness, invalid citation rate |
| Facts | field precision/recall, normalization correctness, raw preservation, review rate |
| Relations | edge precision, unresolved relation detection, false `ANNEX_OF`/`AMENDS` rate |
| Comparison | compatible pair precision, `NOT_COMPARABLE` correctness, two-sided evidence |
| Retrieval | recall/relevance by exact/structured/semantic route, scope leakage = zero |
| Q&A | answer relevance, claim-level faithfulness, citation correctness, abstention quality |
| Runtime/security | budget enforcement, egress denial, tenant/dossier isolation, idempotency, no arbitrary tool |
| Release | n, denominator, version, candidate/golden/not-run/failed, exact command and environment |

CUAD illustrates why expert annotations matter for contract review [7]. ContractNLI illustrates
why evidence identification and contradiction/entailment should be evaluated separately [8]. RAG
research likewise separates retrieval and generation dimensions [9]. Therefore the existing 95
candidate cases cannot become a golden set without review.

**Priority**: P0 for schema/citation/safety/regression; P1 for reviewed business accuracy.

## 3. Target AI2 architecture

```text
Canonical/producer snapshot
        │
        ▼
[1] Boundary validator
    identity · digest · version · tenant · dossier · members · policy
        │
        ▼
[2] Dossier semantic spine
    members · body/annex · structure tree · scope · tables · provenance
        │
        ├──────────────► citation/evidence registry and review issues
        │
        ▼
[3] Profile fact layer
    core facts + typed profile fields + annex extensions
        │
        ▼
[4] Relation layer
    structure/reference/definition/change candidates + CONTEXT_GAP
        │
        ▼
[5] Analysis layer
    within-document · contract-annex · annex-annex comparisons
        │
        ▼
[6] Query layer
    exact → structured → bounded semantic → relation traversal → L3 grounding
        │
        ▼
Result package: facts · structure · relations · findings · answer · citations · trace · state
```

### Design rule

The only authoritative truth source is the validated AI1 snapshot plus resolvable evidence. Every
derived layer may add interpretation metadata, but may not invent source geometry, source text,
membership, value, date, precedence or legal conclusion.

## 4. Recommended completion sequence

### Priority 0 — Contract and safety spine

- Canonical/producer adapter boundary.
- Profile registry schema and version pin.
- Dossier member/scope semantics.
- Citation/evidence registry and safe-state taxonomy.
- Raw immutability, tenant/dossier isolation, budget/egress/lease/idempotency.

**Exit evidence:** invalid payloads reject; valid payload preserves raw; every derived output has
resolvable citation or safe state; baseline tests remain green.

### Priority 1 — Semantic dossier and first vertical slice

- Complete structure tree for contract + annex.
- Implement core fields and one or two type profiles end-to-end.
- Build relation graph with explicit membership/semantic separation.
- Run comparison using typed facts and two-sided evidence.
- Implement bounded Q&A over selected members only.

**Profile recommendation:** start with `SALES` and `SUPPLY_SERVICE` only if the two supplied inputs
and available fixtures are confirmed to map to them; otherwise choose the two profiles with the
most reviewer-confirmed examples. This is `[ASSUMED]`, not an observed corpus fact.

**Exit evidence:** one dossier can answer structure, field, comparison and relation questions with
citations; outside-scope and insufficient-source questions abstain.

### Priority 2 — Profile and annex expansion

- Add `LEASE`, `CONSTRUCTION_WORK`, `EMPLOYMENT`, `NDA` one at a time.
- Add annex extensions only when a field has source evidence and reviewer expectation.
- Maintain backward-compatible profile versions and migration tests.

**Exit evidence:** a new profile adds registry/test fixtures without changing core semantics.

### Priority 3 — Release and evidence maturity

- Reconcile 95-case claim with 65-record manifest.
- Promote only human-reviewed cases to golden.
- Add per-layer metrics and release report.
- Add trace export/monitoring integration if production scope is opened later.

**Exit evidence:** claims are bounded by denominator, version and review status.

## 5. Options / comparison

| Direction | Pros | Cons | Fit |
|---|---|---|---|
| Evidence-first semantic spine | Safest, reusable, debuggable, supports all downstream capabilities | Q&A value appears after foundation | **Priority 1** |
| Profile-first all six | Visible field coverage quickly | Schema sprawl, poor cross-profile evidence consistency | Fallback only |
| Q&A/RAG-first | Fast demo | Scope/citation/faithfulness risk; hard to debug | Reject as primary |
| Universal ontology-first | Long-term abstraction | High modeling cost before corpus/golden | Defer |

## 6. Quick Start

1. Freeze the current evidence model as the source of truth: snapshot digest, member/scope,
   node/page/table/cell citation and review states.
2. Define the type-profile registry as data, not hard-coded prompt branches.
3. Select two reviewer-confirmed profiles for one vertical slice.
4. Make one result package contain structure, facts, relations, findings, answer, citations,
   trace and state.
5. Add adversarial fixtures for missing context, duplicate values, wrong unit/currency, detached
   annex, broken citation, cross-dossier query, prompt injection text and budget exhaustion.
6. Only after that enable optional semantic/vector recall and provider-backed reasoning.

## 7. Common Pitfalls

- Treating a valid JSON payload as proof that its values are correct.
- Using filename, page order or equal `dossier_id` as proof of contract–annex relation.
- Merging same-number clauses across body and annex.
- Normalizing away raw Vietnamese text, currency, unit or conditions.
- Comparing values without subject, scope, validity, unit and currency.
- Counting citation presence instead of citation correctness and claim-level support.
- Letting vector similarity decide truth or relation.
- Letting free-form Q&A call arbitrary tools or retrieve outside selected members.
- Using confidence score as a substitute for evidence.
- Promoting all 95 candidate cases to golden without human adjudication.
- Expanding six profiles and every annex extension before one end-to-end vertical slice passes.

## 8. Open questions

- [ASSUMED] `SALES` and `SUPPLY_SERVICE` are the best first vertical slice; confirm with actual
  corpus mapping and reviewer availability.
- What is the authoritative source/version of the user-mentioned 95 cases, given the current
  65-record manifest?
- Which core fields are mandatory for every profile, and which are only profile extensions?
- Does Q&A v1 allow only evidence-backed answers, or also bounded summaries marked `NEEDS_REVIEW`?
- Which relations are release-critical in wave 1: only membership/structure/reference/amendment,
  or defined-term cascade as well?
- What human review artifact is required to promote a candidate case into golden evidence?
- Should query/result traces use an internal contract now and map to OpenTelemetry later, or adopt
  OpenTelemetry context fields immediately?

## 9. Evidence and references

[1] https://json-schema.org/understanding-json-schema/reference/schema | JSON Schema official documentation | accessed 2026-09-23 | VERIFIED

[2] https://json-schema.org/UnderstandingJSONSchema.pdf | JSON Schema 2020-12 guide | accessed 2026-09-23 | VERIFIED

[3] https://www.w3.org/TR/prov-overview/ | W3C PROV-Overview | accessed 2026-09-23 | VERIFIED

[4] https://genai.owasp.org/llmrisk/llm062025-excessive-agency/ | OWASP LLM06:2025 Excessive Agency | accessed 2026-09-23 | VERIFIED

[5] https://genai.owasp.org/llmrisk/llm01-prompt-injection/ | OWASP LLM01:2025 Prompt Injection | accessed 2026-09-23 | VERIFIED

[6] https://genai.owasp.org/llmrisk/llm102025-unbounded-consumption/ | OWASP LLM10:2025 Unbounded Consumption | accessed 2026-09-23 | VERIFIED

[7] https://www.atticusprojectai.org/cuad/ | The Atticus Project, CUAD | accessed 2026-09-23 | VERIFIED

[8] https://arxiv.org/abs/2110.01799 | Koreeda & Manning, ContractNLI | 2021 | VERIFIED

[9] https://arxiv.org/abs/2405.07437 | Yu et al., Evaluation of Retrieval-Augmented Generation: A Survey | 2024 | VERIFIED

[10] https://airc.nist.gov/airmf-resources/airmf/5-sec-core/ | NIST AI RMF Core | accessed 2026-09-23 | VERIFIED

[11] https://opentelemetry.io/docs/concepts/signals/ | OpenTelemetry Signals | accessed 2026-09-23 | VERIFIED

[12] https://opentelemetry.io/docs/specs/otel/context/api-propagators/ | OpenTelemetry Propagators API | accessed 2026-09-23 | VERIFIED
