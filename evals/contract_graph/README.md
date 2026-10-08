# Contract graph eval (VBHN)

Bộ đo cho luồng 1 (operation-first): mỗi **cặp** là (văn bản sửa đổi, VBHN hợp nhất nó). Gold tự trích
từ chú thích của VBHN; predictor đọc văn bản sửa đổi và trả cạnh sửa đổi; scorer chấm theo loại cạnh,
kèm Wilson 95%. Chỉ dùng stdlib.

## Chạy

Từ repo root (python của venv ai-service; fallback `ai-service/.venv/Scripts/python.exe -m ...`):

```powershell
# test (offline, chặn mạng)
uv run --project ai-service --frozen --extra web --extra dev --extra kafka --extra openai python -m pytest -q -p no:cacheprovider evals/contract_graph/tests

# lấy trang (cache ở data/contract_graph_cache/, khoá sha256(url), bị .gitignore) + chuẩn hoá + đông cứng
python -m evals.contract_graph.run_eval fetch --sources evals/contract_graph/sources.json
python -m evals.contract_graph.run_eval fetch --sources evals/contract_graph/sources.json --offline  # chỉ dùng cache

# chấm (kiểm manifest trước; lệch thì exit 2, không ghi báo cáo)
python -m evals.contract_graph.run_eval score --data evals/contract_graph/data --predictor baseline --out evals/contract_graph/reports/p1-baseline
python -m evals.contract_graph.run_eval score --data evals/contract_graph/data --predictor evals.contract_graph.pipeline_predictor:predict --out ...
```

`--predictor` nhận `baseline` hoặc `module:function` với `predict(pair_dir: Path) -> list[dict]`; mỗi dict cần
`src_address`, `op`, `target_address` (dạng chuẩn hoá bên dưới), key khác được giữ nhưng không chấm. Mục liệt kê
nhiều đích ("Bổ sung điểm d1, d2 …") có thể trả thêm `target_addresses: [...]`: scorer coi mỗi đích là một slot —
ghép tối đa một gold mỗi đích, precision đếm mỗi đích một lần.

## Dữ liệu (`data/`)

- `data/<pair_id>/{amending.txt, vbhn.txt, gold.jsonl}` + `data/manifest.json` (URL, `fetched_at`, sha256 trang gốc,
  sha256 từng file, đếm gold theo op, `total_bytes`). Chỉ commit text đã chuẩn hoá, không commit HTML/DOCX.
- sha256 tính trên bytes UTF-8 **đã đổi CRLF→LF**: checkout có `core.autocrlf` không bị coi là sửa dữ liệu.
- Chuẩn hoá: HTML và DOCX ra cùng dạng — mỗi đoạn một dòng, marker chú thích `[n]` ở đúng chỗ, khối chú thích
  `[n] …` ở cuối. Trang Next.js (vcci) chở lại văn bản dạng `<p>…` trong script: một khối payload chỉ được
  gộp khi nó chứa ≥ một nửa số dòng dài của phần hiển thị (cùng văn bản); khối của văn bản khác bị bỏ.
- Thân thao tác: `operative_body` lấy lần xuất hiện `Điều N.` có thân dài nhất (bỏ mục lục), cắt ở `Điều N+1.`
  nằm **ngoài** ngoặc kép (Điều sửa đổi trích nguyên văn “Điều 2. …”). `operative_article` của cặp nằm trong manifest.

## Gold (`gold.jsonl`)

Một bản ghi = một chú thích `[n] … theo quy định tại <địa chỉ nguồn> <số hiệu văn bản sửa đổi>` của đúng văn bản
sửa đổi của cặp:

- `op` lấy **chỉ từ phần trước** "theo quy định tại" (tên văn bản phía sau lặp "sửa đổi, bổ sung"): bảng OPS
  `sửa đổi, bổ sung`/`sửa đổi`/`thay thế`/`thay cụm từ` → `SUBSTITUTION`, `bổ sung` → `INSERTION`,
  `bãi bỏ`/`bỏ cụm từ` → `REPEAL`; không khớp → `OTHER` (đếm, không chấm). Chú thích trích nhiều văn bản
  ("lần thứ 01 theo … ; được … lần thứ 02 theo …") lấy đúng mệnh đề của văn bản của cặp.
- `target_address` = vị trí marker `[n]` đầu tiên trong thân VBHN, ở cấp chú thích nêu ("Điểm/Khoản/Điều/Phụ lục
  này"); "Cụm từ"/không nêu cấp → đơn vị nhỏ nhất chứa marker. Không có địa chỉ chuẩn (“Tên chương này”, “Mẫu này”,
  marker trong “PHỤ LỤC” không số) → `null`, không đoán.
- `approved: false`, `extractor_version`. Đây là **auto-gold chưa duyệt**: không phải độ chính xác nghiệp vụ.

### Duyệt gold

Người duyệt mở `vbhn.txt` + `amending.txt`, đọc nội dung mới thật (đoạn sau "như sau:") và gán op theo **thay đổi
thật** của văn bản (thêm đơn vị mới = INSERTION, thay nội dung = SUBSTITUTION, bỏ = REPEAL), **không chép động
từ của chú thích** (RT-09: chép động từ thì gold và predictor cùng một quy ước, số đo thành đồng thuận từ vựng).
Sửa `target_address` nếu marker đặt sai chỗ; chỉ khi đó mới đặt `approved: true`, rồi `fetch --offline` lại
**không** được ghi đè bản đã duyệt (đông cứng lại bằng tay hoặc tách file duyệt).

## Địa chỉ chuẩn hoá (chung với P2)

Chữ thường NFC; từ cấp gấp ASCII `diem`, `khoan`, `dieu`, `phu luc`; **chữ điểm giữ `đ`**; bỏ số 0 đầu của phần số;
nhỏ → lớn, cách một dấu cách: `diem đ khoan 2 dieu 1`, `khoan 5 dieu 4`, `phu luc 1`.
Hậu tố là **đơn vị riêng**: điểm `[a-zđ]\d*` (`d1`, `i1`, `a1`), khoản `\d+[a-zđ]?` (`5a`), Điều `\d+[a-zđ]?` (`30a`):
`diem d1 khoan 2 dieu 3` ≠ `diem d khoan 2 dieu 3`, `khoan 05a dieu 18` → `khoan 5a dieu 18`.

## Chỉ số (`score.py`)

Ghép gold↔pred **một-một trong từng cặp**: bước 1 theo `(src_address, target_address)`, bước 2 theo `src_address`
theo thứ tự (gold theo `note_no`, pred theo thứ tự predictor). Gold thừa = miss; pred thừa = `unmatched_predictions`.

| chỉ số | k / mẫu số |
|---|---|
| `src_found` | gold ghép được pred / `n_gold` |
| `op_lexical_agreement` | gold ghép được pred cùng op / `n_gold` |
| `op_precision` | pred ghép được gold cùng op / `n_pred` |
| `target_accuracy` | gold ghép có `target_address` pred == gold / gold đã ghép |

`op_lexical_agreement` là **đồng thuận từ vựng**, không phải độ đúng phân loại: gold lấy op từ động từ chú thích,
predictor map động từ câu thao tác theo cùng quy ước. Mỗi tỷ lệ có `passed`, `denominator`, `rate`, `wilson95`;
báo cáo có `by_pair` để phase sau lấy mốc riêng từng cặp. Output deterministic (không lặp `set`), có test so bytes
giữa hai `PYTHONHASHSEED`.
