# DOC-03 · Product Requirements Document

| Thuộc tính | Giá trị |
|---|---|
| Product / Document ID | Contract Intelligence (PROD-01) / DOC-03 — Product Requirements Document |
| Version / status | v0.10 — Draft · Ready for Review |
| Owner | Trần Thị Kiều Trang — Leader (PRD consolidation) |
| Contributors / reviewer | Trần Thị Kiều Trang (HITL/UX), Phạm Hoàng Chương (Backend/API), Nguyễn Đức Dũng (OCR/ingestion — AI1), Trần Văn Dũng (Finding/semantics — AI2); Mentor |
| Effective / review date | 2026-09-17 / TBD |
| Sprint | Sprint 1 — requirements, wireframe, schema and API draft; project skeleton for structure review is allowed, business feature work waits for mentor architecture approval. |
| Upstream | DOC-01 Product Vision, DOC-02 BRD |
| Downstream | DOC-04, DOC-05, contracts, DOC-06 |
| Thay thế | PRD draft v0.4 (content consolidated into the v0.9 baseline); v0.10 aligns with DOC-04 v0.7 change record (2026-09-17) |

## 1. Personas và journey

| Persona | Journey | Boundary |
|---|---|---|
| Operator | Tạo dossier, upload/confirm manifest, tạo batch, theo dõi/retry task được phép. | Không tạo direct re-OCR hoặc phê duyệt nội dung. |
| Reviewer | Xem source/citation, resolve review item, request evidence, đánh dấu review complete. | Không sửa OCR snapshot hay legal conclusion. |
| Administrator | RBAC, data policy và vận hành. | Không thay nội dung nghiệp vụ. |

Luồng single dossier: upload → manifest → OCR/IDP → evidence review → review complete → internal approval. Re-OCR/rerun tạo effective run mới; result, review và approval cũ vẫn audit được.

## 2. Product state model

| Axis | Values | Owner |
|---|---|---|
| Dossier workflow | `UPLOADED`, `PROCESSING`, `EXTRACTED`, `PENDING_REVIEW`, `REVIEWED`, `APPROVED`, `FAILED` | FastAPI product service |
| Pipeline run | technical execution states trong DOC-04 | Orchestrator |
| Finding | disposition, queue (nullable; `COMPARABLE_MATCH` không có queue) và review revision | AI2/FastAPI/Reviewer |
| Review item | target `FINDING`/`FACT`/`CLAUSE`/`RELATION`, origin `SYSTEM`/`REVIEWER`, effective state | FastAPI backend/Reviewer |
| Re-OCR | request operational `state` và `resolved_route` (hai trục độc lập) | FastAPI backend |

`APPROVED` nghĩa là reviewer có thẩm quyền chấp nhận output được pin theo manifest/effective run/review watermark để dùng nội bộ. Nó không xác nhận hiệu lực, precedence, ký kết hoặc quyết định pháp lý. Effective run mới sau rerun/re-OCR đưa dossier về `PROCESSING` rồi `PENDING_REVIEW`; approval revision cũ được đánh dấu superseded nhưng không bị xóa. `FAILED` không phải trạng thái cuối: Operator có thể rerun whole-dossier hoặc batch retry, đưa dossier về `PROCESSING` với lineage mới; job không biến mất.

## 3. Functional requirements

| Trace | Capability | Acceptance |
|---|---|---|
| BR-01, BR-18 | Single dossier | `1 CONTRACT + 0..n ANNEX`, manifest xác nhận, job/status/evidence truy vấn được. |
| BR-19 | Batch MVP | Batch gồm dossier đã tồn tại, item độc lập, bounded concurrency, retry theo item và summary `DONE/FAILED/NEEDS_REVIEW`. |
| BR-02…BR-05 | OCR/layout/structure | Page classification, raw Unicode, clause/table/bbox và v3 snapshot provenance. |
| BR-07…BR-10 | Citation/bbox | Exact raw span, CPS geometry, machine vs human overlay tách biệt. |
| BR-11…BR-14 | Finding | Context-gated structured/semantic candidate, evidence hai phía cho Conflict. |
| BR-15…BR-17 | HITL | Evidence viewer (page render + OCR line/word, clause tree, fact list, finding panel), `CONFIRM/CORRECT/REJECT/REQUEST_EVIDENCE`, review revision CAS; reviewer có thể mở review item trên fact/clause/match finding (BR-08). |
| BR-16, BR-20 | Review/approval | Review completion và approval revision append-only, role-based, pinned output, stale request `409`. |
| BR-03, BR-06 | Evidence gap | AI2 internal event tạo targeted re-OCR; operator chỉ retry/cancel request audit. |

## 4. Language and data policy

Vietnamese PDF scan/text-layer là Must. English và Vietnamese–English là Should: process/evaluate nhưng không claim production quality trước Gate B. Operator khai báo `declared_language_scope` cho từng document khi confirm manifest (DOC-05 `ConfirmManifestRequest.documents[].declared_language_scope`, mặc định `vi`); manifest version pin giá trị này. OCR snapshot giữ detected profile `vi|en|vi-en|unknown`, detector provenance/confidence và page override khi khác document. `unknown` vẫn process, hiển thị và nằm trong denominator.

## 5. Acceptance vocabulary

| Type | Canonical values |
|---|---|
| Disposition | `COMPARABLE_MATCH`, `COMPARABLE_DIFFERENCE`, `CANDIDATE_AMENDMENT`, `NOT_COMPARABLE`, `INSUFFICIENT_EVIDENCE` |
| Queue | `CONFLICT`, `NEEDS_EVIDENCE`, `NOT_COMPARABLE`, hoặc `null` cho `COMPARABLE_MATCH` (không có system review item) |
| Review item target | `FINDING`, `FACT`, `CLAUSE`, `RELATION` |
| Review action | `CONFIRM`, `CORRECT`, `REJECT`, `REQUEST_EVIDENCE` |
| Page ledger | `PENDING`, `PROCESSING`, `COMPLETED`, `BLANK_VERIFIED`, `NEEDS_REVIEW`, `FAILED`; chỉ `COMPLETED`/`BLANK_VERIFIED` evidence-eligible |
| UI label | “Needs more evidence” maps to queue/action above, never a run state. Run state `NEEDS_REVIEW` là trạng thái kỹ thuật của DOC-04, không phải label này. |

## 6. Non-functional acceptance

Local demo, bounded page/batch concurrency, idempotent queue/event handling, immutable machine outputs, append-only human revisions, private source access, deny-by-default egress, and reportable latency/cost are required. Exact API, contract and measurement behavior are in DOC-04/05/06.

## 7. Purpose, scope and mandatory constraints

PRD states what the product must do, for whom and how acceptance is assessed; it does not own storage, queue, schema field, endpoint wire format or metric formula. A dossier is one commercial contract plus `0..n` PDF annexes, never an FAP/student record.

| ID | Constraint / acceptance boundary |
|---|---|
| CON-01 | Use only mentor-provided GitHub repositories (maximum BE/FE/AI three repositories); do not create a new repository. |
| CON-02 | OJT implementation is a Python 3.12/FastAPI modular monolith with DDD bounded contexts (`contract`, `extraction`, `conflict`, `review`), not microservices; `ai-service` is an internal stateless HTTP service called by the backend (DOC-04 ADR-01/02). |
| CON-03 | Sprint 1–3 input is PDF only, at most 50 MB per file; JPG/PNG is a later extension. |
| CON-04 | External OCR/AI baseline is none; any provider change requires mentor approval and the DOC-04 egress grant controls. |
| CON-05 | Mentor samples never enter the repository or an external service. |
| CON-06 | No business feature code before mentor approves architecture and project structure. A project skeleton (package layout, tooling, empty bounded contexts, health check) may exist on a feature branch solely for that structure review and is not merged before approval. |

## 8. Detailed functional acceptance

| Group | Must acceptance |
|---|---|
| FR-UPL | Create one dossier with `1 CONTRACT + 0..n ANNEX`; batch isolates each dossier failure; reject non-PDF/oversize safely; retain Unicode filenames; role is not inferred from upload order. |
| FR-OCR | Classify every page `TEXT_LAYER/SCANNED/MIXED`; publish immutable, engine-independent snapshot with provenance, text/confidence, word/line geometry, page dimensions/rotation and Vietnamese diacritics; choose engine only from comparable measurements. |
| FR-CLA | Preserve Điều → Khoản → Điểm, annex and table/row/cell structure; every clause resolves to source page and region. |
| FR-FIND | Extract typed price, quantity, date, duration, party, tax code and referenced-contract values with raw/normalized/reason/context/citation; context-gate role, subject, unit, currency, VAT basis, scope and validity; cross-document finding has two evidence sides. |
| FR-FIND | Exactly one disposition is emitted: `COMPARABLE_MATCH`, `COMPARABLE_DIFFERENCE`, `CANDIDATE_AMENDMENT`, `NOT_COMPARABLE` or `INSUFFICIENT_EVIDENCE`. Amendment is a technical candidate only and requires compatible context, reference/amendment wording and effective-date evidence. |
| FR-HITL | Reviewer sees source image/PDF and OCR/clause together, CPS bbox highlight including rotated pages, finding navigation to both sources, and append-only correction; review items exist for findings with a queue and can be opened by a Reviewer on a fact, clause or match finding. Bbox redraw is Should and preserves machine citation. |
| FR-REV / FR-APR | Confirm/correct/reject/request-evidence are distinct from dossier approval; revisions preserve actor/time/reason/parent and use CAS; an authorized Reviewer explicitly approves a pinned output, never a legal conclusion. |
| FR-JOB / FR-AUD | Jobs never disappear on failure; a `FAILED` dossier can be rerun; retries/reruns/re-OCR produce immutable lineage, preserve prior fact/finding/review, and report sample/engine/rule/gold/binding metadata. Operator sees a dossier/job list with status, effective run, derived `conflict_detected` label and readable last error. |

## 9. UX, Sprint 1 and traceability

Sprint 1 delivers wireframes for job list, page evidence view, clause correction and finding panel; the wireframe labels every backend dependency. The team also delivers sample/ground-truth v0, an OCR spike over both text-layer and scan PDFs, real-page bbox demonstration, architecture/API/contracts drafts, and an evaluation protocol. Feature implementation begins only after mentor architecture approval.

| Requirement family | Canonical detailed authority |
|---|---|
| Business scope, personas and out-of-scope | DOC-01 and DOC-02 |
| Snapshot, citation, geometry and re-OCR shape | DOC-04 and `contracts/` |
| Public HTTP payload and review/RBAC actions | DOC-05 |
| Dataset, measurement and quality claims | DOC-06 |

The archived `ST-*` planning material is legacy/audit-only and is not an upstream authority for this PRD; its accepted requirements are consolidated above and in the canonical documents listed in the table.

## 10. Open decisions and approval

| ID | Decision | Owner / current authority |
|---|---|---|
| D-01 | Batch composition and upload UX | Backend + UX; DOC-05 |
| D-02 | `conflict_detected` is a derived label, not a required workflow state | DOC-04 / DOC-05 |
| D-03 | Review completion blockers and direct approval guard | Reviewer + Backend; DOC-04 / DOC-05 |
| D-04 | Product uses `finding`; any `conflict` surface is a queue/API label | DOC-02 / DOC-05 |
| D-05…D-07 | Highlight threshold, OCR engine and preprocessing | Evaluation evidence in DOC-06 |
| D-08 | Snapshot provenance and integration shape | DOC-04 and `contracts/` |
| D-09…D-11 | Semantic comparison boundary, worker concurrency and annex linking | DOC-02 / DOC-04 |
| D-12…D-13 | Image input expansion and external provider use | Mentor approval; DOC-04/DOC-05 |
| D-14 | Remaining integration decisions | Canonical DOC-04 §22 change record |
| D-15 | Backend stack (FastAPI) and backend-push integration with `ai-service` | Decided 2026-09-17, DOC-04 ADR-01/02 and §22 |

Required sign-off: AI1 validates snapshot/provenance/CPS; Backend validates persistence/API/CAS; Frontend validates evidence UX; AI2 validates fact/finding semantics; Leader validates scope; Mentor approves architecture/project structure. Version 1.0 is permitted only after those confirmations and mentor approval.
