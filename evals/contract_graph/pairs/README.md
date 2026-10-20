# Bộ nhãn cặp khoản — contract graph luồng 2 (P1)

Bộ nhãn cho **phân loại cặp** (`GENERAL_SPECIFIC`, `CONFLICT`, `DUPLICATE`, `REFERENCE`,
`UNRELATED`) dựng từ mẫu hợp đồng SALES / SUPPLY_SERVICE công khai (`sources.json`). Plan:
`plans/261008-1500-ai2-contract-graph-implicit/` (phase 1). Định nghĩa nhãn và cách duyệt:
`LABELING.vi.md`.

## Dữ liệu nằm ngoài repo

Văn bản hợp đồng, pool, nhãn GPT, cache và phiếu duyệt nằm ở `AI2_CG_PAIRS_DATA_DIR` (mặc định
`.harness/state/contract-graph-pairs/`). Mọi lệnh ghi đều chạy `manifest.ensure_outside_repo`
trước: thư mục phải bị git bỏ qua (`git check-ignore`) và không nằm dưới `evals/`, `ai-service/`,
`docs/` — sai thì thoát mã 2. `.harness/` chỉ bị bỏ qua qua `.git/info/exclude` cục bộ, nên kiểm
chứ không giả định.

Repo chỉ chứa code, `sources.json`, `manifest.json` (URL, sha256, số đếm, model, split, seed — không
văn bản) và báo cáo tổng hợp `../reports/l2-p1-dataset.{json,md}`.

```
<data-dir>/
  cache/raw/<sha256(url)>          trang/docx gốc
  cache/labeler/<request sha>.json  phản hồi GPT (chạy lại không gọi mạng)
  work/{docs,pools,labels}/…        đầu ra từng bước CLI
  dev|heldout/<doc_id>/{doc.json,pool.jsonl,labels.gpt.jsonl}   sau freeze
```

## Người gán nhãn (GPT)

Endpoint OpenAI-compatible lấy từ `AI2_CG_LABELER_BASE_URL`, `AI2_CG_LABELER_API_KEY`,
`AI2_CG_LABELER_MODEL` (hoặc cùng tên trong `--env-file`). Thiếu biến nào ⇒ thoát mã 2, không
dùng client khác thay thế. Model **thực phục vụ** (`resp.model`) được ghi vào từng nhãn; họ của nó
phải là `openai` (`models.family`), khác ⇒ thoát mã 2 (K-a: người gán nhãn khác họ với bộ phân loại
Claude). Không log văn bản khoản hay phản hồi.

## Lệnh (từ repo root)

```
uv run --project ai-service --frozen --extra web --extra dev python -m evals.contract_graph.pairs.run <lệnh>
```

| Lệnh | Việc |
|---|---|
| `fetch` | tải nguồn vào `cache/raw` (lỗi mạng: giữ phần đã tải, mã 1) |
| `build` | offline: chuẩn hoá tiêu đề, tách Điều/khoản/điểm, loại văn bản < 5 Điều, đánh dấu nhiễm bẩn spike |
| `cluster` | gom cụm gần trùng (shingle 5-từ Jaccard ≥ 0,8 hoặc cùng chuỗi tiêu đề Điều) |
| `pool` | pool S1/S2/S3, in `pool_sha256` (chạy hai `PYTHONHASHSEED` phải ra cùng sha) |
| `label [--env-file F] [--workers N]` | GPT gán nhãn mỗi cặp một lời gọi, có cache |
| `summary` | ghi `reports/l2-p1-dataset.{json,md}`, in ước số dòng HG-1 (dừng nếu > 380) |
| `freeze` | chia split theo cụm, ghi `<split>/<doc_id>/`, ghi `pairs/manifest.json` |
| `verify` | so sha256 dữ liệu với manifest: 0 khớp, 2 lệch/thiếu/thừa |

Mọi đọc held-out ở phase sau đi qua `manifest.read_split`, gọi `verify` trước (lỗi ⇒ mã 2).

## Chia split

Cụm có văn bản nhiễm bẩn (URL spike `clause_key`, `repo:`, hoặc chứa ≥ 50% shingle của một khoản
spike) ⇒ `dev`. Các cụm còn lại sắp theo `min sha256(url)`, `ceil(2/3·n)` cụm đầu ⇒ `heldout`.
`split` không bao giờ ghi tay.

## HG-1 (duyệt của người)

Phiếu duyệt **không** xuất ở P1. P2 thêm tầng S4 (ứng viên cấu trúc trên held-out), gán nhãn GPT
cho S4, chọn mẫu có trọng số (`review.select_for_review`, trần 75/nhãn positive, 80 UNRELATED,
tổng ≤ 380) rồi xuất phiếu (`review.export_sheet`). P5 nhập phiếu (`review.import_sheet`) và chấm
bằng `score.score_relations` (precision bảo thủ quyết định cổng; Horvitz–Thompson 1/π chỉ báo).

## Giới hạn đã biết

- Trang web: `corpus.trim_tail` cắt phần trang sau hợp đồng (bình luận, FAQ, chân trang) tại
  ranh giới tin cậy đầu tiên sau Điều cuối: hết khối chữ ký (giữ Phụ lục nếu bắt đầu trong
  `ANNEX_AFTER_SIGNATURE_LINES` dòng sau đó), nếu không có thì dòng khung trang đầu tiên
  (`_SITE_MARKER`). Không thấy ranh giới ⇒ giữ nguyên, đếm `tail_untrimmed` trong báo cáo; cặp còn
  bẩn thì người duyệt chọn `reject`. Nguồn docx (Google Docs) không qua bước này; đánh số tự động
  của Word không vào văn bản nên chỉ tách tới Điều.
- Nhãn GPT chưa duyệt không phải độ chính xác nghiệp vụ (`ground_truth` trong manifest/báo cáo).
- `predict --split dev` scores the primary metric only on `approved=true`; remaining GPT labels produce `BLOCKED_UNREVIEWED_DEV_GOLD` and stay diagnostic-only.
- To close the dev gate, pass an external JSONL review file with `--dev-review`. Each row must contain `pair_id`, `gold_label` (or `null` for a reject), `gold_direction`, a JSON boolean `approved`, and `source: "user-review"`; the report records its SHA-256. Without this file, dev remains blocked.
- After the human review is complete, first lock the review digest with `python -m evals.contract_graph.pairs.run review-dev-lock --data-dir ... --dev-review ...`. Then rerun the dev prediction with `--dev-review`, and invoke `review-dev-lock` a second time to lock the canonical report path and SHA. The report lock requires `OBSERVED`, `evaluation_gate=PASS`, at least one approved `CONFLICT` and one approved `DUPLICATE`, `manifest_locked=true`, and a self-consistent report digest.
- HG-2 uses a separate sheet and lock so the HG-1 rows never change. Validate a completed sheet with `python -m evals.contract_graph.pairs.run review-hg2-import --data-dir ... --csv .harness/state/contract-graph-pairs/review/hg2_review.csv`; this writes only the ignored `review/hg2_review.decisions.jsonl`. Promote it only after the reviewer explicitly confirms the recall floor and data scope: `review-hg2-lock --human-approved --scope-consent --recall-floor 0.85`. The lock records selection/decision digests, merges HG-2 into held-out scoring, and still requires a committed manifest before P5.
- P5 additionally requires HG-2/P4 manifest fields with paths and SHA-256 digests for `hg2-review.md` and `hg2-sizing.json`; missing or modified receipts block preflight.
