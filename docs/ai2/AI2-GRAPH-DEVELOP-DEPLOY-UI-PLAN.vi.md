# Kế hoạch đưa AI2 Contract Graph lên develop, deploy và bổ sung Graph UI

**Trạng thái:** kế hoạch, chưa triển khai merge/deploy/push  
**Ngày lập:** 2026-10-11  
**Nhánh hiện tại:** `feature/ai2-contract-graph` tại `67e58307190c114676d64633689b1a70b4e24a14`  
**Mốc develop đối chiếu:** `origin/develop` tại `54faa07cc85cb42762afff429d659044b2664943`  
**Nguồn ví dụ hợp đồng:** [Phụ lục 01/2020/PLHĐ-TĐ trong hồ sơ công khai UBND tỉnh Nghệ An](https://datafiles.nghean.gov.vn/nan-ubnd/2298/quantritintuc20248/GPMT_Trang_trai_giong_nuoi_trong_thuy_san_1722915640638591416785065020.pdf)

## 1. Kết quả đối chiếu hiện tại

So sánh commit `HEAD` với `origin/develop` cho thấy nhánh hiện tại **đi trước 47 commit và thiếu 27 commit của develop**. Diff commit có **362 file thay đổi, khoảng 369 nghìn dòng thêm và 43 dòng xóa**. Số dòng thêm bị chi phối đáng kể bởi corpora, JSON goldens và báo cáo đánh giá; không nên hiểu đó là 369 nghìn dòng runtime mới. Working tree còn nhiều thay đổi chưa commit, vì vậy con số này chưa bao gồm trạng thái cuối cùng đang làm.

| Khu vực | `origin/develop` (AI2 cũ tại SHA nêu trên) | Nhánh `feature/ai2-contract-graph` | Hệ quả khi tích hợp |
|---|---|---|---|
| Quan hệ hợp đồng | Đồ thị quan hệ legacy (`PARENT_OF`, `SAME_CLAUSE`, `REFERENCES`, `AMENDS`...) dựng từ relation markers/structure; không có operation-first edge model riêng trong diff này | Thêm `ContractEdge` với thao tác `INSERTION`, `SUBSTITUTION`, `REPEAL`, `REJECTION`, `SCOPE_LIMIT`; resolver địa chỉ điều/khoản; lưu `contract_edges` | Cần migration và kiểm tra tương thích schema/wire; subtype thao tác giữ ở AI2, projected ra finding tương thích `AMENDS` |
| Quan hệ ngầm | Các quan hệ legacy phục vụ reasoning/retrieval | Thêm pair candidate generation, classifier, `PairRelation`, bảng `contract_pair_relations`, consent/flag gate | Không bật classifier/model calls ở production cho đến khi cấu hình, consent, chất lượng và rollback được duyệt |
| Runtime switch | Không có hai feature flag Contract Graph mới | Có `AI2_CONTRACT_GRAPH_ENABLED` và `AI2_CONTRACT_GRAPH_PAIRS_ENABLED`, mặc định `false` trong mã hiện tại | Giữ OFF trong lần deploy đầu; bật theo canary riêng sau khi hoàn tất gate |
| API và review | Backend/front-end hiện có flow finding/review và mindmap cấu trúc hồ sơ | AI2 lưu cạnh và chiếu operation edge vào finding tương thích; diff không có thay đổi `frontend/` | Graph UI sản phẩm chưa được làm; cần API đọc graph theo dossier có authorization và UI riêng |
| Đánh giá | Không có bộ Contract Graph mới trong develop tại mốc so sánh | Thêm eval corpus, gold, candidate/classifier bakeoff, quality reports và tests | Chọn tập gate có thể tái lập, không đưa toàn bộ artifacts lớn không cần thiết nếu repo policy cho phép |

**Phân biệt hai loại graph:** `ContractMindmap` hiện tại tập trung biểu diễn cấu trúc hồ sơ/tài liệu. Nó chưa trực quan hóa trực tiếp cạnh operation-first và pair relations AI2 đã lưu. Không nên đổi nhãn mindmap hiện hữu để tạo cảm giác rằng yêu cầu Graph UI đã xong.

**Trạng thái vận hành quan sát được trong mã:** hai feature flags mặc định `false`. Đây là bằng chứng trạng thái mặc định trong source, không phải xác nhận trạng thái của một môi trường deploy cụ thể. Trước deploy cần đọc config/secret của chính môi trường đích.

## 2. Mục tiêu sản phẩm và tiêu chí chấp nhận

Người dùng mở một hồ sơ trên giao diện và xem được graph do AI2 xử lý cho đúng phiên bản snapshot, gồm:

1. Nút tài liệu và nút điều/khoản, nhóm theo hợp đồng chính/phụ lục.
2. Cạnh có hướng từ nội dung sửa trong phụ lục đến điều khoản đích; hiển thị thao tác, nguồn bằng chứng và trạng thái review.
3. Pair relation ngầm được thể hiện như quan hệ riêng với nhãn (`CONFLICT`, `REFERENCE`, `GENERAL_SPECIFIC`, `DUPLICATE`), citation hai phía và trạng thái `NEEDS_REVIEW`; không trộn nhầm với cạnh `AMENDS`.
4. Chọn cạnh/nút mở đúng citation trong tài liệu/PDF và cho phép quay về graph; có dạng danh sách/bảng thay thế khi graph lớn hoặc không phù hợp accessibility.
5. Target mơ hồ/chưa resolve, graph lỗi, snapshot cũ, graph trống và runtime OFF được giải thích rõ; UI không tự tạo liên kết không có bằng chứng.
6. Endpoint giới hạn tenant/dossier theo quyền đăng nhập, chỉ trả dữ liệu của snapshot hiện hành hoặc cho biết rõ snapshot version; có phân trang/giới hạn kích thước nếu cần.

Ví dụ nghiệp vụ/đồ thị cụ thể nằm trong [tài liệu minh họa hợp đồng thật](ai2-contract-graph-example-contract-annex.vi.md).

## 3. Các pha thực hiện đề xuất

### P0 — Đóng băng baseline và kiểm tra tích hợp

- Giữ nguyên và lập inventory toàn bộ thay đổi tracked/untracked trên worktree; không ghi đè hoặc dọn các file không thuộc feature.
- Chốt commit nguồn, commit `develop` đích, danh sách commit sẽ tích hợp; kiểm tra riêng 27 commit develop đang thiếu.
- Phân loại diff theo runtime, migration, tests, eval data/reports, docs; xác định artifacts nào là source-of-truth cần mang theo.
- Đọc lại kế hoạch/review đã có của nhánh, các thay đổi chưa commit và trạng thái CI để chọn baseline chất lượng đáng tin.
- **Gate:** có manifest file/commit rõ ràng, không lẫn công việc khác; không bắt đầu merge trước khi xử lý lệch nhánh và vùng conflict.

### P1 — Hợp nhất an toàn với develop

- Tạo integration branch/worktree sạch từ `origin/develop` mới nhất; không merge ngay trong worktree dirty.
- Rebase/merge feature theo quy ước repo; giải quyết conflict có chủ sở hữu ở AI2 pipeline, DB migrations, contracts/wire, docs và evals.
- Bảo toàn backward compatibility khi flag OFF: đầu ra legacy, reasoning, snapshot, quota/consent không đổi ngoài các thay đổi đã được chấp thuận.
- Kiểm tra thứ tự Alembic migrations trên DB trống và DB nâng cấp từ develop; kiểm tra rollback/forward-fix vì downgrade dữ liệu graph có thể mất dữ liệu.
- **Gate:** suite hiện hành của develop và AI2 qua; golden flag-off không đổi; migration nâng cấp thành công; API/wire không phát sinh breaking change.

### P2 — Kiểm chứng graph backend và chất lượng

- Chạy test tích hợp AI2 → persistence → backend projection trên cùng snapshot, bao gồm cạnh tường minh, pair relation, duplicate suppression, unresolved/ambiguous target, lỗi builder và flag OFF.
- Chạy eval gates đã đăng ký trong các quality recovery reports với dữ liệu development/training được phép; xác nhận sample scope, manifest, hashes và không dùng held-out đã khóa để tune.
- Xác minh citations giữ node, trang/đoạn, snapshot digest; mọi relation đều `NEEDS_REVIEW` theo policy hiện tại.
- Đặt ngưỡng production cụ thể trước khi chọn bật tính năng; phân biệt gate chất lượng operation edges với pair classifier vì rủi ro khác nhau.
- **Gate:** CI/review PASS; không có false legal winner; quality gates định lượng được thông qua hoặc feature tương ứng giữ OFF.

### P3 — API đọc graph phục vụ giao diện

- Chốt system-of-record: graph đang được persist trong DB AI2 (`contract_edges`, `contract_pair_relations`), trong khi backend hiện tiêu thụ finding projection. Chọn endpoint backend façade hoặc API AI2 có authorization thống nhất; không cho frontend đọc DB/service nội bộ trực tiếp.
- Định nghĩa versioned response DTO: dossier/snapshot ids, document/node summaries, amendment edges, pair relations, issues/unresolved targets, counts, processing status, citations, review state.
- Xác enforce tenant/dossier access, authorization, stale snapshot handling, pagination/graph size cap, timeout, error shape, observability và cache invalidation khi job/snapshot thay đổi.
- **Gate:** contract OpenAPI/JSON Schema, API tests quyền truy cập và dữ liệu snapshot; không leak cross-tenant; dữ liệu trả về khớp persisted AI2 output.

### P4 — Graph UI trong giao diện

- Tạo view/tab “Đồ thị quan hệ AI2” trong trang dossier đang có (đặt cạnh cấu trúc hồ sơ, không thay mindmap hiện tại).
- Dùng SVG/HTML React hoặc thư viện đã được repo chấp thuận sau spike hiệu năng; không thêm dependency trước khi kiểm tra bundle, accessibility và license.
- Vẽ document containers, clause nodes, arrow direction, loại cạnh, legend, review badges; style cạnh amendment tường minh khác cặp quan hệ ngầm.
- Click node/cạnh hiển thị panel chi tiết: trích đoạn hai đầu, tên tài liệu, điều/khoản, citations, phương pháp/độ hỗ trợ, thời điểm/snapshot, trạng thái review và link mở đúng tài liệu.
- Có filter theo tài liệu, loại quan hệ, thao tác, review state; xử lý empty/loading/error/OFF/stale states; fallback table/list accessible với keyboard navigation và screen-reader labels.
- Không để graph khổng lồ render cùng lúc: giới hạn/ẩn nhóm, search/filter, expand-on-demand, virtualize bảng khi cần.
- **Gate:** UI tests cho graph thực từ API fixture, keyboard/accessibility review, responsive layout, lựa chọn cạnh mở đúng citations, không nhầm nhãn/chiều cạnh.

### P5 — Release/deploy theo canary

- Cập nhật runbook, environment variables, DB migration procedure, dashboards/alerts, rollback và support notes.
- Deploy migration theo chiến lược expand-then-contract tương thích phiên bản cũ/mới; deploy AI service/API trước hoặc theo thứ tự đã chứng minh.
- Deploy UI/API khi flag còn OFF; smoke test luồng hồ sơ cũ và kiểm tra endpoint graph trả OFF/empty state đúng.
- Bật `AI2_CONTRACT_GRAPH_ENABLED` cho canary giới hạn với consent và corpus được phép; theo dõi errors, unresolved rate, latency, DB writes, citation validity và reviewer feedback.
- Chỉ bật pair classifier riêng sau khi model/config, consent, quota, quality gate và rollback được xác minh; không bật đồng thời để dễ quy nguyên nhân.
- **Gate:** SLO/threshold và thời gian quan sát do owner sản phẩm/ops xác nhận trước release; rollback về flag OFF không cần xóa snapshot hoặc làm hỏng luồng cũ.

## 4. Các rủi ro cần quyết định trước khi cook

- **Lệch nhánh lớn:** feature thiếu 27 commit mới của develop; merge có thể va chạm vào API, schema và UI. P0/P1 phải giải quyết trước.
- **Eval artifacts nặng:** diff gần 369k dòng chủ yếu là dữ liệu/báo cáo. Cần xác nhận policy lưu corpus/held-out và không vô tình đưa dữ liệu nhạy cảm hoặc artifact tạm vào develop.
- **Data contract frontend chưa chốt:** hiện có dữ liệu ở AI2 persistence và finding projection; cần quyết định endpoint, quyền truy cập và snapshot semantics trước thiết kế UI hoàn chỉnh.
- **Graph không đồng nghĩa auto-legal decision:** review state cần giữ hiển thị xuyên suốt; không dùng màu/nhãn UI khiến người dùng hiểu AI đã xác định hiệu lực pháp lý.
- **Deploy state chưa được xác nhận:** source mặc định OFF không chứng minh cấu hình của môi trường; cần kiểm tra release manifests/secret trực tiếp trong pha deploy.

## 5. Thứ tự làm tiếp

1. Chấp thuận phạm vi và thứ tự P0–P5 này.
2. Tạo integration worktree sạch từ `origin/develop`, audit changeset và xử lý 27 commit develop mới.
3. Chạy review/test/integration gates, khóa wire/API contract và migration strategy.
4. Lập spec/API cho Graph UI rồi triển khai view và kiểm chứng bằng output AI2 thật.
5. Chuẩn bị canary/runbook/rollback; deploy theo từng flag và theo dõi trước khi mở rộng.

Kế hoạch này mới ghi nhận hướng đi và gate kỹ thuật; chưa merge, deploy, commit hay push bất kỳ thay đổi nào.
