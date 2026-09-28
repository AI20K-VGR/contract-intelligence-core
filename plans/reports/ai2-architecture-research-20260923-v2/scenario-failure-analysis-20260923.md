# AI2 scenario và failure analysis

Ngày: 2026-09-23  
Phương pháp: phân tích theo 15 chiều của hs:scenario: actor/input, trigger, state, evidence, authorization, concurrency, transport, persistence, retry, timeout, recovery, observability, privacy, UX và test oracle.

## 1. Invariants áp dụng cho mọi scenario

1. Raw AI1 snapshot không bị sửa.
2. Mọi output có `input_snapshot_id`, `segmentation_version`, `generation_id`, evidence/citation refs và state version.
3. FE connection không phải truth source; snapshot/event store mới là truth source.
4. Command HITL cần authenticated actor, authorization, `correlation_id`, `idempotency_key`, `expected_state_version`.
5. Command duplicate trả kết quả idempotent; không tạo thêm approval, generation, side effect hoặc event semantic mới.
6. Event có `event_id`, sequence, state version và schema version; duplicate/out-of-order phải được xử lý rõ.
7. Kết quả stale không được publish như kết quả hiện hành.
8. User context là annotation, không thay citation.
9. Không stream chain-of-thought hoặc raw sensitive content ngoài scope actor.
10. Mọi timeout, expiration, cancellation, rejection và conflict đều có audit record.

## 2. Scenario bắt buộc

| ID | Scenario/trigger | Expected state/behavior | Failure không được xảy ra | Test oracle |
|---|---|---|---|---|
| F01 | User không phản hồi checkpoint | Giữ `WAITING_FOR_HUMAN`; reminder tùy policy; sau TTL chuyển `EXPIRED` hoặc policy đã duyệt | Auto-approve, mất pending request, worker busy-loop | state + audit không đổi ngoài timeout event |
| F02 | User trả lời thiếu context | Validate schema; trả `422 CONTEXT_INCOMPLETE` hoặc tạo request bổ sung; giữ checkpoint | Resume bằng context rỗng/không đủ, suy diễn phần thiếu | không có generation mới; request mới có missing fields |
| F03 | User reject proposal | Lưu actor/reason; chuyển branch `NEEDS_REVIEW`/`REJECTED` theo policy; không recompute âm thầm | Coi reject như approve hoặc xóa evidence | audit có decision và terminal/intermediate state đúng |
| F04 | User sửa proposal/boundary/fact | Tạo edit proposal + impact preview; chỉ recompute sau confirm; generation mới | Sửa raw AI1, publish output cũ, mất citation | stale set đúng; old generation immutable |
| F05 | Agent timeout khi đang chạy | Lease hết hạn/recovery policy; state `FAILED`/`WAITING` tùy checkpoint; retry có giới hạn | Hai worker cùng commit, mất task, retry vô hạn | fencing/attempt/audit và kết quả deterministic |
| F06 | A2A task mất kết nối | Notification mất không làm mất task; pull status/replay bằng task/context ID | Coi disconnect là task failure hoặc tạo task duplicate | task store vẫn có status/artifact; retry callback dedup |
| F07 | Client reconnect | FE gửi last acknowledged sequence; server replay hoặc snapshot fallback | State UI lệch state server, action stale được submit | reducer khôi phục cùng state hash |
| F08 | SSE disconnect | EventSource reconnect; server auth lại; replay từ sequence; heartbeat không đổi task state | Mất `HITL_REQUESTED`/`RUN_COMPLETED`, duplicate card | disconnect injection và sequence continuity |
| F09 | WebSocket reconnect (nếu được bật sau này) | Re-authenticate, resync snapshot/replay; không coi socket session là task | Reconnect tạo run mới hoặc bypass authorization | same run/generation, no duplicate command |
| F10 | Duplicate event | Consumer dedup bằng event ID/sequence/digest | Hai approval card hoặc hai recompute | apply count = 1; duplicate metric tăng |
| F11 | Event sai thứ tự/gap | Buffer bounded; nếu gap không lấp được thì snapshot; không apply delta sai base | FE ghép state sai hoặc đánh mất warning | event sequence/gap path deterministic |
| F12 | Server restart | Load durable run/checkpoint/event cursor; worker lease recovery | Run biến mất, state về `CREATED`, side effect lặp | restart test giữ run/generation/state version |
| F13 | Task resume sau crash | Resume từ snapshot + event cursor; rerun chỉ phần an toàn/idempotent | Lặp external side effect hoặc thiếu artifact | side-effect spy count và artifact digest |
| F14 | Task bị cancel | Check auth; transition `CANCELLING`/`CANCELLED`; stop future work; compensation nếu cần | Cancel nhầm tenant/run hoặc báo cancelled khi side effect vẫn chạy | cancellation audit + worker fence |
| F15 | Approval hết hạn | Reject command cũ; tạo request mới nếu policy cho phép | Approval stale vượt gate | `409/410` rõ, không generation mới |
| F16 | Hai user approve/reject đồng thời | CAS một winner; loser nhận conflict; cả hai audit | Last-write-wins im lặng, mixed decision | exactly one applied transition |
| F17 | Reasoning tạo kết quả mâu thuẫn | Gắn conflict/warning, giữ citations từng claim; yêu cầu reviewer | Chọn một claim không nói lý do | conflict finding + no auto publish nếu policy cấm |
| F18 | Downstream service unavailable | Retry bounded/backoff; circuit/failure state; preserve checkpoint | Nuốt lỗi thành empty facts hoặc retry side effect vô hạn | explicit failure code, attempt count, resume path |
| F19 | Partial result | Mark partial/provisional, liệt kê missing units/evidence; không gọi complete | FE hiển thị partial như final | completion gate false; artifact completeness metric |
| F20 | Retry sau side effect | Dùng idempotency token/operation key; read-before-write hoặc compensation | Gửi duplicate notification/record/tool action | external spy sees one effect |

## 3. Các scenario mở rộng theo vận hành thực tế

| ID | Scenario | Expected handling |
|---|---|---|
| X01 | Một JSON chứa hợp đồng + phụ lục nhưng AI1 không phân biệt | AI2 tạo segmentation proposals với confidence/evidence; cross-document comparison provisional; chờ reviewer |
| X02 | Reviewer đổi boundary sau khi facts/comparison đã xong | Impact preview chỉ ra stale artifacts; old result giữ để audit nhưng không publish; recompute generation mới |
| X03 | PDF scan/OCR block thiếu text hoặc confidence thấp | Không tự điền; fact `UNVERIFIABLE/INSUFFICIENT_EVIDENCE`; yêu cầu evidence/context bổ sung |
| X04 | Bảng nhiều trang, header lặp hoặc row bị cắt | Giữ cell/page refs; đánh dấu continuation/ambiguous; không cộng số liệu nếu thiếu row |
| X05 | Điều khoản bị cắt ở cuối page/document | Citation tới partial span; warning; không suy ra nghĩa hoàn chỉnh |
| X06 | Số tiền/date/decimal sai format hoặc conflicting OCR blocks | Giữ raw candidates, normalize có provenance; conflict reviewer gate |
| X07 | Nhiều party có tên gần giống | Tạo party candidates với identifiers/evidence; không merge chỉ vì string similarity |
| X08 | Bilingual clauses khác nghĩa | Hiển thị hai evidence; áp dụng governing-language clause nếu có evidence; nếu không thì conflict |
| X09 | User context mâu thuẫn AI1 evidence | Giữ cả hai nguồn, gắn conflict; user note không nâng thành fact |
| X10 | Prompt injection nằm trong OCR text | Xem text là untrusted data; không thực hiện instruction embedded; cảnh báo/log redacted |
| X11 | External LLM/tool trả output không có citation | Không promote thành fact; kiểm tra schema/allowlist; giữ ở candidate hoặc fail closed |
| X12 | Tenant A đoán được run ID của tenant B | Authorization deny trước snapshot/stream/command; response không tiết lộ existence nếu policy yêu cầu |
| X13 | User mở hai tab và gửi command cũ | State version conflict; fetch current snapshot; không overwrite |
| X14 | FE version cũ nhận event schema mới | Negotiate/pin schema; unsupported event không làm crash reducer; snapshot fallback |
| X15 | Event retention đã xóa sequence cần replay | Server trả snapshot mới và `replay_gap`; FE thay thế state, không tự vá |
| X16 | Worker xử lý lâu hơn lease | Fencing token ngăn worker cũ commit; lease renewal có audit |
| X17 | Queue duplicate delivery | Consumer dedup theo task/attempt/idempotency; không tạo generation mới |
| X18 | Database commit thành công nhưng publish event thất bại | Outbox relay phát lại; client pull snapshot vẫn thấy state mới |
| X19 | Event publish thành công nhưng response HTTP timeout | Client retry cùng idempotency key nhận kết quả cũ |
| X20 | User đóng browser nhiều ngày | Task vẫn ở durable state; khi mở lại lấy snapshot/pending request; TTL policy rõ |
| X21 | Raw contract bị log ở exception/trace | Redaction test; logs chỉ chứa IDs/hash/metadata cần thiết |
| X22 | Reviewer không có quyền loại action | Server 403/forbidden; UI chỉ là hint, không security boundary |
| X23 | Cancellation đến trong lúc recompute commit | Atomic state rule xác định winner; không báo cancelled nếu commit đã accepted; audit causation |
| X24 | External tool side effect không hỗ trợ idempotency | Tool bị cấm trước approval hoặc phải qua manual recovery/compensation; không retry mù |
| X25 | Snapshot corrupt hoặc event digest mismatch | Fail closed; không resume từ dữ liệu không toàn vẹn; alert và recovery artifact |

## 4. State/event sequence cho case boundary edit

```text
RUNNING
  -> SEGMENTATION_PROPOSED (generation G1)
  -> HITL_REQUESTED(checkpoint C1, state_version V1)
  -> REVIEW_APPLIED(edit proposal P1, V2)
  -> IMPACT_PREVIEW_READY(stale={F*,R*,C*}, V3)
  -> HITL_REQUESTED(confirm impact, V3)
  -> RECOMPUTE_STARTED(generation G2, V4)
  -> FACTS_READY / COMPARISON_READY(G2)
  -> RUN_COMPLETED(G2)
```

`G1` vẫn được lưu để audit nhưng mọi artifact phụ thuộc boundary cũ phải có `stale=true`. Nếu reviewer chỉ sửa annotation không ảnh hưởng evidence basis, plan có thể giữ artifact; rule này phải được biểu diễn bằng dependency graph, không bằng heuristic UI.

## 5. Failure-mode register tóm tắt

| Risk | Likelihood hiện tại | Impact | Detection | Mitigation/owner |
|---|---:|---:|---|---|
| Mất pending approval | Cao vì chưa có durable HITL | Cao | audit/state reconciliation | BE domain store + outbox |
| Duplicate side effect | Trung bình | Rất cao | idempotency metrics/spy | BE/workflow owner |
| UI lệch reasoning state | Cao khi reconnect | Cao | state hash/version mismatch | FE reducer + snapshot API |
| Cross-tenant read/command | Chưa đo được | Rất cao | authz tests/audit | BE security owner |
| Citation bị stale sau edit | Cao | Cao | generation dependency check | AI2 domain owner |
| Event gap không được phát hiện | Trung bình | Cao | sequence gap metric | event/replay owner |
| External LLM prompt injection | Có thể xảy ra | Cao | red-team corpus | AI2/security owner |
| SSE operational timeout | Chưa đo được | Trung bình/cao | disconnect/reconnect test | BE/infra owner |
| A2UI arbitrary action | Thấp nếu disabled | Cao | catalog/action validation | FE + BE security |
| Ground truth sai | Cao hiện tại | Cao | adjudication/disagreement | product/legal reviewer |

## 6. Test families cần có sau research

- Deterministic reducer/state-transition unit tests.
- Command schema/auth/idempotency contract tests.
- Event envelope ordering, duplicate, gap, replay and digest tests.
- Crash/restart/recovery integration tests.
- Concurrent approval/cancel/timeout race tests.
- SSE disconnect/reconnect and snapshot fallback tests.
- WebSocket tests chỉ khi phương án được bật.
- Tenant/role/retention/redaction security tests.
- Segmentation/fact/citation/relation stale propagation tests.
- Long-running soak/load test với worker lease, queue duplicate và downstream outage.
