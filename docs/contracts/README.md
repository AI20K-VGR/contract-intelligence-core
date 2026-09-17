# Contracts

## Canonical contracts

| Contract | Owner | Purpose |
|---|---|---|
| `ai1.snapshot.v3` | AI1, validated by Spring | Immutable OCR/layout, revision and language provenance. |
| `evidence-gap-event.v2` | AI2 producer | Evidence-backed gap, suggested bounded repair and coverage requirement. |
| `reocr-request.v3` | Spring | Persisted policy-selected repair, state, finite budget and result lineage. |
| `external-egress-approval-grant.v1` | Spring policy subsystem | Immutable, single-use approval for a bounded external provider task. |
| `artifact-dependency.v1` | Spring/AI2 | Page revision → downstream artifact edges. |
| `optimization-control-plane.v1` | Spring control plane | Immutable config, candidate patch and evaluation plan. |

V1/V2 snapshots, evidence-gap v1 and re-OCR v1/v2 remain migration/audit material in archive; they are not new integration targets.

## Semantic validation

Spring validates IDs/digests/task ownership, CPS bounds and ordering (`0≤x0<x1≤1`, `0≤y0<y1≤1`), exact raw Unicode-code-point spans (`char_end>char_start`), line/word/table references, per-snapshot uniqueness of page/page-revision/line/word/table/cell IDs, and authorized object URI access. Every word must belong to its containing line, satisfy `0≤start<end≤len(raw_text)` and equal the exact raw Unicode slice; citation word IDs must belong to the cited line and overlap its cited span. Measured word evidence is only `native` or `detector`; `derived`, `line_only` and `absent` cannot become word-level citation evidence. Table/cell citations inherit their table/cell geometry status and cannot elevate derived/line-only geometry. Human changes are append-only overlays.

For v3, every snapshot is a **full materialized page inventory** for its document version, not a delta. Spring validates page count/identity against the source manifest. If `parent_snapshot_id` is present, source/dossier/document must match the parent; changed page revisions must map to the re-OCR request and unchanged pages must declare `reused_from_snapshot_id` plus matching prior page revision/digest. `reocr` requires a non-null parent and parent page revisions. Aggregate snapshot `SUCCESS` requires every expected page `SUCCESS` with quality `COMPLETE`; otherwise Spring downgrades it to `PARTIAL`/`FAILED`. Declared/detected language never changes raw OCR or document role; `unknown` remains visible and reportable.

## Event and re-OCR rules

AI2 publishes `EvidenceGapDetected.v2`; it never schedules OCR. Spring validates the evidence, chooses the repair action and route, persists `ReOcrRequest.v3`, emits `ReOcrScheduled`, consumes AI1 `SnapshotRevisionPublished`, then emits `SelectiveInvalidationRequested`. Envelope consumers dedupe by event ID and idempotency key; outbox/inbox delivery is at-least-once and order-independent.

Scope semantic rules: `REGION` targets exactly one page with valid CPS regions; `PAGE` targets exactly one page without regions; `PAGE_PAIR` targets exactly two consecutive pages without regions. Repair is limited to `REGION_RESCAN`, `PAGE_PAIR_CONTEXT` or `OUTPUT_SPLIT`. Spring validates source snapshot/document, evidence/artifact bindings, page/chunk coverage, policy, finite quota and profile. A positive fact/finding requires only `COMPLETED` or `BLANK_VERIFIED` source pages and finalized chunks; `NEEDS_REVIEW`, `FAILED` or `PARTIAL` force `insufficient_evidence` unless a reviewer supplies a valid evidence overlay. External routing cannot be requested from the public API.

Repair-action matrix: `REGION_RESCAN` requires `REGION`; `PAGE_PAIR_CONTEXT` requires `PAGE_PAIR` and `TARGET_AND_CONTINUATION`; `OUTPUT_SPLIT` requires `PAGE` or `PAGE_PAIR` and reason `OUTPUT_TRUNCATION`. `EXTERNAL_REVIEW_REQUIRED` is non-executable and must remain `AWAITING_EXTERNAL_REVIEW`; only `EXTERNAL_APPROVED` with an immutable [`external-egress-approval-grant.v1`](external-egress-approval-grant.v1.schema.json) can enqueue a provider task. Spring atomically binds the grant to the exact request, source snapshot, target digest, tenant, policy/consent, provider/model/region/retention and profile, then consumes it once before enqueue. Expired or revoked grants cannot transition or enqueue. Used counters must not exceed the persisted maxima, including crop-child and crop-depth counters.

## Validator and adapter gates

JSON Schema validates structural shape. Spring's semantic validator is mandatory before persist and is covered by contract tests for bbox ordering, raw-span round trip, scope/page-pair rules, lineage, unique IDs, state/outcome and counter limits. `DOC-05` is a public DTO adapter, not a second wire-contract authority: its `ReOcrRequest` and citation invariants must pass parity fixtures against the JSON schemas and this validator before release.

[`validation-fixtures.v1.json`](validation-fixtures.v1.json) is a runner-ready contract: each case declares its `target`, named base payload, ordered RFC-6902 patch and expected schema/semantic/DTO outcomes. `validation_targets` maps the target to the exact JSON Schema (when one is authoritative), Spring validator and DOC-05 component; `null` means that layer has no separate authority (for example Citation has no standalone JSON Schema). Citation vectors carry their raw source line and cover `A😀B` code-point offsets, Vietnamese composed/decomposed text, CRLF and a repeated token. `workflow_cases` additionally gate grant/request binding, expiry/revocation/consume-once, external transition, and re-OCR/batch CAS lineage. A release is blocked unless every invalid case is rejected and a corresponding valid fixture is accepted by the named validator/adapter.
