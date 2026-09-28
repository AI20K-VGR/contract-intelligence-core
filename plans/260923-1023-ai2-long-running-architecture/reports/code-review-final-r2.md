# Code review final R2 — AI2 long-running architecture

## Phạm vi và phương pháp

Review chỉ đọc, không sửa code, không commit/push. Phạm vi chính:

- `ai-service/app/security/policy.py`
- `ai-service/app/transport/events.py`
- `ai-service/app/ops/readiness.py`
- `ai-service/tests/test_p5_api_security.py`
- `ai-service/tests/test_p6_event_ui_convergence.py`
- `ai-service/tests/test_p9_production_readiness.py`
- Các boundary P0–P9 liên quan khi cần đối chiếu contract và tenant/idempotency/replay.

Đã chạy trong workspace-local temp:

- `ai-service/.venv/Scripts/python.exe -m pytest -q tests/test_p5_api_security.py tests/test_p6_event_ui_convergence.py tests/test_p9_production_readiness.py --basetemp=.\tmp\review-r2\pytest-focused` → `25 passed, 1 warning`.
- `ai-service/.venv/Scripts/python.exe -m pytest -q tests/test_p9_production_readiness.py tests/test_p8_migration_boundary.py tests/test_p8_migration_parity.py tests/test_p6_event_ui_convergence.py tests/test_p5_api_security.py tests/test_p4_execution_adapters.py tests/test_p3_persistence_events.py tests/test_p2_hitl_state.py tests/test_p1_canonical_model.py tests/test_p0_contract_baseline.py --basetemp=.\tmp\review-r2\pytest-p0-p9` → `79 passed, 1 warning`.
- Warning duy nhất là `PytestCacheWarning` do `.pytest_cache` bị Windows ACL chặn; không có test failure.

Probe runtime độc lập đã tái hiện các kết quả nêu dưới đây. Security-scan harness không chạy được qua `harness/bin/hs-run` vì wrapper Windows lỗi parse; đây là giới hạn của công cụ, không phải bằng chứng an toàn.

## Trạng thái findings round 1

Các finding round 1 sau đã được xử lý và có regression test tương ứng trong bản hiện tại:

- RequestContext role override: `validate_request_context()` kiểm tra role request khớp `principal.role` tại `ai-service/app/security/policy.py:144-153`; test tại `ai-service/tests/test_p5_api_security.py:164-178`.
- Approved unknown tool fail-open: `ToolPolicy.authorize()` chỉ cho phép tool thuộc `READ_TOOLS` hoặc `SIDE_EFFECT_TOOLS` tại `ai-service/app/security/policy.py:387-395`; test tại `ai-service/tests/test_p5_api_security.py:114-124`.
- AG-UI exact-key-only sanitizer: sanitizer đã normalize key dạng case/camel/punctuation tại `ai-service/app/transport/events.py:37-45`; test nested/copy variants tại `ai-service/tests/test_p6_event_ui_convergence.py:28-73`.
- Unauthenticated SSE leak/command echo: các method SSE fail closed trước authorization tại `ai-service/app/transport/events.py:169-194`; test tại `ai-service/tests/test_p6_event_ui_convergence.py:76-101`.
- Blank readiness references: `_refs_configured()` reject blank/non-string entries tại `ai-service/app/ops/readiness.py:26-28`; test tại `ai-service/tests/test_p9_production_readiness.py:215-232`.
- Retention comparison reversed: hiện đã dùng `retention_days >= recovery_window_days` tại `ai-service/app/ops/readiness.py:193-197`; test bất đẳng thức tại `ai-service/tests/test_p9_production_readiness.py:96-117`.

## Findings còn mở

### Critical — policy scope có thể bị caller ghi đè

Tại `ai-service/app/security/policy.py:289-302`, `SecurityPolicy.authorize()` lấy `tenant_id`/`dossier_id` từ keyword mỗi lần gọi, thay vì giữ cứng scope đã cấu hình ở constructor. Probe:

```text
SecurityPolicy(tenant_id="tenant-a", dossier_id="dossier-a").authorize(
  AuthzRequest(..., tenant_id="tenant-b", dossier_id="dossier-b"),
  tenant_id="tenant-b", dossier_id="dossier-b"
).allowed == True
```

Như vậy caller có thể biến policy đã bind `tenant-a/dossier-a` thành policy cho tenant/dossier khác. Đây là bypass trực tiếp tenant isolation/cross-dossier authorization. Không có test phủ trường hợp policy-bound scope bị override.

Fix cần thiết: không cho phép public override vượt qua scope constructor; nếu cần dynamic scope thì tạo policy/context mới sau khi xác thực principal và ràng buộc scope, đồng thời test override luôn bị deny.

### Critical — `SecurityPolicy.authorize()` tin role do request cung cấp

Tại `ai-service/app/security/policy.py:291-308`, authorization lấy `role = _normalise(request.role)` và cấp quyền theo role đó; `AuthzRequest` không chứa principal/nguồn role đã xác thực. Probe với `actor_id="reader-1"`, `role="admin"`, `action="hitl.command"` trả `allowed == True`.

Round 1 đã sửa đường `RequestContext` override, nhưng đường `SecurityPolicy.authorize(AuthzRequest)` vẫn cho phép caller tự xưng admin. P5 acceptance yêu cầu role authorization ở server; test hiện tại còn chủ động assert mọi role hợp lệ được phép command tại `test_p5_api_security.py:47-56`, nhưng không kiểm tra actor-role binding.

Fix cần thiết: nhận principal đã xác thực từ boundary và không nhận role có thể do request body/header tự khai; hoặc buộc `AuthzRequest` qua context validator có principal trước khi authorize. Thêm negative test actor read-only tự gửi role admin.

### Important — AG-UI mapper không enforce scope và `validate_scope()` kiểm tra event chưa đủ

`map_to_agui()` tại `ai-service/app/transport/events.py:127-143` chỉ kiểm tra event type và payload; nó không nhận `expected tenant/run` và không gọi `validate_scope()`. Probe mapping một `EventEnvelope` của `tenant-b` vẫn trả event có `tenant_id="tenant-b"`. Đồng thời `validate_scope()` tại `ai-service/app/transport/events.py:60-77` trả `True` cho mapping chỉ có `tenant_id`, `run_id`, `event_id`, `sequence`, dù thiếu event type, schema, correlation, state version/hash và payload.

Nếu caller dùng mapper/guard này làm public replay/stream boundary mà quên guard riêng, event ngoài scope hoặc event malformed có thể đi tiếp. Hiện không có production caller nào ghép hai guard này; đó là lý do mức này là Important thay vì khẳng định đã có HTTP data leak đang active.

Fix cần thiết: đưa expected scope vào mapper/transport boundary và reject event không đủ canonical envelope; test cross-tenant, cross-run, missing schema/payload/state fields.

### Important — SSE chỉ bind tenant, không bind resource/run với principal đã xác thực

`SseSession.authorize()` tại `ai-service/app/transport/events.py:160-167` chỉ so sánh tenant. Sau khi authorize tenant-a, session được khởi tạo với bất kỳ `run_id` nào và `heartbeat()`/`reconnect_cursor()` trả run/cursor/hash tại `ai-service/app/transport/events.py:169-184`. Probe `SseSession("tenant-a", "run-other").authorize("tenant-a")` trả `True` và heartbeat chứa `run-other`.

P6 artifact ghi “tenant-bound”, nhưng P5/plan contract yêu cầu replay/stream server-side authorize theo tenant/dossier/resource. Nếu run id do client route cung cấp hoặc đoán được, helper này không đủ để ngăn cross-dossier/run metadata exposure.

Fix cần thiết: bind session vào resource scope/principal đã xác thực và kiểm tra run thuộc dossier/tenant trước khi tạo session; không coi tenant match đơn độc là authorization.

### Important — readiness PASS khi thiếu toàn bộ operational evidence

`evaluate_readiness()` nhận `cases: Iterable[OperationalCase] = ()` tại `ai-service/app/ops/readiness.py:161-166` và không có danh sách case bắt buộc. Probe với config đầy đủ nhưng không truyền `cases` trả `passed == True`. Vì vậy một caller có thể phát readiness PASS mà không cung cấp chaos restart, duplicate/outage, stream saturation, retention-gap, incident-audit hoặc security-regression evidence mà P9 contract/plan yêu cầu.

Fix cần thiết: khai báo required case IDs/categories và fail closed khi thiếu case, hoặc tách rõ configuration-only result khỏi production-readiness PASS; thêm test thiếu từng case bắt buộc.

### Important — approval/tool boundary vẫn tin cờ `approved` từ caller

Tại `ai-service/app/security/policy.py:387-395`, mọi side-effect tool đã biết được phép nếu caller truyền `approved=True`; không có principal, approval record, actor, tenant hay command binding trong quyết định. Artifact P5 cũng ghi limitation này: approval là caller signal, chưa phải durable workflow approval ledger.

Đây chưa phải route đang public vì module chưa nối HTTP, nhưng không đáp ứng đầy đủ acceptance “server authorization” nếu caller truyền dữ liệu không đáng tin vào primitive này.

Fix cần thiết: approval phải là capability/record đã xác thực và bind tenant/dossier/actor/command digest; boolean caller input không được tự nâng quyền.

## Các điểm đã kiểm tra nhưng không coi là finding mới

- Unknown tool dù nằm trong `approved_tools` đã fail closed.
- Retention shortfall và blank artifact refs đã có regression test.
- P3 durable store vẫn enforce tenant theo run, monotonic sequence, digest conflict, replay gap và lease fencing trong các test P0–P9 targeted.
- SSE unauthenticated helper không trả tenant/run/cursor/hash và không echo command.
- Production HTTP/SSE route chưa được nối là limitation đã ghi trong P6 artifact, không tự nâng thành code finding trong phạm vi helper này.

## Verdict

**BLOCKED**. Còn 2 Critical và 4 Important chưa được xử lý trong các boundary authorization/tenant isolation/readiness. Vì vậy không được chọn `PASS` hoặc `PASS_WITH_RISK`; test xanh chỉ chứng minh các case hiện có, không phủ các bypass đã tái hiện.
