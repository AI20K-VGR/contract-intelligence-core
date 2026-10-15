# Validation của main trước approval

Ngày 2026-10-10. Phạm vi: kế hoạch; không chứng nhận implementation hoặc chất lượng sản phẩm.

## Kết quả kiểm tra thực

- `hs-run plan graph --require` qua Python entrypoint: exit0, warnings[], cycles[], missing_post[]; batches `[[P1],[P2],[P3],[P4],[P5]]`.
- `plan_graph.graph_size_facts`: declared_files40, directories5, phases5, independent_clusters1, longest_chain5. Count bao gồm report/manifest/tests, không phải40 production modules.
- Đối chiếu file Modify chưa được Create ở phase trước: missing_existing_modify[]. Plan và5 phases: placeholder_files[].
- `hs-run plan record planner` đạt `needs_model_attestation`. Engine chỉ chứng minh presence/shape; main đã đọc nội dung và independent review để kiểm chất lượng.
- Independent red-team: RT-QR-01/02/03 được xử lý trong plan sau recheck; final verdict PASS cho design. Xem report red-team chứa vòng đầu, disposition và hashes. Không dùng verdict này thay product gate.
- Main chỉnh reference helper P2 cho rõ số probe dùng `bakeoff.wilson`/scorer. Reviewer phát hiện giả thuyết evaluator/runtime dùng z khác nhau không đúng; main đã gọi cả hai helper và xác nhận cùng z=1.96, cùng lower57/60 `0.8629926537490016` và56/60 `0.8407442010623228`. P2 đã sửa đúng bằng chứng; không đổi threshold/historical metric.
- Lỗi CLI Windows launcher đã được tránh bằng Python entrypoint; main không sửa harness. Dashboard so sánh kích thước từ `plan next` lỗi `AttributeError: 'list' object has no attribute 'get'`; direct `graph_size_facts` chạy thành công cho plan này. Không tạo/giả mạo `scope-sizing.json`; size choice cần ghi bằng approval CLI sau câu trả lời của người dùng.

## Whole-plan consistency sweep

| Nội dung | Kết quả |
|---|---|
| Goal và gates | Recall exact từng nhãn, precision độc lập, direction A/B fail closed, n60/lower.85, DUPLICATE observed/unreviewed0; runtime OFF |
| Phase dependency | P1 evidence/telemetry → P2 scoring/gates/reader/lock plumbing → P3 reviewed dev/rubric → P4 preliminary tuning → P5 final source confirmations/fresh heldout |
| Fingerprints | P5 code hoàn tất trước2 confirmation dev; immutable versioned successor records, không ghi đè legacy locks; code/data/config drift block |
| Ledger | Max4 P4 tuning repeats +2 P5 same-winner confirmation repeats +1 oracle20pairs; total7dev runs, max3500000tokens; mỗi run550s/500000tokens |
| Dataset | Recall membership khóa độc lập trước candidate generation; union-only rows precision/safety; sample/quota không bị bù bằng candidate-selected positives |
| Ownership | Shared source files ghi tuần tự, một owner/module; dirty edits giữ nguyên; all declared existing Modify paths tồn tại |
| Compatibility | Legacy metric/readers historical-only; new schema/paths/gold dispatch và test Create được khai báo; public wire/storage/flags không đổi |
| Human gates | Approval kế hoạch mới, HG-QR1 cho rubric/dev, HG-QR2 cho fresh heldout; approval cũ không áp dụng dữ liệu mới |
| Outcome | Technical tests PASS khác product PASS; không mark quality complete nếu real metric chưa đạt |

## Validation log và quyết định còn chờ

| ID | Category | Câu hỏi/kiểm tra | Đáp án hoặc default đề xuất | Owner/gate |
|---|---|---|---|---|
| VL-1 | Constraints | Có đổi model/floor/budget không? | Không: cx/gpt-5.5, floor>=.85,550s/500000tokens; user đã chốt, kế thừa |
| VL-2 | Architecture | Một plan hay tách nhỏ? | Đề xuất keep:5phase một chain,1independentcluster;40 declared files. User quyết định cùng approval, chưa ghi receipt |
| VL-3 | Assumptions | Đủ fresh sources và nhãn REFERENCE không? | Chưa biết; P3/P5 yield audit/readiness trước khóa và classifier calls; không bịa quota hoặc hạ floor |
| VL-4 | Risk | Có independent reviewer và review capacity không? | Chưa xác nhận người/thời gian; chuẩn bị blind packet và người dùng chốt tại HG-QR1/HG-QR2; không tự ghi human approval |
| VL-5 | Trade-offs | Corpus proposed100positive/label có vừa budget không? | Chưa biết; sizing từ dev, blocker định lượng nếu không vừa; không chỉnh sampling sau thấy heldout results |
| VL-6 | Assumptions | Override là nguyên nhân false duplicate? | Chưa xác nhận; P4 bounded dev ablation, không tune/relabel historical heldout |
| VL-7 | Evidence | Coverage thấp có chạy tái hiện không? | Có: current candidate probe C174/covered74/101, B165/covered77/101; full historical runtime parity vẫn P1 nghĩa vụ |

## Trạng thái bàn giao

Kế hoạch `pending`, chưa có plan approval, chưa bắt đầu cook, không source/test changes hoặc live model calls trong planning. Các phép probe offline nằm `research/local-probes.md`.

Sau người dùng duyệt nội dung và keep/split, ghi receipt qua `plan_approval.py` đúng envelope, đọc lại `plan next` rồi dùng cook command do engine sinh. Không tự gán APPROVED dựa trên user approval của kế hoạch cũ.
