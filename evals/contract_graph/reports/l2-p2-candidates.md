# Contract graph luồng 2 — P2 ứng viên cặp cấu trúc

- Ground truth: `gpt-labels (approved=false), dev` — nhãn GPT chưa duyệt; recall là độ phủ nhãn GPT-positive của dev, không phải độ chính xác nghiệp vụ.
- `CANDIDATES_VERSION` `pairs-cand-v1`, `PAIRS_TOP_K` 40 (chọn 40: quy tắc cho K=10 (K nhỏ nhất có recall@K ≥ 0.95 × recall không cắt); người dùng giữ 40: dev degenerate: max 20 candidates/doc so recall@K is flat for every K in the grid; held-out docs reach 42 nodes (user decision 2026-10-09)); vòng chỉnh lexicon/cụm trên dev: 0.
- Văn bản dev: 7; ứng viên/hồ sơ (không cắt) {'min': 1, 'median': 3, 'max': 20, 'total': 38}.
- Recall không cắt: 15/24 (0.625; Wilson95 0.427–0.788)
- Loại trừ: {'candidates_capped': 0, 'candidates_kept': 38, 'candidates_total': 38, 'excluded_ancestor': 14, 'excluded_external_ref': 0, 'excluded_luong1': 0, 'excluded_short': 1}

## Theo nguồn (riêng / chỉ nguồn đó tìm được)

| nguồn | recall | biên |
| --- | --- | --- |
| SAME_ARTICLE | 6/24 (0.250; Wilson95 0.120–0.449) | 6/24 (0.250; Wilson95 0.120–0.449) |
| EXPLICIT_REF | 7/24 (0.292; Wilson95 0.149–0.492) | 7/24 (0.292; Wilson95 0.149–0.492) |
| SAME_KEY | 2/24 (0.083; Wilson95 0.023–0.259) | 2/24 (0.083; Wilson95 0.023–0.259) |
| REFERENCE_CUE | 0/24 (0.000; Wilson95 0.000–0.138) | 0/24 (0.000; Wilson95 0.000–0.138) |

## Recall@K

| K | recall |
| --- | --- |
| 10 | 15/24 (0.625; Wilson95 0.427–0.788) |
| 20 | 15/24 (0.625; Wilson95 0.427–0.788) |
| 30 | 15/24 (0.625; Wilson95 0.427–0.788) |
| 40 | 15/24 (0.625; Wilson95 0.427–0.788) |
| 60 | 15/24 (0.625; Wilson95 0.427–0.788) |
| 80 | 15/24 (0.625; Wilson95 0.427–0.788) |

## Theo tầng P1

| tầng | recall |
| --- | --- |
| S1 | 6/6 (1.000; Wilson95 0.610–1.000) |
| S3 | 9/18 (0.500; Wilson95 0.290–0.710) |

## Theo nhãn GPT

| nhãn | recall |
| --- | --- |
| CONFLICT | 3/5 (0.600; Wilson95 0.231–0.882) |
| DUPLICATE | 2/2 (1.000; Wilson95 0.342–1.000) |
| GENERAL_SPECIFIC | 8/13 (0.615; Wilson95 0.355–0.823) |
| REFERENCE | 2/4 (0.500; Wilson95 0.150–0.850) |

## Held-out S4 và phiếu HG-1

- S4: chưa sinh.
- Phiếu HG-1: chưa chọn mẫu.

## Theo văn bản

| doc_id | gold | phủ | ứng viên |
| --- | --- | --- | --- |
| pd-ae9bb69ee7 | 6 | 6 | 8 |
| pd-b300e5ad70 | 2 | 2 | 2 |
| pd-b6d8628d32 | 2 | 1 | 3 |
| pd-bf1d9346b4 | 9 | 3 | 20 |
| pd-e0d65645f2 | 0 | 0 | 1 |
| pd-eec95ad3b2 | 3 | 3 | 3 |
| pd-fa299625d8 | 2 | 0 | 1 |
