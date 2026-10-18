# PR #125: sửa các điểm review (2026-10-18)

Nhánh `feature/ai2-contract-graph`, sửa tại chỗ, **chưa commit/push**. Không có lời gọi LLM/OpenAI/Mistral nào.

## Tổng kết cổng kiểm tra

| Cổng | Kết quả |
|---|---|
| ai-service, toàn bộ suite `-m "not live"` (AI2_REQUIRE_DATABASE=false) | **2487 passed, 3 skipped**, 0 failed (7m06s) |
| Chạy lại sau `ruff format`: test mới, paragraph nodes, golden flag-off, golden pairs, process isolation | 81 passed |
| backend `tests/unit` | **800 passed** |
| backend integration: query gate, fe_reported_fixes, query_history, consent | 51 passed. 3 test trong `test_clause_frame_review_flow.py` lỗi do môi trường: thiếu `AI2_FRAME_TEST_DATABASE_URL` (cần Postgres riêng). Lỗi này có từ trước, không do thay đổi lần này |
| ruff check, các file đã sửa | All checks passed |
| ruff format | Đã format các file mới/đã sửa. `citations.py`/`outline.py` vốn đã chưa format từ trước, tôi không format lại cả file để tránh diff nhiễu |
| Golden | `test_contract_graph_flag_off_regression` và `test_contract_graph_pairs_flag_regression` vẫn pass, nên **golden không đổi** |

Kết quả RED (trên code cũ, trước khi sửa): `tests/test_pr125_review_fixes.py` có **23 failed, 13 passed**. Danh sách test đỏ lưu ở `C:\Users\dungs\.claude\jobs\ad849255\tmp\red.txt`. Backend RED: 2 failed (`be-red.txt`).

Test mới nằm trong `ai-service/tests/test_pr125_review_fixes.py` (36 test) và `backend/tests/unit/test_query_prefers_ai2_over_pinned_semantic.py` (+2 test).

---

## 1a. `_HEADING_ONLY` (frame_context.py)

- **Tái hiện:** có. 3 câu reviewer đưa đều trả `True` (3 test `test_1a_sentences_are_not_headings` đỏ).
- **Sửa:** `ai-service/app/pipeline/frame_context.py:46-67`
  - Thêm `\b` sau số hiệu, nên "chỉnh"/"lớn" không còn bị đọc là số La Mã.
  - Chỉ coi là tiêu đề khi phần chữ sau số hiệu có ≤ 8 từ và không chứa vị ngữ (`có|được|phải|sẽ|chịu|kể từ|do|bị|không`).
- **Test:** 3 câu reviewer đưa phải trả False. Các câu sau vẫn phải là heading (True): "Điều 15. Hiệu lực hợp đồng", "Điều 5. Thanh toán", "ĐIỀU 3. QUYỀN VÀ NGHĨA VỤ CỦA CÁC BÊN", "Chương IV. Điều khoản chung", "Mục 2".
- **Golden:** không đổi.

## 1b. `conflict_no_value_difference` (pair_classifier.py)

- **Tái hiện:** có. 3 cặp đều bị reject (3 test đỏ).
- **Sửa:** `ai-service/app/pipeline/contract_graph/pair_classifier.py:255-283`. Bộ lọc chỉ áp dụng khi `_wording(a) == _wording(b)`, tức phần chữ đã bỏ nhãn, con số, hoa/thường và dấu câu phải giống nhau. Nếu không, giữ nhãn CONFLICT của model.
- **Test:** 3 cặp của reviewer giữ CONFLICT. Một bản nhắc lại cùng chữ ("05 ngày" và "5 ngày") vẫn bị reject.
- **Thay đổi hành vi có chủ đích:** test cũ `test_conflict_without_any_differing_value_rejected` khẳng định đúng hành vi reviewer báo là sai ("cùng 05 ngày, khác mốc tính"). Tôi tách nó thành 2 test:
  - `test_conflict_on_a_restatement_without_any_differing_value_rejected`: vẫn reject bản nhắc lại.
  - `test_conflict_with_different_wording_is_left_to_the_model`: 2 cặp cũ giờ giữ CONFLICT.
- **Golden:** golden pairs không đổi.

## 1c. `_cites` (pair_candidates.py)

- **Tái hiện:** có. "theo khoan 4.21 cua hop dong" trả True.
- **Sửa:** `ai-service/app/pipeline/contract_graph/pair_candidates.py:172`, đổi lookahead thành `(?!\d|\.\d)`.
- **Test:** "4.21" → False, "4.2" → True, "4.2.1" → False, "theo khoan 4.2" ở cuối chuỗi → True.
- **Golden:** không đổi.

## 1d. Các điểm "đọc code, chưa chạy thử": tôi tái hiện bằng test trước khi sửa

| Điểm | Tái hiện? | Sửa | Test |
|---|---|---|---|
| `compare.py:182` khóa theo đợt | **Có**, cả 2 ý. (1) "tạm ứng 30%" có khóa `None`, không vào nhóm `Đợt 1`, nên `compare_facts` không tạo cặp. (2) Câu "đợt 1: 30%; đợt 2: 40%" gán 40% vào đợt `1` | `compare.py:183-228`. `_installment` lấy "đợt N" gần nhất đứng trước giá trị; nếu không xác định được giữa nhiều đợt thì để không gán đợt. `_share_unmarked_installments` đưa fact không có đợt vào mọi nhóm đợt của cùng item. Bỏ trùng ứng viên theo cặp fact (`compare.py:110-119`). Chỉ áp dụng khi `split_installments` (pairs bật), nên đường flag-off giữ nguyên byte | `test_1d_split_groups_receive_unmarked_facts`, `test_1d_multi_installment_sentence_...`, `test_1d_unmarked_advance_...` |
| `ask_intent.py:160` "khác nhau" | **Có.** "Điều 5 hợp đồng và Phụ lục 1 khác nhau thế nào?" trả `unscoped` (trên develop là `compare`) | `ask_intent.py:160-167`. Nhánh synthesis bỏ qua câu hỏi có từ so sánh và có nguồn được nêu (giống điều kiện của nhánh compare). Các câu #121 ("Mỗi đợt…", "Tóm tắt…") vẫn là `unscoped` | `test_1d_khac_nhau_with_a_source_stays_compare` (2 câu), cùng `test_ask_intent_synthesis.py` hiện có |
| `pair_classifier.py:494` CONFLICT có span lệch bị đổi thành REFERENCE | **Có.** CONFLICT/DUPLICATE có span không ground trên cặp có dẫn chiếu rõ thì thành quyết định REFERENCE, và stat reject bị trừ lại. Trên develop, cặp này là validator reject và được tính `pairs_unclassified` | `pair_classifier.py:629-636`. Chỉ fallback sang REFERENCE khi nhãn model không phải CONFLICT/DUPLICATE. Lưu ý: dù sửa hay không, CONFLICT có span lệch vẫn không thể thành finding vì span không có trong văn bản. Bản sửa làm nó hiện ra ở dạng "chưa phân loại" thay vì REFERENCE | `test_1d_conflict_with_off_span_is_not_relabelled_reference` (CONFLICT, DUPLICATE) |
| `frame_context.py:340` batch 8 frame dùng `max_output_tokens` của 1 frame | **Có.** Lời gọi gửi `bounds.max_output_tokens` cho 8 frame | `frame_context.py:348-350`: `min(bounds.max_output_tokens * len(batch), 8192)`, với 8192 là trần `ContextBounds`. Lưu ý: profile production đã đặt 8192 nên trên prod giá trị không đổi. Bản sửa có tác dụng với profile có giá trị theo frame thấp hơn | `test_1d_slot_batch_output_budget_scales_with_frames` |
| `main.py:304` lease (ngân sách + 30s) hết trước khi kill (ngân sách + 60s) | **Có.** Worker claim với `lease_ms = 330000` khi ngân sách 300s, nhỏ hơn mốc kill 360000 tính từ lúc spawn | `app/api/main.py:341-350, 499`: `_job_lease_ms = (ngân sách + 60 + 30) * 1000`, nên lease còn hiệu lực khi tiến trình con bị kill và job ghi `PROCESSING_TIMEOUT`. Đánh đổi: sweep phát hiện replica chết thật chậm hơn 60s | `test_1d_job_lease_outlives_the_isolated_child_kill`, `test_1d_worker_claims_with_the_long_lease` (chạy `_execute_wire_job` thật trên SQLite) |

**Golden:** không đổi ở cả 5 điểm.

## 2. OCR/bbox của AI1 (`ai1_snapshot_adapter._line_nodes`)

- **Không cần đổi hợp đồng dữ liệu AI1↔AI2.** Chỉ sửa trong adapter của AI2. Text và bbox của AI1 (`page.text`, `page.line_texts`, `page.line_bboxes`) không bị ghi đè.
- **Tái hiện:**
  - Khi snapshot AI1 có `text` riêng với dấu ngăn dòng `"\r\n"` hoặc `" "`, text của node ghép (nối bằng `"\n"`) **không** phải chuỗi con của `page.text`. Citation của frame evidence không có `char_start` nên không VALID.
  - Với `"\r\n"`, `citation_for_node` cắt lệch offset vì `_span_for_line_ids`/`_line_ranges` giả định mỗi dấu ngăn dòng dài đúng 1 ký tự.
  - Citation của node ghép không mang bbox từng dòng.
  - Có thêm 2 test đỏ do lỗi trong chính test (`SemanticCitation` không subscript được), đã sửa test. Test chuỗi con và test bbox là RED thật.
- **Sửa:**
  - `citations.py:129-156`: `line_offsets(page)` định vị từng dòng trong `canonical_page_text` theo thứ tự đọc, không giả định dấu ngăn dòng. `_line_ranges` dùng hàm này. `node_line_fragments` trả bbox từng dòng do AI1 cung cấp.
  - `ai1_snapshot_adapter.py:2564-2700`:
    - Text của node ghép được **cắt từ chính page text**: `page_text[đầu đoạn : cuối dòng mới]`.
    - Chỉ ghép khi giữa hai dòng chỉ có khoảng trắng và cả hai dòng định vị được.
    - `node.bbox` chỉ là khung bao; bbox từng dòng vẫn ở `page.line_bboxes` / `source_line_ids`.
  - `outline.py:183-190`:
    - `citation_for_node` gắn `bbox_fragments` bằng đúng bbox từng dòng của AI1 khi node có nhiều dòng.
    - `_span_for_line_ids` dùng `line_offsets`.
- **Test:**
  - Dấu ngăn dòng `None`, `"\n"`, `"\r\n"`, `" "`: text node ghép là chuỗi con chính xác; citation VALID và `text_span == node.text`; frame evidence VALID.
  - bbox từng dòng của node ghép bằng đúng giá trị AI1 trả về, `bbox_fragments` bằng các bbox đó, `node.bbox` là khung bao.
  - Trên **snapshot AI1 thật có sẵn trong repo** (`ai1/examples/dossier-001/{contract-001,annex-001}/*.json`):
    - `page.text`, `line_texts`, `line_bboxes` giữ nguyên so với snapshot (`bbox_normalized`).
    - Mọi node có text là chuỗi con và citation VALID.
- **Giới hạn cần nói rõ:**
  - Không snapshot AI1 thật nào trong repo đi qua nhánh ghép dòng. Các snapshot này có `nodes` cấu trúc riêng của AI1. Kết quả trên develop và trên nhánh này giống hệt nhau: một node `_unnumbered_1` gồm 12 dòng, đến từ AI1 chứ không do PR tạo ra.
  - Vì vậy test ghép dòng dùng dòng tổng hợp theo đúng format snapshot.
  - Trên đường BE→AI2, schema cấm `pages[].text` (`Additional properties are not allowed ('text' was unexpected)`), nên page text luôn được nối từ các dòng bằng `"\n"`. Rủi ro reviewer nêu chỉ xảy ra trên đường `adapt_snapshot`/batch.
- **Golden:** không đổi.

## Chuongpham2004 #1: AI2 `/query` và `snapshot_digest`

- **Hiện trạng AI2** (`app/api/main.py:1234-1395`):
  - `/query` **có** ràng buộc vào `snapshot_digest` hiện hành. Digest lệch thì trả `INSUFFICIENT_EVIDENCE`, không có citation.
  - Citation lấy từ registry của bản snapshot đó, kèm `validation_status` do `CitationResolver` tính (offset khớp chính xác, `source_hash`, `quote_sha256`).
  - **Nhưng** AI2 không loại citation không VALID (`_enrich_citations` vẫn trả chúng ra), và backend chỉ chạy `enforce_result_acl`.
- **Sửa (backend):** `backend/src/contract_intelligence/api/v1/dossiers.py`
  - Với hồ sơ có semantic (`semantic_extension` khác None) và ACL `passed`, mọi citation của câu trả lời phải qua `verify_citation`, dùng `_canonical_citation_item` (cùng DTO lúc lưu).
  - Citation bị từ chối thì bị loại. Nếu có citation bị loại thì giữ lại câu trả lời, `state=BLOCKED`, code `BACKEND_CITATION_UNVERIFIED`, giống cách xử lý khi ACL lọc citation.
  - Hồ sơ chưa có semantic giữ nguyên hành vi cũ, theo đúng phạm vi reviewer nêu.
- **Test:** `test_semantic_dossier_answer_keeps_only_guard_verified_citations`, `test_semantic_dossier_answer_with_a_forged_citation_is_withheld`. Cả hai RED trước khi sửa, xanh sau khi sửa.

## Chuongpham2004 #3: ký tự nối ô bảng

- **AI1 nối mọi dòng bằng `"\n"`, kể cả ô bảng** (`ai-service/src/contract_ocr/application/use_cases/build_snapshot.py:262-266`: `page_cursor = end + 1  # account for the "\n" joiner`).
- Mỗi ô bảng là một dòng OCR. Snapshot thật cho thấy đúng như vậy: `"STT\nHang muc\nSo luong\n1\nDich vu A…"`.
- Hàng bảng dạng `| a | b |` hoặc có tab nằm **trong** một dòng, nên không tạo khoảng cách giữa hai dòng.
- **Kết luận:** không lệch, nên không sửa `citation_guard.py`.
- Điểm phụ (span bắt đầu/kết thúc đúng tại ký tự xuống dòng) chưa được giao sửa, nên tôi giữ nguyên.

---

## Bản nháp trả lời trên PR (tiếng Việt)

**@nguyenddung, 1a `_HEADING_ONLY`:**
> Đã sửa ở `frame_context.py:46-67`. Thêm `\b` sau số hiệu, và chỉ coi là tiêu đề khi phần sau số hiệu ≤ 8 từ và không có vị ngữ (có/được/phải/kể từ…). Đã thêm test cho đúng 3 câu bạn đưa (giờ trả False). "Điều 15. Hiệu lực hợp đồng", "Điều 5. Thanh toán", "Chương IV. Điều khoản chung" vẫn là tiêu đề.

**@nguyenddung, 1b `conflict_no_value_difference`:**
> Đã sửa ở `pair_classifier.py:255-283`. Bộ lọc chỉ áp dụng khi phần chữ ngoài con số giống hệt nhau; nếu không thì giữ CONFLICT của model. 3 cặp bạn nêu (30 ngày làm việc/30 ngày, Bên A/Bên B 8%, nghiệm thu/giao hàng) đã có test, giờ đều giữ CONFLICT. Test cũ khẳng định "cùng 05 ngày nhưng khác mốc thì reject" được đổi theo hướng bạn đề xuất.

**@nguyenddung, 1c `_cites`:**
> Đã đổi lookahead thành `(?!\d|\.\d)` (`pair_candidates.py:172`). Test: `4.21` → False, `4.2` → True, `4.2.1` → False.

**@nguyenddung, 1d:**
> Mình đã viết test tái hiện từng ý trước khi sửa, cả 5 ý đều tái hiện được:
> - `compare.py`: fact không ghi đợt ("tạm ứng 30%") giờ được so với mọi đợt cùng item. Câu nhắc nhiều đợt thì mỗi giá trị lấy đợt đứng ngay trước nó. Chỉ áp dụng khi bật pairs, golden flag-off không đổi.
> - `ask_intent.py`: câu có "khác nhau" kèm điều/phụ lục/hợp đồng quay lại `compare`.
> - `pair_classifier.py`: CONFLICT/DUPLICATE có span lệch không còn bị đổi thành REFERENCE; chúng được tính là chưa phân loại như trên develop. Lưu ý: span lệch thì dù sao cũng không thành finding được.
> - `frame_context.py`: `max_output_tokens` của mỗi lần gọi = giá trị cho 1 frame × số frame, tối đa 8192. Profile prod đang ở 8192 nên trên prod không đổi.
> - `main.py`: lease = ngân sách + 60s (thời gian chờ trước khi kill) + 30s, nên job treo bị kill và ghi `PROCESSING_TIMEOUT` trước khi sweep kịp ghi `AI2_WORKER_RESTARTED`.

**@nguyenddung, 2 OCR/bbox:**
> PR không đổi hợp đồng dữ liệu AI1↔AI2, và AI2 không ghi đè text hay bbox của AI1:
> - Node ghép giờ cắt text từ chính `page.text`, nên vẫn khớp khi AI1 dùng dấu ngăn dòng khác `"\n"`. Chỉ ghép khi giữa hai dòng chỉ có khoảng trắng.
> - `node.bbox` chỉ là khung bao. Citation của node ghép mang `bbox_fragments` đúng bằng bbox từng dòng của AI1 (`page.line_bboxes` qua `source_line_ids`).
> - Test với dấu ngăn dòng `\n`, `\r\n`, dấu cách, và trên snapshot AI1 thật trong `ai1/examples/dossier-001`: text, `line_texts`, `line_bboxes` giữ nguyên, mọi citation VALID.
> - Lưu ý: hai snapshot này dùng `nodes` của AI1 nên không đi qua nhánh ghép dòng, vì vậy phần ghép được test bằng dòng tổng hợp cùng format.
> - Trên đường BE→AI2, schema không cho gửi `pages[].text`, nên page text luôn là các dòng nối bằng `"\n"`.
>
> Về đề xuất tách PR, mình để Lead quyết.

**@Chuongpham2004, #1 citation trên `/query`:**
> AI2 `/query` có bind vào `snapshot_digest` hiện hành (lệch digest thì trả `INSUFFICIENT_EVIDENCE`), và citation có `validation_status` từ `CitationResolver`. Nhưng AI2 không loại citation không VALID, nên mình đã thêm bước ở backend: với hồ sơ có semantic, mọi citation của câu trả lời đi qua `verify_citation` (dùng chung DTO `_canonical_citation_item` với lúc lưu). Citation không khớp OCR bị loại, và câu trả lời bị giữ lại (`BLOCKED`, `BACKEND_CITATION_UNVERIFIED`) như khi ACL lọc citation. Đã có test.

**@Chuongpham2004, #2 `reasoning_effort=low`:**
> Điểm này cần Lead ghi một dòng đồng ý trên PR theo `DEC-BE-AI2-01`; mình không đổi code.

**@Chuongpham2004, #3 ký tự nối ô bảng:**
> AI1 nối mọi dòng bằng `"\n"`, kể cả ô bảng: `build_snapshot.py` có `page_cursor = end + 1  # account for the "\n" joiner`, và mỗi ô bảng là một dòng OCR. Snapshot mẫu `ai1/examples/...contract-001` cho thấy `"STT\nHang muc\nSo luong…"`. Hàng bảng dạng `| a | b |` hoặc có tab nằm trong một dòng. Vì vậy việc chèn `"\n"` ở khoảng cách 1 ký tự là khớp, không cần sửa. Trường hợp span bắt đầu/kết thúc đúng tại ký tự xuống dòng mình ghi nhận là hiếm và chưa sửa ở PR này.

**@Chuongpham2004, #4 và #5:**
> Ghi nhận. 409 `CURRENT_RUN_CHANGED` sau khi đã tính tiền LLM và 502 khi AI2 không trả lời là đánh đổi đã chấp nhận ở #121; PR này không đổi.

## Câu hỏi còn mở

1. Ngưỡng tiêu đề (≤ 8 từ, danh sách vị ngữ) là heuristic. Có cần thêm mẫu tiêu đề thật từ hồ sơ prod không?
2. Lease dài thêm 60s làm sweep phát hiện replica chết chậm hơn 60s. Có chấp nhận được không?
3. Guard citation ở backend hiện chỉ áp dụng cho hồ sơ có semantic. Có muốn mở rộng cho mọi hồ sơ không? Nếu mở rộng thì phải sửa các mock test hiện thiếu offset.
4. Trong lúc tôi làm, có người khác commit `e8d9c80b` vào frontend. Tôi không đụng `ProcessingTimeline.tsx`.
