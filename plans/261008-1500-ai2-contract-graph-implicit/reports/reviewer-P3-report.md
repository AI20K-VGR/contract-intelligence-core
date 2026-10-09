# Rà soát độc lập P3

## Phạm vi và kết luận

Snapshot: `HEAD 0383f383d97e9ce02a86c753ed98bdb7fc772dcc` cùng thay đổi P3 chưa commit, đọc ngày 2026-10-09. Rà soát `contracts/contract_graph.py`, `llm/client.py`, `pair_classifier.py`, `pair_builder.py`, `pairs/predictor.py`, `pairs/run.py` và 4 file test tương ứng. Chỉ ghi báo cáo; chưa tạo receipt hoặc sửa trạng thái phase.

**Snapshot đầu BLOCKED; recheck `bffe37e3` PASS cho phạm vi P3.** Hai lỗi báo cáo/đường đo heldout đã sửa và được kiểm tra lại ở mục cuối. Chưa tìm thấy lỗi ở cổng consent/egress, grounding, nhãn đóng hoặc chặn model ngoài Anthropic trong đường đã kiểm tra. Phần findings dưới đây giữ lịch sử snapshot đầu, không phải blocker còn mở.

Quy trình: `hs:scout` tìm trực tiếp 2 nhóm phụ thuộc (runtime/grounding và eval/corpus), sau đó `hs:code-review` với 2 lượt critical/informational; đọc checklist `base.md` và `api.md`. Ngôn ngữ được xác định bằng `output_config.py --resolved`: `vi`, `code_style=3`.

## Findings cần sửa

### F1 — Critical, confirmed: đường predict heldout bỏ toàn bộ gold duyệt

`evals/contract_graph/pairs/predictor.py:267`:

```python
"approved": False, "source": "gpt"})
```

`evals/contract_graph/pairs/predictor.py:189`:

```python
scored = score_relations(gold, predictions, approved_only=(split == "heldout"))
```

`predict_split(..., split="heldout", allow_heldout=True)` chuyển nhãn GPT sang gold và ép mọi dòng thành chưa duyệt. Sau đó scorer chỉ nhận gold đã duyệt, nên bỏ hết. Đường CLI được công bố cho P5 vẫn trả báo cáo `OBSERVED`, nhãn ground truth `reviewed gold (approved=true), heldout` và mã 0 dù số liệu không dựa trên HG-1.

Probe bằng 1 cặp synthetic có nhãn `CONFLICT`, `approved=True` và response Claude đúng: kết quả `n_pred=1`, `n_gold=0`, `CONFLICT.passed=0`, `status=OBSERVED`. Không gọi mạng. Đây là lỗi tính toán có thể lặp lại, không phải ý kiến về chất lượng model.

Sửa: trước mọi lời gọi heldout, kiểm HG-1 đã khoá, nạp gold duyệt từ `review.py`; thiếu phiếu hoặc digest sai phải mã 2 trước mạng. Thêm test 1 gold duyệt + 1 prediction đúng phải cho `n_gold=1`, `passed=1`, đồng thời test thiếu phiếu không gọi LLM. Nếu P5 dùng runner riêng, đóng đường CLI này cho tới khi nó có cùng precondition.

### F2 — Important, confirmed: chưa có khoảng thống kê tổng điều chỉnh theo cụm

`evals/contract_graph/pairs/predictor.py:197`:

```python
by_cluster[cluster] = score_relations([g for g in gold if g.get("doc_id") in ids],
                                    [p for p in predictions if p["doc_id"] in ids],
                                    approved_only=(split == "heldout"))["by_label"]
```

`by_cluster` là bảng k/n + Wilson của từng cụm. Báo cáo tổng ở `by_label` vẫn chỉ có Wilson với giả định mọi cặp độc lập; không có khoảng tổng điều chỉnh cho các cặp cùng hợp đồng. Khác yêu cầu `plan.md:205`, phase 3 §Requirements 4 và `harness/rules/sampled-rate-reporting.md` mục Clustered samples.

Probe trên báo cáo synthetic: trường `cluster_adjusted` không tồn tại. Báo cáo live `l2-p3-classifier-dev.json` cũng chưa có số đo điều chỉnh theo cụm tại snapshot này. Cần sửa để hoàn tất acceptance P3; không thay threshold P5.

Sửa: tái dùng phép điều chỉnh của `harness/scripts/wilson.py`, ghi method, số cụm thực có mẫu số và khoảng tổng cho precision/recall/hướng. Có thể tính lại từ k/n đã ghi, không cần gọi lại model; kiểm thử dữ liệu nhiều cặp cùng một cụm để chứng minh khoảng không bị thu hẹp như các mẫu độc lập.

## Scouting và bằng chứng đã chạy

- API runtime giữ quota HTTP dưới lock, bao gồm retry/fallback; classifier kiểm budget và deadline trước từng lô, bắt `ProcessingTimeout`, giữ quyết định trước đó. `max_calls` giới hạn lô logic; tổng HTTP vẫn chịu `runtime.max_llm_calls`.
- Gate xếp `NO_CONSENT`, `EGRESS_DENIED`, `LLM_UNAVAILABLE`, `MODEL_UNSET`, `BUDGET_EXHAUSTED`, `DEADLINE`; override eval không bỏ gate.
- Span được khớp NFC/khoảng trắng về đoạn nguồn nguyên văn, xác minh citation cả 2 phía; trạng thái quan hệ chỉ nhận `NEEDS_REVIEW`; output lạ không tạo nhãn/hướng/trạng thái mới.
- Kiểm `served_model` sau mỗi response và chỉ lấy trace của lời gọi hiện tại; output model không phải Claude không tạo quan hệ. Eval kiểm family Anthropic/OpenAI trước khi chấp nhận output.
- Candidate B/C so với P2: **42/42 đối chiếu** (7 dev + 14 heldout, mỗi doc 2 biến thể) khớp cả node pair, sources và score. Heldout B có **165**, C có **174** candidate, toàn bộ thuộc `pool ∪ S4`; không có candidate phát sinh ngoài vũ trụ gold.
- E khớp chính xác union pool: **7/7 doc dev, 215 cặp**; **14/14 doc heldout, 655 cặp**. Probe chỉ tính deterministic, không gọi classifier trên heldout và không ghi văn bản dataset vào báo cáo.
- `../ai-service/.venv/Scripts/python.exe -m pytest -q tests/test_contract_graph_pair_classifier.py tests/test_contract_graph_pair_builder.py tests/test_llm_complete_json.py` từ `ai-service/`: **93 passed**, exit 0.
- `ai-service/.venv/Scripts/python.exe -m pytest -q evals/contract_graph/tests/test_cg_pairs_predictor.py` từ root worktree: **14 passed**, exit 0.
- Ruff theo config và cwd của plan: **All checks passed** cho toàn bộ code/test P3 đã rà soát. Config root mặc định của máy có thêm rules; không dùng kết quả đó thay gate cấu hình dự án.
- Không đo coverage trong lượt này; không có phần trăm coverage để báo. Full regression do lead thực hiện riêng, chưa xác nhận trong lượt review này.

## Kiểm tra production và giới hạn

Đã kiểm concurrency, error boundary, nullability/API contracts, input validation tại ranh giới LLM, consent/egress, mutation, log/report không chứa văn bản và backward compatibility của `EdgeOp`/`ContractEdge`. P3 không thêm route, authorization, DB query hoặc migration; auth và N+1 không có đường mới trong phạm vi. P4 cần review riêng khi nối pipeline/storage.

Probe production lưu `p3-production-probe.json` ghi requested `ag/claude-sonnet-4-6`, served `claude-sonnet-4-6`, family `anthropic`, 2176 prompt tokens, 20 completion tokens. Reviewer chỉ đọc artifact này; không gọi lại endpoint hay đọc secret. Báo cáo dev hiện có 11 prediction và 1 false DUPLICATE theo GPT chưa duyệt; đây là số đo dev để đánh giá, không phải bằng chứng mở cờ.

## Ghi chú độ phức tạp, không chặn

`predict_doc` và `candidate_set` đều dựng record/graph cho cùng doc. Có thể chuyển record/index/excluded đã tính vào helper nội bộ để giảm lặp. Đây là lựa chọn **Shrink/Existing**, không ảnh hưởng severity hoặc verdict của F1/F2.

## Theo dõi plan

Model/client trace/classifier/builder và focused regression đã có bằng chứng. `PROMPT_VERSION=pairs-v1` tại snapshot; chưa có việc nới threshold hoặc chỉnh candidate P2 trong diff. Chưa thể kết luận P4/P5 hoàn tất. Trạng thái F1/F2 sau sửa được ghi dưới đây.

## Recheck — `bffe37e3d0084b000d00ea6d3fbe26a56e23fa60`

**PASS cho phạm vi P3 đã rà soát; không còn blocker F1/F2.** `git diff --name-only bffe37e3 -- <6 module P3>` không trả file thay đổi. P4 đang thực hiện ở file khác; không nằm trong kết luận này. Không tạo receipt hoặc sửa plan.

- **F1 đã giải quyết:** `predictor.py:283` gọi `_read_reviewed_gold` trước classifier; `predictor.py:304` đưa gold duyệt vào scorer. `predictor.py:313` kiểm file selection/decisions và digest; tiếp theo kiểm số dòng, id, approval và hướng. Test thiếu HG-1 trả mã 2, `client.calls=0`. Probe synthetic với nhãn GPT UNRELATED và gold human CONFLICT nay trả `n_pred=1`, `n_gold=1`, `CONFLICT.passed=1`.
- **F2 đã giải quyết:** `predictor.py:200` tổng hợp `cluster_intervals` bằng `harness.scripts.wilson.cluster_adjusted`, chỉ đưa cụm có mẫu số vào phép tính và ghi method/conf/route/K/N. `predictor.py:237` thêm số đo vào report. Tính lại từ `l2-p3-classifier-dev.json['by_cluster']` bằng đúng trường `cluster_intervals` đã lưu. Test 2 cụm xác nhận precision `N=12`, `K=2`, route `cluster-floor`; recall `N=15`.
- D13 của báo cáo live đúng `[10000, 16000]`. Không gọi lại endpoint để kiểm tra phần bổ sung số liệu.
- Chạy lại focused sau sửa: **93 passed** ai-service và **16 passed** predictor eval, exit 0. Ruff với cwd/config của plan: **All checks passed**. Đây là kết quả reviewer tự chạy; full regression `13 failed, 1440 passed, 9 skipped` ai-service và `161 passed` eval do lead cung cấp, chưa chạy lại full trong review này.
- Probe đọc HG-1 thật tại thời điểm recheck: manifest chưa có `heldout_review`, loader dừng mã 2 đúng như thiết kế. P5 cần import/freeze phiếu đã approve và ghi manifest trước trial; đây là bước P5 còn lại, không phải lỗi P3.

Candidate B/C/E vẫn dùng code P2 đã đóng băng. Prompt giữ `pairs-v1`; không nới threshold. Lead có thể chốt gate/receipt P3 theo regression tổng và tiếp tục P4. Cần review riêng integration/storage và bake-off khi các phase đó hoàn thành.
