# Brainstorm — Định hướng lại AI2: clause frame, conflict typology, timeline phụ lục

Ngày: 2026-10-01 · Nhánh: `feature/ai2-oracle-full-260928` · Quyết định: DEC-dungskbg2004-1, DEC-dungskbg2004-2

## 1. Vấn đề

AI2 hiện so sánh ở mức **fact** theo `item_key`. Key sinh từ ký hiệu, không từ nghĩa (OBSERVED):

- `structured_key` của AI1 — `ai-service/app/pipeline/fact.py:31`
- regex `item X` / `hạng mục X` — `ai-service/app/pipeline/fact.py:53`
- số thứ tự dòng bảng — `ai-service/app/pipeline/table.py:168`
- so điều khoản giữa file bằng token overlap — `ai-service/app/pipeline/clause_compare.py:297`
- amendment bằng regex `AMEND_RE`, chỉ `CANDIDATE_AMENDMENT` — `ai-service/app/pipeline/compare.py:20,304`

Hệ quả: "giao hàng chậm" (Điều 9) và "chậm trễ bàn giao" (Điều 12) không bao giờ được ghép; không phân biệt được chế tài bậc thang với conflict; không có timeline giá trị theo phụ lục.

Đề xuất của người dùng: tách mỗi điều/khoản thành cấu trúc có kiểu (vd. nhân–quả: Nhân = {giao hàng, chậm}, Quả = {phạt, 10.000.000, VND}), so conflict trên cấu trúc đó, nối phụ lục vào điều bị sửa.

## 2. Ràng buộc đã chốt

| # | Ràng buộc | Nguồn |
|---|---|---|
| R1 | Phụ lục: AI2 dựng timeline + đề xuất giá trị hiệu lực, **luôn `NEEDS_REVIEW`**; không `LEGAL_WINNER` | DEC-dungskbg2004-1, AI2-15 §1, §4 |
| R2 | Kiểm tra trần luật (vd. phạt > 8%) **ngoài scope AI2** | DEC-dungskbg2004-1 |
| R3 | Phủ cả 6 profile: `SALES`, `SUPPLY_SERVICE`, `LEASE`, `CONSTRUCTION_WORK`, `EMPLOYMENT`, `NDA` | người dùng |
| R4 | Dữ liệu: golden giả lập (mở rộng `evals/golden/`) + hợp đồng thật ẩn danh | người dùng; D-A6/D-A7 |
| R5 | Giữ plan A làm thước đo trung lập; viết lại B/C quanh frame | DEC-dungskbg2004-2 |
| R6 | Chọn kiến trúc **sau** spike cơ chế tách key | DEC-dungskbg2004-2 |

## 3. Mô hình frame

"Nhân–quả" chỉ là một loại. Đề xuất typology đóng:

| Frame | Tín hiệu | Ví dụ |
|---|---|---|
| `OBLIGATION` | "phải", "có nghĩa vụ" | Bên B phải giao hàng trước ngày X |
| `REMEDY` | "nếu/trường hợp … thì … phạt/bồi thường/chấm dứt" | chậm giao > 15 ngày phạt 10tr |
| `RIGHT` | "có quyền", "được" | Bên A có quyền kiểm tra |
| `PROHIBITION` | "không được", "nghiêm cấm" | không được tiết lộ |
| `PARAMETER` | "giá/đơn giá/thời hạn … là/bằng" + số | đơn giá 200tr |
| `DEFINITION` | "được hiểu là" | "Hàng hóa" là … |

Key so sánh: `(bearer, action, qualifier[, object])`; condition lưu **có cấu trúc** (khoảng số).

## 4. Conflict typology

| Tình huống | Đầu ra |
|---|---|
| Cùng key, cùng loại hậu quả, cùng điều kiện, khác giá trị | `COMPARABLE_DIFFERENCE` |
| Cùng key, khác loại hậu quả, điều kiện lồng/tách (≤15 ngày phạt, >30 ngày chấm dứt) | `GRADUATED` / `DIFFERENT_REMEDY` — không phải conflict |
| Cùng key, khác loại hậu quả, điều kiện chồng lấn + từ loại trừ ("chỉ", "duy nhất") | `CONFLICT_CANDIDATE` → review |
| Khoản riêng "trừ trường hợp …" vs điều chung | `EXCEPTION_OF` (vòng 2) |
| Frame chung ("vi phạm bất kỳ nghĩa vụ nào") vs frame cụ thể | `GENERAL_VS_SPECIFIC` → review |
| Phụ lục có tín hiệu sửa đổi + `effective_from` | timeline, `NEEDS_REVIEW` (R1) |
| Phụ lục khác giá trị, không tín hiệu sửa | `CANDIDATE_AMENDMENT` (giữ như hiện tại) |
| Khác unit/currency/scope | `NOT_COMPARABLE` (giữ như hiện tại) |

## 5. Cơ chế tách key — trích xuất tách khỏi chuẩn hóa

Nguyên tắc: **LLM chỉ chép chữ nguyên văn; key do bước chuẩn hóa có kiểm soát sinh ra.**

1. **Tách mệnh đề** trong khoản (`;`, "đồng thời", cặp "nếu … thì").
2. **Phân loại frame** bằng cue lexicon (luật trước), LLM enum cho phần còn lại.
3. **Trích slot thô** bằng LLM JSON schema: `bearer_text`, `action_text`, `qualifier_text`, `condition_text`, `consequence_text` — mỗi slot phải khớp nguyên văn, verify qua `pipeline/grounding.py`; không khớp → loại.
4. **Chuẩn hóa**:
   - `bearer`: tra bảng bên (Bên Bán = Bên B = Công ty X) — tất định.
   - `action`: ① lexicon alias theo profile (có version) → ② LLM chọn trong enum đóng, cho phép `NONE` → ③ `UNMAPPED` + review.
   - `qualifier`: tập đóng (`LATE`, `NOT_PERFORMED`, `DEFECTIVE`, `WRONG_QTY`, …).
   - `condition`: regex số + đơn vị → khoảng; số phải có trong span.
   - `consequence`: enum loại + giá trị qua `money_decimal`.
5. **Blocking theo key**, chỉ so frame cùng key (tránh N²).

**Lexicon bootstrap**: chạy bước 3 trên corpus → cluster `action_text` bằng embedding → người duyệt đặt tên action chuẩn + alias → `UNMAPPED` mới quay lại vòng duyệt. Embedding chỉ đề xuất cụm, **không** quyết key ("chậm giao hàng" và "chậm thanh toán" gần nhau về embedding nhưng khác key).

Ví dụ khoản 9.2 *"Trường hợp Bên Bán chậm giao hàng quá 15 ngày thì phải chịu phạt 10.000.000 đồng; quá 30 ngày Bên Mua có quyền đơn phương chấm dứt hợp đồng"*:

```
key = (SELLER, DELIVER, LATE)
  A: days_late > 15 → PENALTY_FIXED 10.000.000 VND
  B: days_late > 30 → TERMINATION
→ GRADUATED (không conflict), xác định bằng so khoảng, không cần LLM
```

### Điểm gãy đã biết

| Ca | Xử lý vòng 1 |
|---|---|
| Tham chiếu gián tiếp "vi phạm nghĩa vụ tại Điều 5" | `BREACH_REF:Điều 5` → `UNMAPPED`; cần cạnh `BREACHES` (vòng 2) |
| Frame chung "vi phạm bất kỳ nghĩa vụ nào" | `ANY_BREACH` → `GENERAL_VS_SPECIFIC` |
| Chủ thể ngầm ("bên vi phạm", bị động) | `bearer = ANY_PARTY` |
| Lexicon 6 profile | ~40–60 action, vài trăm alias `[ASSUMED]` — đo thật ở bước bootstrap |

## 6. Phương án

| Tiêu chí | 1. Fact++ (MVS) | 2. Frame đầy đủ | 3. Frame phân tầng |
|---|---|---|---|
| Nội dung | Thêm `norm_id`, `norm_role`, `norm_key`, `condition_struct` vào `Fact`; `compare.py` đổi key | Thực thể `Frame` 6 loại, cạnh `BREACHES`/`EXCEPTION_OF`/`AMENDS`, lexicon mỗi profile | Vòng 1: `PARAMETER`+`REMEDY` cho 6 profile, tất định cho giá trị/timeline, LLM trọng tài chỉ vùng mơ hồ; vòng 2: `OBLIGATION`, `BREACHES`, `EXCEPTION_OF` |
| Phủ ví dụ người dùng | giá trị + phụ lục | tất cả | giá trị + phụ lục + chế tài; ngoại lệ vòng 2 |
| Rủi ro false conflict | thấp | cao (gom key) | trung bình (`UNMAPPED` + trọng tài) |
| Tái dùng code | cao | thấp | trung bình |
| Đo bằng golden | dễ | khó | vừa |
| Hệ quả | có thể phải làm lại khi cần `BREACHES` | khóa sớm schema lớn | mở rộng dần |

Khuyến nghị của brainstorm: **phương án 3**. Người dùng chọn **spike trước rồi chọn** (R6) — chấp nhận.

## 7. Cổng spike (bước tiếp theo)

- **Mẫu**: ~30 điều khoản `REMEDY`/`PARAMETER` rải 6 profile, giả lập + thật ẩn danh.
- **Đo**:
  - precision gom key (gom sai = conflict giả) — đề xuất **≥ 95%**
  - recall gom key (phần thiếu rơi `UNMAPPED`) — đề xuất **≥ 80%**
  - độ chính xác từng slot; tỷ lệ condition parse được thành khoảng
  - kích thước lexicon thực tế sau bootstrap
- **Mutation golden mới** (`evals/golden/spec.py`): `paraphrase` (cùng ý khác chữ → phải gom) và `near_miss` (chữ gần, ý khác → không được gom).
- **Quyết định sau spike**: đạt cả hai ngưỡng → phương án 3 (hoặc 2 nếu recall rất cao); precision < 95% → phương án 1.

Ngưỡng là đề xuất, người dùng chốt khi lập plan spike.

## 8. Câu hỏi mở

1. Ngưỡng spike 95%/80% — chốt hay điều chỉnh?
2. Nguồn và số lượng hợp đồng thật ẩn danh cho spike.
3. Ai duyệt lexicon (D-A10: một người duyệt → không đo được inter-annotator agreement).
4. Plan B/C viết lại theo thứ tự nào so với tiến độ plan A.

## 9. Bước tiếp theo

`/hs:plan` cho spike cơ chế tách key (fast, không đụng code production), rồi lập lại B/C theo kết quả spike.
