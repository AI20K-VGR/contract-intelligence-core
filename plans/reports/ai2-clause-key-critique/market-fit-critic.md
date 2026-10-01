# Market-Fit Critic — AI2 clause → frame → canonical key

Ngày: 2026-10-01 · Lens: khả năng phòng thủ, khác biệt hóa, đường thu giá trị. Ngoài lens: người dùng có muốn không (product), có build được không (tech).
Nhãn: **proven** = có anchor đọc được; **suspected / [ASSUMED]** = chưa xác nhận được. Claim thị trường không tìm được nguồn thì ghi ungrounded, không điền số.

Viết tắt anchor: `SPIKE` = `plans/reports/spike-261001-0147-ai2-clause-key-rules-baseline-report.md`; `RES` = `plans/reports/research-261001-0147-ai2-clause-frame-deep-dive-report.md`; `VIS` = `docs/ai2/AI2-DOC-01-product-vision.vi.md`; `BRD` = `docs/ai2/AI2-DOC-02-brd.vi.md`; `POL` = `docs/ai2/AI2-01-business-policy-perspective.vi.md`.

## 1. Bảng phát hiện (xếp theo mức độ)

| ID | Mức | Trạng thái | Anchor | Vị thế đang bị đe dọa |
|---|---|---|---|---|
| MF-1 | major | proven | `VIS:47` "Giả thuyết (chưa phỏng vấn user)"; `VIS`/`BRD` không nêu đối thủ hay phương án thay thế nào | Chưa ai kiểm tra ai đang bị "sa thải" để thuê AI2 |
| MF-2 | major | proven | `VIS:18` "Một người trên một máy thí điểm"; `VIS`, `BRD` không có mô hình thu phí / chi phí phục vụ | Không có đường thu giá trị; chi phí tăng theo từng điều khoản (LLM) và từng profile (người duyệt lexicon) |
| MF-3 | major | proven | `SPIKE:334` "Không thấy dấu hiệu hội tụ nhanh tới 80% chỉ bằng thêm luật"; `SPIKE:317` held-out 2 key đúng 51,6%, recall 55,2%; `SPIKE:237-244` held-out 1 recall 25,5% | Lexicon thủ công là khoản nợ bảo trì có đuôi dài, chưa phải tài sản tích lũy |
| MF-4 | major | proven | `POL:102` "Dữ liệu tenant này không dùng train/cải thiện model cho tenant khác nếu chưa opt-in" vs vòng tăng trưởng lexicon (`SPIKE:347`) | Hiệu ứng tích lũy (moat) của lexicon bị chính chính sách dữ liệu của sản phẩm cắt |
| MF-5 | major | suspected `[ASSUMED]` | `SPIKE:89-127`, `SPIKE:310-319`: chỉ đo LLM *bên trong* cơ chế; không có baseline "LLM tự so hai điều khoản" cùng held-out | "Không gom sai" chưa được chứng minh là thứ LLM trần + ràng buộc trích dẫn không làm được |
| MF-6 | major | proven | `SPIKE:345` "1 false merge / 17 cặp"; `SPIKE:340` cận dưới Wilson 73,0%; `SPIKE:232` nhãn do cùng tác giả; `SPIKE:311-319` đổi model làm kết quả đổi (34,1% vs 43,2%) | Điểm bán "precision cao" đang dựa trên n=17, một người gán nhãn, một model |
| MF-7 | minor | suspected `[ASSUMED]` | `VIS:9` "không đọc hết từng file" vs recall ~50% | Định vị "không cần đọc hết" mâu thuẫn với recall; im lặng của hệ thống có thể bị đọc là "không có xung đột" |
| MF-8 | minor | suspected `[ASSUMED]` | Kyta (FPT), VNPT eContract, MISA WeSign: https://kyta.fpt.com/vi/blogs/top-20-nen-tang-quan-ly-vong-doi-hop-dong-clm-hang-dau-hien-nay | Đối thủ có phân phối sẵn có thể thêm "so sánh điều khoản" bằng LLM; độ sâu thực tế không xác minh được |
| MF-9 | minor | proven | `RES:23` "Hướng đi không mới về lý thuyết"; LegalRuleML là chuẩn mở | Không có lợi thế IP từ mô hình khái niệm; thứ tự chép chỉ là tốc độ |

## 2. Phương án thay thế mà người mua thực sự có

Anchor chung: tài liệu sản phẩm không nêu phương án nào (MF-1). Dưới đây là tập mà người mua hoặc đối thủ có thể dùng. Mục đã xác minh ghi nguồn; mục còn lại là `[ASSUMED]`.

| Phương án thay thế | Bằng chứng | Điểm mạnh so với AI2 | Điểm yếu |
|---|---|---|---|
| Người đọc + Excel / Word compare (mặc định, hiện tại) | `VIS:15` "không đọc hết từng file" ngụ ý đây là đối thủ chính | Không chi phí thêm, recall cao | Chậm, không có trích dẫn tự động |
| LLM đa dụng, ngữ cảnh dài, "so hai hợp đồng này" | [ASSUMED] (không có sản phẩm cụ thể được nêu) | Rẻ, không cần lexicon, recall cao | `RES:16` (CLAUSE): LLM bỏ sót lỗi tinh vi và khó biện minh pháp lý; không có "không gom sai" bảo đảm. Chưa được so đối đầu (MF-5) |
| SaaS review/redline quốc tế (Ironclad, Spellbook…) | https://www.spellbook.legal/learn/best-ai-contract-redlining-tools (qua https://spellbook.com/learn/best-ai-contract-redlining-tools): có "phát hiện bất nhất giữa các bản nháp"; **không** nêu hỗ trợ tiếng Việt; không công bố giá | Có phân phối, playbook, quy trình | Nguồn không xác nhận tiếng Việt, cũng không xác nhận so thân-phụ lục theo BLDS 403 |
| CLM Việt Nam (FPT Kyta, VNPT eContract, MISA WeSign) | https://kyta.fpt.com/vi/blogs/top-20-nen-tang-quan-ly-vong-doi-hop-dong-clm-hang-dau-hien-nay: Kyta tự mô tả AI, "tối ưu cho pháp lý và doanh nghiệp Việt", trang không công bố giá hay chi tiết so sánh điều khoản | Phân phối, ký số, tích hợp sẵn | Độ sâu so sánh điều khoản: ungrounded |
| Công cụ rà soát tiếng Việt nguồn mở/nhỏ | https://github.com/Hoa26040005/legal-ai-contract-reviewer (Graph-RAG, Neo4j, xuất track changes) | Cho thấy rào cản gia nhập thấp | Mức trưởng thành không rõ |

Kết luận lens: bốn trong năm phương án không có dữ liệu đối đầu trong repo. Một artifact chưa kiểm tra "có cần không so với phương án nào" thì chưa xác lập được nhu cầu tương đối (xem MF-1, MF-5).

## 3. Phần nào khác biệt thật, phần nào là hàng phổ thông

| Thành phần | Khác biệt? | Dễ sao chép? | Đánh giá |
|---|---|---|---|
| Lexicon alias tiếng Việt + khóa (bearer, action, qualifier) | Thấp-trung bình | Cao. Danh sách alias có thể lặp lại, LLM tạo/bootstrap alias rẻ; `SPIKE:139` cho thấy thay đổi lớn nhất v0→v1 đến từ **prompt, không phải lexicon** | Liability nhiều hơn moat (MF-3) |
| "LLM chỉ chép span + chọn enum; code tạo key; không chắc thì không gom" | Trung bình về kỷ luật, thấp về IP | Cao (một thiết kế, không phải tài sản) | Điểm bán hợp lý nhưng chưa chứng minh so baseline (MF-5). Precision cao rẻ khi recall thấp: một hệ thống abstain 70% cũng có precision cao |
| Trích dẫn neo nguồn (file/trang/hộp chữ), mọi finding mở được nguồn (`VIS:62`) | Trung bình-cao nếu gắn với AI1 OCR | Trung bình. Khó hơn alias vì cần lớp OCR/bbox tiếng Việt ổn định | **Ứng viên khác biệt thật nhất.** Nhưng nằm ở AI1 + UI rà soát, không ở cơ chế key |
| Bảng quyết định đặc thù Việt Nam: BLDS 403 (phụ lục chỉ sửa khi được chấp nhận), LTM 307 (phạt + bồi thường cộng dồn), `basis` phạt (`RES:34-37`) | Trung bình | Cao: luật công khai. Nhưng áp dụng đúng là tri thức vận hành | Khác biệt về *kỷ luật trình bày* (không phán hiệu lực, `BRD:9`), không phải bí mật. Ưu điểm so với LLM đa dụng: tính nhất quán, nhưng chỉ khi được chứng minh |
| Lớp rà người (confirm/correct/reject, lịch sử, `BRD:33`) | Trung bình | Trung bình | Đây là nơi **dữ liệu nhãn thật** sinh ra. Nếu dùng đúng, là mầm moat (xem §5) |
| Đồ thị khái niệm theo LegalRuleML (`RES:23,45-53`) | Không | Rất cao | Mượn chuẩn mở, đúng hướng, nhưng không tạo phòng thủ |

## 4. Lexicon: moat hay liability?

**Lập luận để coi là liability (proven từ chính số liệu của repo):**
- Đuôi dài không hội tụ: mỗi tập thật mới mở ra nhóm lỗi mới; recall trên dữ liệu chưa thấy 25% → 55% sau hai vòng (`SPIKE:237-244`, `SPIKE:317`, `SPIKE:334`). Cải thiện trên dev (34% → 75%) gần như không chuyển sang held-out mới (45% → 52%, `SPIKE:323`).
- Chi phí bảo trì tỉ lệ với số profile × số kiểu hợp đồng (6 profile, `RES:188` "Lexicon 6 profile phình to"), cần người có hiểu biết pháp lý duyệt từng alias. Đây là chi phí nhân công cố định, không giảm theo quy mô.
- Mức độ nhạy với model: cùng mechanism, đổi model làm key đúng thay đổi 9 điểm (`SPIKE:319`). Model frontier tiếp theo sẽ tự chuẩn hóa nhiều hơn phần "enum" hiện phải hand-curate. Lexicon càng lớn thì càng là lớp trùng lặp với khả năng của model.
- Nhãn và lexicon do cùng một tác giả (`SPIKE:17`, `SPIKE:232`): chưa có bằng chứng ngoài mẫu rằng alias list tổng quát hóa.

**Lập luận để coi là moat (có điều kiện):**
- Moat không phải *danh sách alias*, mà là **corpus hợp đồng thật đã gán nhãn bởi người rà** cùng **bảng quyết định đã được kiểm chứng** trên corpus đó. Vòng "UNMAPPED → người duyệt → lexicon" (`SPIKE:347`) sinh chính tài sản này, nhưng chỉ khi dữ liệu được gom qua nhiều khách hàng (MF-4).
- Nếu lexicon trở thành *bộ kiểm thử hồi quy cộng chuẩn hóa đầu ra* thay vì logic trích xuất chính, frontier model nâng cấp sẽ nâng recall mà lexicon vẫn giữ vai trò guardrail (precision). Khi đó lexicon không bị thương mại hóa mà được dùng làm cổng.

**Kết luận:** ở trạng thái hiện tại, là liability. Có thể thành tài sản nếu thiết kế lại theo hướng ở §5.

## 5. Điều gì làm cho nó phòng thủ được

1. **Đo đối đầu với baseline LLM trần trên cùng held-out** (MF-5), cùng mức abstain. Nếu "LLM + ràng buộc trích dẫn + rule phạt/dồn/ngưỡng" đạt precision tương đương với recall cao hơn, cơ chế key không có lý do tồn tại ngoài vai trò guardrail. Phải biết trước khi đầu tư lexicon.
2. **Chọn một nêm hẹp, đánh giá được bằng tiền**: fixture hiện có (`HD-TONG-HOP`, `SALE-BRD-07`, `SERVICE-BRD-08`, `VIS:57`) nghiêng về so giá/MST/phạt giữa thân và phụ lục cho người mua hàng. Đó là bài toán "số + phạm vi" (bậc thang, `basis`, phạt vs bồi thường), nơi bảng quyết định tất định có giá trị thực và lexicon chỉ cần phủ ít key (PRICE, PENALTY, PAYMENT_TERM…), không cần phủ toàn bộ hành vi vi phạm. Phủ rộng mọi hành vi (`ANY_OBLIGATION`, nghĩa vụ ngầm NDA…) là nơi recall thấp và chi phí cao.
3. **Tài sản dữ liệu có opt-in**: hợp đồng ẩn danh + quyết định người rà, với hợp đồng pháp lý rõ về việc dùng nhãn (MF-4). Nếu không thể, nói thẳng là lexicon theo tenant và không tính là moat.
4. **Tự động hóa chi phí lexicon**: LLM đề xuất alias từ `UNMAPPED`, người duyệt chấp nhận/bác. Nếu không, chi phí người duyệt tăng tuyến tính.
5. **Tách giá trị bán khỏi cơ chế**: bán "mỗi cảnh báo mở được trang gốc + không phán hiệu lực + lịch sử rà" (đã có trong `VIS:62`, `BRD:33`). Lexicon key là chi tiết triển khai có thể thay.
6. **Công bố chỉ số theo version lexicon trên hợp đồng của chính khách hàng** (`SPIKE:347`), kèm cờ rõ ràng cho phần chưa phủ, để giảm rủi ro MF-7.

## 6. Giá trị thu được và kinh tế đơn vị

- Không có mô hình doanh thu, đơn vị tính tiền, hay giả định giá trong `VIS`/`BRD` (đã grep "giá / thu phí / doanh thu / pricing / moat / đối thủ": chỉ có các kết quả "giá" theo nghĩa giá hàng). Giá của đối thủ cũng không công bố (Kyta, Spellbook đều ẩn giá ở nguồn đã đọc), nên không có mốc tham chiếu: **ungrounded**.
- Chi phí phục vụ: mỗi điều khoản → ít nhất một lần gọi LLM (`llm-full`), thêm lần retry/timeout (`SPIKE:295`, `SPIKE:296`: đã phải đổi model vì giới hạn tốc độ). Với recall ~50%, nửa còn lại rơi về hàng đợi người rà hoặc `clause_compare.py`, nghĩa là chi phí LLM trả đủ nhưng chỉ nửa số điều khoản hưởng lợi từ so sánh tất định.
- Người duyệt lexicon là chi phí nhân công theo khối lượng hợp đồng mới thấy, đặc biệt với hợp đồng đa profile.
- Đường chấp nhận được: định giá theo hồ sơ (dossier) cho nêm hẹp ở mục 5.2, biên gộp phụ thuộc vào tỉ lệ `UNMAPPED` thực tế. Đây là giả định `[ASSUMED]`; không có dữ liệu trong repo.

## 7. Rủi ro thị trường còn lại (chấp nhận được với điều kiện)

| Rủi ro | Điều kiện để chấp nhận |
|---|---|
| Frontier LLM thu hẹp khoảng cách ở so sánh ngữ nghĩa | Chứng minh được giá trị phần tất định (bảng quyết định + chặn gom sai) trong baseline đối đầu; nếu không, rút key graph về guardrail |
| Đối thủ có phân phối (CLM Việt) thêm so sánh điều khoản | Có nêm hẹp gắn chặt với trích dẫn nguồn và quy trình rà soát mà CLM không có; chưa xác minh được Kyta/VNPT/MISA có tính năng này hay không |
| Precision đã đo ở n=17 cặp | Không đưa "không gom sai" vào tài liệu bán hàng cho tới khi có ≥120 cặp, nhãn do người thứ hai gán (`RES:163`) |
| Định vị "không đọc hết" với recall ~50% | Ghi rõ trong sản phẩm: im lặng ≠ không xung đột; hiển thị tỷ lệ phủ (đã phù hợp `VIS:39` "số liệu phủ") |

## 8. Ngoài lens (chuyển sang lens khác)

- Người mua mua hàng có thực sự cần phát hiện xung đột ở mức khóa hành vi hay chỉ cần bảng giá/phạt thân-phụ lục: lens product.
- Tính đúng của "qualifier LATE", "quét câu", v.v.: lens tech.
