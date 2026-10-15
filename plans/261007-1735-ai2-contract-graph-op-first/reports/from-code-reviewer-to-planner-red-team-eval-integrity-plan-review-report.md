# Red-team review plan — AI2 contract graph luồng 1 (operation-first)

- Ngày: 2026-10-07 · Artifact: `plans/261007-1735-ai2-contract-graph-op-first/plan.md` + 4 phase · Trạng thái plan: `pending` (chưa cook)
- Persona: **(A) eval-integrity skeptic** (chính) · **(B) backward-compat / BE-contract / vận hành** · **(C) domain / legal-text realist**
- Phạm vi: chỉ đánh rủi ro thực thi. Không đụng các quyết định đã khoá K1–K9 và các quyết định người dùng trong `research/researcher-01-synthesis.md`.
- Nhãn: **proven** = có lệnh tái lập hoặc `file:line` cho thấy chắc chắn; **suspected** `[ASSUMED]` = có thể xảy ra nhưng chưa kích hoạt được.
- Không có fact `code.fan_in` trong envelope nên không có dòng fan-in.

**Verdict: REVISE trước khi cook.** Có 4 High (golden flag-off phụ thuộc `PYTHONHASHSEED`; không có dạng địa chỉ hậu tố `5a`/`d1` nên gold và pred sai giống nhau; rollback P4 làm hỏng boot; lỗi ghi cạnh làm FAILED cả job). Cả 4 đều sửa rẻ bằng cách chỉnh plan/test, không phải đổi hướng. Không thấy đường mất dữ liệu nào không hồi phục được.

## Bảng finding (xếp theo mức nghiêm trọng)

| id | Mức | proven / suspected | Anchor | Cách sửa rẻ nhất |
|---|---|---|---|---|
| RT-01 | High | proven | `ai-service/app/pipeline/compare.py:67-71`; `phase-3-operation-parser.md:129,225` | Capture và kiểm golden trong **subprocess** với `PYTHONHASHSEED=0` cố định. Thêm test chạy 2 subprocess với seed khác nhau. Sửa hướng dẫn "tìm thêm nguồn uuid/time" thành "uuid/time/**thứ tự set**" |
| RT-02 | High | proven | `phase-1-vbhn-eval-harness.md:40-41`; `phase-2-address-resolver.md:31-38,84`; dữ liệu `nd50.html` | Thêm hậu tố vào canonical P1 §3, nhãn segment P1 §4 và grammar P2 §2: `điểm [a-zđ]\d*`, `khoản \d+[a-zđ]?`, `Điều \d+[a-zđ]?`, cùng danh sách trần "d1, d2". Thêm bất biến INSERTION `canonical(new) != canonical(anchor)` |
| RT-03 | High | proven | `plan.md:182`; `ai-service/app/db/migrations/env.py:5`; `ai-service/app/db/engine.py:43` → `migrate.py:29` | Sửa runbook: revert code P4 khi chưa downgrade sẽ làm **hỏng boot**, không "vô hại". Thêm entrypoint downgrade (vd `python -m app.db.migrate --downgrade 0004_ai2_job_indexes`) và test cho nó. Rollback mặc định = tắt flag, không revert code |
| RT-04 | High | proven (đường code) · trigger `[ASSUMED]` | `phase-4-edge-storage.md:54,126`; `ai-service/app/api/main.py:319-337`; `plan.md:66` (D11) | Bọc `replace_contract_edges` trong `cx.begin_nested()`. Lỗi thì log, giữ cạnh cũ và vẫn commit job + snapshot (cùng ngữ nghĩa với "builder lỗi ⇒ giữ cạnh cũ"). Lọc `\x00` khỏi các cột text. Thêm test ở mức `_execute_wire_job` |
| RT-05 | Medium | proven | `phase-1-vbhn-eval-harness.md:41`; `phase-3-operation-parser.md:71`; nhãn trong `ai-service/fixtures` | Thêm chế độ đo thứ hai: gập cây VBHN thành node chỉ có "Điều N" (giống hình dạng AI1) rồi báo cả hai trong `p2-resolver`/`p3-operation-parser` |
| RT-06 | Medium | proven | `phase-3-operation-parser.md:58`; `phase-2-address-resolver.md:59`; `persistence.py:834,851` | Chỉ phát REJECTION/SCOPE_LIMIT khi nguồn nằm ở phần `annex:*` hoặc dưới một đơn vị chứa thao tác. Sửa đánh giá tác động ở `phase-3:227` |
| RT-07 | Medium | proven | `plan.md:58,60` (D3, D5); `persistence.py:815,1047-1050` | Cạnh nào đã mở khoá một candidate thì đặt `metadata.candidate_id` = id của candidate đó (BE bỏ qua finding trùng); hoặc mở rộng R6 và ghi rõ trong AI2-19 |
| RT-08 | Medium | proven | `phase-3-operation-parser.md:46-55,58`; `relation_markers.py:16` | Thêm mẫu SUBSTITUTION (không std) cho `Điều chỉnh|Thay đổi <địa chỉ> … như sau:` và `<địa chỉ> được thay bằng`; thêm fixture phụ lục hợp đồng |
| RT-09 | Medium | proven | `phase-3-operation-parser.md:57,182`; `vbhn_notes.py:12-13` | Đổi tên chỉ số thành `op_lexical_agreement`. Thêm điều kiện precision (`unmatched_predictions` không tăng) vào `test_p3_report_not_worse_than_baseline` |
| RT-10 | Medium | proven | `phase-2-address-resolver.md:140,169`; spike §Giới hạn 1 | Thay mốc 16/26 bằng số `target_correct` đo được của `p1-baseline` (P1 bước 8); bỏ chữ "đúng" gắn với 16 |
| RT-11 | Medium | proven | `ai-service/tests/test_ai2_postgres_store.py:612`; `phase-4-edge-storage.md:136`; `.github/workflows/ai-service.yml:23-24` | Đưa file vào inventory P4, đổi assert thành `version == head` (mẫu `_ai2_state`, dòng 445-460) |
| RT-12 | Medium | proven | `plan.md:59` (D4); `idp.py:279,292-318`; `compare.py:64,196-221` | Append issue graph **sau** `idp.py:318`. Viết lại test `test_flag_on_keeps_existing_review_item_ids`: chỉ khẳng định cho fixture không mở khoá cặp nào, hoặc chỉ cho tiền tố trước điểm chèn |
| RT-13 | Medium | proven (gap) · tác động `[ASSUMED]` | `phase-1-vbhn-eval-harness.md:43`; `vbhn02bxd.html.gold.json` (2 bản ghi cùng src); `op_parser_eval.py:51-63` | Đặc tả scorer: ghép theo `(src_address, target_address)` một-một; pred thừa cùng src → unmatched. Thêm test 2 gold cùng src |
| RT-14 | Medium | suspected `[ASSUMED]` | `phase-1-vbhn-eval-harness.md:33`; `op_parser_eval.py:43`; `nd50.html` (có “Điều 23.” trong Điều 1) | `operative_body` bỏ qua `Điều N.` nằm trong “…”. Thêm fixture "Sửa đổi Điều 2 như sau: “Điều 2. …”" |
| RT-15 | Low | proven (dữ liệu) · suspected (mạng) | `phase-1-vbhn-eval-harness.md:24,84-85`; `.git/info/exclude:12` | Cook ngay trong worktree `contract-intelligence-develop` hoặc chép `raw/` vào cache trước. Cho phép P2 bắt đầu với nd50 + mini fixture khi P1 bị BLOCKED vì thiếu cặp |

## Chi tiết theo persona

### (A) Eval-integrity skeptic

**RT-01 — Golden flag-off không tái lập được giữa các process (High, proven).**
- Tái lập: chạy `run_idp` trên `fixtures.catalog.all_cases()` + `mock_record` đúng cách P3 quy định. Patch `uuid4` ở `idp`/`clause`/`compare` bằng bộ đếm (`phase-3:80`), `job_id="job_golden"`, rồi lấy sha256 của `json.dumps(job_result.model_dump(mode="json"), sort_keys=True)`. Từ `ai-service/` chạy `PYTHONHASHSEED=<s> .venv/Scripts/python.exe <probe>` với s = 1..7. Kết quả OBSERVED: 65/66 case ổn định; riêng `SERVICE-BRD-08` cho `2b99d4e14780226f` ở seed 1, 6, 7 và `ca5b52137ea6e838` ở seed 2, 3, 4, 5.
- Nguyên nhân: `compare.py:67` dựng `fee_keys` là một set chuỗi, `:68` lặp set đó thành list, `:70-71` lấy `scopes[0]`/`scopes[1]` làm hai vế left/right. Diff giữa hai seed cho thấy `fx`↔`fy` đổi chỗ (`text_span` "50%"↔"10%").
- Vì sao plan bỏ sót: `test_run_idp_is_deterministic_under_patched_uuid` (`phase-3:129`) chạy 2 lần **trong cùng process**, cùng hash seed, nên luôn xanh. Golden capture ở một process còn pytest chạy ở process khác, nên `test_flag_unset_matches_golden` sẽ flaky khoảng 3/7. Phép kiểm chéo worktree `70998af` ở P3 bước 1 cũng có thể lệch. Ở `phase-3:225` plan hướng cook đi tìm "nguồn uuid/time", tức là sai hướng.
- Sửa rẻ nhất: chạy capture và kiểm tra trong subprocess với `PYTHONHASHSEED=0`. Thêm một test so sha giữa 2 subprocess seed khác nhau để lộ ra các phụ thuộc thứ tự set mới. **Không** sửa `compare.py` trong đợt này, vì như vậy đổi bytes của đường cũ.

**RT-02 — Địa chỉ hậu tố (`khoản 5a`, `điểm d1`, `Điều 30a`) không có trong canonical, segment hay grammar (High, proven).**
- Bằng chứng dữ liệu (probe trên `.harness/state/vbhn-probe/raw/nd50.html`): "Bổ sung điểm i1 vào sau điểm i khoản 1", "Bổ sung điểm d1, d2 vào sau điểm d khoản 2", "Bổ sung điểm d1 vào sau điểm d khoản 3", "Bổ sung điểm d1 vào sau điểm d khoản 5", "Bổ sung điểm a1 vào sau điểm a khoản 4", "Bổ sung khoản 5a vào sau khoản 5". Thân VBHN ghi "d1) [8] Hợp đồng theo chi phí cộng phí ; d2) [9] …", "d1) [13]", "d1) [14]"; `vbhn02bxd.html` có "Bổ sung Điều 30a". Gold spike có 9 INSERTION, trong đó **7** trỏ tới đơn vị có hậu tố.
- Gap trong spec: canonical P1 §3 (`phase-1:40`) chỉ có `diem <chữ>`/`khoan <số>`. Nhãn segment `"a)"` (`phase-1:41`), `anchor_target` theo dõi `x)` (`phase-1:38`). Grammar P2 là `điểm <chữ>`, `khoản <số>(.<số>)?`, `Điều <số>(.<số>)?` (`phase-2:84`).
- Sai lệch tương quan: segment không nhận "d1)" là nhãn, nên marker `[8]` bị gán cho điểm d đứng trước, và gold ra `diem d khoan 2 dieu 3`. Regex địa chỉ đọc "điểm d1" thành "điểm d" (nếu không neo `\b`), và pred cũng ra `diem d khoan 2 dieu 3`. Hai bên sai giống nhau nên được chấm **đúng**. `target_accuracy` của INSERTION bị thổi phồng đúng ở loại cạnh khó nhất.
- Hệ quả runtime: "khoản 5a vào sau khoản 5" có địa chỉ mới bằng anchor (`khoan 5 dieu 18`), nên cạnh khẳng định khoản 5 là khoản được chèn. Trên hợp đồng gốc khoản 5 có thật, nên đây là sai lặng lẽ chứ không phải `NOT_FOUND`.
- Sửa: mở rộng 3 chỗ spec như cột "Cách sửa". Thêm test gold trên chính các dòng trên (`[8]`→`diem d1 khoan 2 dieu 3`, `[9]`→`diem d2 …`). Thêm bất biến INSERTION `canonical(new) != canonical(insert_after)` → `NOT_FOUND`.

**RT-05 — Cây đích của harness khác hình dạng cây runtime (Medium, proven).**
- `segment.py` sinh node "Điều 3"/"1."/"a)" (`phase-1:41`). Đếm `raw_label` trong `ai-service/fixtures` + `docs/contracts/examples`: 73 "Điều N", 14 "Điều N.N", 4 "(a)", **0** nhãn kiểu "N." hay "a)". Chính P2 cũng ghi rủi ro "Cây AI1 thật không tách khoản/điểm" ở mức Cao.
- Như vậy harness đo resolver chủ yếu qua đường `EXACT` trên cây lý tưởng. Đường `ANCESTOR` + kiểm nhãn trong text, vốn là đường runtime thật sẽ đi, gần như không được đo. Câu "cái đo = cái chạy" (`phase-3:71`) chỉ đúng về code, không đúng về phân phối đầu vào.
- Sửa: trong `resolver_eval`/`pipeline_predictor`, thêm chế độ `--tree-shape=article-only` (gộp text của khoản/điểm vào node Điều) và báo hai cột.

**RT-09 — Op accuracy là đo hai bên tự đồng ý về từ vựng; cổng P3 không chặn precision (Medium, proven).**
- Gold lấy op từ động từ trong chú thích qua bảng `OPS` (`vbhn_notes.py:12-13`). Predictor P3 map động từ "cùng quy ước … để so được với gold" (`phase-3:57`). Chú thích VBHN chép lại đúng động từ của văn bản sửa đổi, vì cùng cơ quan soạn và hợp nhất `[PRIOR]`. Vì vậy 26/26 chỉ đo việc **tìm ra câu thao tác**. Nó không đo việc **phân loại đúng nghĩa**: "Sửa đổi, bổ sung Điều 4" mà thực chất thêm khoản mới vẫn ra SUBSTITUTION ở cả hai phía.
- `test_p3_report_not_worse_than_baseline` (`phase-3:182`) chỉ so `op_correct` và `target_correct`, đều là đếm recall. Một parser sinh thêm cạnh rác (`unmatched_predictions`) vẫn qua cổng.
- Sửa: đổi nhãn chỉ số trong báo cáo/AI2-19 thành `op_lexical_agreement`. Thêm điều kiện precision vào test. Trong quy trình duyệt Q1, người duyệt gán op dựa trên `new_text`, không dựa trên động từ của chú thích.

**RT-10 — Mốc 16/26 không phải chỉ số "đúng" (Medium, proven).**
- Spike §Kết quả: 16/26 là "đủ cấp". §Giới hạn 1 nói độ đúng đích là `[ASSUMED]`. `phase-1:18` cũng thừa nhận điều này. Vậy mà `phase-2:140,169` dùng 16 làm mốc **đúng** tối thiểu. Kết hợp với RT-02: nếu sửa gold cho đúng (d1/d2), số đúng có thể tụt dưới 16, nên cook có động cơ giữ bug tương quan cho test xanh.
- Sửa: lấy mốc từ `p1-baseline.json` `target_correct` (OBSERVED ở P1 bước 8).

**RT-13 — Scorer chưa đặc tả cách ghép khi nhiều gold cùng src (Medium; gap proven, tác động `[ASSUMED]`).**
- `vbhn02bxd.html.gold.json` có 26 bản ghi nhưng chỉ 25 src khác nhau: `điểm e khoản 2 điều 1` sinh 2 gold (`[8]`, `[9]`, chính là ca d1/d2). Spike ghép pred theo dict khoá bằng src (`op_parser_eval.py:51-63`), nên chỉ giữ được 1 pred cho mỗi src. P1 §6 (`phase-1:43`) không nói cách ghép. Câu "Bãi bỏ khoản 3 và khoản 4 Điều 7" sinh 2 gold cùng src, đúng loại REPEAL đang thiếu dữ liệu.
- Sửa: ghép một-một theo `(src, target)`. Phần còn lại tính là unmatched hoặc miss. Thêm test.

**RT-14 — `operative_body` cắt ở "Điều 2." đầu tiên (Medium, suspected `[ASSUMED]`).**
- Spec `phase-1:33` và bản port `op_parser_eval.py:43` (`text.find("Điều 2.", …)`). Ngay trong Điều 1 của nd50 đã có “Điều 23.”, “Điều 36.”, “Điều 42.” nằm trong ngoặc kép (probe OBSERVED). Cặp nào sửa chính Điều 2 ("Sửa đổi Điều 2 như sau: “Điều 2. …") sẽ bị cắt mất phần sau mà không báo gì. Hậu quả là recall thấp, dễ bị đổ lỗi cho parser.
- Sửa: theo dõi độ sâu ngoặc kép khi tìm điểm cắt. Thêm fixture.

**RT-15 — Dữ liệu spike chỉ có ở worktree này; P1 BLOCKED giữ chân cả chuỗi (Low).**
- `git check-ignore` → `.git/info/exclude:12:/.harness/` nằm trong common dir `contract-intelligence-core/.git`. `raw/nd50.html` chỉ tồn tại ở `contract-intelligence-develop`. Nếu cook mở worktree mới cho `feature/ai2-contract-graph` thì P1 bước 6 không có dữ liệu.
- Nguồn tải ≥10 cặp là `[ASSUMED khả dụng]` (Q4). Phụ thuộc lại tuyến tính, nên P1 BLOCKED sẽ chặn luôn P2–P4.

### (B) Backward-compat / BE-contract / vận hành

**RT-03 — Rollback P4 không chạy được như viết, và hậu quả bị đánh giá sai (High, proven).**
- Tái lập 1 (CLI không chạy): `cd ai-service && .venv/Scripts/alembic.exe current` → `KeyError: 'connection'` tại `app/db/migrations/env.py:5`. Bước "chạy alembic downgrade về 0004" ở `plan.md:182` và `phase-4:184` không có lệnh nào chạy được.
- Tái lập 2 (revert code khi DB đã ở 0005): dựng env Alembic tạm (SQLite, revision `0004_ai2_job_indexes` → `0005_ai2_contract_edges`), `upgrade head`, xoá file 0005, gọi lại `upgrade head`, giống hệt `migrate.py:29`. Kết quả OBSERVED: `alembic.util.exc.CommandError: Can't locate revision identified by '0005_ai2_contract_edges'`. `ensure_database` (`engine.py:43`) gọi `migrate()` ở lần dùng DB đầu tiên, nên mọi đường Postgres hỏng. `plan.md:182` lại viết "bảng mồ côi (vô hại nhưng bẩn)".
- Sửa: thêm entrypoint downgrade có kiểm thử. Ghi rõ "rollback runtime = tắt flag; **không** revert code P4 trên DB đã migrate". Nếu bắt buộc phải revert code thì chạy downgrade trước bằng entrypoint đó.

**RT-04 — Lỗi ghi cạnh làm FAILED cả job, trái với D11 (High; đường code proven, trigger `[ASSUMED]`).**
- `phase-4:54` chọn rollback nguyên tử. Exception thoát khỏi `complete_with_snapshot` bị bắt ở `main.py:319`, và `main.py:328-336` gọi `set_wire(status="FAILED")` với `worker_token` vẫn còn hiệu lực (vì transaction đã rollback nên job còn RUNNING). Kết quả: job `FAILED`/`BLOCKED`, `AI2_WORKER_FAILED`, BE nhận một run thất bại dù phần trích xuất đã xong. D11 (`plan.md:66`) và R10 chỉ bọc builder.
- `test_edge_write_failure_rolls_back_job_completion` (`phase-4:126`) chỉ khẳng định "job vẫn RUNNING" ở tầng store, không thấy hệ quả ở tầng worker.
- Trigger khả dĩ `[ASSUMED]`: byte `\x00` trong `new_text`/`scope_text` (cột Postgres TEXT từ chối NUL, trong khi snapshot hiện tại đi qua `json.dumps` nên được escape), CHECK `op` lệch enum, hoặc bất kỳ bug nào trong `edge_row`.
- Sửa: dùng savepoint `begin_nested()`. Lỗi thì giữ cạnh cũ, ghi log/metric, và vẫn commit job + snapshot. Lọc NUL. Thêm test end-to-end qua `_execute_wire_job`.

**RT-07 — Flag bật thì BE nhận 2 hàng review cho cùng một thay đổi (Medium, proven).**
- D3 cố ý mở khoá cặp thân↔phụ lục, nên candidate mới đi vào `findings`. D5 phát thêm context finding `AMENDS` với `metadata={}` (`phase-4:39`). BE gộp cả hai vào `finding_items` (`persistence.py:1047-1050`). Cơ chế chống trùng duy nhất của BE là bỏ finding có `metadata.candidate_id` (`persistence.py:815`), mà `metadata={}` thì không bao giờ kích hoạt. Chính fixture của `test_flag_on_relation_pairs_unlock_cross_file_candidate` (`phase-3:164`) sinh ra đúng 2 hàng: context finding luôn `severity="high"` (`persistence.py:851`), candidate cũng `"high"` khi `NEEDS_REVIEW` (`persistence.py:1095`).
- R6 (`plan.md:195`) chỉ nói về `AMENDMENT_SIGNAL` cũ, mà loại này BE đã bỏ do chỉ có 1 tài liệu.
- Sửa: khi cạnh mở khoá được một candidate thì gắn `metadata.candidate_id`. Chuỗi này không chứa loại con nên không vi phạm K3. Nếu không làm thì ghi rõ trong R6/AI2-19.

**RT-11 — Test Postgres hiện có hardcode head revision (Medium, proven).**
- `tests/test_ai2_postgres_store.py:612`: `assert version == "0004_ai2_job_indexes"`. Có 0005 thì test này đỏ. `phase-4:136` đòi "toàn bộ xanh" nhưng không đưa file vào inventory. Máy cook không có Docker (R9), và CI ai-service là no-op (`.github/workflows/ai-service.yml:23-24` chỉ `echo`), nên lỗi chỉ lộ khi có người chạy với Postgres.

**RT-12 — D4 sai tiền đề, test review-id tự mâu thuẫn (Medium, proven).**
- `idp.py:292` không phải cuối danh sách issue: sau nó còn issue `table-context:*` (`idp.py:293-304`) và `context_issues` (`idp.py:307-318`). Chèn issue graph sau dòng 292 sẽ dịch chỉ số `review:{code}:{index}` (`idp.py:495-500`) của các issue phía sau.
- Mở khoá `relation_pairs` còn làm mất issue `BODY_ANNEX_RELATION` (`compare.py:196-221`, gọi ở `compare.py:64`) trong kết quả pairer (`idp.py:279`), vốn đứng ở đầu danh sách, nên dịch toàn bộ.
- Kết quả: `test_flag_on_keeps_existing_review_item_ids` (`phase-3:165`) sẽ đỏ nếu dùng chung fixture với test mở khoá, còn nếu fixture không có các issue đó thì xanh mà không chứng minh gì.

### (C) Domain / legal-text realist

**RT-06 — REJECTION/SCOPE_LIMIT đi vòng qua bộ lọc thao tác và không giới hạn nguồn (Medium, proven).**
- Probe `has_amend_marker`: "Bên A có quyền từ chối nghiệm thu theo khoản 2 Điều 7." → `False`; "Điều 5 không áp dụng đối với lô hàng 2." → `False`. Quy tắc loại trừ (`phase-3:58`) miễn lọc cho đúng hai mẫu này. `default_target_parts` cho phép nguồn ở thân (`phase-2:59`). Vì vậy các quyền và phạm vi thông thường trong thân hợp đồng đều thành cạnh, rồi thành `AMENDS`.
- Khi phụ lục là file riêng (vd phụ lục kỹ thuật ghi "có quyền từ chối … theo Điều 7"), BE map thành `candidate_amendment`, `severity="high"` (`persistence.py:834,851`). `phase-3:227` đánh tác động "Thấp", nhưng trên BE thì không thấp.
- Sửa (không đụng K3): chỉ sinh hai op này khi đơn vị nguồn thuộc `annex:*`, hoặc nằm dưới một đơn vị chứa thao tác.

**RT-08 — Thiếu các động từ thao tác phổ biến nhất của phụ lục hợp đồng (Medium, proven).**
- Probe: "Điều chỉnh khoản 2 Điều 5 như sau: …" cho marker `True`, nhưng không mẫu nào trong `phase-3:46-55` khớp ("Điều chỉnh" chỉ có ở mẫu `… thành …`), nên bị bỏ. "Thay đổi Điều 7 của Hợp đồng như sau:" và "Khoản 2 Điều 5 được thay bằng nội dung sau:" cho marker `False`, nên bị loại bởi `phase-3:58`.
- Mẫu phụ lục duy nhất đã thấy cũng dùng "Nội dung điều chỉnh: thay đổi …" (synthesis §5). Harness VBHN không đo được các động từ này vì từ vựng gold là VBQPPL.
- Sửa: thêm mẫu không std; thêm fixture `contract_graph_records.py` có ba câu trên.

## Đường không đảo ngược / mất dữ liệu

- **Không có đường mất dữ liệu không hồi phục.** `ai2.contract_edges` là bảng mới và tái sinh được từ snapshot + bật flag. Bảng hiện có không bị đụng, vì 0005 chỉ `create_table`/`drop_table` của chính nó.
- **Gần không đảo ngược nhất là RT-03**: một lần revert code P4 trên DB đã migrate làm hỏng `migrate()` cho mọi pod. Hồi phục cần deploy lại code có 0005 hoặc sửa tay `ai2.alembic_version`. Đây là sự cố vận hành, không mất dữ liệu.
- **RT-04** làm mất kết quả của một job: BE nhận FAILED cho một run đã trích xong. Hồi phục được bằng cách chạy lại với flag tắt.
- Test downgrade (`test_0005_downgrade_then_upgrade`) chạy trên DB trỏ bởi `AI2_TEST_DATABASE_URL`. Nếu ai đó trỏ URL này vào Postgres dev dùng chung, test sẽ drop `ai2.contract_edges` ở đó. Vô hại về dữ liệu nghiệp vụ, nhưng nên ghi trong P4 bước 1 rằng URL phải là DB dùng một lần.

## Rủi ro tồn dư chấp nhận được (kèm điều kiện)

| Rủi ro | Chấp nhận khi |
|---|---|
| Phủ định "Điều 8 … không bị sửa đổi" (marker `True`, probe OBSERVED) có thể khớp mẫu bị động `(được\|bị) sửa đổi` `[ASSUMED]` | Mọi cạnh vẫn `NEEDS_REVIEW` và cổng PASS đóng (D13). Nên thêm 1 case vào `test_exclusions_return_none` |
| Địa chỉ dạng khoảng ("từ khoản 2 đến khoản 5"), nhãn `PL1` (fixture có 3 nhãn "PLN"), `Mục N` → `NOT_FOUND` | Có issue `TARGET_NOT_FOUND` và được đếm riêng trong báo cáo P2 |
| Sau P4, `store.py` import `app.contracts.contract_graph` ngay cả khi flag tắt, nên câu "không import module mới" (`phase-3:87`) không còn đúng | Byte-identity vẫn giữ (golden), và test chỉ khẳng định builder không bị import |
| REJECTION/SCOPE_LIMIT không bao giờ có gold VBHN nên n=0 mãi | Cổng PASS đóng. Q1 phải chỉ rõ hai op này chỉ calibrate được bằng dữ liệu hợp đồng đã duyệt |
| Bảng giữ cạnh của job cũ khi job mới tắt flag hoặc builder lỗi | Chưa có consumer đọc bảng (Out of scope). Mỗi dòng có `job_id` + `source_snapshot_digest` |

## Đã kiểm và không thành finding

- D9 đúng: `0001_ai2_initial.py:14` `metadata.create_all(cx)`; dùng `MetaData` riêng thì tránh được `DuplicateTable`.
- `[ASSUMED]` ở P3 về `citation_for_node` là an toàn: hàm trả `citation.model_dump()` (`outline.py:179`), nên `Citation(**…)` dựng được.
- D8: `InMemorySnapshotStore.put` giữ tham chiếu (`store.py:75-76`), nên `record.contract_edges` tới được `complete_with_snapshot` qua `processing_store.get` (`main.py:300`). `complete_with_snapshot` chỉ có một call site (`main.py:302`).
- Wire: context finding chỉ mang `metadata` của finding gốc (`wire.py:313-324`). Với `metadata={}` thì không có chuỗi loại con nào trong `context_findings`. `contract_context.findings` lồng trong `index_contribution` cũng chỉ là dump của chính các finding đó.
- Wilson: `wilson(26,26)` có cận dưới ≈0,8713; (54, 60) ≈0,7985; (60, 60) ≈0,9398. Khớp kỳ vọng trong test P1/P3.
