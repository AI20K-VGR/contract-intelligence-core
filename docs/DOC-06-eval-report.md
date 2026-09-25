# DOC-06 - Evaluation protocol và report template

LF-2.0 | 18/09/2026 | Trạng thái ban đầu: NOT_RUN

## 1. Mục tiêu và giới hạn

Đo xem pilot có giúp một reviewer rà soát bộ **hợp đồng chính + phụ lục PDF** trong hai domain SALE và SERVICE nhanh hơn, có bằng chứng hơn và ít bỏ sót hơn hay không. Đây là protocol cho controlled pilot, không phải claim độ chính xác thị trường và không thay thế thẩm định pháp lý.

Không đưa các tài liệu báo giá, PO, biên bản nghiệm thu, giấy chuyển nhượng vào baseline. Những loại đó là backlog ngoài scope và không được dùng để làm tăng điểm.

## 2. Datasheet của tập đánh giá

| Trường | Quyết định |
|---|---|
| Đơn vị | Một dossier gồm 1 hợp đồng chính và 0-n phụ lục PDF |
| Domain | SALE hoặc SERVICE; báo cáo tách theo domain |
| Ngôn ngữ | Tiếng Việt ưu tiên, có thể vi/en/vi-en |
| Tối thiểu | 10 dossier smoke (5/domain); mở rộng sau khi có consent |
| Gold | Hai reviewer độc lập gán page, text span, facts, clause, disposition; adjudication thứ ba khi lệch |
| Split | development 60%, validation 20%, holdout 20%; không trộn cùng bộ hợp đồng |
| PII | Redact hoặc lưu local có consent; không đưa raw hồ sơ vào báo cáo public |
| Versioning | dataset_id, manifest digest, annotator, adjudication revision, tool/model/provider version |

## 3. Chỉ số và công thức

| ID | Metric | Công thức/định nghĩa | Gate đề xuất |
|---|---|---|---|
| M01 | OCR CER | `(S+D+I)/N` trên gold text, báo cáo theo page và tổng | theo dõi, không publish nếu page critical fail |
| M02 | Critical fact accuracy | đúng exact/normalized value của tiền, ngày, party, obligation / gold facts | >= 90% selected scope |
| M03 | Citation precision | citations hỗ trợ đúng claim / tất cả citations được publish | >= 95%; fail là chặn publish |
| M04 | Citation recall | claims có ít nhất một citation đúng / tất cả gold claims | >= 90% |
| M05 | Clause/structure F1 | span/label clause khớp gold, exact hoặc IoU theo quy ước | >= 80% |
| M06 | Conflict precision | finding CONFLICT đúng sau adjudication / findings CONFLICT | >= 90% |
| M07 | Conflict recall | finding CONFLICT tìm được / gold conflicts | >= 80% |
| M08 | Evidence completeness | pages có status + digest + citation/issue / tổng pages | 100% inventory; >=95% publishable |
| M09 | Review time | median phút/dossier và so với baseline thủ công | mục tiêu giảm >=30%, đo thực tế |
| M10 | Cost | actual provider spend + retry spend / dossier | <= 3,000,000 VND pilot cap |

Confidence hiển thị cho user chỉ là calibrated quality estimate từ OCR/structure/evidence signals; không được xem là xác suất đúng. Reliability phải báo bằng các metric M01-M08 trên gold/holdout.

## 4. Test cases

| ID | Tình huống | Kỳ vọng |
|---|---|---|
| TC01 | PDF text-native | page inventory và text span ổn định |
| TC02 | PDF scan tiếng Việt | OCR tạo text + bbox + page digest |
| TC03 | Dossier 50 trang | xử lý theo page/batch, không giữ toàn bộ ảnh trong RAM |
| TC04 | Thiếu/hỏng một page | PARTIAL + MISSING_PAGE, không publish complete |
| TC05 | Bảng qua nhiều trang | table group giữ header/continuation metadata |
| TC06 | Số tiền/ngày khác nhau | finding có hai citations và normalized values |
| TC07 | Phụ lục điều chỉnh lương/giá | AMENDMENT nếu scope/date/precedence hợp lệ |
| TC08 | Conflict semantic | SUSPECTED hoặc CONFLICT theo rule + review, không hallucinate |
| TC09 | Chỉ một tài liệu | baseline so sánh không crash, findings là NONE/UNRESOLVED |
| TC10 | Không chữ ký/con dấu | evidence issue, không suy luận vô hiệu pháp lý |
| TC11 | Review edit bbox/text | append-only revision, machine result giữ nguyên |
| TC12 | Page re-OCR | child run, parent lineage và stale overlay |
| TC13 | Restart worker | checkpoint resume, idempotent batch |
| TC14 | Provider timeout | retry có giới hạn, AMBIGUOUS không tự gửi lại |
| TC15 | Budget cap | batch NOT_SENT/BUDGET_BLOCKED và status rõ |
| TC16 | CSRF/Origin lạ | local API từ chối; không wildcard CORS |
| TC17 | Citation thiếu một phía | MISSING_CITATION/UNRESOLVED, không publish claim |
| TC18 | Offline giữa run | INTERRUPTED/PAUSED, không báo thành công |
| TC19 | Memory 16 GB | peak memory và thời gian ghi nhận; không crash |
| TC20 | New engineer setup | fixture handshake chạy được sau một command |

## 5. Report template

```
run_id / dataset_id / manifest_digest / date
scope: domain, pages, dossiers, provider/model versions
counts: TP FP FN unresolved missing_pages
M01..M10: value, denominator, confidence interval (nếu phù hợp)
per-domain + per-document-role + per-page-size breakdown
blocking evidence/citation failures
reviewer disagreement and adjudication notes
cost and retry ledger
known limitations / NOT_RUN items
decision: D1 pilot / D2 conditional / D3 stop
```

## 6. Release gates

- **D1 — internal smoke:** TC01-TC05, TC13, TC19, schema/API/static checks pass; no external user claim.
- **D2 — controlled pilot:** gold labels và consent hoàn tất; M03/M08 không fail; reviewer có thể reject/undo/re-OCR.
- **D3 — expand:** holdout đạt M02/M06/M07 mục tiêu, M09 có baseline, chi phí dưới cap; nếu không thì giữ scope hoặc dừng.

Current status: `NOT_RUN`. Không được đổi thành PASS chỉ từ static document review.
