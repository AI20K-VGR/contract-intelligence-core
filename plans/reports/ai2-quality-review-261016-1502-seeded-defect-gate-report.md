# Đánh giá chất lượng luồng AI2 bằng hồ sơ cài lỗi (HD-TEST-2026-001)

Ngày: 2026-10-16 · Nhánh: `feature/ai2-contract-graph` (chưa commit)

## 1. Vì sao cần cổng này

"Sinh được N cạnh" không chứng minh graph đúng. Trên hồ sơ mẫu, job cũ có 13 cạnh nhưng 2 cạnh là chân trang, cặp lặp 1.1≡1.3 bị bỏ sót, còn xung đột thanh toán cố ý (5.2 "07 ngày" ↔ PL02 §1 "10 ngày") không tầng nào báo được. Tiêu chí mới: **kỳ vọng ⊆ kết quả, cấm ∩ kết quả = ∅**, và báo được kỳ vọng bị rơi ở tầng nào.

## 2. Cổng mới

| Thành phần | Đường dẫn | Chạy |
|---|---|---|
| Fixture tổng hợp + gold | `ai-service/fixtures/seeded/hd_test_2026_001.py` | văn bản hư cấu theo đúng từng dòng OCR (kể cả dòng bị ngắt và chân trang); id/tenant/chữ ký giả |
| Funnel (ghi lại từng tầng) | `ai-service/fixtures/seeded/funnel.py` | dùng chung cho offline và live |
| Cổng offline (tất định) | `ai-service/tests/test_seeded_hd_test.py` | mỗi PR, không mạng |
| Cổng live (classifier LLM) | `python -m fixtures.seeded.run_live --repeats 3` | khi đổi prompt/model; tốn phí |

Kỳ vọng offline: 4 cạnh luồng 1, slot thời hạn của 5.2/PL02 §1/6.1, 2 ứng viên phải lọt top-K (1.1↔1.3, 4.1↔PL01 2.1), chân trang không bao giờ thành ứng viên, số hiệu điều khoản không phải "giá trị". Kỳ vọng live: CONFLICT 4.1↔PL01 2.1, DUPLICATE 1.1↔1.3, REFERENCE 3.2→5.2 và 3.3→6.1; cấm DUPLICATE trên chân trang.

## 3. Kết quả

| Kỳ vọng | Trước | Sau |
|---|---|---|
| Cổng offline | 6/12 đạt | **19/19 đạt**, 4 xfail có chủ đích (mục 5) |
| Live: CONFLICT 4.1↔PL01 2.1 | 3/3 | 3/3 |
| Live: DUPLICATE 1.1↔1.3 | không lọt top-K | **3/3** |
| Live: REFERENCE 3.2→5.2, 3.3→6.1 | 3/3 | 3/3 |
| Live: DUPLICATE chân trang (cấm) | 2 cạnh | **0** |
| `CLOSED_SYMBOL` trên job 13:22 (offline) | 18 cặp | 8 cặp |

Bộ test ai-service: 1890 passed, 3 skipped, 4 xfailed. Còn 1 test fail, `test_a8_env_flags::test_slow_query_llm_returns_retrieval_answer_within_deadline`, nhưng nó **vẫn fail khi đã cất toàn bộ thay đổi**: lỗi môi trường có sẵn (≈10,7 s nằm ở ghi file/chờ thread).

## 4. Lỗi đã sửa (TDD: test đỏ trước, xanh sau)

| # | Lỗi | Tầng | Sửa |
|---|---|---|---|
| 1 | OpenAI trả 400 khi prompt JSON mode thiếu chữ "json"; 12 lời gọi slot/alias hỏng, đốt hết budget 20/20 | client | `app/llm/client.py` `_json_mode_messages`; prompt ở `frame_context.py`, `tenant_aliases.py` |
| 2 | Trace ghi "Đã hoàn tất · 0 mục" khi classifier lỗi | trace | `app/pipeline/idp.py` `_pairs_reason_code` → `PARTIAL_<lý do>` |
| 3 | Không log được loại lỗi provider | runtime | `app/pipeline/runtime.py` `_log_provider_failure` (`ai2.llm_call_failed`), chỉ ghi identifier |
| 4 | Tiêu đề "Điều 5. Thanh toán" thành frame `PAY` | semantic | `frame_context.py` `_is_heading_only` |
| 5 | "trong vòng 07 ngày" không trích được thời hạn | semantic | `frame_extraction.py` regex deadline |
| 6 | Câu trần thuật "Bên A thanh toán…" có modality UNKNOWN nên mọi cặp bị BACKOFF | semantic | `frame_extraction.py`: `REQUIRED` + `reason="declarative_obligation"`; câu có rào đón (không/chưa/được/quyền/có thể) vẫn UNKNOWN |
| 7 | Thiếu trigger "kể từ ngày nhận hóa đơn" | semantic | `_payment_trigger` → `INVOICE` |
| 8 | Điều khoản PAY chỉ nói thời hạn bị đòi số tiền | semantic | extractor ghi `amount/unit` = ABSENT khi văn bản không còn số nào (sau khi bỏ số thứ tự, dẫn chiếu, thời hạn); comparator coi đó là điều khoản thời hạn. Phản chứng: số không đọc được vẫn UNKNOWN; hai đợt thanh toán khác tiền không thành DUPLICATE |
| 9 | Chân trang thành ứng viên/DUPLICATE | pairs | `pair_candidates.py` `_page_furniture`: dòng không đánh số, lặp trên ≥ 2 trang **cùng file** |
| 10 | 1.1≡1.3 bị cắt khỏi top-K | pairs | thưởng điểm gần trùng (Jaccard ≥ 0,85) trong xếp hạng core |
| 11 | `VALUE_MISMATCH` coi số hiệu điều khoản là giá trị, và so "07 ngày" với "02 bản" | pairs | bỏ số thứ tự/địa chỉ; so số theo đơn vị đi kèm |
| 12 | Validator chặn DUPLICATE đúng của LLM vì "1.1"/"1.3" | classifier | `pair_classifier.py` `_LINE_LABEL` bỏ được nhãn nhiều cấp; phản chứng 1,5% ≠ 2,5% vẫn bị chặn |

Quan sát thêm: `coverage.contract_graph.pairs` có `excluded_page_furniture` và `near_duplicate_kept`. `CANDIDATES_VERSION` nâng lên `pairs-cand-v6`.

## 5. Lỗ hổng còn lại, xếp theo mức độ

1. ~~**P0, cấu trúc: mỗi dòng OCR là một node**~~ **Đã xử lý** (`plans/261016-1524-ai2-paragraph-nodes/plan.md`): node đoạn văn ghép các dòng bị ngắt; 07→10 ngày giờ là `COMPARABLE_DIFFERENCE` trên OCR thật. Mô tả gốc: (`ai1_snapshot_adapter._line_nodes`). Mọi điều khoản xuống dòng đều bị cắt (4.1, PL02 §1, 1.1…). Vì vậy thay đổi 07→10 ngày vẫn chưa tới bước review trên hồ sơ thật (`test_planted_value_change_reaches_review`, `test_wrapped_clause_is_one_node` để `xfail(strict=True)`). Sửa việc này đổi node id, bbox, citation, bộ phân giải của luồng 1 và golden, nên cần plan riêng.
2. **Luồng 1 nối cạnh sửa đổi nhưng không so giá trị cũ → mới.** UI graph quan hệ cho cặp 5.2↔PL02 §1 hiện "không có quan hệ". Cần quyết định nghiệp vụ: hiện là *sửa đổi kèm 07 → 10* (khuyến nghị) hay *xung đột*.
3. **Luồng 1 xếp PL02 §4 ("theo quy định tại khoản 1 Điều 6") là sửa đổi 6.1**, đúng ra là dẫn chiếu kèm quyền bổ sung. **PL02 §3 ("Khoản 2 Điều 7 không áp dụng…")** không được nhận là giới hạn phạm vi.
4. **Reindex không gửi `semantic_profile`** (job 13:57). Reindex không dựng semantic frame, và Backend không tính lại xung đột: UI giữ bộ xung đột cũ cho tới khi `reprocess`.
5. **`CLOSED_SYMBOL` chưa gộp với `ai2.canonical`/`ai2.context`**, và severity `high` vẫn gắn cho `confidence 0.0`/`not_comparable`.
6. **Giới hạn top-K:** `_CORE_TOP_K_SHARE = 1.0` khiến nguồn exploratory chỉ lấp chỗ thừa (0/19 `VALUE_MISMATCH` được giữ). Chưa chỉnh vì bộ nhãn đã duyệt chỉ có 1 CONFLICT, không đủ đo.
7. **Bộ nhãn eval:** `quality-recovery-manifest.v4` có 600 dòng nhưng chỉ 1 CONFLICT / 2 DUPLICATE đã duyệt. Cần ≥ 30–50 ca dương tính (đột biến có kiểm soát, người duyệt).
8. **Luật DUPLICATE đã đổi nghĩa (mục 4, #12) nhưng `REJECTION_REASON_VERSION` vẫn giữ `pair-rejections-v1`**, vì manifest/báo cáo đã khóa có người duyệt ghi cứng giá trị này. Chủ bộ eval cần quyết định có nâng lên v2 và khóa lại không.
9. **Vận hành:** log mới ghi được `APIConnectionError` và `TimeoutError` (`LLM_TIMEOUT`; 7 lần trong 3 lượt live sau khi ghép dòng, không ảnh hưởng kỳ vọng nào, cần đo xem là lời gọi nào); worker tạo `review_items.created count=1931` cho một hồ sơ nhỏ (chưa điều tra).
10. **Test môi trường:** `test_a8…` (thời gian) và 2 test eval `review_quality_*` (đòi thư mục dữ liệu được git ignore) fail cả khi không có thay đổi.

## 6. Bước tiếp theo đề xuất

1. Plan riêng cho P0 (ghép dòng thành đoạn). Khi xong, 4 xfail sẽ báo XPASS và phải bỏ đánh dấu.
2. Hiện giá trị cũ → mới trên cạnh luồng 1 (sau khi chốt quyết định nghiệp vụ ở mục 5.2).
3. Thêm hồ sơ cài lỗi thứ hai (giới hạn phạm vi, dẫn chiếu không phải sửa đổi, xung đột body↔annex khác số hiệu điều).
4. Chạy `run_live` trong CI hằng đêm hoặc khi đổi prompt/model; mở rộng bộ nhãn CONFLICT/DUPLICATE.
