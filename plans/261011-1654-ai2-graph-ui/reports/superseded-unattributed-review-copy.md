# Red-team review — AI2 graph UI plan

**Artifact under review:** `plans/261011-1654-ai2-graph-ui/plan.md` và bốn phase P1–P4.  
**Phạm vi:** authorization/snapshot, telemetry trung thực, accessibility/performance, scope và phase gates. Chỉ review, không sửa plan hoặc code.  
**Lenses:** Security; Operations/observability; Performance/accessibility. Scenario sweep tập trung vào ACL, lỗi giữa chừng, dữ liệu rỗng/truncated, snapshot race, mobile/keyboard và lifecycle retry/restart.

## Findings

| ID | Severity | Evidence | Finding | Cheapest fix |
|---|---|---|---|---|
| RT-01 | High · suspected `[ASSUMED]` | `phases/phase-2-backend-facade.md:16,43`; `research/graph-ui-research.md:77-79`; `backend/src/contract_intelligence/shared/acl.py:124-132`; `ai-service/app/contracts/models.py:216-223` | DTO có excerpt/citation spans nhưng phase chỉ yêu cầu dossier ACL trước lời gọi AI2. Một share chỉ cho `query` có thể nhận trích đoạn khi không có quyền `citation_read`. | Đưa `CITATION_READ` vào kiểm tra trước khi trả nội dung trích dẫn; nếu thiếu quyền, chỉ trả ID tham chiếu không chứa text và để endpoint citation có ACL riêng. Thêm test grant giới hạn `actions=["query"]`. |
| RT-02 | High · proven source path | `ai-service/app/tools/jobs.py:584-598,600-611`; `phases/phase-1-ai2-graph-and-trace.md:21-23,45-48,68-70` | Lỗi ghi operation/pair graph bị rollback ở savepoint nhưng job vẫn `SUCCEEDED`. Plan chưa yêu cầu lưu kết quả ghi graph để phân biệt “0 quan hệ thật” với “ghi graph thất bại”; read model có thể không có tín hiệu để chọn `PARTIAL/UNAVAILABLE`. | Persist kết quả ghi riêng cho operation/pair (success/count/digest hoặc safe error code) trong cùng completion transaction; chỉ `READY`/empty-ready khi xác minh được cả nhánh xử lý lẫn persistence. Test lỗi store và zero-edge hợp lệ. |
| RT-03 | Medium · suspected `[ASSUMED]` | `phases/phase-2-backend-facade.md:16,40-45`; `backend/src/contract_intelligence/contract/interfaces/api/routers/contract_router.py:1427-1441` | ACL chỉ được nêu trước lời gọi AI2. Quyền share có thể bị thu hồi trong lúc service read đang chờ; route hiện có đã chạy ACL lần hai trước khi trả citations. | Re-read dossier và kiểm tra ACL/snapshot lần hai sau AI2, trước khi serialize DTO; test bằng adapter bị chặn, thu hồi grant rồi mới trả response. |
| RT-04 | Medium · suspected `[ASSUMED]` | `phases/phase-2-backend-facade.md:40-44`; `phases/phase-3-accessible-views.md:22-24,42-45`; `plan.md:62` | API bị giới hạn và phân trang, nhưng P3 không giao việc tải cursor tiếp theo hoặc điều khiển trang cho list. Với graph nhiều hơn một page, “list là fallback đầy đủ” có thể chỉ hiển thị page đầu. | Chốt paging end-to-end: cursor gắn `job_id` + digest, UI list có next/previous hoặc load thêm, và không gọi kết quả hoàn chỉnh khi còn trang. Thêm fixture nhiều hơn hai page và kiểm tra toàn bộ edges/citations. |
| RT-05 | Medium · suspected `[ASSUMED]` | `phases/phase-1-ai2-graph-and-trace.md:22-25,43-48,68-70`; `ai-service/app/api/main.py:262-274,291-319,343-363` | Trace theo stage chưa có yêu cầu ghi bền vững hoặc cách tạo `trace-incomplete` khi worker chết. Khi tiến trình chết giữa stage, sweeper có thể đóng job thành `FAILED`, nhưng không thể tự khôi phục chính xác stage đang dở nếu chỉ có trace trong bộ nhớ. | Chỉ định nguồn trace bền vững và quy tắc crash finalization; sweeper ghi dấu `incomplete/unknown` cho stage đang mở, không suy diễn stage thất bại. Test kill/restart giữa operation và pair stage. |

## Chi tiết đường lỗi có hậu quả khó đảo ngược

### RT-01 — Nội dung citation vượt quyền share

`research/graph-ui-research.md:77-79` đề xuất node có `excerpt` và edge có citation refs/spans. AI2 `Citation.text_span` là nội dung trích dẫn (`ai-service/app/contracts/models.py:216-223`). ACL cho phép grant giới hạn theo danh sách action (`backend/src/contract_intelligence/shared/acl.py:124-132`), còn route search hiện chạy kiểm tra `CITATION_READ` lần hai và lọc citation trước khi trả kết quả (`backend/src/contract_intelligence/contract/interfaces/api/routers/contract_router.py:1427-1441`). P2 chỉ ghi authorize bằng dossier ACL trước khi gọi AI2 (`phases/phase-2-backend-facade.md:16,43`).

**Trigger cụ thể:** dossier được share với grant `actions=["query"]`; người nhận gọi graph endpoint; DTO trả excerpt hoặc text span. Nếu endpoint chỉ dùng kiểm tra `QUERY`, response chứa nội dung mà grant không cấp `CITATION_READ`. Đây là `[ASSUMED]` vì route/DTO chưa được implement và plan có thể chọn lọc nội dung an toàn.

**Điều kiện chấp nhận:** hoặc graph endpoint kiểm `CITATION_READ` trước khi trả excerpts/spans, hoặc public DTO chỉ chứa opaque citation IDs/geometry refs và citation detail luôn đi qua endpoint có kiểm tra quyền riêng. Cần kiểm tra cả grant action-restricted và role được chia sẻ.

### RT-02 — Lỗi persistence bị hiểu như “không có quan hệ”

`complete_with_snapshot()` gọi ghi graph trong savepoint. Khi write lỗi, `_replace_contract_edges()` bắt exception, ghi log rồi tiếp tục; cặp quan hệ cũng bắt lỗi tương tự (`ai-service/app/tools/jobs.py:584-611`). Do đó lỗi này không nhất thiết làm job thành `FAILED`. P1 yêu cầu status phân biệt storage unavailable/empty và `READY` đúng snapshot, nhưng chưa yêu cầu một receipt cho việc ghi từng graph store (`phases/phase-1-ai2-graph-and-trace.md:21-23,45-48,68-70`).

**Reproduction:** trong completion của một job đáng lẽ có edges, làm `replace_contract_edges()` ném lỗi (ví dụ lỗi constraint/DB trong transaction). Job vẫn có thể hoàn tất `SUCCEEDED`; savepoint rollback giữ dữ liệu trước đó hoặc để thiếu rows. Nếu read API chỉ nhìn DB đang tồn tại và số rows bằng 0, nó không phân biệt được zero-edge hợp lệ với lần ghi graph vừa thất bại.

**Điều kiện chấp nhận:** persist `graph_persist_status` và số lượng edge đã commit gắn cùng `job_id`/digest; khi store write fail, API phải trả `PARTIAL`/`UNAVAILABLE`/`FAILED` theo contract đã chọn, tuyệt đối không `READY` rỗng.

## Rủi ro còn lại và điều kiện chấp nhận

- RT-03 chỉ được chấp nhận nếu endpoint cố ý chấp nhận quyết định ACL tại thời điểm bắt đầu request. Do hệ thống đã kiểm tra quyền citations lần hai sau lời gọi AI2 (`contract_router.py:1427-1441`), cùng nguyên tắc đó nên áp dụng cho graph response có excerpts/citation data.
- RT-04 có thể chấp nhận nếu sản phẩm giới hạn rõ số quan hệ hiển thị và hiển thị “còn dữ liệu”/trang tiếp theo. Hiện P2 nói có continuation, trong khi tiêu chí P3 mô tả list là fallback đầy đủ; hai điều này cần được nối thành một hành vi UI đo được.
- RT-05 có thể chấp nhận nếu UI luôn hiển thị `trace-incomplete/unknown` khi job bị sweeper đóng và không gán trạng thái thành công/thất bại cho stage chưa có terminal record.
- Canvas có fallback danh sách, thao tác bàn phím và manual review; giữ các cổng đó. Cần fixture dày và dữ liệu đa phụ lục đại diện trước khi chọn renderer hoặc đặt budget.

## Verdict

**CAUTION — chưa cook P1/P2 cho tới khi chốt hai ràng buộc High:** (1) citation excerpt/spans phải tôn trọng `CITATION_READ`; (2) trạng thái graph phải phản ánh write failure độc lập với trạng thái job. Các concern còn lại cần thêm acceptance/test cụ thể trước khi P3/P4 hoàn tất.
