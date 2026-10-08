# Developer P2 — Structural Candidates (in place, main)

- Commit: `b0022c8` (module + eval + test + báo cáo dev), `29c4dc1` (S4 + khoá mẫu HG-1). Chưa push.
- RED: `tests/test_contract_graph_pair_candidates.py` và `evals/.../test_cg_pairs_candidate_eval.py` đều `1 error during collection` (module chưa có). Lưu ý: `pair_candidates.py` được viết trước khi chạy RED; RED được ghi bằng cách tạm dời module ra ngoài rồi chạy lại.
- GREEN: ai-service focused 105 passed; full suite 13 failed (đúng 13 lỗi môi trường) / 1313 passed / 44 skipped; evals 145 passed; ruff (`ai-service/` config) sạch.
- Dev (nhãn GPT, approved=false): recall không cắt 15/24 (0,625; Wilson 0,427–0,788); S1 6/6, S3 9/18; theo nguồn EXPLICIT_REF 7, SAME_ARTICLE 6, SAME_KEY 2, REFERENCE_CUE 0. Ứng viên/văn bản tối đa 20 ⇒ recall@K phẳng ở mọi K.
- `PAIRS_TOP_K`: quy tắc cho 10; **người dùng chốt giữ 40** (dev suy biến, held-out tới 42 node). Ghi trong báo cáo (`pairs_top_k_rule`, `k_choice_reason`). `tuning_rounds` 0: phần sót là "điều khoản chung" ↔ Điều cụ thể, không sửa được bằng lexicon trong spec.
- S4 held-out: 31 cặp (CONFLICT 2, GENERAL_SPECIFIC 2, REFERENCE 3, UNRELATED 24), served `gpt-4o-mini-2024-07-18` họ openai; `verify` exit 0.
- HG-1: 181 dòng (CONFLICT 30, DUPLICATE 29, GENERAL_SPECIFIC 34, REFERENCE 8, UNRELATED 80; S1 80 / S2 12 / S3 72 / S4 17), sha khoá trong manifest (`29c4dc1`) trước khi xuất `.harness/state/contract-graph-pairs/review/heldout_review.csv`.
- Deviation: sửa `pairs/manifest.py` (ngoài inventory) để `verify` chấp nhận và kiểm sha file S4 ghi trong `extension_s4`; không sửa thì `read_split` hỏng sau khi sinh S4.
- `pair_candidates.py` dùng hàm nội bộ của `address.py` (`_atoms`, `_chains`, `_shared`, `_address`) để lấy vị trí cuối địa chỉ cho luật RT-09 (60 ký tự sau địa chỉ).
