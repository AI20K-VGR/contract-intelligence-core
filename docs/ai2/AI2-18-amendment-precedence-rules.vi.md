# AI2-18 — Quy tắc "phụ lục ký sau sửa văn bản ký trước" (ST-068)

**Trạng thái:** ĐỀ XUẤT, chờ duyệt. Chưa có code. DOC-11 §4.4 yêu cầu quy tắc phải có DEC trước khi code.
**Ngày:** 2026-10-02
**Mở rộng:** DEC-dungskbg2004-1, AI2-16 §6.3 (timeline tham số).
**Đọc trước:** [AI2-16 §6.3](AI2-16-clause-key-graph-v2.vi.md), [AI2-05 worked examples](AI2-05-worked-examples.vi.md) EC-028/EC-029, [AI2-15](AI2-15-contract-profiles-structure-relations-and-free-form-qa.vi.md) (ranh giới không `LEGAL_WINNER`).

Nhãn bằng chứng:
- **OBSERVED**: đã đọc trong repo.
- `[ASSUMED]`: chưa kiểm.

---

## 1. Bài toán

Một hồ sơ có văn bản gốc và một hoặc nhiều phụ lục cùng nói về một điều khoản. Người dùng muốn biết giá trị nào đang được đề xuất áp dụng.

Hiện AI2 chỉ có:
- **Cạnh `AMENDS`**: tạo khi văn bản nói rõ "sửa / thay thế" (`app/reasoning/relations.py`, `RelationSupport.EXPLICIT_TEXT`).
- **Nhãn `CANDIDATE_AMENDMENT`**: gắn khi phần trích dẫn có từ sửa đổi (`app/pipeline/compare.py`, `AMEND_RE`).
- **Event `SIGNING`, `AMENDMENT`, `EFFECTIVE_TERM`**: có trích (`app/reasoning/contract_events.py`), nhưng **không có code so ngày** giữa hai văn bản. Grep `effective_from|signed_at` trong `app/` cho 0 kết quả (OBSERVED, `research/semantic-conflict-rules.md`).

ST-068 thêm một trục mới là **thứ tự ngày ký**, để AI2 *đề xuất* (không kết luận) bản nào đang áp dụng.

## 2. Ranh giới (không đổi)

- Không `LEGAL_WINNER`, không kết luận hiệu lực pháp lý (AI2-15, DEC-dungskbg2004-1).
- Mọi kết quả của quy tắc này đều có `review_state=NEEDS_REVIEW`. Người duyệt là người quyết định.
- Kết quả phải có citation **hai phía**: một ở văn bản gốc, một ở phụ lục.
- Không kiểm điều khoản so với luật (DEC-dungskbg2004-1).

## 3. Quy tắc đề xuất

Đầu vào cho mỗi cặp *(văn bản gốc B, phụ lục A)* cùng một điều khoản (cùng clause key, AI2-16):

| Ký hiệu | Ý nghĩa | Nguồn |
|---|---|---|
| `AMENDS(A→B)` | A nói rõ là sửa hoặc thay phần nào của B | cạnh `AMENDS` loại `EXPLICIT_TEXT` |
| `signed(X)` | ngày ký của X | event `SIGNING` |
| `effective_from(A)`, `effective_to(A)` | khoảng hiệu lực của phần sửa | event `EFFECTIVE_TERM` |
| `accepted(A)` | bằng chứng hai bên chấp nhận: chữ ký hai bên, BLDS 2015 Điều 403 | DEC-dungskbg2004-1 |

Xét lần lượt từ trên xuống. Gặp dòng đầu tiên khớp thì dừng.

| # | Điều kiện | Kết quả |
|---|---|---|
| R0 | Không có `AMENDS(A→B)` rõ | **Không** áp quy tắc này. Giữ hành vi hiện tại: thiếu câu sửa rõ → `INSUFFICIENT_EVIDENCE` / `NEEDS_REVIEW` (EC-028) |
| R1 | Thiếu `signed(A)` hoặc `signed(B)` | `CANDIDATE_AMENDMENT` |
| R2 | `signed(A) < signed(B)`: phụ lục ký **trước** văn bản gốc | cờ `AMENDMENT_SIGNED_BEFORE_BASE`, cần người xem |
| R3 | Có từ hai phụ lục cùng sửa điều khoản với khoảng hiệu lực **chồng nhau** | cờ `AMENDMENT_OVERLAP` trên từng cặp chồng, cần người xem, không xếp thứ tự |
| R4 | `effective_from(A) < signed(A)`: hồi tố | cờ `AMENDMENT_RETROACTIVE`, cần người xem |
| R5 | Thiếu `effective_from(A)` | `CANDIDATE_AMENDMENT` (giống AI2-16 §6.3) |
| R6 | Thiếu `accepted(A)` | `PROPOSED_EFFECTIVE_UNACCEPTED` (giống AI2-16 §6.3) |
| R7 | Còn lại: `signed(A) ≥ signed(B)`, đủ ngày, đủ chữ ký | `PROPOSED_EFFECTIVE`, citation hai phía, `legal_winner=null` |

Ghi chú:
- `signed(A) = signed(B)` (ký cùng ngày) vẫn rơi vào R7, vì chiều sửa đã rõ qua `AMENDS`.
- Tên ba cờ `AMENDMENT_SIGNED_BEFORE_BASE`, `AMENDMENT_OVERLAP`, `AMENDMENT_RETROACTIVE` là **đề xuất**. Phải chốt cùng DEC trước khi vào contract `errors[].code` / `findings[]`.
- Thứ tự R2–R4 đặt trước R5–R7, để một bất thường về thời gian không bị che bởi `PROPOSED_EFFECTIVE`.

## 4. Đề xuất DEC

> **DEC (đề xuất) — AI2 amendment precedence by signing order is review-only**
>
> Mở rộng DEC-dungskbg2004-1. AI2 có thể dùng thứ tự ngày ký (`SIGNING`) giữa phụ lục và văn bản gốc, cùng `AMENDS` rõ, `effective_from` và bằng chứng chấp nhận, để đề xuất giá trị đang áp dụng (`PROPOSED_EFFECTIVE`). Kết quả luôn `NEEDS_REVIEW` và có citation hai phía; không bao giờ `LEGAL_WINNER`.
> Thiếu ngày ký ở một phía thì ra `CANDIDATE_AMENDMENT`. Phụ lục ký trước văn bản gốc, khoảng hiệu lực chồng nhau, hoặc hồi tố thì gắn cờ riêng để người xem. Thứ tự áp dụng theo bảng R0–R7 của AI2-18 §3.
> Code timeline (`PROPOSED_EFFECTIVE`) chỉ bắt đầu sau khi DEC này `active` và biên bản §5 được duyệt.

Ghi vào sổ DEC:
- DEC-dungskbg2004-1 hiện chỉ có trong `docs/decisions.md` của nhánh `feature/ai2-oracle-full-260928`, chưa có trên `develop`.
- Plan go-live không sửa `docs/decisions.md` của `develop` (D-10).
- Vì vậy DEC này và DEC-dungskbg2004-1 được đưa vào sổ theo quy trình của người giữ sổ, qua issue hoặc PR riêng. Doc này là nội dung để đưa vào.

## 5. Biên bản thử bằng tay trên 3 cặp

Áp bảng §3 bằng tay lên fixture có sẵn, không chạy code.

### Cặp 1: EC-028, sửa đổi ngầm

- **Nguồn:** `ai-service/fixtures/catalog.py:716-723` (fixture), `docs/ai2/AI2-05-worked-examples.vi.md:316-323` (kỳ vọng hiện có).
- **Nội dung:**
  - Trang 1: "Các bên thống nhất điều chỉnh thời hạn."
  - Trang 2: "Thời hạn còn 12 tháng."
  - Không nêu điều khoản nào bị sửa, không có ngày ký.
- **Quy tắc khớp:** R0. Không có `AMENDS` rõ.
- **Kết quả mong đợi:** không áp quy tắc ST-068; `model_disposition=INSUFFICIENT_EVIDENCE`, `review_state=NEEDS_REVIEW`, lý do `no_explicit_amend_pointer`; không `PROPOSED_EFFECTIVE`.
- **Kiểm điều gì:** quy tắc mới không biến một câu "điều chỉnh" mơ hồ thành sửa đổi có thứ tự.

### Cặp 2: EC-029, hai phụ lục cùng sửa Điều 5

- **Nguồn:** `ai-service/fixtures/catalog.py:726-734` (fixture), `docs/ai2/AI2-05-worked-examples.vi.md:325-332` (kỳ vọng hiện có).
- **Nội dung:**
  - "PL1 sửa Điều 5 phạt 0.1%."
  - "PL2 sửa Điều 5 phạt 0.05%."
  - Văn bản gốc ghi "Điều 5 phạt 0.2%."
  - `AMENDS` rõ ở cả hai phụ lục, nhưng **không có ngày ký** ở phía nào. Bản mô tả AI2-05 chỉ có ngày *hiệu lực* 01/01 và 01/03.
- **Quy tắc khớp:** R1 cho cả hai cặp (PL1→gốc, PL2→gốc). Thiếu `signed`.
- **Kết quả mong đợi:** hai `CANDIDATE_AMENDMENT`, `model_disposition=UNCLEAR`, `legal_winner=null`; không xếp PL2 trên PL1; citation ba phía (gốc, PL1, PL2).
- **Kiểm điều gì:** khi thiếu ngày ký, ngày hiệu lực không được dùng thay để xếp thứ tự.

### Cặp 3: G01-Q07, hai phụ lục hiệu lực chồng nhau

- **Nguồn:**
  - `evals/data/golden/snapshots/G01.json:618-619` (`g01-q07-s01-l01`): "Phụ lục số 1 sửa điều khoản này, hiệu lực từ 01/03/2026 đến 31/08/2026."
  - `evals/data/golden/snapshots/G01.json:632-633` (`g01-q07-s02-l01`): "Phụ lục số 2 tiếp tục sửa cùng điều khoản, hiệu lực từ 01/06/2026 đến 30/09/2026."
  - Câu hỏi `G01-Q07`: `evals/data/golden/questions.json`, mutation `overlapping_amendment`, `expected_state=NEEDS_REVIEW`.
- **Quy tắc khớp:** R1 nếu xét riêng từng cặp, vì không có ngày ký. Nhưng R3 xét trên nhóm phụ lục, nên cờ chồng lấn **luôn được gắn** dù có ngày ký hay không.
- **Kết quả mong đợi:**
  - Cờ `AMENDMENT_OVERLAP` cho cặp (PL1, PL2), khoảng chồng 01/06/2026–31/08/2026.
  - Mỗi phụ lục `CANDIDATE_AMENDMENT`, `review_state=NEEDS_REVIEW`, citation hai span `G01-Q07-R01` và `G01-Q07-R02`, `legal_winner=null`.
- **Kiểm điều gì:** chồng khoảng là bất thường cần người xem, không được tự chọn phụ lục sau.

### Lỗ hổng của bộ thử

Không fixture nào có đủ ngày ký hai phía và chữ ký hai bên. Vì vậy **R2, R4, R6, R7 chưa được thử**, trong đó có ca dương `PROPOSED_EFFECTIVE`. Đề xuất người duyệt chọn một trong hai:
- (a) duyệt 3 cặp trên cho ST-068 đợt này, ghi rõ R2/R4/R6/R7 chưa thử;
- (b) soạn thêm 2 cặp tổng hợp (một ca R7, một ca R2) trước khi duyệt.

## 6. Duyệt

| Cặp | Kết quả mong đợi đúng? | Người duyệt | Ngày | Ghi chú |
|---|---|---|---|---|
| 1. EC-028 | ☐ Đồng ý ☐ Không | | | |
| 2. EC-029 | ☐ Đồng ý ☐ Không | | | |
| 3. G01-Q07 | ☐ Đồng ý ☐ Không | | | |
| Quy tắc R0–R7 + DEC §4 | ☐ Đồng ý ☐ Sửa | | | |
| Lỗ hổng §5: chọn (a) hay (b) | ☐ (a) ☐ (b) | | | |

ST-068 chỉ đóng khi bảng này có tên người duyệt và ngày.
