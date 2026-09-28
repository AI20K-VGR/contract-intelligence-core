# So sánh code hiện tại với origin/feature/code-full

Ngày đối chiếu: 2026-09-27. Cây hiện tại là nhánh `feature/ai2-integration`, commit `23aa6f2` (27/09 04:11, `dungskbg2004@gmail.com`) cộng toàn bộ sửa chưa commit trong thư mục làm việc. Đầu `origin/feature/code-full` là `5e8d2c6` (27/09 12:12, `changggfpt@gmail.com`). Hai bên tách tại `2c0a707`.

`git diff origin/feature/code-full` trên code sản phẩm (bỏ `node_modules`, `output/`, `apps/web`): khoảng 104 file. Chiều `+` là dòng chỉ có ở cây hiện tại. Chiều `-` là dòng chỉ có trên `feature/code-full`.

`clause_compare.py` không nằm trong diff. Cả hai đã có so sánh điều khoản thân hợp đồng với phụ lục tải riêng từ `a9b0e5b`.

## Commit mỗi bên tự có

Chỉ có trên nhánh hiện tại, chưa có trên `feature/code-full`:

| Commit | Nội dung |
|---|---|
| `b9ec2c7` | Ngừng theo dõi artifact sinh ra |
| `4205154`, `6962165` | README: backend là Python, bỏ claim Celery |
| `8dc1559` | Ghi plan dọn repo |
| `2128d23` | AI2 gắn cờ case im lặng, chặn gọi ra ngoài khi hết quyền |
| `198e426` | Không coi tiêu đề bảng là furniture |
| `025b842` | Khóa fixture EC, không bịa node |
| `0095e02` | Câu hỏi mã số thuế tiếng Anh map về MST bên bán |
| `b8b633f` | Cùng khóa thì chỉ xuất một fact |
| `c996a62` | Citation fixture chưa kiểm vẫn ở trạng thái review |
| `d0d2426` | Bỏ boilerplate phụ lục không đánh số |
| `23aa6f2` | Merge `feature/code-full` tại `2c0a707` |

Chỉ có trên `feature/code-full`:

| Commit | Nội dung |
|---|---|
| `5e8d2c6` | HITL finding lên cây điều khoản và hai màn thẩm định. Không sửa pipeline AI2 |

`feature/code-full` vẫn theo dõi `apps/web/node_modules` và dump OCR trong `output/`. Nhánh hiện tại đã bỏ các file đó ở `b9ec2c7`.

## Pipeline AI2

Nhánh hiện tại đi tiếp extractor và query. `feature/code-full` giữ pipeline tại `2c0a707`.

| File | Hiện tại thêm | code-full có mà hiện tại không |
|---|---|---|
| `ai1_snapshot_adapter.py` | +176 / −21. Fact từ dòng OCR: tên bên, MST theo bên, lịch thanh toán theo %, tổng `Tổng cộng` ở dòng kế | Không có luật dòng này |
| `fact.py` | +27 / −8. Khóa `party_*`, `mst*`, `payment_schedule`. Số có dấu chấm hoặc phẩy chuẩn hóa ở L0. Prompt LLM bắt chuỗi cùng ngôn ngữ | Không |
| `llm/client.py` | +30. `complete_json` là method của client. Health phân biệt tắt / sẵn sàng / không gọi được | Method bị lệch chỗ ở bản cũ; code-full không có bản sửa này |
| `grounding.py` | +16. Câu model viết lại không nằm trong trang thì `NEEDS_REVIEW`, không `PASS` | Không |
| `contract_events.py` | +12. Sự kiện bên chỉ trên dòng tiêu đề `BÊN A/B` | Mọi câu có “Bên A” vẫn thành sự kiện |
| `edge_flags.py` | +101. Case im lặng, numbering, header/footer | Không có file hành vi này trên diff (bản hiện tại dài hơn 101 dòng) |
| `contract_context.py` | +80 / −4. Cặp cùng `item_key` trong một snapshot thành ghi chú `UNCONFIRMED` | Giữ logic phụ lục theo file của `a9b0e5b` |
| `idp.py` | +54 / −13. Egress và candidate | Bản code-full ngắn hơn ở chỗ kiểm soát này |
| `l1_retrieval.py`, `l2_plan.py`, `relations.py`, `stack.py` | Siết phụ lục, điều khoản, câu LLM chỉ giữ khi đủ citation | Không |
| `api/main.py` | +46 / −23. Query backend dùng LLM khi egress bật. Health không còn nghĩa “có key là ready” | Không |
| Test EC | `test_ec_audit.py`, `test_ec_silent_pass.py`, `test_ec_policy_block.py`, `test_l0.py`, `test_ai1_snapshot_adapter.py` | Không có các test này |

## Backend

| File | Ý nghĩa |
|---|---|
| `worker.py` +116 | Nhánh hiện tại sửa worker extraction/render. code-full không có các dòng này |
| `extraction_service.py` +62, extraction repository +30, `extraction_full_router.py` +17 | Đường extraction riêng của nhánh hiện tại, chưa commit |
| `contract_router.py` +18 | Search đọc citation lồng nhau (`line_id`, trang, file) |
| `settings.py` +8 | Cờ egress AI2 |
| `conflict/.../repository_impl.py` −52 | code-full lấy lượt thẩm định mới nhất, join tên và email. Nhánh hiện tại chưa có |
| `review_service.py` −157, review router −95, review DTO −33, review repository −45 | code-full có GET/POST `/findings/{id}/review`, trạng thái, lịch sử, thẩm định cũ của lần phân tích trước |
| `identity/provision.py` −34, `dependencies.py` −11, `auth_router.py` −8 | code-full tạo dòng `app_user` ở lần gọi profile đầu tiên để join được tên |
| `test_ensure_app_user.py` −83, `test_review_router.py` −58 | Test của phần HITL trên code-full |

## Frontend

code-full tô xung đột lên cây và lưu ai đã thẩm định. Nhánh hiện tại làm nút trích dẫn search và hai phía trong cùng một file.

Chỉ có trên code-full:

- `conflictAnchors.ts`: neo finding vào nút cây bằng trang và dòng OCR của phía hợp đồng. Trạng thái `open` / `reviewed` / `dismissed`. Cây không chọn bên thắng.
- `ConflictBadge` trong `StructureViewShell.tsx`: vàng đậm khi chưa thẩm định, vàng nhạt có tick khi đã Chính xác hoặc Sửa, xám khi đã đánh Sai lệch. Nút cha đang gấp hiện số xung đột bên trong.
- `ConflictNotice.tsx`: banner “N xung đột chưa ai thẩm định”, bấm mở đúng finding.
- `ConflictFindingReview.tsx`: HITL trên finding, timeline, tên và email người duyệt.
- `findingReview.ts`, `reviewerLabel.ts`, `timeline.ts`.
- `SearchCitationReview.tsx` bản code-full dài hơn: thấy xung đột neo vào nút và nhảy sang màn đối soát.
- `DossierStructurePage.tsx`: cây nhận `markers`. Header có số xung đột còn mở.

Chỉ có trên nhánh hiện tại:

- `conflictCite.ts` +15: `sameFileCitationSides`. Thân và phụ lục cùng một file vẫn là hai trích dẫn.
- `ClauseConflictPage.tsx` +272 / −96: mỗi phía là nút bấm, nhảy tới trang của phía đó. Ba nút Chính xác / Sai lệch / Sửa nằm trên thẻ, không chạy ngược lên cây.
- `DossierStructurePage.tsx`: danh sách hit search là nút “mở và đánh giá”. `SearchCitationReview` mở cả khi câu không khớp nút cây. Cây chỉ gom `clauseIds` thành sao “chỗ cần kiểm tra”, không có chấm vàng/xám.
- `analysis.ts` +62, `ContextFindingsPanel.tsx` +6, `DynamicCitationViewer.tsx` +48, `CitationPane.tsx` +79: màn phân tích và viewer trích dẫn của nhánh hiện tại.

## Cách ghép

Lấy `5e8d2c6` vào nhánh hiện tại nếu cần chấm xung đột trên cây và timeline người duyệt. Giữ nguyên pipeline AI2, fact dòng OCR, grounding, và hai nút trích dẫn cùng file. Ba file sẽ đụng nhau: `ClauseConflictPage.tsx`, `DossierStructurePage.tsx`, `SearchCitationReview.tsx`.
