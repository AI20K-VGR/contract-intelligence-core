# Archive Manifest

| Archived area | Canonical replacement | Reason | Archived date | Compatibility |
|---|---|---|---|---|
| `ai2-sprint1-planning/` | DOC-01…DOC-06, AI2 pipeline, `contracts/` | Sprint planning/review drafts were consolidated. | 2026-09-17 | Audit only. |
| `pipelines/IDP-OPTIMIZATION-PIPELINE.md` | `AI2-IDP-OPTIMIZATION-PIPELINE.md` | Sequential pipeline lacks controlled re-OCR feedback. | 2026-09-17 | Audit only. |
| `contracts/ai1.snapshot.v1.schema.json` | `contracts/ai1.snapshot.v3.schema.json` | Legacy OCR wire contract. | 2026-09-17 | Read-only legacy input. |
| `contracts/ai1.snapshot.v2.schema.json` | `contracts/ai1.snapshot.v3.schema.json` | Draft v2 lacks language provenance and v3 invariants. | 2026-09-17 | Read-only migration input. |
| `contracts/reocr-request.v1.schema.json` | `contracts/evidence-gap-event.v2.schema.json`, `contracts/reocr-request.v3.schema.json` | AI2 intent and Spring-owned request state were conflated. | 2026-09-17 | Read-only migration input. |
| `contracts/evidence-gap-event.v1.schema.json` | `contracts/evidence-gap-event.v2.schema.json` | v2 adds coverage requirement and bounded repair suggestion. | 2026-09-17 | Read-only migration input. |
| `contracts/reocr-request.v2.schema.json` | `contracts/reocr-request.v3.schema.json` | v3 records Spring-selected repair and finite retry/submission budget. | 2026-09-17 | Read-only migration input. |
