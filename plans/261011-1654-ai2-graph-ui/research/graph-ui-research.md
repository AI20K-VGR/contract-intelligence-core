# Nghiên cứu: UI graph AI2 dễ hiểu cho hồ sơ hợp đồng

**Mode**: depth  
**Ngày**: 2026-10-11  
**Câu hỏi**: Thiết kế UI nào giúp người dùng vừa hiểu AI2 đã xử lý hợp đồng ra sao, vừa đọc được quan hệ điều khoản trong hồ sơ nhiều tài liệu?  
**Tiêu chí**: khớp React hiện tại; phân biệt quy trình xử lý với quan hệ pháp văn bản; điều hướng tới bằng chứng; truy cập được bằng bàn phím/màn hình nhỏ; mở rộng theo dữ liệu; bảo vệ ACL và snapshot.  
**Ngoài phạm vi**: implementation, kiểm thử UI, đo bundle/performance, quyết định SLO và deploy.

## Tóm tắt

- Nên làm **hai lớp liên kết nhưng tách nghĩa**: timeline “AI2 đã làm gì” và đồ thị “điều khoản nào liên quan điều khoản nào”. Không ghép các bước pipeline thành node trong graph hợp đồng.
- Ưu tiên **React Flow (@xyflow/react) + ELK Layered (elkjs) sau spike nhỏ**; nodes/edges tùy biến hợp React, bố cục có hướng hợp source→target. Frontend hiện dùng React 19/TypeScript/Vite, không có thư viện graph; đã có SVG mindmap riêng cho cây OCR.
- UI chỉ vẽ đủ graph khi có API mới: AI2 persist ContractEdge/PairRelation, nhưng processing wire hiện trả context_findings, không trả toàn bộ hai collection. Frontend đang đọc cấu trúc OCR, chưa có DTO graph.
- Xem kết quả như đề xuất cần review. Hiển thị loại cạnh, hướng, citation và trạng thái bằng nhãn/hình thức ngoài màu; kèm danh sách accessible thay thế.

## Bằng chứng về repo hiện tại

- **OBSERVED** — Frontend là React 19.2 + TypeScript 5.9 + Vite 7; frontend/package.json:1-35. Dependencies hiện tại không gồm thư viện graph.
- **OBSERVED** — StructureMindmap dựng cây OCR qua SVG, có pan/zoom, expand/collapse, click citation: frontend/src/components/StructureMindmap.tsx:586-605, 838, 979-1015; trang cấu trúc chọn outline/document/tree/mindmap tại frontend/src/pages/DossierStructurePage.tsx:936-959. ContractMindmap chỉ là tên tương thích cho cấu trúc hồ sơ, không phải view của cạnh Contract Graph.
- **OBSERVED** — AI2 model operation edge có op, source/target node IDs, target address, method/support, citations, review state và snapshot digest: ai-service/app/contracts/contract_graph.py:43-69. Pair relation có label, hai node IDs, directed, candidate sources, evidence spans, hai citations, model/prompt, review state, snapshot digest: ai-service/app/contracts/contract_graph.py:72-97.
- **OBSERVED** — AI2 ghi operation edges và pair relations vào hai store theo dossier/job (ai-service/app/tools/jobs.py:575-611); flags quyết định flow graph/pair có chạy (ai-service/app/pipeline/idp.py:279-295, 370-390). Không có cạnh không đủ để kết luận “không liên quan”; UI cần đưa trạng thái OFF/skipped/failed/incomplete từ coverage/issues ra riêng.
- **OBSERVED** — job_result_to_wire() trả facts, findings, context_findings, events, citations, index_contribution; không có edges[] hoặc relations[]: ai-service/app/contracts/wire.py:357-373. Pair/operation edge persistence chưa được trình bày như API đọc graph cho UI.
- **OBSERVED** — events[] trong result lấy từ contribution.events (ai-service/app/contracts/wire.py:294-297), tức event trích xuất nghiệp vụ; chưa có bằng chứng đây là nhật ký từng bước pipeline với timestamp/status. Timeline cần telemetry processing riêng, không đổi nghĩa events[] hiện tại.
- **OBSERVED** — Backend có route dossier detail kiểm tra ACL (backend/src/contract_intelligence/contract/interfaces/api/routers/contract_router.py:1469-1481), còn frontend structure lấy document/clause tree qua frontend/src/api/structure.ts. Một API graph được bảo vệ theo dossier/snapshot cần bổ sung; không cho UI truy cập DB AI2.

## Đề xuất hình ảnh và tương tác

### 1. “Luồng xử lý” — timeline/stepper

Trong dossier, thêm tab **Đồ thị AI2** cạnh cấu trúc hồ sơ, giữ mindmap OCR hiện tại. Phía trên canvas hiển thị trạng thái job/snapshot rồi chuỗi bước, mỗi bước có trạng thái, thời gian và artifact/số lượng nếu có:

OCR AI1 → Backend xác nhận tài liệu/snapshot → AI2 dựng cấu trúc & trích facts → nhận diện sửa đổi tường minh → tạo candidate pairs → phân loại cặp (nếu bật) → kiểm tra citations & lưu → Backend chờ review

Mỗi bước mở panel “đầu vào / đầu ra / vì sao bỏ qua / lỗi”. Nếu graph flag OFF, classifier bị skip, job lỗi hoặc snapshot stale, ghi rõ trạng thái. Không hiện “0 quan hệ” như kết luận khi bước chưa chạy. Cần bổ sung event/status/timing theo stage để timeline là dấu vết thực tế của job; đừng dựng timeline tĩnh rồi trình bày như log đã chạy.

### 2. “Quan hệ trong hợp đồng” — graph theo tài liệu

- Nhóm nodes thành lane/khung theo **Hợp đồng chính**, **Phụ lục 1…N**; trong mỗi lane giữ thứ tự điều/khoản tài liệu. Mặc định mở article-level summary và luôn mở các clause có cạnh; người dùng mở thêm các khoản để xem toàn hợp đồng mà không dồn toàn bộ text vào canvas.
- Vẽ cạnh có hướng và nhãn trực tiếp. INSERTION/SUBSTITUTION/REPEAL/REJECTION/SCOPE_LIMIT là operation edges; REFERENCE/CONFLICT/DUPLICATE/GENERAL_SPECIFIC là pair relations, nằm lớp hiển thị riêng. Tôn trọng directed; không mặc định mọi pair là mũi tên một chiều.
- Dùng **màu + chữ + kiểu nét/biểu tượng** cho loại cạnh/trạng thái. Legend luôn hiện; edge label ngắn như “Sửa đổi”, “Dẫn chiếu”, “Xung đột”. Nút ghi số điều, tên tài liệu và review badge; node không mang cạnh vẫn mở được từ cây/outline.
- Click node/cạnh mở inspector bên phải: tài liệu, điều khoản, thao tác/nhãn quan hệ, nguồn→đích, hai đoạn trích, trang và trạng thái review. “Mở bằng chứng” mở citation/PDF hiện có; highlight hai đầu khi chọn cạnh. Không diễn giải cạnh thành phán quyết hiệu lực pháp lý.
- Toolbar: tìm điều khoản, lọc tài liệu/loại cạnh/trạng thái review, chỉ hiện cạnh quanh một node, fit/reset. Unresolved/ambiguous target hiện ở danh sách issues và tại nguồn dưới dạng cảnh báo, **không bịa node đích**.
- Có tab **Danh sách** tương đương canvas: mỗi hàng là cạnh với source, label, target, review state và citation actions. Trên mobile/keyboard đây là lối thao tác đầy đủ. Graph cần Tab/Enter/Escape, focus rõ và nhãn screen reader.

### 3. Phác thảo bố cục

    ┌ Hồ sơ thuê đất · AI2 · snapshot abc… · Đang chờ review ─────────┐
    │ OCR ✓ → Cấu trúc ✓ → Sửa đổi ✓ → Candidate ✓ → Review          │
    ├ Luồng xử lý │ Đồ thị quan hệ │ Danh sách ──────────────────────┤
    │ Lọc: [Tất cả tài liệu ▾] [Loại quan hệ ▾] [Tìm điều khoản…]   │
    │                                                               │
    │ HỢP ĐỒNG CHÍNH                   PHỤ LỤC 01                    │
    │ ┌ Điều 1 · Thời hạn ┐ ── Sửa đổi ── ┌ Điều 1 · thời hạn mới ┐ │
    │ ├ Điều 2 · Giá      ┤ ── Dẫn chiếu ─┤ Điều 2 · giá sửa đổi ┤ │
    │ └ Điều 3 · Thanh toán┘                └ Khoản 3 · kỳ hạn     ┘ │
    │                         chọn cạnh → inspector / citations       │
    └───────────────────────────────────────────────────────────────┘

Hướng mũi tên tùy chiều source/target thật của từng quan hệ; UI dùng hướng API, không đảo để “đẹp”.

## So sánh kỹ thuật, xếp hạng

| Hạng | Hướng | Hiệu năng / bố cục | Phức tạp & bảo trì | Chi phí / rủi ro áp dụng | Fit dự án |
|---|---|---|---|---|---|
| **1** | **React Flow + ELK Layered, sau spike** | Node/edge theo React; ELK hỗ trợ bố cục có hướng, compound graph, nhãn và routing. Cần giới hạn/expand nhóm và đo trên hồ sơ thật; chưa có benchmark dự án. | Thấp-vừa để có pan/zoom/select/custom node; cần adapter graph DTO→view model và tránh re-render theo hướng dẫn thư viện. | Thêm 2 dependency; cần ghim phiên bản và đánh giá upgrade. React Flow v12 đổi tên package/API so với v11; migration là rủi ro đã ghi nhận. ELK.js chỉ bố trí tọa độ, không phải renderer. | Tốt nhất: React-first, custom clause nodes/edge labels, direction, keyboard/ARIA support; ELK phù hợp cạnh chéo và compound nodes hơn layout cây hiện có. |
| **2** | **SVG/HTML custom renderer hiện có + layout cố định** | Đủ cho graph giới hạn đã lọc; SVG rõ nét, DOM labels. Chưa đo khi nhiều cạnh. | Không thêm dependency ngay, nhưng cần tự viết crossing layout, edge routing/selection/keyboard, edge labels và tests. | Ít rủi ro dependency, rủi ro cao hơn về tự xây công cụ graph/accessibility. | Có thể prototype một vài loại cạnh; không nên mở rộng cây StructureMindmap thành canvas quan hệ dài hạn. |
| **3** | **Cytoscape.js** | Graph/network chuyên dụng, gestures, layout/data selectors; hợp graph dày và thao tác network. | Core mạnh, nhưng cần nối lifecycle/DOM và custom React inspector qua adapter. | Thêm renderer/lifecycle; layout có extension/configuration. Docs tự mô tả cadence đều và “highly optimised” — claim maintainer, không phải benchmark AI2. | Dự phòng nếu spike cho thấy graph lớn/dày làm React Flow không đạt; tính network tổng quát chưa cần cho review điều khoản ban đầu. |

## Khuyến nghị

**Ưu tiên 1 — React Flow + ELK Layered cho canvas, Backend API là façade theo ACL dossier.** Làm spike trên graph đa tài liệu đã scrub, đo initial render, layout latency, zoom/selection và số node/cạnh trước khi chốt dependency. Tắt drag/connect để canvas chỉ đọc. Chỉ chọn Cytoscape nếu spike cho thấy density/performance cần renderer network chuyên biệt. Dùng layout trái→phải theo tài liệu/cross-document edge và stable sorting theo document order.

**API trước UI:** thiết kế versioned GET /dossiers/{id}/contract-graph ở Backend; endpoint kiểm tra ACL giống dossier detail, lấy graph của snapshot/job hiện hành từ AI2 service-to-service, rồi trả projection tối thiểu. DTO đề xuất:

- dossier_id, job_id, snapshot_digest, generated_at, status, processing/coverage counts, issues[], steps[] (stage/status/timestamps/counts/reason);
- documents[] (id, role, display name);
- nodes[] (node/document IDs, clause address/title, excerpt ngắn, page span/citation reference);
- edges[] (edge ID, kind/label/op, source/target, directed, review state, evidence/method/support, source+target citation refs/spans);
- paging/size cap hoặc nhóm/cursor nếu graph lớn; response phân biệt OFF, PENDING, READY, PARTIAL, FAILED, STALE theo design contract. Các state này là **đề xuất DTO**, chưa phải enum repo.

Không gửi toàn văn điều khoản chỉ để vẽ graph; click lấy citation/detail qua luồng Backend đang có. Kiểm tra trước khi làm API xem node_id AI2 map ổn định với ClauseNode.id Backend; nếu không, bổ sung mapping định danh rõ ràng thay vì so khớp text. UI dùng digest/status để không gắn cạnh snapshot cũ vào clauses mới.

## Pha đề xuất cho hs:plan

1. **API/data contract**: chốt owner graph, job/snapshot semantics, ID mapping, API permission/size/error states, OpenAPI + fixtures. Đây là blocker trước UI.
2. **UX skeleton**: tab riêng; timeline thực; graph/list toggle; lane tài liệu; legend, filters, citation inspector; empty/off/partial/stale/error states.
3. **Spike renderer**: React Flow + ELK với dossier đa tài liệu đã scrub và cạnh sửa đổi/dẫn chiếu/xung đột; đo bundle delta/latency/interaction, kiểm tra đọc mobile. So nhanh với custom SVG baseline.
4. **Product implementation**: API client/types, adapter, canvas, list, deep link tới citation, giữ lựa chọn cạnh khi quay lại nếu phù hợp.
5. **Review gate**: contract tests BE↔AI2, UI tests cho hướng cạnh/stale/OFF/keyboard/mobile, accessibility review thủ công, chứng minh click cạnh mở đúng citations; nghiệm thu với hợp đồng nhiều phụ lục.
6. **Release**: deploy read API + UI trước với feature graph runtime OFF; bật operation/pair flags theo canary và consent gate độc lập, giữ rollback về OFF.

## Rủi ro và câu hỏi mở

- **ID mapping chưa xác minh** giữa AI2 node IDs/citations và Backend ClauseNode.id; cần kiểm tra dữ liệu thật trước khi đóng DTO.
- AI2 edge stores là persistence source nhưng wire không đưa raw graph qua Backend; cần quyết định façade đọc AI2 hay mở result contract + persist projection ở Backend. Khuyến nghị façade để frontend chỉ gọi Backend, nhưng latency/availability service-to-service cần spike.
- Cross-reference chu kỳ và nhiều cạnh tạo giao nhau. ELK giảm crossing theo thuật toán, không đảm bảo sơ đồ luôn dễ đọc; cần test corpus đại diện.
- **Chưa đo** cỡ graph lớn nhất, payload, bundle delta, render/layout latency, browser baseline hay SLO; không tự đặt ngưỡng số khi chưa đo/owner xác nhận.
- Runtime flags trong source mặc định OFF không chứng minh cấu hình môi trường deploy. UI hiển thị trạng thái từ job/API, không suy luận từ code default.

## Nguồn tham khảo

| Nguồn | Tổ chức / độ tin cậy | Dùng cho |
|---|---|---|
| [1] [React Flow accessibility](https://reactflow.dev/learn/advanced-use/accessibility) | xyflow maintainer docs; truy cập 2026-10-11; credibility: cao cho khả năng thư viện | Keyboard focus/operability nodes/edges, ARIA và localize thông báo; không thay kiểm thử WCAG sản phẩm. |
| [2] [React Flow performance](https://reactflow.dev/learn/advanced-use/performance) | xyflow maintainer docs; truy cập 2026-10-11; credibility: cao cho hướng dẫn framework | Memo hóa node/edge/custom props; không khẳng định performance AI2. |
| [3] [React Flow v12 migration discussion](https://github.com/xyflow/xyflow/discussions/3764) | xyflow maintainer release discussion; 2024-01-03; credibility: cao cho breaking changes project | Package rename/API đổi v11→v12; ghim version, migration review. |
| [4] [ELK Layered reference](https://eclipse.dev/elk/reference/algorithms/org-eclipse-elk-layered.html) | Eclipse ELK official docs; truy cập 2026-10-11; credibility: cao | Directed layers, edge labels/routing, compound/cross-hierarchy support. |
| [5] [elkjs repository](https://github.com/kieler/elkjs) | Maintainer repo; truy cập 2026-10-11; credibility: cao cho phạm vi package/release, không phải benchmark | JavaScript layout engine, Web Worker, không phải renderer. |
| [6] [Cytoscape.js docs](https://js.cytoscape.org/) | Project docs; truy cập 2026-10-11; credibility: cao cho API/functionality; “highly optimised” là maintainer claim | Graph-specific renderer, gestures, graph querying/layout. |
| [7] [W3C WCAG 2.2 — Use of Color](https://www.w3.org/WAI/WCAG22/Understanding/use-of-color.html) | W3C/WAI guidance; truy cập 2026-10-11; credibility: cao | Không phân biệt relation/review chỉ bằng hue; thêm chữ/hình dạng. |
| [8] [MDN: SVG in HTML accessibility](https://developer.mozilla.org/en-US/docs/Web/SVG/Guides/SVG_in_HTML) | MDN/Web platform guidance; truy cập 2026-10-11; credibility: cao | SVG title/desc/ARIA; đồ họa cần mô tả và bảng văn bản thay thế. |

## Giới hạn nghiên cứu

Tài liệu framework xác nhận khả năng được mô tả, không chứng minh renderer nào nhanh hơn trên dữ liệu VSF. Chưa cài thư viện, dựng spike, đo bundle/render, chạy assistive technology, rà license theo release cụ thể, hoặc đọc cấu hình môi trường deploy. Khuyến nghị React Flow + ELK là xếp hạng kiến trúc theo độ khớp hiện tại; quyết định dependency cuối cần spike và review lockfile/license.
