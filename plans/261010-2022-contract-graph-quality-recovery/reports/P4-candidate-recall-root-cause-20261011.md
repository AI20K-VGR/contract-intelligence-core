# Candidate recall P4: nguyên nhân gốc và quyết định khắc phục

Ngày: 2026-10-11  
Phạm vi: chỉ dùng frame phát triển 32 tài liệu đã khóa và nhãn được duyệt. Runtime vẫn OFF. Không mở dữ liệu held-out và không gọi model xếp hạng trong lần điều tra này.

## Kết luận

Candidate recall **chưa được khắc phục**. Replay với generator runtime và `top_k=40` tái hiện **11/37** cặp dương tính. Có hai nguyên nhân đã xác nhận: source hiện tại không sinh 8 cặp dương tính; giới hạn top-40 loại thêm 18 cặp đã được sinh. Các thử nghiệm xếp hạng tất định và blend với selector model đều thấp xa mục tiêu phát triển 95% theo từng nhãn. Không tích hợp heuristic chưa qua gate vào runtime.

## Dữ liệu và tái hiện

Các đầu vào đã khóa:

- Recall frame: `.harness/state/quality-recovery-p3-dev-20261011-v3/recall-frame.v1.jsonl`, 600 dòng.
- Nhãn đã duyệt: `.harness/state/quality-recovery-p3-dev-20261011-v3/reviewed-gold.v1.jsonl`, 37 cặp dương tính: 1 CONFLICT, 2 DUPLICATE, 27 GENERAL_SPECIFIC, 7 REFERENCE.
- Tài liệu nguồn: `.harness/state/contract-graph-pairs-extended-rescan-20261011/work/docs/`.
- Generator: `ai-service/app/pipeline/contract_graph/pair_candidates.py`.

Replay hiện tại với `top_k=40` sinh tổng cộng 1.000 ứng viên trên 32 tài liệu. Trong 600 dòng review, C/40 trùng 69 dòng: 11 cặp dương tính đã duyệt và 58 cặp âm tính. Độ bao phủ dương tính theo nhãn: CONFLICT 1/1, DUPLICATE 1/2, GENERAL_SPECIFIC 8/27, REFERENCE 1/7. 58 cặp âm tính chỉ là phần giao với frame đã review, không phải ước lượng precision trong sản phẩm.

Ở mục tiêu kỹ thuật 95% từng nhãn, mẫu số hiện tại cần ít nhất CONFLICT 1/1, DUPLICATE 2/2, GENERAL_SPECIFIC 26/27 và REFERENCE 7/7 (tổng 36/37). C/40 còn thiếu 25 lượt đạt mục tiêu: 1 DUPLICATE, 18 GENERAL_SPECIFIC và 6 REFERENCE.

> Có một chi tiết replay quan trọng: C có nhánh giữ ứng viên core khi áp dụng cap. Lấy 40 dòng đầu từ kết quả uncapped **không** tái hiện một lần gọi với `top_k=40`; replay đúng phải gọi generator trực tiếp ở top_k đã giới hạn. Phép tính scratch ban đầu dùng prefix của danh sách uncapped đã bị loại. Các số trong báo cáo này dùng phép gọi có giới hạn đúng.

## Nguyên nhân 1: source bỏ sót tám cặp

Ở chế độ uncapped, C chứa 29/37 cặp dương tính; tám cặp còn lại không được source nào hiện tại đề xuất. Cả tám là cặp liên điều khoản, đủ điều kiện, không bị loại vì là cặp Luong-1 hoặc cặp cha-con. Nhãn gồm năm GENERAL_SPECIFIC và ba REFERENCE. Khoảng cách theo thứ tự cấu trúc lần lượt là 1, 1, 2, 4, 5, 6, 8 và 14.

Các source hiện có là SAME_ARTICLE, EXPLICIT_REF, SAME_KEY, REFERENCE_CUE và VALUE_MISMATCH. Các miss cho thấy:

- SAME_KEY chỉ gán tối đa một topic hẹp; nếu heading không có topic thì `topic_of` chỉ xem 80 ký tự đầu của điều khoản. Topic xuất hiện muộn trong điều khoản dài có thể bị bỏ qua.
- REFERENCE_CUE nhận diện một tập cue nhỏ và chỉ tìm vài điều khoản đủ điều kiện đứng trước có cùng topic khác null. Nó bỏ sót tham chiếu hướng tới phía trước, liên kết khái niệm rộng không có cue đã liệt kê, và cue mà bộ trích topic không nhận ra.
- EXPLICIT_REF cần địa chỉ trích xuất và phân giải duy nhất; nó không tìm được diễn đạt lại hoặc liên kết rộng giữa các điều khoản khi không có địa chỉ rõ.
- VALUE_MISMATCH cần số liệu khác nhau cùng mức trùng từ vựng đáng kể. Đây là source có phạm vi hẹp, không phải nguồn liên kết ngữ nghĩa tổng quát.

Vì vậy, sửa prompt của classifier phía sau không thể khôi phục tám cặp này: classifier chưa bao giờ nhận chúng.

## Nguyên nhân 2: cap mỗi tài liệu bị clique chiếm chỗ

C/40 tìm được 11/37; C uncapped tìm được 29/37. Có 18 cặp dương tính được sinh nhưng nằm ngoài cap. Trong đó 17 cặp SAME_ARTICLE đứng ở hạng 46–1.898 trong danh sách uncapped; cặp còn lại là VALUE_MISMATCH ở hạng 129.

SAME_ARTICLE tạo mọi cặp trong cùng điều khoản. Điều khoản có nhiều khoản tạo clique tăng theo bình phương số khoản. Các cặp này nhận điểm cấu trúc thấp giống nhau rồi được sắp ổn định theo vị trí node. Cách xếp đó thiên về node đầu văn bản và cho phép nhiều tổ hợp trong cùng điều khoản chiếm cap. Mã đặt `_CORE_TOP_K_SHARE = 1.0`, dành cả 40 suất cho SAME_ARTICLE/EXPLICIT_REF khi nhóm core có ít nhất 40 cặp. Khi đó các source thăm dò liên điều khoản không thể thay thế bất kỳ cặp core nào.

Chỉ tăng K không giải quyết được hiệu quả: C/80 đạt 13/37. Trần theo source vẫn là 29/37; uncapped C tạo 11.143 ứng viên nên không phù hợp làm fallback runtime với giới hạn độ trễ và lượt gọi hiện tại.

## Thử nghiệm xếp hạng và giới hạn

Các biến thể xếp hạng tất định đã đo trước đây đạt cao nhất 15/37. Selector ngữ nghĩa đã đăng ký trước trả về 816 cặp trên frame dev và tự chọn được 11/37. Union không giới hạn với C/40 chứa 17/37 cặp dương tính nhưng có tổng cộng 1.539 cặp. Một phép merge giới hạn cap, giữ 31 cặp C/40 rồi bù từ thứ tự selector đã lưu, đạt 16/37 trong replay cục bộ: tổng 1.081 ứng viên, giao với frame review 67 cặp (16 dương tính được duyệt, 51 âm tính).

Kết quả merge 16/37 là thăm dò và được chọn dựa trên chính nhãn dev dùng để phân tích. Đây không phải kiểm chứng độc lập; vẫn bỏ sót 21 cặp dương tính và chỉ nhãn có một mẫu CONFLICT đạt target. Lần selector trực tiếp trước dùng 206.907 token, mất 199,02 giây cho 32 tài liệu; con số đó không chứng minh một bước xếp hạng model trong runtime sẽ phù hợp với mọi tài liệu hoặc ngân sách classifier đầu-cuối. Danh sách `/models` của endpoint đã cấu hình không có model được nhận diện là embedding hoặc reranker.

Thêm heuristic lân cận hoặc blend selector đã lưu đều chưa phải cách sửa hoàn chỉnh. Tích hợp một trong hai sẽ biến mức tăng nhỏ, đã tune trên dev, thành thay đổi runtime chưa có bằng chứng tổng quát hóa.

### Cập nhật điều tra dense retrieval (2026-10-11)

Đã đo thêm full MiniLM contextual embedding (attention-mask mean pooling theo cấu hình MiniLM) và BGE-M3 dense CLS embedding theo pooling config đã cache. MiniLM semantic top-40 đạt 7/37; C32+semantic blend đạt 14/37, tổng 1.200 cặp, 59,58 giây CPU. BGE-M3 top-40 đạt 8/37; blend đạt 16/37, tổng 1.200 cặp, 590,83 giây và gần 2,1 GB working set. Cả hai phép chạy chỉ dùng 32 tài liệu dev đã khóa, không dùng held-out/API. BGE-M3 là blend cao nhất quan sát được nhưng vẫn hụt mục tiêu 36/37 tới 20 cặp; DUPLICATE (1/2), GENERAL_SPECIFIC (11/27), REFERENCE (3/7) chưa đạt. Chi phí BGE-M3 cũng quá cao để đề xuất runtime.

Kết quả loại bỏ giả thuyết rằng chỉ cần đổi sang multilingual dense embedding là candidate recall được giải quyết. Candidate misses gồm source recall và top-K selection, cần retriever lai/reranker có ngân sách; chưa có biến thể qua gate, nên không có căn cứ sửa runtime an toàn hoặc đánh dấu vấn đề đã khắc phục. Chi tiết preregistration/kết quả: `plans/reports/retrieval-probe-prereg-261011-1005-static-subword-report.md`, `plans/reports/retrieval-probe-prereg-261011-1200-bge-m3.md`.

## Vì sao chưa thể kết luận đã sửa hoàn toàn

Thiết kế yêu cầu candidate coverage ít nhất 95% từng nhãn đã review, sau đó phải qua các gate riêng cho classifier, precision, exact-direction và chi phí. Coverage hiện tại còn thấp xa mục tiêu. Frame đã duyệt chỉ có 1 CONFLICT và 2 DUPLICATE, nên chưa đủ mẫu để thiết lập floor thống kê từng nhãn kể cả khi tìm đúng tất cả các ví dụ này. Bảy REFERENCE và 27 GENERAL_SPECIFIC cũng chưa đủ để chứng minh Wilson lower-bound theo yêu cầu.

Mình đã kiểm tra tài liệu dev chưa dùng mà không mở split held-out. Thư mục rescan có 34 tài liệu, trong khi recall frame dev đã khóa dùng 32. Hai tài liệu ngoài frame đều có metadata `contaminated=true`; nguồn P3 đã loại chúng khỏi 32 tài liệu sạch. Một tài liệu chỉ có bảy node cấu trúc. Mình không dùng chúng làm bằng chứng dev sạch và không đọc nội dung điều khoản của chúng. Thư mục này hiện không còn tranche dev sạch, chưa dùng, đã xác minh để kiểm tra rule retrieval mới.

Thay đổi candidate generator hoặc selector sẽ làm đổi universe ứng viên cấp cho S4/HG-1/HG-2. Không thể dùng lại các lock đó như thể chúng mô tả generator mới. P4/P5 tiếp tục bị khóa; không mở held-out cho đến khi phiên bản candidate mới và universe review tương ứng có lock hợp lệ. Runtime tiếp tục OFF.

## Lộ trình khắc phục cần thiết

1. Giữ C/40 làm baseline đo được; không gọi 15/37 hay 16/37 là PASS.
2. Thiết kế retriever lai có ngân sách rõ: rule cấu trúc/địa chỉ chính xác; truy xuất lexical/topic liên điều khoản giữ nhiều cue trên toàn văn bản; scorer ngữ nghĩa theo cặp có giới hạn ứng viên, độ trễ và token. Thay clique SAME_ARTICLE không giới hạn bằng shortlist có đa dạng để nhóm core không chiếm toàn bộ 40 suất.
3. Đo từng tín hiệu riêng và cấu hình kết hợp đã đóng băng trên các tài liệu dev đã duyệt nhưng chưa dùng để chọn rule. Báo cáo coverage theo source/nhãn, rank-at-K, yield ứng viên đã review, số ứng viên runtime, token và độ trễ. Không tune trên held-out.
4. Nếu chọn được phiên bản candidate, tạo lại universe S4 và phiếu/lock review mới. Giữ lock cũ làm lịch sử. Chỉ dev gate hợp lệ mới cho phép chuẩn bị P5; không tự bật runtime.
5. Giữ runtime OFF cho đến khi candidate, classifier, exact-direction, precision, false-DUPLICATE và budget đều qua các gate trên bằng chứng đã khóa.

> Lần điều tra này không sửa production code hoặc hằng phiên bản candidate. Không đọc hoặc ghi file held-out.
