# Current-state AI2 audit

Ngày kiểm tra: 2026-09-23  
Phạm vi: code liên quan tới AI2, contract/schema, test/eval, API và FE. Không đọc các artifact sinh tự động như nguồn implementation; không sửa code.

## 1. Kết luận điều hành

AI2 hiện có một pipeline deterministic có grounding tương đối đầy đủ cho snapshot AI1: validate handoff, dựng outline/relation graph, extract fact/table/event, tạo comparison candidate, kiểm tra citation và trả review state. Có hai input lane rõ ràng: canonical `ai1.snapshot.v1`/Backend processing và compatibility `ai1.result.v0.1`. Có thêm OCR-lab batch API nhưng batch này chủ động xử lý từng JSON độc lập và chỉ cho `relation_policy=INDEPENDENT`.

Các yêu cầu của Outcome Contract về long-running HITL chưa phải runtime hiện tại. `plan_units()` tạo unit/checkpoint serializable để chuẩn bị resume, nhưng `run_idp()` vẫn chạy synchronous trong process. `/jobs/idp` dùng FastAPI `BackgroundTasks`; SQLite lưu wire job/lease/idempotency nhưng chưa có worker scheduler, event log, replay hoặc startup recovery. Không có SSE, WebSocket, AG-UI, A2UI, ADK adapter hay A2A endpoint. FE chỉ gọi REST `ask` và hiển thị answer/status.

## 2. Phạm vi code đã kiểm tra

| Vùng | Vai trò thực tế | Trạng thái |
|---|---|---|
| `ai-service/app/contracts/` | Pydantic models, service envelope, wire conversion và validation | Đã chạy trong runtime |
| `ai-service/app/pipeline/` | Adapter, handoff, structure/table, fact, compare, context, events, grounding, IDP | Đã chạy trong runtime |
| `ai-service/app/reasoning/` | Query routing và bounded reasoning/retrieval/grounding | Đã chạy cho workspace/query |
| `ai-service/app/tools/` | In-memory evidence store, gateway, SQLite jobs/session | Một phần durable local; store chính còn process-local |
| `ai-service/app/api/main.py` | Workspace demo và Backend→AI2 job API | Đã có HTTP routes; orchestration vẫn local |
| `ai-service/app/ai2/v1/` | Package API `vsf-ai2` | Đã có, OCR-lab relation policy còn giới hạn |
| `ai-service/src/contract_ocr/` | AI1/OCR-lab và snapshot serializer | Ngoài ownership reasoning AI2 nhưng là upstream |
| `backend/src/` | Public backend skeleton | Placeholder |
| `frontend/`, `packages/typescript/` | FE hỏi tự do và consumer types | Minimal; chưa có live review |
| `ai-service/tests/`, `evals/` | Unit/API/contract/eval/regression | Nhiều coverage cho evidence; thiếu runtime long-running |

## 3. Flow thực tế

### 3.1 Canonical Backend lane

1. `POST /jobs/idp` nhận dict và xác thực signed service envelope (`ai-service/app/api/main.py:1225`).
2. `adapt_be_ai2_processing_request()` kiểm tra request, snapshot identities, member/relation map và tạo record (`ai-service/app/pipeline/ai1_snapshot_adapter.py:58`).
3. `SQLiteJobStore.create_or_get()` ghi job `QUEUED`, tenant/dossier/idempotency/attempt/nonce và fingerprint (`ai-service/app/tools/jobs.py:126`).
4. FastAPI `BackgroundTasks` gọi `_run_wire_job`; worker claim lease rồi chạy `run_idp()`.
5. `run_idp()` (`ai-service/app/pipeline/idp.py:39`) chạy handoff validation → relation graph → outline → bounded units → fact/table extraction → events → candidate comparison → contract context → citation validation → review items → index proposal.
6. `job_result_to_wire()` serialize kết quả thành `ai2.be.processing.result.v1`; job store lưu wire/result. `GET /jobs/{job_id}` đọc SQLite và kiểm tra service envelope (`main.py:1285`).

### 3.2 Workspace/demo lane

1. `POST /api/workspace/ai1-snapshot` hoặc `/api/workspace/ai1-result` gọi adapter tương ứng; không cho hai lane nhận nhầm nhau.
2. Session được lưu SQLite qua `save_session()` nhưng record hiện được nạp vào `InMemorySnapshotStore`.
3. `/extract` gọi synchronous `run_idp()` (`main.py:955`); `/reason` có thể tự extract; `/ask` phân loại câu hỏi và chạy reasoning (`main.py:1057`).
4. `/review` hiện nhận `confirm|correct|reject` cho candidate hiện tại, lưu overlay/revision/reason; không có command correlation/idempotency/audit actor/timestamp riêng.
5. `/publish` chỉ đặt cờ session sau các guard hiện có; authoritative publish production vẫn chưa thuộc runtime này.

### 3.3 FE/API

`frontend/src/app/App.tsx` chỉ giữ `sessionId`, query, answer và status; `VsfApiClient` có `getSession`, `ask`, `verifyCitation`. Không có upload client, review card, context form, impact preview, event subscription, reconnect hay replay UI.

## 4. Boundary hiện tại

| Boundary | Contract/guard hiện có | Khoảng trống liên quan Outcome Contract |
|---|---|---|
| AI1→AI2 | `ai1.snapshot.v1`, adapter và citation/provenance validation | `ocr.json` kiểu mới nhiều logical document chưa có canonical segmentation contract trong repo |
| BE→AI2 | `be.ai2.processing.request.v1`, signed envelope, tenant/dossier, idempotency, attempt | chưa có durable orchestration thật, correlation lifecycle và event API |
| AI2→BE | `ai2.be.processing.result.v1`, facts/findings/citations/index proposal/errors | chưa có task event/replay/partial checkpoint contract |
| AI2→LLM/tool | egress flag, budget, `ToolGateway`, grounding/citation | chưa có policy model cho HITL side-effect tool đầy đủ |
| AI2→FE | REST workspace/ask/review/publish | chưa có AG-UI/A2UI event boundary, SSE/WebSocket, state-version/reconnect |
| persistence | SQLite jobs/session + in-memory record | chưa chứng minh restart recovery, append-only audit, event replay, multi-user concurrency |

## 5. Đã hoạt động

- Snapshot schema/semantic adapter và compatibility lane có test phân biệt.
- Handoff fail-closed cho page/OCR/table/citation thiếu hoặc lỗi.
- Raw citation, page/table scope, source hash và validation status được giữ trong model/output.
- Fact extraction deterministic có normalization giới hạn; LLM normalization là optional và budget/egress-gated.
- Comparison có scope, `MATCH`/difference/amendment/not-comparable/insufficient-evidence và không chọn legal winner.
- Relation graph có `PARENT_OF`, `SAME_CLAUSE`, `REFERENCES`, `AMENDS`, `DEFINES`, `USES_DEFINED_TERM` với citation.
- Contract context có body/annex heuristic và context findings; đây là detection/review signal, chưa là authoritative legal precedence.
- Free-form query có bounded retrieval/grounded answer path.
- Job idempotency, nonce replay conflict, payload conflict, owner scope và lease claim đã có local tests.
- Eval framework có scorer, mutation, corpus, production replay và release verification artifacts.

## 6. Placeholder hoặc chỉ là groundwork

- `backend/src/contract_intelligence/main.py`: workspace route trả `NOT_IMPLEMENTED`; backend production persistence/orchestration chưa có.
- `plan_units()`/`UnitCheckpoint`: serializable shape cho tương lai, không phải checkpoint persistence/resume thực tế.
- `BackgroundTasks`: asynchronous HTTP response nhưng worker lifecycle vẫn gắn process.
- `SQLiteJobStore`: durable local wire state/lease, chưa thay thế queue/worker/audit production.
- Review overlay: có stale detection theo processing basis, chưa phải durable HITL state machine và chưa hỗ trợ reviewer assignment/multi-role.
- `docs/reviews/demo-board.html` có mô tả SSE/HITL nhưng không được dùng làm bằng chứng runtime; code search không tìm thấy endpoint SSE/WebSocket.
- `ai1.snapshot.v1` là canonical contract trong repo, nhưng input thực tế `ocr.json` mới theo Outcome Contract vẫn cần nghiên cứu mapping/segmentation riêng trước khi xem là tương thích đầy đủ.

## 7. Test coverage và thiếu coverage

Repository hiện có 33 test files và khoảng 229 test functions trong `ai-service/tests/`; ngoài ra có eval tests dưới `evals/`. Các nhóm đã có test đáng kể: adapter, schema semantics, citation, table continuity, fact/compare, query, API review stale, job store, service envelope, package API, security scope và release replay.

Các nhóm chưa có bằng chứng runtime đủ cho Outcome Contract:

- state transition durable: `RUNNING → WAITING_FOR_HUMAN → RESUMED → COMPLETED`;
- context request/response versioning và missing/invalid user response;
- approval/rejection race giữa nhiều actor;
- command correlation/idempotency cho từng HITL action;
- append-only audit với actor/timestamp/reason;
- impact preview trước recompute và dependency-level stale graph;
- event envelope sequence/order/duplicate/replay/resume;
- SSE disconnect/reconnect/heartbeat hoặc WebSocket reconnect/backpressure;
- server restart/crash recovery với task tiếp tục đúng checkpoint;
- timeout/expiration/cancellation của human gate;
- UI state reconciliation với durable reasoning state;
- ADK/A2A interoperability/authentication/task handoff;
- AG-UI/A2UI conformance;
- long-running load/latency/recovery metrics.

## 8. Fact, inference và thiếu dữ liệu

### Fact đã kiểm chứng từ code

- AI2 có pipeline và wire contracts nêu ở trên.
- `relation_policy=INDEPENDENT` là giới hạn của OCR-lab batch/package v1.
- Backend skeleton chưa có production workspace implementation.
- Không có code SSE/WebSocket/AG-UI/A2UI/ADK/A2A trong các vùng AI2 đã kiểm tra.
- Job/session persistence hiện là SQLite local; record store chính là in-memory.

### Inference cần dùng làm giả thuyết nghiên cứu

- Với interaction chủ yếu tại checkpoint, hybrid HTTP command + một chiều event stream có thể phù hợp hơn WebSocket; đây chưa phải quyết định cuối.
- ADK có thể là lớp orchestration nội bộ và A2A chỉ cần khi có agent boundary độc lập; cần kiểm tra official capability trước khi ghi vào plan.
- `ocr.json` nên được đưa qua segmentation/versioning trước khi relation-aware comparison; cần xác nhận bằng format mới và ground truth.

### Thiếu dữ liệu

- Contract schema chính thức cho `ocr.json` mới và quy tắc logical-document segmentation.
- Backend queue/worker/DB/audit/RBAC production thật.
- FE review wire contract và hạ tầng proxy/load balancer.
- Chính sách timeout/retention/approval nhiều người.
- Ground truth nghiệp vụ được reviewer phê duyệt.

## 9. Artifact và validation

- `docs/code-standards.md` và `docs/system-architecture.md` đã được đồng bộ theo code hiện tại, mỗi file dưới 800 dòng.
- Standards scaffold check: cả hai file đều `conform` với section-set chuẩn.
- Chưa có code implementation nào được sửa trong phase này; chỉ cập nhật tài liệu và báo cáo.
