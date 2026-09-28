# Logic xử lý từng tính năng AI2

**Ngày:** 2026-09-28  
**Cách đọc:** mỗi mục là một tính năng. Các bước là thứ tự `if` trong code, không phải mô tả chung.

Đầu vào của mọi tính năng là snapshot AI1 (trang, dòng OCR, `line_id`, bbox). AI2 không nhận `pdf_bytes`. Worker chỉ gọi khi manifest và input AI1 đã có (`worker.py:467`).

## 1. Trích fact trên dòng chữ

Hàm: `_line_nodes` rồi `_labelled_line_facts` (`ai1_snapshot_adapter.py:2036`, `:2208`).

Với mỗi dòng:

1. Dòng trống thì bỏ.
2. Bỏ dấu để so nhãn. Chữ gốc giữ nguyên.
3. `_track_party` (`:2176`): dòng bắt đầu `Bên A/B/C/Y` thì nhớ bên đó. Dòng `4.1.` không có `(Bên X)` thì xóa bên đang nhớ. `Bên A thanh toán` ở giữa câu không đổi bên.
4. `_labelled_line_facts` cộng các nhánh khớp, không loại nhau:

| Nhánh | Điều kiện | Khóa |
|---|---|---|
| Tên | `Tên đơn vị:` khi đang có bên, hoặc tiêu đề `Bên A:` có tên từ 3 ký tự | `party_a` |
| MST | Chữ MST, tối đa 40 ký tự không phải số, rồi 8–14 chữ số. `Bên A` trên cùng dòng thắng bên đang nhớ | `mst_party_a` hoặc `mst` |
| Giá | Có nhãn tổng giá trị / giá hợp đồng / tổng cộng, và có `đồng` hoặc `vnd`. Lấy cụm số | `contract_value` |
| Hàng bảng | Nhánh giá không ra, dòng bắt đầu `Tổng cộng` hoặc `Tổng giá trị`, số cuối từ 6 chữ số | `contract_value` |
| Lịch thanh toán | Dòng `4.2.` có `thanh toán` và ít nhất một `%`, hoặc có `thanh toán` và từ hai `%` | `payment_schedule` = cả dòng |
| Phương thức / thời hạn | Có nhãn và dấu `:`, và chưa lấy lịch ở trên | phần sau dấu `:` |

5. Dòng chỉ có chữ `Tổng cộng` thì lấy số dạng `49.900.000` ở dòng kế (`_amount_after_total_label`, `:2094`). Dòng số đó bị đánh đã dùng.
6. Không nhánh nào khớp: giữ dòng loại `CLAUSE` hoặc `UNNUMBERED_BLOCK`, không khóa fact.
7. Khớp: mỗi cặp `(khóa, giá trị)` là một nút `FIELD`.

`run_idp` chỉ gọi `FactExtractor.extract` khi router trả `FIELD` và nút chưa có fact (`idp.py:176-179`). Nút thường không vào extractor.

## 2. Chuẩn hóa giá trị

Hàm: `FactExtractor._normalize` (`fact.py:83`). Gặp nhánh đầu thì dừng.

1. Alias trong hồ sơ bên thuê → `L0`.
2. Cả chuỗi là số hoặc số phần trăm → bỏ `%`, `L0`.
3. Số cụm ba chữ số (`1.000.000.000`) → chỉ còn chữ số, `L0`.
4. Có `đồng` hoặc `vnd`, không có `%`, có chữ số → chỉ còn chữ số, `L0`.
5. Cụm thang số viết chữ → `L0`.
6. Không nhánh nào ra và LLM được cấu hình: gọi `complete_json`. `normalized` phải là một chuỗi cùng ngôn ngữ. Object hoặc chuỗi rỗng thì bỏ, provenance giữ `L0` (`fact.py:112-119`). Không có LLM thì `normalized` là `None`.

## 3. Cổng chữ với trang

Hàm: `GroundingGate.ground_fact` (`grounding.py:12`).

1. Chữ gốc hoặc đoạn trích nằm đúng trong trang, và fact chưa `BLOCKED`.
2. Câu đã chuẩn hóa không còn là đoạn của trang, và không phải số thuần rút từ cùng số tiền → `NEEDS_REVIEW` (`:16-18`, `:177-187`).
3. Ngược lại → `PASS`.
4. Không khớp đúng nhưng gần (ngưỡng 0,86) → `NEEDS_REVIEW`.
5. Alias của hồ sơ có trong trang → `NEEDS_REVIEW`.
6. Chỉ câu chuẩn hóa nằm trong trang → `NEEDS_REVIEW`.
7. Không khớp gì → `INSUFFICIENT_EVIDENCE`.

## 4. Ô bảng

Hàm: `TablePipeline.extract` (`table.py:42`).

1. Không tìm được cột tiền trong header → trả danh sách rỗng.
2. Bỏ hàng header, hàng chú thích (`Lưu ý:`, `Ghi chú:`), hàng lại là một header.
3. Ô tiền trống hoặc `None` → fact `raw_value = "MISSING"`, `normalized_value = None`, `NEEDS_REVIEW`. Không ghi `0` (`:74-89`).
4. Ô có chữ → fact L0, hoặc L2 nếu mã sửa ô do LLM viết.

## 5. So hai fact cùng mục

Hàm: `compare_facts` (`compare.py:42`) rồi `_pair` (`:220`).

Nhóm theo `item_key`. Bỏ fact định danh. MST người bán không vào nhóm so.

Ghép (`_pair_two_sources`, `:101`):

1. Có thân và phụ lục: mỗi giá trị phụ lục ghép với một đại diện thân. Cùng một file thì được ghép. Hai file khác nhau chỉ ghép khi đã có cạnh quan hệ (`:152-157`).
2. Thân có từ hai giá trị khác nhau: thêm một cặp trong thân.
3. Chỉ có thân, từ hai giá trị: một cặp.
4. Từ hai phụ lục, không có thân: `NOT_COMPARABLE`, chữ “không chọn phụ lục nào thắng”.

`_pair` dừng ở nhánh đầu:

1. Khác tiền tệ, hoặc VND với USD → `NOT_COMPARABLE`. Không quy đổi.
2. Khác `scope` → `NOT_COMPARABLE`.
3. Khác điều kiện → `NOT_COMPARABLE`.
4. Hai phụ lục khác số → `NOT_COMPARABLE`.
5. Chữ nguồn có mẫu sửa/thay và không phải cặp phụ lục–phụ lục → `CANDIDATE_AMENDMENT`. Không xác nhận hiệu lực.
6. Một bên có kỳ, bên kia không → `NEEDS_EVIDENCE`. Không lấy bên tải sau.
7. Cả hai ra được số tiền. Bằng nhau → `COMPARABLE_MATCH`, `PASS`. Khác nhau → `COMPARABLE_DIFFERENCE`, `NEEDS_REVIEW`.
8. Không ra số nhưng chuỗi chuẩn hóa bằng nhau → khớp. Khác → khác.
9. Không có giá trị chuẩn hóa → `NEEDS_EVIDENCE`.

Tiền so bằng `Decimal`, không dùng float (`money_decimal`, `:24`).

## 6. So điều khoản thân với phụ lục

Hàm: `compare_clauses_across_files` (`clause_compare.py:129`).

1. Dựng dàn ý từng file: tiêu đề Điều, rồi các khoản. Dòng lặp ở đầu/cuối trang và dòng nhiễu bị bỏ.
2. Ghép điều cùng số hoặc cùng tiêu đề (`_align_articles`).
3. Trong một điều, ghép khoản (`_align_units`).
4. `_compare_units` (`:399`) chỉ nhìn số có đơn vị (`%`, ngày, đồng, …). Cùng đơn vị mà danh sách số khác → một cặp `COMPARABLE_DIFFERENCE`.
5. Không khác số, hoặc không dựng được citation có offset và `line_id` → không ra cặp.
6. Lý do ghi hai nguồn và câu máy không kết luận bên thắng (`:437-440`).

## 7. Phụ lục và chú thích chưa xác nhận

Hàm: `build_contract_context` (`contract_context.py:72`).

1. Trang chỉ thành phụ lục khi một dòng bắt đầu bằng `PHỤ LỤC <số>`. Nhắc phụ lục trong một câu không đổi cả phần còn lại của hợp đồng (`:80-83`).
2. File khai `role = annex` là cả một phần phụ lục. Không gộp với thân chỉ vì trùng số trang (`:87-89`).
3. `Phụ lục 1` và `PHỤ LỤC 01` là cùng số (`_annex_key`, `:63`).
4. Đã có fact thân và fact phụ lục cùng `item_key`, nhưng thân không dẫn chiếu số phụ lục → ghi `relation: UNCONFIRMED` kèm hai `fact_id` (`_unconfirmed_value_pair`, `:40-59`). Cặp so ở mục 5 vẫn còn.
5. Citation của phần ngữ cảnh chỉ được giữ khi `CitationResolver.verify` trả valid (`:378-388`). Citation trang lấy dòng OCR không rỗng đầu tiên, có offset (`_page_citation`, `:416`). Không có dòng thì không có citation.

## 8. Sự kiện trên dòng

Hàm: `extract_contract_events` (`contract_events.py:49`).

1. Bỏ nút `FIELD` và nút không dựng được citation.
2. Với mỗi loại trong `EVENT_RULES`, dòng phải chứa một từ của loại đó.
3. `PARTY_DECLARATION` chỉ khi một dòng bắt đầu bằng `Bên A` hoặc `Tên đơn vị` (`_party_heading`, `:39`). Câu `Bên A thanh toán` không thành sự kiện bên.
4. Một nút một loại chỉ một sự kiện. Tối đa 256 sự kiện.
5. Ngày chỉ là chữ bắt được trên dòng (`date_signals`). Không suy ra ngày lịch.

## 9. Cờ biên, không bịa điều

Hàm: `dossier_edge_issues` (`edge_flags.py:26`).

1. Các tiêu đề `Điều N` dưới cùng cha. Thiếu số ở giữa → cờ `NUMBERING_GAP`. Không tạo điều bị thiếu (`:35-50`).
2. Trang bắt đầu bằng token `HEADER ` hoặc `FOOTER ` → cờ, không nối câu qua furniture (`:54-59`).
3. Cặp song ngữ và định nghĩa bị sửa thành cờ. Cờ định nghĩa ghi không chọn bên thắng (`:83`).

## 10. Cây kết quả

Hàm: `enrich_result_structure` (`result_structure.py:20`).

1. Copy từng nút (`model_copy`). Không ghi đè nút AI1 (`:1`, `:23`).
2. Nhãn `Trang 1/20` hoặc mã hợp đồng lặp bị loại khỏi chữ điều (`_is_running_furniture`, `:9`).
3. Bảng nối trang xử lý ở module này và `table_headers`: header kế thừa được gắn cờ cần rà, không nuốt hàng dữ liệu.

## 11. Hỏi trên hồ sơ

Hàm: `FourLayerReasoner.run` (`reasoning/stack.py:30`).

1. Danh sách thành viên được chọn có id lạ → `BLOCKED`, không trả lời (`:41-49`).
2. Câu không khoanh vùng, hoặc chính sách bật vector → bỏ lối tắt L0 (`:58-62`).
3. L0 trả được câu từ quy tắc và khóa có cấu trúc → đưa thẳng L3, không gọi L2 (`:64-80`).
4. L1 lấy tối đa các đoạn đã khóa. Bị chặn → L3 `BLOCKED`.
5. Câu hỏi so sánh mà L1 không có hit → `INSUFFICIENT_EVIDENCE`, câu “không suy đoán từ toàn bộ outline” (`:100-106`).
6. L2 chỉ khi loại câu là so sánh, câu không quá rộng, và (`egress_allowed` cùng `use_llm`) hoặc lời gọi cũ không mang cờ (`:118-128`).
7. L3 gắn trạng thái và citation. Không có nguồn thì không bịa câu trả lời.

## 12. Việc cố ý không chạy

`contract_profiles.py` có sáu loại hợp đồng. Pipeline trích xuất không import file đó. Mọi hồ sơ đi một bộ nhãn ở mục 1.

## Nguồn trong code

- `ai-service/app/pipeline/ai1_snapshot_adapter.py:2036-2236`
- `ai-service/app/pipeline/fact.py:25-128`
- `ai-service/app/pipeline/grounding.py:12-31` và `:177-187`
- `ai-service/app/pipeline/table.py:42-89`
- `ai-service/app/pipeline/compare.py:42-379`
- `ai-service/app/pipeline/clause_compare.py:399-440`
- `ai-service/app/pipeline/contract_context.py:40-118` và `:378-445`
- `ai-service/app/pipeline/contract_events.py:39-96`
- `ai-service/app/pipeline/edge_flags.py:26-59`
- `ai-service/app/pipeline/result_structure.py:1-24`
- `ai-service/app/reasoning/stack.py:30-128`
- `ai-service/app/pipeline/idp.py:172-183`
- `docs/ai2/AI2-DOC-02-brd.vi.md:24-58`
