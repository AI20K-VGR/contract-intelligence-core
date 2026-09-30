# Red-team review: plan AI2-A (measurement baseline)

- **Artifact:** `plans/260929-2323-ai2-a-measure-baseline/` (`plan.md`, 4 phase, `plan-graph.yaml`, `research/*.md`, `artifacts/scope-sizing.json`)
- **Ngày:** 2026-09-30 · **Vai trò:** hs-red-teamer (chỉ tư vấn, không sửa plan hay code)
- **Persona (4):** P-G Goodhart auditor (gate xanh giả) · P-S Statistician · P-C CI/Security engineer · P-F Delivery/feasibility lead
- **Phạm vi:** tấn công cách *thực thi* các quyết định D-A1..D-A13, không bàn lại bản thân quyết định. B và C nằm ngoài phạm vi.
- **Verdict:** **REVISE trước khi cook.** Có 7 finding High. 6 finding đã chứng minh: 5 lỗ Goodhart làm gate xanh giả và 1 deadlock thứ tự ở P2. Finding còn lại là nghi vấn lộ key/chi phí ở workflow live. Finding nào cũng có bản vá rẻ đặt được ngay trong plan, không cần đổi D-A*.

## Cách đã kiểm (chỉ đọc; file tạm để ở scratchpad)

| Lệnh / probe | Kết quả |
|---|---|
| `$PY -m pytest -q -p no:cacheprovider evals/tests` | `2 failed, 9 passed`, cả 2 đều `ConfigDriftError` (khớp research §1) |
| Repo git tạm, `core.autocrlf=true`, thêm `evals/cards/* text eol=lf` rồi chạy `git checkout -- evals/cards` | file vẫn là `w/crlf`. Phải `rm` file rồi checkout lại mới ra `w/lf` (RT-11) |
| `probe_cite2.py`: snapshot 11 dòng qua `adapt_ai1_input` → `FourLayerReasoner(llm=None)` | citation ở mức từng dòng, `bbox` không được dùng; câu hỏi giá trị đơn ra `NEEDS_REVIEW`; answer trích nguyên văn (RT-03, RT-05, RT-08) |
| `OCR_DPI=300 pytest tests/unit/test_core.py::test_schema_and_config` | `DID NOT RAISE ValueError`. Tái lập được T10 (RT-12) |
| `yaml.safe_load(.github/workflows/ai-service.yml)` | khoá `on` bị parse thành `True`; `wf.get("on")` → `None` (RT-10) |
| Đọc `app/reasoning/l0_rules.py`, `fixtures/reasoning/hd_tong_hop_tasks.json`, `evals/corpus/candidate_manifest.json`, `uv.lock` | xem RT-04, RT-05, mục "Đã kiểm, không phải vấn đề" |
| GitHub docs (WebFetch) | `CI` "Always set to `true`"; `workflow_dispatch`/`schedule` "only trigger … if the workflow file exists on the default branch" |

## Bảng findings (xếp theo mức độ × khả năng xảy ra)

| ID | Mức | Loại | Persona | Anchor | Bản vá rẻ nhất |
|---|---|---|---|---|---|
| RT-01 | High | proven | P-G | `phase-2:19,120,187`; `phase-4:39-44`; `.github/CODEOWNERS:3`; `plan.md:66,192` | Gate PR đọc baseline từ `origin/$BASE`, không đọc từ cây của PR; PR có sửa `evals/baselines|cards|data/golden` → exit 1 trừ khi có CODEOWNER riêng duyệt |
| RT-02 | High | proven (theo spec) | P-G | `phase-2:197-198`; `plan.md:137` | Với chỉ số tripwire: đơn vị FAIL mà không có trong tập FAIL của baseline thì tính là hồi quy, kể cả item mới |
| RT-03 | High | proven (cấu hình) | P-G | `phase-3:56`; `phase-4:47-50`; `l3_ground.py:196-198,313-327`; `l0_rules.py:379,388` | Workflow live chạy `--fail-on-threshold` cho tripwire (any-fail-in-k) và diff với `ai2_live.baseline.json` → run đỏ; không chặn PR |
| RT-04 | High | proven | P-G | `l0_rules.py:338-392`; `hd_tong_hop_tasks.json:17,53,62`; `plan.md:124,173`; `phase-1:34` | Bỏ 15 task HD khỏi mẫu số có gate; thêm test "leakage lint"; báo cáo theo split; generator có `--seed` để sinh tập biến thể ở lúc release |
| RT-05 | High | proven | P-G | `phase-1:46,109,112,128,129,178,180`; `plan.md:82,222` | Đảo thứ tự: guideline + `expected_state` commit trước lần chạy reasoner đầu tiên; `expected_state = f(MutationSpec)` có test; worksheet giấu nhãn cũ |
| RT-06 | High | proven (mâu thuẫn trong spec) | P-F | `phase-2:66,88,172-175,226`; `plan.md:65,138`; `phase-3:153` | Card v2 đề xuất nằm ở file riêng (`evals/cards/proposed/…`) + cờ `--card-proposal` trong `--draft`, τ tạm ghi vào report |
| RT-07 | High | **suspected** `[PRIOR]` | P-C | `phase-4:47-50,132`; `plan.md:176,224`; `research/measurement-methodology.md:118`; `pr-guard.yml:44-50` | HC-5 thêm "Deployment branches: `main`"; đặt hard cap ngân sách ở project OpenAI; ghi rõ acceptance cần workflow nằm trên default branch |
| RT-08 | Medium | proven | P-G/P-S | `phase-2:60-62`; `phase-1:30`; `plan.md:65,78,130`; `outline.py:114-117,162` | Gọi đúng tên chỉ số (Jaccard trên tập dòng); `acceptable_spans` là tập dòng tường minh, không lấy cả điều khoản; thêm chẩn đoán `bbox_consistency` |
| RT-09 | Medium | proven | P-C | `phase-1:44,48,131`; `phase-2:39,105,184,199,205`; `phase-3:57`; `phase-4:83,129` | Test happy-path gọi `monkeypatch.delenv("CI")`; P4 bước 7 chạy lại suite evals với `CI=true` |
| RT-10 | Medium | proven | P-C | `phase-4:76-79,140` | Đọc `wf.get("on", wf.get(True))`, assert tập trigger khác rỗng; thêm fixture âm có `pull_request_target` |
| RT-11 | Medium | proven | P-F | `phase-1:55,100,169`; `plan.md:161` | `rm` file rồi `git checkout --`; cấm P1 đụng `*.sha256`; hoặc hạ claim "11/11" xuống P2 |
| RT-12 | Medium | proven (phần mạng `[ASSUMED]`) | P-C/P-F | `src/contract_ocr/infrastructure/config.py:40`; `app/api/main.py:63,79-80`; `phase-4:64,192`; `plan.md:226`; `phase-3:192` | Fixture autouse trong `ai-service/tests/conftest.py` xoá `OCR_DPI`, `AI2_*`, `OPENAI_API_KEY` trừ khi `AI2_LIVE_TESTS=1`; T10 sửa bằng `delenv`, không xfail |
| RT-13 | Medium | proven (số học), độ lớn `[ASSUMED]` | P-S | `research/measurement-methodology.md:98-100`; `phase-2:32-36,193,196`; `plan.md:84` | Thêm cluster bootstrap theo `contract_id` vào `unit_metrics`; in cận dưới Wilson cạnh verdict |
| RT-14 | Medium | DERIVED | P-S | `phase-3:52`; `research/internal-baseline.md:68`; `plan.md:79` | Gate p95 trên các lượt `used_llm=true` (n ≥ 60, thiếu thì `UNDERPOWERED`); bootstrap resample theo `question_id` |
| RT-15 | Low | proven | P-F | `phase-4:60-62,174`; `.gitignore:3`; `fixtures/case_pdf.py:37-56` | Marker riêng `requires_pdf_fixture` + đếm trong CI summary + issue có hạn |

## Đường không đảo ngược được (xếp trước)

1. **RT-07: lộ `OPENAI_API_KEY` hoặc tiêu tiền vượt trần.** Tiền đã tiêu và key đã lộ đều không thu hồi được, key phải xoay vòng. Guard duy nhất phía repo (`max_usd ≤ 20`, `BudgetedClient`) nằm trong code của chính ref được dispatch. Lớp thứ hai là trần ở phía provider: research đã đề xuất (`research/measurement-methodology.md:118`) nhưng plan bỏ, R6 (`plan.md:224`) không nhắc.
2. **RT-01: baseline nuốt hồi quy.** Khi một PR sửa code và chạy `--update-baseline` trong cùng PR, tín hiệu hồi quy mất khỏi mọi lần chạy sau. Lịch sử git vẫn còn, nhưng không ai diff baseline thì không ai thấy. Đây là mất bằng chứng "âm thầm".
3. **RT-11 kết hợp RT-06: tự duyệt.** Ở cả hai chỗ, đường nhanh nhất để agent làm gate xanh là băm lại sidecar hoặc tự chạy `approve_card.py` / `build_golden approve --by "Văn Dũng"`. Guard duy nhất là biến `CI`. Shell của agent có `CI_set=False` (đã quan sát), và xác nhận tương tác bị vượt qua bằng `echo y |` (đã quan sát). Kết quả là chữ ký duyệt bị giả mà mọi acceptance "(invariant)" vẫn xanh (`plan.md:192`).

## Chi tiết từng finding

### RT-01 · High · proven: gate hồi quy tự tham chiếu (P-G)
- **Claim của plan:** PR gate "chặn pass→fail so với baseline đã commit" (`phase-2:19`). Theo VD-2(a), đây là thứ **duy nhất** chặn PR cho tới C (`plan.md:66`).
- **Enforcement thật:** baseline được đọc từ cây của chính PR. Runbook còn cho phép "làm mới baseline (chỉ qua PR)" (`phase-2:120`, bước 9 `:187`). Job CI không fetch base ref (`phase-4:39-44`). `CODEOWNERS:3` là `*` → cả team, nên bất kỳ thành viên nào cũng duyệt được một PR vừa hồi quy vừa cập nhật baseline.
- **Tái lập (viết được thành test ở 2d):** golden mini ở thư mục tạm, baseline có Q1 PASS → sửa pipeline để Q1 FAIL → commit → `run_grounded_query_evals.py --update-baseline` → `run_ai2_gate.py --mode pr` ra exit 0.
- **Cùng lớp lỗi:** duyệt golden/card là presence gate. `plan.md:192` ghi `approval.approved_by = "Văn Dũng"` là "(invariant)", trong khi `approve` chỉ từ chối khi có `CI` (`phase-1:44`). Plan đã thừa nhận giới hạn này ở `plan.md:178`, nhưng acceptance vẫn dán nhãn invariant.
- **Vá:** ở `--mode pr`, lấy baseline từ `git show origin/$BASE:evals/baselines/<f>` (checkout `fetch-depth: 0`). PR có sửa `evals/baselines/**`, `evals/cards/**`, `evals/data/golden/manifest.json` → gate in diff và exit 1, trừ khi có label hoặc CODEOWNER riêng duyệt (thêm dòng CODEOWNERS cho 3 path này, cần mentor duyệt). Đổi mục HC-1 ở `plan.md:192` thành `manual — manual_test_anchor.py` kèm SHA commit của Văn Dũng.

### RT-02 · High · proven theo spec: "item mới không phải hồi quy" bỏ ngỏ đúng các chỉ số zero-tolerance (P-G)
- `phase-2:197`: "item mới hoặc bị bỏ được báo nhưng không phải hồi quy". `phase-2:198`: ngưỡng trượt khi không enforce → exit 0. Với chỉ số phía phát ra (`value_fabricated`, `citation_correct`, `fact_value_fabricated`), item là `question_id`, và item chỉ xuất hiện khi hệ thống phát ra đơn vị (`plan.md:137`).
- **Input kích hoạt:** câu Q có gold ANSWERED. Ở baseline, hệ thống trả ANSWERED với answer chỉ là heading "Điều 2. …", không có giá trị nào (probe cho đúng dạng này với "Điều 2 nói gì?"). `value_accuracy` của Q đã FAIL sẵn, `value_fabricated` không có item Q. Ở bản mới, answer chứa "1.586.400.000 đồng", giá trị không có trong tài liệu. Khi đó `state_match` vẫn PASS, `value_accuracy` FAIL→FAIL (không phải hồi quy), `value_fabricated` là item mới (không phải hồi quy) → **exit 0**. Lỗi D-A8 nặng nhất lọt qua PR gate.
- Item đã FAIL sẵn trong baseline (khoảng 12% nếu mốc là 87,5%) có thể xấu đi tuỳ ý mà không bị báo.
- **Vá:** cho tripwire (`max_failures: 0` hoặc ngưỡng 1,0), hồi quy = mọi đơn vị FAIL có `(item_id, unit_id)` chưa nằm trong tập FAIL của baseline. Thêm vào `test_regression_detection` một case "item mới FAIL ở tripwire → hồi quy".

### RT-03 · High · proven (cấu hình): gate "0 bịa" không bao giờ đỏ ở lane có LLM (P-G)
- **Offline:** answer do L0/L1 ghép từ dòng nguồn. Probe trả "Các đoạn liên quan … (trích nguyên văn)" và "Chữ nguồn · Giá trị hợp đồng là 1.286.400.000…". Vì vậy `value_fabricated` offline chỉ có thể bắt được các literal hardcode của L0 (`l0_rules.py:379` "100 USD", `:388`). Nó gần như không nhạy với rủi ro thật, là văn xuôi của LLM (research `measurement-methodology.md:47`).
- **L3 không chặn được bịa trong văn xuôi LLM:** `_extractive` trả True chỉ cần **một** `text_span` của citation có trong text (`l3_ground.py:313-320`), và chỉ áp cho ANSWERED (`:196-198`).
- **Live:** exit 0 khi ngưỡng trượt, trừ khi có `--fail-on-threshold` (`phase-3:56`). Lệnh trong workflow (`phase-4:50`) không truyền cờ đó, và không có bước diff với `ai2_live.baseline.json`.
- **Hệ quả:** suốt giai đoạn A→C, không lane tự động nào đỏ khi LLM bịa giá trị. Lỗi chỉ lộ ra ở release (VD-2a).
- **Vá (không chặn PR, giữ đúng VD-2):** workflow live truyền `--fail-on-threshold --tripwire-only`, và `benchmark.py` so với `ai2_live.baseline.json` theo item (any-fail-in-k). Run theo lịch sẽ đỏ và gửi thông báo.

### RT-04 · High · proven: rò rỉ tập test; holdout chỉ để trang trí (P-G)
- `l0_rules.py:338-392` hardcode answer **và** node id của fixture cho đúng các câu hỏi HD: T-FX "Quy đổi 100 USD…" → `field_usd`; T-SCOPE → `field_penalty_build/equip`; T-PL7 → `cl_9`; T-GAP3 "Điều 3"; T-UNNUM "Thanh toán". Các id này chính là `must_cite` ở `hd_tong_hop_tasks.json:17,53,62`. Như vậy ít nhất 5/15 task HD được trả lời nhờ luật đã khớp sẵn câu hỏi thi.
- Plan vẫn đưa 15 task này vào mẫu số của `state_match` có gate (`plan.md:124`, HC-2 ở `plan.md:173`: "phần legacy HD của `state_match`"). Con số 21/24 (`research/internal-baseline.md:69`) nhiều khả năng cũng đo trên loại câu này.
- Golden giả lập sẽ nằm công khai trong `questions.json`, và CI in lỗi theo từng item (`phase-4:44`). C (nâng lên ≥ 95%) có sẵn cơ chế: thêm regex theo đúng câu hỏi. Split `holdout {G06, G07}` (`phase-1:34`) không được tách khi chấm. Nếu có tách thì holdout cũng dưới 60 đơn vị, nên sàn D-A9 ép phải gộp, và gộp thì mất holdout.
- **Vá:** (1) HD tasks chỉ là chỉ số chẩn đoán `tuned_legacy`, không vào mẫu số gate. (2) Thêm `test_no_eval_leakage`: không có chuỗi câu hỏi golden/HD hay node id fixture (`field_usd`, `cl_9`…) mới nào trong `ai-service/app/**`, allowlist ghi rõ 5 literal hiện có. (3) Report tách theo split. (4) `build_golden --seed N --variant` sinh tập biến thể (tên, số liệu, cách hỏi) chưa từng commit, dùng cho verdict release của B/C.

### RT-05 · High · proven: nhãn gold bị neo vào output hệ thống (P-G)
- Thứ tự thực thi ở P1: bước 6 "làm G01 trước, chạy smoke cho xanh" (`phase-1:109`). Smoke chạy `FourLayerReasoner` (`:128`). Guideline định nghĩa 5 trạng thái được viết ở **bước 9** (`:112`), mâu thuẫn với R4 "Guideline viết trước" (`plan.md:222`, `phase-1:180`). Người đặt `expected_state` cho 84 câu là agent cook, và agent đã thấy output.
- Ngữ nghĩa trạng thái hiện do hệ thống quyết định. Probe cho "Giá trị hợp đồng là bao nhiêu?" (một giá trị, không xung đột) ra `NEEDS_REVIEW` "không chọn bản nào đúng". Gold ghi ANSWERED hay NEEDS_REVIEW chính là chỗ bị neo.
- `phase-1:178`: adapter tách/gộp dòng khác spec thì "sửa spec (không sửa adapter)". Nghĩa là gold được uốn theo hệ thống đang bị đo.
- **HC-2:** worksheet hiện "nhãn hiện tại map sang ReviewState" (`phase-1:46`). Nhãn này lấy từ `eval_suite.py` (61/95 REVIEW) và khớp với hệ thống 69/95 (`plan.md:82`). Test "blind" chỉ kiểm `sys.modules` (`phase-1:129`), không kiểm việc lộ nhãn sẵn. Một người duyệt với mặc định có sẵn thì bấm APPROVE là xong.
- **Vá:** commit guideline + catalog có `expected_state` **trước** lần chạy reasoner đầu tiên (ghi SHA vào `verification-P1.json`). `expected_state` sinh theo luật từ `MutationSpec` (xung đột → NEEDS_REVIEW, phụ lục thiếu → INSUFFICIENT_EVIDENCE…) và có test cho luật. Smoke không in state. Worksheet giấu nhãn cũ; sau khi Văn Dũng điền xong thì tính độ đồng thuận với nhãn của tác giả fixture. Việc này cho một con số hai nguồn miễn phí cho mục hạn chế D-A10, không đổi D-A10.

### RT-06 · High · proven: deadlock ở P2 giữa card drift, τ và HC-3 (P-F)
- Card v2 được viết "đề xuất (không đụng sidecar)" (`phase-2:172`) → sidecar lệch → drift. Theo hợp đồng, drift → exit 2 (`plan.md:138`). `--draft` chỉ nới điều kiện duyệt golden (`phase-2:88`). Thiếu τ → lỗi setup (`phase-2:66`).
- VD-1(c) cần histogram IoU từ một lượt draft (`phase-2:175`, `plan.md:65`). Nhưng lượt draft cần card đã duyệt và có τ, còn duyệt card (HC-3) lại cần τ.
- **Hệ quả:** số đo draft ở bước 4 (`phase-2:174`), gate "trước HC là `--draft` → exit 0" (`phase-2:226`) và gate của P3 (`phase-3:153`) đều không đạt được trước HC-3. Agent bị kẹt thì cám dỗ lớn nhất là tự chạy `approve_card.py`.
- **Vá:** card đề xuất đặt ở `evals/cards/proposed/<domain>.v2.json`. `--draft --card-proposal <path>` chạy được; report ghi `card_approved: false` và `tau_provisional`, **không bao giờ** ghi được baseline. `approve_card.py` là đường duy nhất để chuyển card đề xuất sang `evals/cards/`.

### RT-07 · High · suspected `[PRIOR]`: workflow live chạy code của ref tuỳ ý với secret (P-C)
- `workflow_dispatch` cho người có quyền write chọn ref `[PRIOR]`. Workflow và `run_live_benchmark.py` chạy từ ref đó, nên cả bước chặn `max_usd > 20` (`phase-4:49`) lẫn `BudgetedClient` đều nằm trong code do người dispatch kiểm soát. Rào duy nhất là reviewer bấm "Approve deployment", và màn hình đó không hiện diff.
- HC-5 (`plan.md:176`, `phase-4:132`) không giới hạn deployment branch. Plan cũng không có trần ngân sách phía OpenAI.
- **Đã quan sát (docs):** `workflow_dispatch` và `schedule` chỉ chạy khi file workflow nằm trên default branch. Luồng repo là feature → `develop` → `main` (`pr-guard.yml:44-50`), nên "sau khi merge" (`phase-4:132`) vào `develop` chưa đủ để đạt acceptance live của P4. Ngoài ra, mỗi run theo lịch sẽ chờ required reviewer, tức phải có người bấm duyệt mỗi tuần.
- **Vá:** HC-5 thêm "Deployment branches: `main` (protected)" và hard budget ở project OpenAI. Acceptance P4 ghi rõ điều kiện workflow đã lên default branch. **Điều kiện chấp nhận nếu không vá:** key chỉ có quyền của một project OpenAI riêng có hard limit.
- **Xác minh cần làm:** khi làm HC-5, thử dispatch trên một nhánh không phải `main`. Nếu run bị từ chối thì hạ finding này xuống Low.

### RT-08 · Medium · proven: D-A11 "span/bbox" không thật sự được đo (P-G/P-S)
- F2.4 lấy vùng được cite từ bbox **dòng của snapshot** (`phase-2:60`), không từ bbox hệ thống phát ra. Bbox phát ra hiện là `[]` (PB-4, `plan.md:78`). Nếu B/C sau này phát bbox sai hệ toạ độ, scorer vẫn cho PASS.
- Citation thật ở mức dòng (probe: `line_ids ['p1-l7']`…; `outline.py:114-117,162` gán `line_ids` theo dòng của node). Gold cũng ở mức dòng. Các dòng không chồng nhau, nên IoU chỉ nhận giá trị {0, 1} và τ (VD-1) không có tác dụng.
- `acceptable_spans` gồm "các dòng của điều khoản chứa span đó" (`phase-1:30`). Có hai cách hiểu, và cách nào cũng hỏng: (a) từng dòng là một span → mọi dòng trong điều khoản đều đúng. Probe hỏi "Thời hạn thanh toán…" thì hệ thống cite cả `p1-l8` "Tiền phạt chậm thanh toán…" lẫn `p1-l5` heading, và cả hai sẽ bị tính là đúng. (b) Hợp thành một bbox → IoU của một dòng so với điều khoản n dòng ≈ 1/n, nên span đó không bao giờ khớp.
- **Vá:** đặt tên đúng cho chỉ số (Jaccard trên tập dòng, ngưỡng τ áp lên tập dòng). `acceptable_spans` là các tập dòng tường minh theo từng câu hỏi, không lấy cả điều khoản. Thêm chỉ số chẩn đoán `bbox_consistency` (bbox phát ra so với hợp các dòng khi `geometry_available`). Thêm test đối nghịch: cite đúng điều khoản nhưng sai dòng trong một điều khoản ≥ 5 dòng → FAIL.

### RT-09 · Medium · proven: guard `CI` làm đỏ các test happy-path trên GitHub (P-C)
- `promote`, `approve`, `approve_card`, `write_baseline`, `--write-baseline` đều từ chối khi có `CI` (`phase-1:44,48`; `phase-2:39,105`; `phase-3:57`). GitHub **luôn** đặt `CI=true` (docs). Các test happy-path `test_promote_moves_is_idempotent_and_keeps_separation` (`phase-1:131`), `test_approve_card` (`phase-2:205`) và `test_gate_exit_codes` (cần baseline trong thư mục tạm, `phase-2:184`) sẽ đỏ **chỉ** trên CI.
- Bước "chạy local trước" (`phase-4:83,129`) không bắt được lỗi này, vì shell local có `CI_set=False` (đã quan sát). Khi đó, cách sửa "rẻ" mà cook dễ chọn là nới luôn guard.
- **Vá:** test happy-path gọi `monkeypatch.delenv("CI", raising=False)`; test từ chối gọi `setenv("CI","true")`. P4 bước 7 chạy thêm một lượt `CI=true $PY -m pytest evals/tests`.

### RT-10 · Medium · proven: test bất biến bảo mật của workflow đạt một cách rỗng (P-C)
- PyYAML parse `on:` thành `True`. Repro:
  ```
  ai-service/.venv/Scripts/python.exe -c "import yaml;wf=yaml.safe_load(open('.github/workflows/ai-service.yml'));print(list(wf), set(wf.get('on') or {}) <= {'workflow_dispatch','schedule'})"
  ```
  → `['name', True, 'permissions', 'jobs'] True`. Nghĩa là workflow hiện tại, vốn có `pull_request`, vẫn qua kiểm tra "trigger ⊆ {dispatch, schedule}", và "không có `pull_request_target`" cũng qua mà không kiểm gì.
- `test_live_workflow_is_isolated` và `test_pr_workflow_has_no_secrets_and_read_only` (`phase-4:76-79,138-140`) viết theo cách tự nhiên sẽ luôn xanh.
- **Vá:** `triggers = wf.get("on", wf.get(True))`; `assert triggers`; kèm fixture YAML âm (có `pull_request_target`, có `pull_request` ở workflow live) và test phải bắt được.

### RT-11 · Medium · proven: bản sửa CRLF ở P1 không có hiệu lực trên Windows (P-F)
- Repro ở repo tạm (`core.autocrlf=true`): commit LF → checkout ra `w/crlf` → thêm `evals/cards/* text eol=lf` → `git checkout -- evals/cards` → vẫn `i/lf w/crlf attr/text eol=lf`. Git bỏ qua file đã sạch theo stat. Chạy `rm` rồi `git checkout --` mới ra `w/lf`.
- Thêm nữa, `evals/eval_config.json` không nằm trong 4 luật F1.10 (`phase-1:55`). Vì vậy claim "11/11, 2 test mutation hết đỏ" (`phase-1:100,169`, `plan.md:161`) sẽ trượt ở P1, và đường tắt để xanh là băm lại sidecar trên byte CRLF, tức là giả chữ ký duyệt (xem mục đường không đảo ngược).
- **Vá:** ở bước 2, xoá file rồi `git checkout --` (hoặc `git rm --cached` + `git checkout`). Ghi rõ P1 **không** được sửa `*.sha256`. Nếu vẫn đỏ thì ghi vào verification, để P2 (F2.9) xử lý.

### RT-12 · Medium · proven: nguyên nhân gốc của T10 là `.env` bị nạp vào suite "offline" (P-C/P-F)
- `load_settings` đè `dpi` bằng `os.environ["OCR_DPI"]` (`src/contract_ocr/infrastructure/config.py:40`). `ai-service/.env` có key `OCR_DPI` (chỉ đọc tên key). `app/api/main.py:63` gọi `load_dotenv(ROOT/".env")` ngay khi import, và 11 module test import `app.api.main`.
- Repro: `OCR_DPI=300 .venv/Scripts/python.exe -m pytest tests/unit/test_core.py::test_schema_and_config` → `DID NOT RAISE`. Chạy riêng không có env → pass. Trên CI không có `.env`, nên T10 sẽ xanh. Kế hoạch "bisect 2 giờ rồi `xfail(strict=False)`" (`phase-4:64,192`) chỉ che lỗi, và mâu thuẫn R8 "xfail `strict=True`" (`plan.md:226`).
- Cùng cơ chế đó nạp `OPENAI_API_KEY`, `AI2_LLM_API_KEY`, `AI2_VECTOR_RECALL_ENABLED` vào lượt chạy offline local. `VECTOR_RECALL` được dựng ở module level sau `load_dotenv` (`main.py:79-80`). Vì vậy R3-6 "Thấp" (`phase-3:192`) sai, và cơ chế opt-in ở F3.5/F3.8 bị vượt qua. Phần "gọi mạng thật" là `[ASSUMED]` vì tuỳ giá trị trong `.env`, mà review này không đọc giá trị.
- **Vá:** fixture autouse ở `ai-service/tests/conftest.py`, trừ khi `AI2_LIVE_TESTS=1` thì `delenv` các biến `OCR_DPI`, `AI2_*`, `OPENAI_API_KEY`, `*_API_KEY`. T10 sửa bằng `monkeypatch.delenv("OCR_DPI")`. Việc chuyển `load_dotenv` vào startup là thay đổi code production, nên ghi làm follow-up cho B.

### RT-13 · Medium · proven (số học), độ lớn `[ASSUMED]`: Wilson trên đơn vị bị cụm và "PASS" theo ước lượng điểm (P-S)
- Đơn vị cùng câu hỏi hoặc cùng hợp đồng tương quan với nhau. Golden chỉ có 8 hợp đồng, và G05 chiếm phần lớn. Research khuyến nghị cluster bootstrap theo hợp đồng (`research/measurement-methodology.md:98`), nhưng F2.1 chỉ có Wilson (`phase-2:32-36`), nên CI hẹp hơn thực tế.
- `test_threshold_boundary`: 57/60 → PASS (`phase-2:196`). Cận dưới Wilson là 86,3% (`plan.md:84`), nên nhãn "PASS ≥ 95%" nói nhiều hơn bằng chứng.
- **Vá (không đổi ngưỡng D-A8):** thêm `cluster_bootstrap_ci(units, cluster_key="contract_id")` và in cạnh Wilson. Verdict ghi `PASS(point)` kèm `lower_95`. Mục hạn chế của AI2-16 nêu rõ n hiệu dụng.

### RT-14 · Medium · DERIVED: p95 gộp bị pha loãng bởi các câu không dùng LLM (P-S)
- Offline mất 0–6 ms/câu (`plan.md:79`). Chỉ khoảng 3/27 câu dùng LLM (`research/internal-baseline.md:68`). Gọi s là tỉ lệ lượt dùng LLM: p95 gộp rơi vào nhóm LLM chỉ khi s > 5%, và khi đó nó xấp xỉ **phân vị (1 − 0,05/s)** của nhóm LLM. Với s = 11%, p95 gộp ≈ p55 của nhóm LLM. Ví dụ LLM có p50 = 15 s, p95 = 40 s → p95 gộp ≈ 15 s → gate < 20 s vẫn PASS. Với s < 5%, p95 gộp nằm ở mức mili giây, bất kể LLM chậm tới đâu.
- k = 5 lượt của cùng một câu không độc lập. Bootstrap theo lượt (`phase-3:52`) cho CI quá hẹp.
- **Vá:** `latency_p95_s` có gate tính trên các lượt `used_llm=true` (sàn 60, thiếu thì `UNDERPOWERED`); p95 gộp chỉ là chẩn đoán. Bootstrap resample theo `question_id`.

### RT-15 · Low · proven: 5 test PDF bị tắt vĩnh viễn trên CI (P-F)
- T4–T8 dùng `skipif(not path.exists())` (`phase-4:60-62`) cho các PDF không bao giờ commit được (`.gitignore:3`, `pr-guard`), nên trên CI chúng luôn skip. Kiểu guard này cũng skip âm thầm nếu sau này fixture bị đổi tên.
- `fixtures/case_pdf.py` sinh được PDF, nhưng trên Linux sẽ rơi về font Helvetica (`:37-56`), mất dấu tiếng Việt, nên không thay thế trực tiếp được.
- **Vá:** marker `requires_pdf_fixture`, số test skip của marker này in ra `$GITHUB_STEP_SUMMARY`, kèm issue follow-up có hạn chót. **Chấp nhận được** nếu `verification-P4.json` ghi đúng 5 test này và không có skip nào khác (`phase-4:174` đã gần như vậy).

## Rủi ro còn lại được chấp nhận (kèm điều kiện)

- **`gh` không có trong môi trường này** (`phase-4:126` `[ASSUMED]`; lệnh `gh` báo "No such file or directory"). Thay bằng `git ls-remote https://github.com/actions/checkout refs/tags/v4`. Đã kiểm: tag v4/v5 của checkout, upload-artifact, setup-python là lightweight (không có `^{}`), nên SHA từ ls-remote chính là commit SHA.
- **Job `evals-offline` không có `uv sync` riêng** (`phase-4:40-43`). Mỗi job chạy trên runner mới, nên phải tự sync. Chấp nhận nếu `test_pr_workflow_runs_gate_offline` kiểm có bước sync trong job đó.
- **Ruff F401 autofix sẽ xoá re-export có chủ đích** ở `app/tools/jobs.py:12-20` (comment ghi "exposing the canonical durable run boundary"; trong repo không có importer nào). Chấp nhận nếu thêm `__all__` hoặc `# noqa: F401` trước khi autofix.
- **`test_offline_is_hermetic` dùng sentinel raise** (`phase-2:201`), trong khi `runtime.py:101` nuốt `Exception`. Hiện chưa nguy hiểm vì `real_pipeline` truyền `llm=None` tường minh. Chấp nhận nếu dùng spy đếm lời gọi thay cho raise.
- **`fact_value_fabricated` chỉ tính trên case GOLDEN** → trước HC-2 thì n = 0, tripwire trơ. Kiểm tra này không cần nhãn (giá trị có trong text hay không), nên có thể gate trên fact của candidate mà không vi phạm `docs/code-standards.md:42`. Đây là quyết định cho người dùng, không phải blocker.
- **`build` và `--check` so với khối `approval`** (`phase-1:39,42,120`). Chấp nhận nếu `--check` chỉ so `files[]`, và `build` giữ nguyên `approval` hoặc từ chối ghi đè khi `approval` khác null.
- **Required check có paths filter:** nếu mentor đặt `ai-service` thành required, các PR không đụng những path đó sẽ treo `[PRIOR]`. Ghi vào `ai-service/README.md` trước khi mentor quyết.

## Đã kiểm, không phải vấn đề (giúp đóng câu hỏi mở)

- `uv.lock` có `aiokafka` và `mistralai` (câu hỏi mở số 3, `plan.md:241`; riêng `uv sync --frozen` thì chưa chạy). `openai` là dependency gốc, không phải extra, nên CI không thiếu.
- `adapt_ai1_input` với snapshot thô cho `egress_approved` mặc định True (`app/tools/store.py`, `DossierRecord`), nên `run_idp` có LLM không bị BLOCKED vì egress.
- T9: artifact có trong `10ae216` (`git cat-file -e` OK). T11: `parents[3]/docs/contracts` đúng là thư mục có thật. T3: `_answer_language_instruction` đúng là không có trong `app/`.
- Tag action: lightweight, nên pin SHA qua `object.sha` không bị lấy nhầm tag-object.

## Checklist red-team
- [x] Tấn công giả định và đường hỏng, không bàn style
- [x] Mỗi finding có `file:line`, lệnh repro hoặc input kích hoạt
- [x] Tách proven và suspected (RT-07 `[PRIOR]`; phần mạng của RT-12 `[ASSUMED]`)
- [x] Đường không đảo ngược xếp trước (RT-07, RT-01, RT-11 + RT-06)
- [x] Kiểm khoảng cách giữa claim và enforcement (RT-01, RT-08, RT-10, presence gate duyệt)
- [x] Mỗi finding có bản vá rẻ nhất hoặc điều kiện chấp nhận
- [x] Không sửa code hay plan; chỉ ghi file report này (probe nằm ở scratchpad)
