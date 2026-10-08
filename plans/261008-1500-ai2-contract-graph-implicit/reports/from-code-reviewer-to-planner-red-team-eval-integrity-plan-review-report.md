# Red-team plan 261008-1500-ai2-contract-graph-implicit — persona chính: eval/data-integrity

Ngày: 2026-10-08 · HEAD `83f2d75` (worktree `contract-intelligence-develop`) · Vai trò: hs:red-teamer (chỉ tư vấn, không sửa plan/code).
Persona: **(A) eval/data-integrity skeptic** (chính) · **(B) LLM safety/cost** · **(C) backward-compat/BE guardian**.
Phạm vi: chỉ tấn công rủi ro thực thi; không re-litigate L2-1..L2-4, K-a..K-e.

**Verdict:** GO-with-fixes. Không có đường mất dữ liệu không phục hồi được ở runtime. Có 4 lỗi High phải sửa trước khi cook chạm tới tài nguyên dùng một lần (held-out + giờ duyệt HG-1) hoặc trước khi P4 merge:
- RT-01, RT-02: thước đo của cổng P5 bị lệch do cách chọn mẫu.
- RT-03: CONFLICT phá bất biến review-id của luồng 1 (đã repro).
- RT-04: kiểm tra K-a dựa trên tên model và fail-open.

Nhãn: **proven** = có lệnh/đầu vào tái hiện hoặc dẫn chứng từ chính văn bản plan/code. **suspected `[ASSUMED]`** = có khả năng xảy ra nhưng chưa kích hoạt được.

## 1. Bảng phát hiện (xếp theo mức độ)

| id | mức | proven / suspected | anchor | cách sửa rẻ nhất |
|---|---|---|---|---|
| RT-01 | **High** | proven (theo cấu trúc) | `plan.md:74` (D18), `phase-5:45`, `phase-5:55` | `decide()` tính `predictions_without_approved_gold` là **sai** khi xét cổng (cận dưới bảo thủ), hoặc gán trọng số 1/π cho tầng UNRELATED đã lấy mẫu; báo cả hai số |
| RT-02 | **High** | proven (cấu trúc + proxy) | `phase-1:45` (S3 = `min(40, …)`), `phase-5:45` | P5 bước 0, **trước** mọi lời gọi LLM trên held-out: sinh ứng viên B/C deterministic trên held-out, GPT gán nhãn các cặp ngoài pool, đưa vào phiếu duyệt theo quy tắc pre-register (khoá sha selection lần 2) |
| RT-03 | **High** | proven (repro §5.1) | `phase-4:47` (D11), `ai-service/app/pipeline/contract_context.py:254-278`, `ai-service/app/pipeline/idp.py:359-361, 556` | Chuyển khối pairs xuống **sau** `issues.extend(graph_issues)` (`idp.py:361`), trước `coverage`/`propose`; thêm fixture phụ lục **nhúng cùng file** vào `test_existing_review_item_ids_prefix_preserved` |
| RT-04 | **High** | proven | `phase-3:59`, `plan.md:72` (D16), `ai-service/app/llm/client.py:108`, `ai-service/tests/test_llm_complete_json.py:12` | `family()` xét đoạn cuối sau `/`, **fail-closed** khi không nhận ra họ; client ghi thêm `served_model = resp.model` vào trace; P3 probe và P5 bước 0 khẳng định họ `served_model` == anthropic |
| RT-05 | Medium | proven (repro §5.2) | `ai-service/app/security/policy.py:43`, `phase-3:43-44` | Không dùng `classify_prompt_injection` làm bộ lọc **bỏ cặp**; mẫu riêng có `\b`, chạy trên văn bản đã gập dấu, áp lên **cả `text` lẫn `context`**; cặp có tín hiệu vẫn gửi (output đóng đã giới hạn tác hại), chỉ đếm |
| RT-06 | Medium | proven (repro §5.3) | `ai-service/tests/test_contract_graph_edge_store.py:112-121`, `phase-4:186` | Thêm file vào inventory P4; đổi sang head động + khẳng định `0006.down_revision == "0005_ai2_contract_edges"` |
| RT-07 | Medium | proven (cơ chế) / `[ASSUMED]` (hệ quả lease) | `phase-3:45`, `ai-service/app/pipeline/runtime.py:180-201`, `ai-service/app/api/main.py:258` | Trước mỗi lô, đòi `remaining() ≥ PAIRS_DEADLINE_RESERVE_S + max_attempts × call_timeout_seconds`; không đủ thì `stopped_reason="DEADLINE"` |
| RT-08 | Medium | proven (văn bản plan) | `phase-3:85` (probe dùng base_url riêng), `phase-3:52`, `plan.md:62`, `plan.md:92`, `ai-service/app/api/main.py:278` | Probe bước 0 đi qua `classifier_client(NineRouterClient(), model)` với env production; hoặc thêm `AI2_CONTRACT_GRAPH_PAIRS_BASE_URL/_API_KEY` (tuỳ chọn, mặc định = `llm`) |
| RT-09 | Medium | proven (repro §5.4) | `phase-2:43`, `ai-service/app/pipeline/contract_graph/documents.py:16-19` | `EXPLICIT_REF` bỏ địa chỉ khi câu nêu văn bản ngoài (`named_document(...)` khác None **hoặc** token `luật/bộ luật/nghị định/thông tư/quyết định` đứng sau địa chỉ); thêm test phủ định |
| RT-10 | Medium | proven | `backend/src/contract_intelligence/shared/ai/persistence.py:1087, 1095`, `phase-4:53` | Trần số candidate CONFLICT mỗi hồ sơ (vd ≤5, phần dư chỉ đếm ở coverage); evidence = citation **cả node** (`text_span=None`), span LLM chỉ vào bảng `ai2`; ghi ánh xạ severity vào AI2-20 |
| RT-11 | Medium | proven (cơ chế) / `[ASSUMED]` (topology) | `plan.md:205`, `phase-4:237-239`, `ai-service/app/db/engine.py:39-44` | Runbook: dừng/scale về 0 **mọi** process code mới (API, Kafka worker, batch) → `python -m app.db.migrate downgrade 0005_ai2_contract_edges` → deploy code cũ |
| RT-12 | Medium | `[ASSUMED]` (proxy đo được) | `plan.md:7`, `plan.md:243` (Q5), `phase-1:60` | Trần mẫu UNRELATED cố định (vd 60–100, phân tầng S1/S2/S3, có trọng số — gắn với RT-01); in số dòng dự kiến ở `pool` **trước** `freeze`; P5 bước 0 kiểm khả thi n≥60 từ tỷ lệ của `l2-p3`, bỏ E nếu chắc chắn `KEEP_OFF_INSUFFICIENT_N` |
| RT-13 | Medium | `[ASSUMED]` | `phase-1:56`, `evals/spikes/clause_key/heldout_sources.json` | Trước khi chia split: chuẩn hoá văn bản, gom cụm gần trùng (shingle Jaccard ≥ 0,8 hoặc sha chuỗi tiêu đề Điều); cả cụm vào cùng split; kiểm nhiễm bẩn bằng hash nội dung ngoài URL |
| RT-14 | Low | proven (văn bản plan) | `phase-4:44`, `phase-4:233` | Chỉ thay dòng khi `mode=="llm"` và có ít nhất một lô hoàn tất, hoặc `rule_only_reason=="NO_CONSENT"` (xoá vì quyền riêng tư); còn lại `pair_relations_ran=False` |
| RT-15 | Low | proven (thiếu trong plan) | `phase-5:38`, `phase-5:54-58` | Commit khối `heldout_review` (sha decisions) **trước** trial 1; mỗi file trial ghi sha decisions; `decide()` từ chối khi sha lệch |

Không có fact `code.fan_in` trong envelope ⇒ bỏ dòng fan-in.

## 2. Chi tiết

### RT-01 (High): precision/recall của cổng tính trên mẫu phân tầng theo nhãn GPT mà không gán trọng số

- D18 (`plan.md:74`, `phase-1:60`) chỉ duyệt:
  - **mọi** cặp GPT gán nhãn ≠ UNRELATED;
  - **20 %** (tối thiểu 30) cặp GPT gán UNRELATED.
- P5 bỏ mọi dự đoán trên cặp chưa duyệt khỏi mẫu số precision (`phase-5:45`). `n_L` của cổng chỉ đếm "dự đoán L có gold đã duyệt" (`phase-5:55`).
- Lỗi bộ phân loại độc lập với GPT rơi chủ yếu vào các cặp GPT gán UNRELATED. Khoảng 80 % số cặp đó không được duyệt, nên lỗi FP ở đây bị loại khỏi mẫu số. Hệ quả: precision **lệch lạc quan**, theo hướng chắc chắn.
- Recall cũng lệch lạc quan, cùng cơ chế. Positive mà GPT bỏ sót nằm trong 80 % UNRELATED chưa duyệt nên vô hình. Vì vậy `recall_any` và McNemar C vs B chỉ đo trên những positive "GPT tìm được".
- Ví dụ minh hoạ (số giả định): C dự đoán CONFLICT trên 70 cặp. 50 cặp GPT gán positive (40 cặp người xác nhận). 20 cặp GPT gán UNRELATED (18 cặp thực sai). Mẫu 20 % thấy khoảng 4 cặp. Precision báo cáo ≈ 40/54 = 0,74, trong khi thật ≈ 40,4/70 = 0,58.
- Không thể phục hồi: held-out chỉ chạy được một lần (`phase-5:65`). Chạy xong với thước đo lệch thì held-out đã "bị nhìn", giống AI2-16, và phải dựng corpus mới + duyệt HG-1 lại.

### RT-02 (High): ứng viên khác Điều của C hầu như không có gold

- Pool = S1 (cùng Điều, đủ hết) ∪ S2 (thân↔phụ lục, trần 200) ∪ S3 = `min(40, …)` cặp khác Điều chọn ngẫu nhiên (`phase-1:45`). Đơn vị chấm là `pair_id` của pool (`phase-5:45`).
- Proxy đo trên fixture repo (`AI2-TEST-MASTER.body.md`, script §5.5): 1218 cặp khác Điều, S3 lấy 40, tức **≈3,3 %**.
- Như vậy ≈97 % cặp `SAME_KEY`/`REFERENCE_CUE`/`EXPLICIT_REF` khác Điều mà C gửi LLM không có gold, và rơi vào `predictions_without_approved_gold`.
- Đó chính là phần giá trị luồng 2 thêm vào, và cũng là kiểu lỗi của run1 (CONFLICT tràn lan giữa các cặp cùng chủ đề khác hành vi, E precision 11/32). Cổng hầu như không đo được phần này; precision chủ yếu đến từ S1, nơi tác vụ dễ hơn.
- Cách sửa giữ được pre-register: ứng viên B/C là deterministic và không dùng LLM. Có thể sinh chúng trên held-out **trước** khi chạy bộ phân loại, gán nhãn GPT phần ngoài pool, rồi thêm vào phiếu theo một quy tắc cố định (ví dụ "mọi cặp B∪C ngoài pool").

### RT-03 (High): CONFLICT tạo thêm context finding + evidence issue, chèn **trước** `graph_issues`

- D11 append candidate CONFLICT **trước** `build_contract_context` (`phase-4:47`; `idp.py:327-329`).
- `build_contract_context` duyệt mọi candidate (`contract_context.py:254-278`). Nếu evidence nằm ở ≥2 phần trong **cùng một file** (thân ↔ phụ lục nhúng) và không phải `COMPARABLE_MATCH`, hàm phát một `CONTEXT_CONFLICT`.
- Chuỗi hệ quả:
  1. `context_issues` có thêm một `EvidenceIssue`.
  2. Issue này được `issues.extend(context_issues)` ở `idp.py:359`, tức **trước** `issues.extend(graph_issues)` ở `idp.py:361`.
  3. Mọi id review theo vị trí `review:{code}:{index}` (`idp.py:556`) của issue luồng 1 dịch đi. Đây là đúng bất biến mà comment D4 ở `idp.py:360` bảo vệ.
  4. Mỗi CONFLICT ra **2** hàng review ở AI2: issue context + candidate.
- Repro §5.1 (OBSERVED): `findings without pair candidate: 2 | with: 3`, có thêm `CONTEXT_CONFLICT NEEDS_REVIEW {'candidate_id': 'cand_pair_demo', ...}`.
- Fixture dự kiến (`phase-4:86`, mẫu `fixtures/contract_graph_records.dossier`) đặt phụ lục ở **file riêng**. Nhánh cross-file `contract_context.py:260-263` bỏ qua candidate, nên `test_existing_review_item_ids_prefix_preserved` (`phase-4:146`) **xanh nhưng sai**. Trong khi đó P1 lại ưu tiên mẫu có phụ lục nhúng (`phase-1:37`), và điểm thưởng thân↔phụ lục (`phase-2:47`) đẩy đúng loại cặp này lên đầu.
- Phía BE không nhân đôi: `_context_findings_as_items` bỏ qua `metadata.candidate_id` (`persistence.py:815`). Vì vậy lỗi chỉ nằm ở phía AI2 (review-id + hàng đợi review).

### RT-04 (High): K-a được thực thi bằng tên model và fail-open

- Quy tắc họ model dựa trên tiền tố `gpt*`/`o<digit>*`/`claude*` (`plan.md:72`, `phase-3:59`).
- Repo dùng id model có tiền tố router: `NineRouterClient(..., model="gh/gpt-4o-mini")` (`tests/test_llm_complete_json.py:12`), `openrouter/openai/text-embedding-3-small` (`docs/ai2/AI2-06-implementation-gap.vi.md:7`).
- Với `gh/gpt-4o-mini`, `family()` ra "không rõ" ≠ `openai`. Kiểm tra coi là khác họ, cho chạy, và vi phạm K-a một cách im lặng.
- Thêm nữa, trace của client ghi `"model": model` — tên **được yêu cầu** (`client.py:108`), không phải `resp.model`. Nên "model thật từ trace" (`phase-3:61`) không chứng minh được model nào thực sự phục vụ. Đây đúng là lỗ hổng làm run1 mơ hồ (`plan.md:93`).
- Sửa ở client là một dòng (`trace["served_model"] = getattr(resp, "model", None)`).

### RT-05 (Medium): bộ lọc injection bỏ nhầm cặp lành tính, không lọc `context`, dễ né

- Do thứ tự ưu tiên của phép `|`, `secret_exfiltration` = `reveal|print|dump|show\s+.*(secret|token|prompt)` (`policy.py:43`) khớp **chuỗi con trần** `reveal`/`print`/`dump`.
- Repro §5.2: 5/5 khoản lành tính bị gắn cờ: "shall not reveal" (bảo mật, song ngữ), "printing services", "anti-dumping duty", "dump truck", "blueprint". Plan quy định "signals khác rỗng ⇒ cặp không gửi" (`phase-3:44`), nên cả chủ đề `CONFIDENTIALITY` ở HĐ song ngữ bị bỏ im lặng.
- Người gán nhãn GPT không lọc, nên gold vẫn có các cặp này và recall bị phạt mà không đổi lại được gì về an toàn.
- Ngược lại, cụm mệnh lệnh nằm trong câu dẫn của cha thì đi vào `context` (`phase-3:43`) mà không qua lọc. Mẫu tiếng Việt chạy trên chuỗi có dấu nên "bo qua moi huong dan" lọt qua.
- Lớp chặn thật là output đóng + span + trạng thái do code gán. Lọc chỉ nên đếm, không nên bỏ cặp.

### RT-06 (Medium): migration 0006 làm đỏ một test luồng 1 không cần DB

- `test_0005_is_the_single_head_after_0004` khẳng định `script.get_heads() == ["0005_ai2_contract_edges"]` (`test_contract_graph_edge_store.py:120`).
- Test này chạy trong suite mặc định: OBSERVED `1 passed` khi không có Postgres.
- Mô phỏng thêm 0006 vào bản sao thư mục migrations (§5.3): `heads = ['0006_ai2_contract_pair_relations'] … equal: False`.
- File này không có trong inventory P4, còn `phase-4:186` lại hứa "test luồng 1 … xanh không sửa (trừ file Postgres)". Cổng "đúng 13 lỗi môi trường" sẽ trượt ở bước 6.
- R12 chỉ nêu `test_contract_graph_postgres_store.py`. Memory class #3 (hard-code head) đã được sửa ở `test_ai2_postgres_store.py:460`, nhưng còn sót ở đây.

### RT-07 (Medium): "dự trữ 30 s" chỉ được kiểm trước lô

- Trong một lô, `complete_json` lặp tối đa `max_attempts` (mặc định 3) lần. Mỗi lần dùng `min(45 s, remaining)`, cộng backoff, cho tới khi `remaining ≤ 0` (`runtime.py:180-201`).
- Lô bắt đầu khi còn 31 s có thể ăn hết hạn job. `ProcessingTimeout` bị nuốt ngay trong pairs. Phần còn lại của `run_idp` (context, propose, review) và `complete_with_snapshot` chạy sau hạn, chỉ còn khoảng 30 s ân hạn của lease (`main.py:258`).
- R7 (`plan.md:218`) hứa "dừng khi remaining() < 30s", nhưng cách thực thi không bảo đảm điều đó.
- Rủi ro timeout cao hơn ước tính: gold run1 dùng khoản ngắn (OBSERVED `clauses_heldout.jsonl` trung bình 225 ký tự, max 615). Lô P3 có thể chứa tới 8 × 2 × (1200 + 300) ≈ 24k ký tự. Con số 10–16k token/hồ sơ (`plan.md:69`) suy từ khoản ngắn nên có thể thấp vài lần `[ASSUMED]`.

### RT-08 (Medium): đường client "anh em" (D6) không được probe

- Runtime tạo client phân loại từ `llm.base_url` (`phase-3:52`). Trong HTTP, `llm = NineRouterClient()` đọc `AI2_LLM_BASE_URL` (`main.py:278`), và theo `plan.md:92` biến này đang trỏ OpenAI.
- Probe P3 bước 0 dùng `base_url=…` do người dùng cấp (`phase-3:85`). Nó có thể xanh trên một endpoint Claude riêng, trong khi production không bao giờ tới được model đó. Hệ quả: mọi job ra `mode="llm"`, `stopped_reason="LLM_FALLBACK"`, 0 quan hệ, và còn kết hợp với RT-14 (xoá dòng cũ).
- Giả định "router phục vụ nhiều model" vẫn đang là `[ASSUMED]` (`plan.md:62`).

### RT-09 (Medium): `EXPLICIT_REF` trỏ dẫn chiếu luật ngoài vào chính khoản của hợp đồng

- Repro §5.4: "…khoản 2 Điều 7 Luật Thương mại 2005" cho ra `['khoan 2 dieu 7']`, `named_document` = `None` (regex đòi số có `/`, `documents.py:16-19`).
- Spec `EXPLICIT_REF` (`phase-2:43`) không có bộ lọc văn bản ngoài. Hợp đồng có khoản 2 Điều 7 thì sinh ra cặp có trọng số **cao nhất** (4, `phase-2:47`). Cặp này chiếm suất `top_k`, sau đó guard `reference_explicit` lại bỏ nhãn REFERENCE.
- HĐ mẫu VN dẫn LTM/BLDS/NĐ rất thường xuyên. Test `test_explicit_ref_resolves_clause_level` không có ca phủ định.

### RT-10 (Medium): CONFLICT ra BE thành severity `high`, không trần, evidence do LLM chọn

- BE gán `severity="high"` cho mọi finding `NEEDS_REVIEW` (`persistence.py:1095`).
- `key_or_topic` lấy `finding_id` vì `item_key=None` (`persistence.py:1087`).
- Không có trần ⇒ tối đa `PAIRS_TOP_K = 40` finding high mỗi hồ sơ, đều cùng một câu `_CONFLICT_REASON`.
- Evidence (`evidence_left=[citation_a]`, `phase-4:53`) dựng từ span 8–240 ký tự **do LLM chọn**. Citation tồn tại thật, nhưng việc chọn đoạn nào làm bằng chứng là output của LLM. Điều này lệch với K-d "Không dùng LLM output làm evidence".
- Cổng hiện chặn sau cờ + consent, nhưng một khi bật thì hàng review BE nhận toàn bộ.

### RT-11 (Medium): runbook rollback bỏ qua process code mới đang sống

- `ensure_database` chạy `migrate()` (upgrade head) ở lần dùng DB đầu tiên của **mỗi process** (`engine.py:39-44`).
- Giữa lúc downgrade và lúc rollout code cũ, bất kỳ process code mới nào khởi động (restart, autoscale, Kafka worker, `ai2_batch`) cũng tạo lại 0006. Code cũ sau đó nổ "Can't locate revision" ở mọi đường Postgres (memory class #2).
- Runbook hiện tại (`plan.md:205`, `phase-4:237-239`) không có bước dừng process. Hậu quả phục hồi được bằng cách deploy lại code mới, nhưng là outage.

### RT-12 (Medium): khối lượng HG-1 bị ước thấp

- Proxy (§5.5) dùng segmenter + `normalize_headings` gần đúng: `AI2-TEST-MASTER.body.md` pool = 213, `HD-TONG-HOP.vi.md` pool = 240 (S2 bị cắt từ 629).
- Với 10 văn bản held-out: ≈2,1–2,4k cặp. 20 % UNRELATED ≈ 400–450 dòng, cộng mọi positive GPT (GPT gán rộng tay, run1 E precision 11/32).
- Plan ước 150–300 dòng / "3–5 giờ" (`plan.md:7, 243`), có thể thấp ~2–4 lần. P5 bị chặn chờ người duyệt.
- Cùng lúc, R2/Q6 gần như chắc chắn ra `KEEP_OFF_INSUFFICIENT_N`. Hai trial biến thể E (tới 300 cặp/văn bản, `phase-5:44`) chủ yếu tốn tiền cho một verdict đã biết trước.

### RT-13 (Medium, `[ASSUMED]`): chia split theo URL, không khử trùng nội dung

- `assign_splits` chỉ sắp theo `sha256(url)` (`phase-1:56`), và kiểm nhiễm bẩn chỉ bằng chuỗi URL khớp chính xác.
- Mẫu HĐ công khai bị chép lại qua nhiều domain. Riêng nguồn spike đã có "thuê mặt bằng" trên 4 domain khác nhau (homedy, hoiluatsu, maudon, luatsuhopdong — `heldout_sources.json`).
- Hai bản gần trùng rơi vào dev và held-out thì 2 vòng lexicon + 3 vòng prompt chỉnh trên dev sẽ rò sang held-out.
- Chưa tải về để chứng minh trùng nội dung.

### RT-14 (Low): chạy rule-only/hỏng giữa chừng xoá quan hệ đã phân loại

- `pair_relations_ran=True` cả khi rule-only (`phase-4:44, 233`). `LLM_FALLBACK`/`DEADLINE` trước lô đầu cũng cho `mode="llm"` với `relations=[]`.
- Job store khi đó DELETE toàn bộ dòng của hồ sơ. Một sự cố provider tạm thời hoặc trích xuất ăn hết ngân sách là xoá sạch dữ liệu do LLM sinh. Muốn có lại phải trả token lần nữa.
- Hiện chưa có ai đọc bảng (không UI/query), nên tác động thấp.

### RT-15 (Low): quyết định duyệt không bị khoá trước khi chạy held-out

- `selection_sha256` khoá **tập được chọn**, không khoá **quyết định** (`phase-5:38`).
- Có thể `review-import` lại sau khi đã thấy scoreboard trial 1, tức relabel theo hướng bộ phân loại. `decide()` (`phase-5:54-58`) không kiểm sha decisions.

## 3. Đường không thể phục hồi

- **Không có** đường runtime nào làm mất dữ liệu nguồn hay để lại trạng thái không phục hồi được:
  - dữ liệu bảng `ai2.contract_pair_relations` tái sinh được bằng cách chạy lại job;
  - downgrade 0006 chỉ drop bảng mới;
  - cờ mặc định tắt.
- Tài nguyên **dùng một lần** của plan là **held-out đã khoá + giờ duyệt HG-1**. Mọi lỗi thước đo phát hiện **sau** P5 (RT-01, RT-02, RT-04, RT-15; RT-05 và RT-09 làm méo số đo) đòi corpus mới + duyệt lại (ước ≥ 8–13 giờ người theo proxy RT-12). Vì vậy các lỗi này phải sửa trong P1/P3, trước khi `--allow-heldout` chạy lần đầu.
- RT-11 là outage (phục hồi được bằng redeploy), không phải mất dữ liệu.
- RT-14 mất dữ liệu phái sinh, phục hồi được bằng tiền token.

## 4. Rủi ro còn lại được chấp nhận (kèm điều kiện)

| Rủi ro | Chấp nhận khi |
|---|---|
| n ≥ 60/nhãn không đạt ⇒ `KEEP_OFF_INSUFFICIENT_N` (R2/Q6) | Artifact ghi `min_n_needed` + số văn bản cần thêm; không hạ ngưỡng |
| Người duyệt thấy `gpt_label` trên phiếu (`phase-1:61`) ⇒ bị neo theo GPT; người gán mù đã bị loại (discovery-brief "Mẫu người gán mù: Không") | Báo cáo ghi rõ ma trận GPT↔người là **cận trên** của mức đồng thuận, không phải hiệu chuẩn độc lập |
| Dev chỉ ≈5 văn bản để chốt K, lexicon, prompt | Ghi số vòng tune và k/n theo cụm; không dùng số dev làm bằng chứng |
| Tất định của pool/E-cap chỉ test cùng process (memory class #1) | Trước `freeze`: chạy `pool` 2 lần trong subprocess với `PYTHONHASHSEED` khác nhau, sha phải bằng. Golden graph-on: OBSERVED 67 case ổn định ở seed 0/1/7 (`AI2_CONTRACT_GRAPH_ENABLED=1 … capture_idp_golden.py --emit-shas`), nên không cần thêm mục `HASHSEED_SENSITIVE` |
| Kafka gọi LLM nhưng không ghi bảng (out of scope) | Coverage `pairs.llm_calls` hiển thị chi phí |

Đã kiểm, **không** phải phát hiện (OBSERVED):
- Consent fail-closed: `ProcessingPolicyFlags.egress_allowed: bool = False` (`wire.py:102`); egress thật lấy từ server (`ai1_snapshot_adapter.py:170`).
- Schema wire cho phép `item_key: null`, `scope: string` ⇒ candidate CONFLICT không làm `job_result_to_wire` nổ (worker boundary, memory class #5).
- `graph_mode` không có consumer nào ngoài `projection.py:101` ⇒ đổi giá trị an toàn.
- BE không nhân đôi context finding có `candidate_id` (`persistence.py:815`).
- `harness/scripts/wilson.py` có đủ `--mcnemar/--diff/--clusters/--judge-screen/--min-n`.
- `bakeoff_rank.py preflight` giới hạn `budget_tokens ≤ 2_000_000`, `budget_seconds ≤ 600` theo mặc định. Biến thể E dễ vượt nên `over_budget` chỉ mang tính tư vấn; cần đặt ngân sách rõ ở P5.

## 5. Phụ lục tái hiện (script đặt ngoài repo, chạy từ `ai-service/`)

### 5.1 RT-03

```
PYTHONIOENCODING=utf-8 uv run --frozen --extra web --extra dev python /tmp/rt_l2/repro_conflict_context.py
→ parts: ['body', 'annex:01']
→ findings without pair candidate: 2 | with: 3
→ EXTRA: CONTEXT_CONFLICT NEEDS_REVIEW {'candidate_id': 'cand_pair_demo', 'disposition': 'COMPARABLE_DIFFERENCE'}
```

Nội dung script, rút gọn:
1. Dùng `fixtures.contract_graph_records.dossier` dựng thân (`Điều 8`/`1.` phạt 8 %) và phụ lục (`Phụ lục 01`/`1.` phạt 12 %).
2. Gộp trang 2 vào **cùng** `source_file_id="f-one"` (`page_revision_id="f-one:p2"`).
3. Dựng `Candidate(COMPARABLE_DIFFERENCE, UNCLEAR, NEEDS_REVIEW, item_key=None)` với citation `citation_for_node(..., text_span="phạt 8%"/"phạt 12%")`.
4. So `build_contract_context(rec, candidates=[])` với `build_contract_context(rec, candidates=[cand])`.

### 5.2 RT-05

```
PYTHONIOENCODING=utf-8 uv run --frozen --extra web --extra dev python -c "from app.security.policy import classify_prompt_injection as c; print(c('Bên B không được tiết lộ (shall not reveal) thông tin bảo mật').signals)"
→ ('secret_exfiltration',)   # tương tự: 'printing services', 'anti-dumping duty', 'dump truck', 'blueprint'; 'Phạt 8% giá trị…' → ()
```

### 5.3 RT-06

- Chạy test: `uv run --frozen --extra web --extra dev python -m pytest -q "tests/test_contract_graph_edge_store.py::test_0005_is_the_single_head_after_0004"` ⇒ `1 passed`.
- Mô phỏng: chép `app/db/migrations` ra thư mục tạm, thêm `0006_ai2_contract_pair_relations.py` (`down_revision="0005_ai2_contract_edges"`), rồi gọi `ScriptDirectory.get_heads()`. Kết quả: `['0006_ai2_contract_pair_relations']` ≠ giá trị test khẳng định.

### 5.4 RT-09

```
uv run … python -c "from app.pipeline.contract_graph.address import parse_addresses, canonical; from app.pipeline.contract_graph.documents import named_document; t='Mức phạt theo quy định tại khoản 2 Điều 7 Luật Thương mại 2005.'; print([canonical(a) for a in parse_addresses(t)], named_document(t))"
→ ['khoan 2 dieu 7'] None
```

### 5.5 RT-02 / RT-12 (proxy pool)

```
PYTHONPATH=<repo> uv run --project ai-service --frozen python /tmp/rt_l2/pool_size.py ai-service/fixtures/contracts/AI2-TEST-MASTER.body.md ai-service/fixtures/contracts/HD-TONG-HOP.vi.md
→ AI2-TEST-MASTER.body.md: nodes=54 roots=14 S1=69 S2=104 S3=40 (raw cross-article 1218) pool=213
→ HD-TONG-HOP.vi.md: nodes=54 roots=54 S1=0 S2=200 (raw 629) S3=40 (raw cross-article 802) pool=240
```

Script dùng `evals.contract_graph.segment.segment` sau một `normalize_headings` gần đúng, rồi đếm cặp không tổ tiên–hậu duệ theo S1/S2/S3. Không in văn bản khoản.
