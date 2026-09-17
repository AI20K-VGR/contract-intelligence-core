# Protocol đánh giá v0.2

Thiết kế dùng cho run sau này; các ví dụ dưới là tính tay, không phải số đo model. Đơn vị và cỡ mẫu dự kiến ở GROUND-TRUTH-PLAN.vi.md: 15 logical cases × 2 representation types = 30 tổ hợp mỗi round; 12 structured và 3 semantic. Báo riêng từng representation, round, rule version và gold version.

## Matching tái lập

1. Đóng băng gold adjudicated và evidence bindings. Prediction so với gold cùng representation; ánh xạ predicted fact qua document/source region tới logical fact, không so ID do model tự sinh như giá trị nghiệp vụ.
2. Structured fact exact match gồm entity_type, role, normalized value và subject/unit/currency/VAT/scope/validity có áp dụng; evidence phải trỏ đúng nguồn. Null do missing không được đoán là giá trị đúng. Báo riêng lỗi extraction và lỗi evidence để thấy nguyên nhân.
3. Matching một-một: sắp prediction theo prediction_id, mỗi prediction nhận gold tương thích chưa được dùng có ID nhỏ nhất. Các matches phải exact, không fuzzy ở protocol v0.2. Duplicate còn dư là FP; gold chưa match là FN; prediction sai role/value là FP và gold bị bỏ lại là FN.
4. Pair chuẩn hóa theo logical IDs; within_document/annex_annex có thể đảo hai phía nếu giữ evidence tương ứng. Amendment giữ hướng nguồn bị sửa → nguồn sửa. Ghép một-một theo pair, scope, family, type, disposition; sai disposition là FP ở lớp dự đoán và FN ở lớp gold.
5. Citation metric dùng tập logical fact bindings duy nhất, không nhân số citation do cùng fact xuất hiện ở nhiều pairs. Exact validity: snapshot/document/page/line/span/word/bbox refs resolve tới đúng nguồn; bbox tồn tại chưa đủ nếu highlight sai. Missing binding được báo riêng và đánh failed evidence, không loại im lặng khỏi denominator. Audit chưa làm → validity metric chưa đủ dữ liệu.

## Tách ba phép đánh giá

- Fact extraction: TP/FP/FN theo bảy entity types; semantic propositions báo riêng.
- Disposition classification: confusion matrix cho năm disposition, trên 12 structured cases mỗi representation; mỗi gold case có một expected class. Không có output là missing prediction và FN. Output lặp tính FP theo quy tắc trên. Báo raw counts trước micro/macro nếu tính.
- Difference alerts: positive gold = comparable_difference (C01,C03,C05–C08, tổng 6 structured). Comparable_match/not_comparable là controls (C09–C12). Candidate_amendment C02 báo riêng là amendment review; insufficient_evidence C13 báo riêng là evidence queue. Nếu model gắn difference alert cho C02/C09–C13 thì FP của difference alerts. Nếu gold positive bị trả match/not_comparable/insufficient thì FN của difference alerts. Sai subtype trên đúng positive pair có thể đúng binary alert nhưng sai classification; báo tách hai chỉ số.
- Semantic C04/C14/C15: chỉ báo bảng candidate + outcome review + lý do; không cộng vào structured precision/recall.

## Công thức và trường hợp biên

precision = TP/(TP+FP); recall = TP/(TP+FN); F1 = 2TP/(2TP+FP+FN).
Mẫu số của chỉ số nào bằng 0 thì chỉ số đó N/A và ghi lý do. Không suy F1 từ precision/recall đã làm tròn. Nếu TP=0, FP=1, FN=1 thì P=0, R=0, F1=0. Nếu tất cả counts bằng 0 thì cả ba N/A. Nếu TP=0,FP=0,FN=1 thì P=N/A,R=0,F1=0.

| Ví dụ structured classification | TP | FP | FN | P | R | F1 |
|---|---|---|---|---|---|---|
| Một gold, một prediction đúng | 1 | 0 | 0 | 1 | 1 | 1 |
| Một gold, hai prediction đúng trùng | 1 | 1 | 0 | 0.5 | 1 | 2/3 |
| Một gold difference, prediction match | 0 | 1 | 1 | 0 | 0 | 0 |
| Một gold, không có output | 0 | 0 | 1 | N/A | 0 | 0 |
| Không gold và không prediction | 0 | 0 | 0 | N/A | N/A | N/A |

Ví dụ binary: C03 bị trả match → FN=1; C09 bị báo difference → FP=1; tổng TP=0,FP=1,FN=1,F1=0. C02 trả đúng amendment không là TP của difference alerts; ghi đúng vào amendment classification.

## Audit và báo cáo

Chọn trước C02,C13,C15, kiểm tra hai phía/cả hai representations khi thực thi; thêm fact audit để đủ ceil(20% × n_gold_facts). Báo riêng audited logical cases/facts/bindings và missing bindings. Peer review số học còn chờ người thứ hai; bảng ví dụ đủ để walkthrough, không khẳng định đã audit độc lập.

Mọi kết quả phải kèm counts, denominator, failed/not-run cases, gold/rule/snapshot version và tập phát triển hay tập đánh giá độc lập. Baseline v0.2 dùng fixture phát triển, không có claim khái quát hóa. Không đặt ngưỡng accuracy tùy ý để tự chứng nhận thành công.
