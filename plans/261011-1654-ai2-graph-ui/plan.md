---
id: 261011-1654-ai2-graph-ui
title: "Trực quan hóa Contract Graph AI2 trên giao diện"
description: "Hiển thị riêng dấu vết xử lý AI2 và quan hệ điều khoản, có ACL citation, trạng thái lưu graph và phân trang trung thực."
status: completed
priority: P2
effort: "5 pha tuần tự; phạm vi AI2, Backend và frontend; sizing chờ người dùng xác nhận"
mode: hard
tdd: true
branch: feature/ai2-contract-graph
created: 2026-10-11
author: user:dungskbg2004@gmail.com
decisions: []
phases:
  - phases/phase-1-ai2-graph-persistence.md
  - phases/phase-2-ai2-durable-processing-trace.md
  - phases/phase-3-backend-secure-paged-api.md
  - phases/phase-4-accessible-views.md
  - phases/phase-5-canvas-integration.md
harness_version: 7.0.0
harness_kit_digest: 3d7949cb37672c0adc9085ddeddad1b8ac1617ee19b3ab4d9179877708328595
harness_schema_version: 1.0
---

# Kế hoạch: trực quan hóa graph và luồng xử lý AI2

## Mục tiêu

Thêm hai góc nhìn riêng trên trang hồ sơ: **Luồng xử lý AI2** cho biết stage nào thực sự chạy, bị bỏ qua, lỗi hoặc bị gián đoạn; **Quan hệ điều khoản** cho biết điều khoản nào được AI2 đề xuất liên hệ và dẫn tới bằng chứng. Giữ nguyên outline/document/tree OCR hiện có tại frontend/src/pages/DossierStructurePage.tsx:936-959.

Backend tiếp tục sở hữu public API và ACL; frontend không truy cập AI2 trực tiếp. Graph operation và pair relation là hai loại cạnh khác nhau (ai-service/app/contracts/contract_graph.py:43-69,79-97). Chúng là đề xuất cần review, không phải kết luận pháp lý.

## Đề xuất phạm vi đang chờ người dùng xác nhận

- **HOLD:** chỉ thêm read API, graph/trace projection và UI. Không chỉnh candidate generation/classifier/prompt/threshold; không bật AI2_CONTRACT_GRAPH_ENABLED hoặc AI2_CONTRACT_GRAPH_PAIRS_ENABLED.
- Dùng Backend ACL action CITATION_READ cho mọi graph response. Graph DTO không chứa trích đoạn, text_span, new_text, scope_text, prompt hay toàn văn. Citation chỉ là tham chiếu opaque; nội dung bằng chứng mở qua endpoint Backend có ACL citation.
- Phân biệt riêng kết quả pipeline với receipt ghi graph. Job SUCCEEDED không chứng minh graph lưu thành công: hai ghi graph hiện được cô lập bằng savepoint và lỗi được bắt/log riêng (ai-service/app/tools/jobs.py:575-611).
- Phân trang cursor-bound theo job và snapshot. Danh sách chỉ được gọi đầy đủ sau khi tải hết các trang; canvas có thể là trang/đồ thị giới hạn và phải báo rõ.
- Giữ runtime flags ở trạng thái hiện hành; UI mới mặc định tắt.

## Luồng dữ liệu

AI2 job + source snapshot → operation/pair builders → ghi graph trong store Postgres và ghi receipt theo từng store → endpoint nội bộ có service signature → Backend kiểm tra tenant/dossier/job/digest và ACL → DTO chỉ gồm node/edge metadata + citation refs + page cursor → frontend gọi Backend → list/timeline/canvas.

Luồng trace là append-only và tách khỏi events[]: events[] hiện là event nghiệp vụ trích xuất (ai-service/app/contracts/wire.py:294-297), không phải nhật ký stage. Worker ghi mốc stage vào durable trace store; route đọc trace đối chiếu job status/lease. Trace thiếu, worker chết giữa stage hoặc store lỗi phải hiện INCOMPLETE_UNKNOWN/TRACE_UNAVAILABLE, không tự suy ra thành công.

### Điều kiện trạng thái graph

Mỗi loại graph có trạng thái processing và persistence riêng:

- READY với 0 cạnh chỉ hợp lệ khi đúng stage đã chạy và hoàn tất, snapshot khớp, receipt ghi đúng store là COMMITTED với row_count=0.
- PERSIST_FAILED/PARTIAL khi builder thành công nhưng ghi store lỗi; status job vẫn có thể SUCCEEDED.
- OFF/SKIPPED khi stage không chạy hoặc bị consent/flag bỏ qua.
- PERSISTENCE_UNKNOWN/UNAVAILABLE với job cũ thiếu receipt, SQLite không có graph store, hoặc store không đọc được.
- Receipt operation và pair được ghi bên ngoài savepoint ghi cạnh, nhưng trong transaction completion hiện có. Nếu transaction ngoài cùng rollback, job không được xem như đã commit SUCCEEDED.

Các trạng thái DTO là contract mới, không thay đổi ai2.be.processing.result.v1.

## Bằng chứng repo và xác minh caller

- AI2 lưu operation và pair riêng trong Postgres; complete_with_snapshot đổi job/snapshot rồi ghi graph bên trong hai savepoint (ai-service/app/tools/jobs.py:553-582,584-611); graph tables nằm tại ai-service/app/db/tables.py:63-84.
- Cờ xử lý thực tế có trên record (ai-service/app/tools/store.py:64-67); nhánh operation và pair chạy theo gate riêng (ai-service/app/pipeline/idp.py:279-307,370-401,433-436).
- Worker HTTP xác nhận trạng thái RUNNING, gọi run_idp, commit result rồi sweeper kết thúc job treo (ai-service/app/api/main.py:254-319,343-364). Đây là nguồn stage trace cho plan; direct demo/package routes không được giả làm trace của worker.
- CITATION_READ là ACL action riêng; share có thể giới hạn action (backend/src/contract_intelligence/shared/acl.py:25-32,124-132). Backend đã kiểm tra citation lần hai sau lời gọi AI2 tại backend/src/contract_intelligence/contract/interfaces/api/routers/contract_router.py:1427-1441; endpoint tài liệu cũng yêu cầu CITATION_READ tại :1647-1656. Digest hiện dùng helper :1305-1307.
- Backend detail được ACL bảo vệ tại contract_router.py:1474-1481; route graph mới phải kiểm tra quyền chứ không dựa vào frontend.
- Mindmap hiện là cây OCR, các chế độ hiện hành tại DossierStructurePage.tsx:936-959; không đổi semantics thành relation graph.

**Caller audit:** hs-run plan next --fact-subjects contract_intelligence.contract.interfaces.api.routers.contract_router::_require_readable trả facts:{} nên dùng rg theo fallback được chỉ dẫn. Có 12 call-site; 10 đầu: restart_dossier_ocr:724, retry_failed_dossier_ocr:779, split_dossier_document:843, retry_dossier_ai2:982, reindex_dossier_ai2:1036, delete_dossier:1140, search_dossier:1364, get_dossier:1480, patch_dossier:1510, get_dossier_access:1537; 2 còn lại là update_dossier_access:1570 và list_dossier_documents:1654 trong cùng router. Không sửa caller hiện hữu ngoài route graph mới.

rg -n 'run_idp\(' ai-service/app cho 9 application call-site: api/main.py:292,1136,1492,1699,1714,1750; transport/kafka_idp_worker.py:180; pipeline/ai2_batch.py:115,179. Trace trong scope chỉ gắn vào worker HTTP ở main.py:292; đường demo, Kafka và batch không instrumented phải trả TRACE_UNAVAILABLE cho đến khi được đưa vào scope riêng. Trace writer truyền dependency rõ ràng theo lần gọi; không thêm mutable process-global accumulator.

## Phases

| Pha | Deliverable | Phụ thuộc |
|---|---|---|
| P1 | Graph read contract + persistence receipts, phân biệt 0 thật với lỗi lưu | — |
| P2 | Durable processing trace và trạng thái worker crash | P1 |
| P3 | Backend API có CITATION_READ, ACL/snapshot recheck và cursor paging | P1, P2 |
| P4 | Timeline + relation list/inspector accessible, paging end-to-end | P3 |
| P5 | Renderer spike và canvas integration có fallback | P4 |

**Lý do tạm giữ trên 3 pha — câu hỏi xác nhận với người dùng:** năm cổng giữ riêng các failure domains: graph write correctness, trace durability/recovery, ACL + paging, list/timeline usability, renderer/performance. Gộp P1/P2 có thể làm trace lỗi ảnh hưởng diễn giải graph; gộp P3/P4 trộn bảo mật API với trạng thái UI; gộp P4/P5 khiến renderer trở thành điều kiện để có fallback accessible. Đây là đề xuất kỹ thuật, chưa phải quyết định người dùng. Trước cook cần hỏi người dùng có muốn giữ năm pha tuần tự hay gộp pha nào.

## Tiêu chí nghiệm thu toàn plan

- [ ] Test chứng minh READY rỗng chỉ khi builder hoàn tất và receipt đúng snapshot là COMMITTED/0; giả lập lỗi từng store cho PERSIST_FAILED/PARTIAL, không thể hiện như “không có quan hệ”.
- [ ] Job SUCCEEDED, graph persistence result và trace completion là ba điều riêng biệt.
- [ ] Graph API và DTO không trả nội dung citation/span/excerpt; query-only share bị từ chối bởi CITATION_READ.
- [ ] Backend re-fetch dossier sau khi chờ AI2, kiểm tra lại CITATION_READ và digest trước khi serialize. Thu hồi share trả 403; đổi snapshot trả 409; cả hai không có graph body.
- [ ] Cursor ràng buộc job_id + digest + thứ tự ổn định; mọi page kiểm tra ACL/snapshot; cursor lỗi/cũ bị từ chối.
- [ ] Fixture nhiều hơn hai page: list tải tiếp đến hết, không trùng/thiếu relation; trạng thái “đầy đủ” chỉ xuất hiện khi next_cursor vắng mặt và count khớp.
- [ ] Worker bị dừng giữa stage vẫn có durable start marker; recovery cho INTERRUPTED_UNKNOWN hoặc dangling-start INCOMPLETE_UNKNOWN, không suy ra terminal stage thành công.
- [ ] UI tách timeline xử lý khỏi graph điều khoản; operation/pair giữ đúng hướng, label, NEEDS_REVIEW, evidence refs.
- [ ] Keyboard, focus, tên accessible và viewport 320 CSS px dùng được; canvas luôn có list thay thế.
- [ ] Existing OCR views, events[], wire v1 và runtime flags không thay đổi.
- [ ] Runtime flags OFF, không deploy/enable trong plan này.

## Ma trận kiểm thử

| Lớp | Invariant/cases | Gate |
|---|---|---|
| AI2 receipt | Postgres success/fail từng savepoint, zero thật, skipped/OFF, outer rollback, job legacy thiếu receipt | unit + migration |
| AI2 read | signature, tenant/dossier/job/digest, sort/cursor, SQLite unavailable, text/span stripping | API/schema |
| AI2 trace | append start/end, safe allowlist, retry epoch/fencing, store unavailable, process death + sweep + restart | unit + integration |
| Backend ACL | owner/share, actions=["query"], CITATION_READ, revoke while adapter blocked, changed digest, AI2 timeout | async route/adapter |
| Paging | cursor tamper, job/digest stale, repeated request, >2 pages, count, stable order | Backend integration |
| Frontend | every status, page continuation, duplicate protection, no “complete” while more, citations only via Backend | component + client integration |
| E2E/manual | multi-annex, operation + REFERENCE/CONFLICT, OFF, persist failure, crash trace, mobile/keyboard/screen reader | UI integration + manual receipt |

Full test gates khi cook: AI2 uv run pytest -q; Backend uv run pytest; Frontend npm test, npm run lint, npm run build. Mỗi phase chạy focused RED→GREEN trước regression suite. Plan hiện chưa chạy test hay benchmark.

## Tương thích ngược

- Giữ nguyên ai2.be.processing.result.v1, events[] và các API dossier hiện hữu; thêm versioned AI2 internal reads và Backend GET.
- Job trước migration hoặc thiếu receipt trả PERSISTENCE_UNKNOWN; job cũ không có durable trace trả TRACE_UNAVAILABLE. Không nâng trạng thái cũ thành READY theo suy đoán.
- Graph store hiện chỉ Postgres; SQLite/local phải trả UNAVAILABLE, không trả 0 cạnh.
- UI mới nằm sau UI flag mặc định OFF; rollback giữ OCR tree và citations hiện có.
- Không xóa lịch sử graph/trace khi rollback; migration chỉ thêm bảng.

## Risk theo plan

- **High (M×H), false empty graph:** receipt tách từng graph store, commit ngoài savepoint nhưng trong transaction completion; fault-injection từng store.
- **High (M×H), lộ evidence hoặc share bị thu hồi:** yêu cầu CITATION_READ trước và sau AI2; DTO bỏ span/text; test query-only, revoke và snapshot race.
- **High (M×H), cursor đọc nhầm snapshot hoặc bỏ relation:** cursor bind job/digest, stable keyset, ACL từng page, count parity và fixture ba trang.
- **High (M×H), timeline bịa terminal stage sau crash:** durable append start/end + recovery marker; dangling start được biểu diễn unknown; test kill/restart.
- **Medium (M×M), node identity không ánh xạ clause:** không fuzzy-match; node/edge lỗi mapping vào issue, chặn hiển thị/selection tới khi định danh được chứng minh.
- **Medium (M×M), graph dày hoặc canvas inaccessible:** giữ relation list là đường thao tác đầy đủ; spike đo trước khi chọn renderer.
- **Medium (L×H), stage telemetry làm hỏng job:** trace append best-effort, không đổi job result; lỗi ghi trace làm read status TRACE_UNAVAILABLE.
- **Medium (M×M), job cũ/SQLite bị hiểu thành kết quả rỗng:** trạng thái UNAVAILABLE/PERSISTENCE_UNKNOWN, có bài test rõ.

## Rollback

- P1: tắt internal graph read route; giữ graph tables cũ và additive receipt table.
- P2: tắt trace writer/read route; giữ job pipeline và wire result; dữ liệu trace không xóa.
- P3: tắt Backend graph/trace routes và adapters; không fallback sang stale payload.
- P4: tắt UI flag; giữ OCR view và API độc lập.
- P5: revert canvas dependency/page integration; list + timeline vẫn dùng được; AI2 flags không đụng.
- Migration rollback chỉ sau xác nhận deployment không còn route đọc bảng mới; mặc định rollout chỉ cần tắt route, không drop bảng.

## Dispositions và quyết định còn mở

| Finding | Disposition | Pha / bằng chứng hiện tại |
|---|---|---|
| RT-01 citation disclosure (CITATION_READ) | Đóng trong thiết kế: P3 yêu cầu CITATION_READ trước/sau await; DTO không chứa text/span; citation detail qua endpoint có ACL. | shared/acl.py:25-32,124-132; contract_router.py:1427-1441,1647-1656; P3 test query-only grant |
| RT-02 graph write swallowed nhưng job SUCCEEDED | Đóng trong thiết kế: P1 receipt riêng per store ngoài savepoint; thất bại thành PERSIST_FAILED/PARTIAL, không thể READY-empty. | ai-service/app/tools/jobs.py:575-611; P1 zero-vs-write-failure test |
| RT-03 share thu hồi trong lúc gọi AI2 | Đóng trong thiết kế: P3 re-fetch ACL và digest sau adapter; race test có barrier. | contract_router.py:1427-1441; P3 |
| RT-04 paging chỉ tới page đầu | Đóng trong thiết kế: P3 cursor, P4 load-more/list-complete chỉ sau page cuối; >2-page E2E. | P3/P4 test matrix |
| RT-05 trace mất khi worker chết | Đóng trong thiết kế: P2 durable stage start/end, sweeper finalization, dangling-start unknown; restart test. | ai-service/app/api/main.py:254-319,343-364; P2 |

**Red-team artifact reconciliation:** report from-code-reviewer-to-planner-red-team-security-operations-ux-plan-review-report.md là artifact nguồn; bản sao cùng nội dung đã được chuyển nguyên văn thành reports/superseded-unattributed-review-copy.md, không tính là lượt review độc lập. Xem reports/red-team-artifact-reconciliation.md. Không khẳng định có hai lượt red-team độc lập.

**Còn cần người dùng xác nhận trước khi cook:** (1) giữ HOLD và runtime flags OFF; (2) giữ năm pha tuần tự hay gộp pha; (3) chấp nhận CITATION_READ là điều kiện mở mọi graph view; (4) identity field nào nối AI2 node ID sang Backend clause ID nếu mapping hiện tại không rõ. Plan không được coi là approved chỉ vì các finding đã có disposition.

