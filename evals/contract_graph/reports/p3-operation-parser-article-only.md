# Contract graph eval — evals.contract_graph.pipeline_predictor:predict_article_only

- Ground truth: `vbhn-note auto-gold (approved=false)` (chưa duyệt; không phải độ chính xác nghiệp vụ)
- Dataset: 11 cặp, manifest sha256 `f74399ae07193ba8975e2cb58e8d83af8abaaa112c00a3b9c31c24b615b05220`

## Tổng

| op | n_gold | n_pred | src_found | op_lexical_agreement | op_precision | target_accuracy |
| --- | --- | --- | --- | --- | --- | --- |
| SUBSTITUTION | 83 | 72 | 60/83 (0.723; CI95 0.618–0.808) | 60/83 (0.723; CI95 0.618–0.808) | 60/72 (0.833; CI95 0.731–0.902) | 59/60 (0.983; CI95 0.911–0.997) |
| INSERTION | 18 | 16 | 16/18 (0.889; CI95 0.672–0.969) | 16/18 (0.889; CI95 0.672–0.969) | 16/16 (1.000; CI95 0.806–1.000) | 15/16 (0.938; CI95 0.717–0.989) |
| REPEAL | 12 | 8 | 6/12 (0.500; CI95 0.254–0.746) | 6/12 (0.500; CI95 0.254–0.746) | 6/8 (0.750; CI95 0.409–0.928) | 6/6 (1.000; CI95 0.610–1.000) |
| ALL | 113 | 96 | 82/113 (0.726; CI95 0.637–0.799) | 82/113 (0.726; CI95 0.637–0.799) | 82/96 (0.854; CI95 0.770–0.911) | 80/82 (0.976; CI95 0.915–0.993) |

> `op_lexical_agreement` = đồng thuận từ vựng: gold lấy op từ động từ của chú thích VBHN và predictor map động từ của câu thao tác theo cùng quy ước, nên chỉ số này đo việc tìm đúng câu thao tác + động từ khớp, không đo phân loại đúng nghĩa (RT-09).

- gold OTHER (đếm, không chấm): 0; pred ghép vào OTHER: 0
- marker_hit: 0/0 (n/a)

## Theo cặp

| pair | n_gold | src_found | op_lexical_agreement | op_precision | target_accuracy |
| --- | --- | --- | --- | --- | --- |
| nd50-2021 | 26 | 26/26 (1.000; CI95 0.871–1.000) | 26/26 (1.000; CI95 0.871–1.000) | 26/26 (1.000; CI95 0.871–1.000) | 26/26 (1.000; CI95 0.871–1.000) |
| tt01-2022-bct | 12 | 5/12 (0.417; CI95 0.193–0.680) | 5/12 (0.417; CI95 0.193–0.680) | 5/5 (1.000; CI95 0.566–1.000) | 5/5 (1.000; CI95 0.566–1.000) |
| tt119-2014-btc | 11 | 8/11 (0.727; CI95 0.434–0.902) | 8/11 (0.727; CI95 0.434–0.902) | 8/10 (0.800; CI95 0.490–0.943) | 7/8 (0.875; CI95 0.529–0.978) |
| tt13-2023-btc | 4 | 4/4 (1.000; CI95 0.510–1.000) | 4/4 (1.000; CI95 0.510–1.000) | 4/5 (0.800; CI95 0.376–0.964) | 4/4 (1.000; CI95 0.510–1.000) |
| tt130-2016-btc | 6 | 5/6 (0.833; CI95 0.436–0.970) | 5/6 (0.833; CI95 0.436–0.970) | 5/5 (1.000; CI95 0.566–1.000) | 5/5 (1.000; CI95 0.566–1.000) |
| tt14-2019-nhnn | 3 | 0/3 (0.000; CI95 0.000–0.561) | 0/3 (0.000; CI95 0.000–0.561) | 0/0 (n/a) | 0/0 (n/a) |
| tt21-2018-bct | 14 | 12/14 (0.857; CI95 0.601–0.960) | 12/14 (0.857; CI95 0.601–0.960) | 12/13 (0.923; CI95 0.667–0.986) | 12/12 (1.000; CI95 0.757–1.000) |
| tt23-2016-nhnn | 6 | 5/6 (0.833; CI95 0.436–0.970) | 5/6 (0.833; CI95 0.436–0.970) | 5/7 (0.714; CI95 0.359–0.918) | 5/5 (1.000; CI95 0.566–1.000) |
| tt26-2015-btc | 17 | 10/17 (0.588; CI95 0.360–0.784) | 10/17 (0.588; CI95 0.360–0.784) | 10/12 (0.833; CI95 0.552–0.953) | 10/10 (1.000; CI95 0.723–1.000) |
| tt27-2014-nhnn | 6 | 6/6 (1.000; CI95 0.610–1.000) | 6/6 (1.000; CI95 0.610–1.000) | 6/10 (0.600; CI95 0.313–0.832) | 6/6 (1.000; CI95 0.610–1.000) |
| tt43-2018-nhnn | 8 | 1/8 (0.125; CI95 0.022–0.471) | 1/8 (0.125; CI95 0.022–0.471) | 1/3 (0.333; CI95 0.061–0.792) | 0/1 (0.000; CI95 0.000–0.793) |

## Sai đích (2)

- tt119-2014-btc [27] INSERTION khoan 5 dieu 3: gold `diem a khoan 4 dieu 14` ≠ pred `khoan 4 dieu 14`
- tt43-2018-nhnn [10] SUBSTITUTION khoan 1 dieu 1: gold `diem v khoan 1 dieu 5` ≠ pred `diem c khoan 1 dieu 5`

## Pred không ghép được gold (14)

- tt119-2014-btc SUBSTITUTION diem a khoan 6 dieu 3 → `diem c khoan 3 dieu 15`
- tt119-2014-btc SUBSTITUTION diem c khoan 6 dieu 3 → `diem c khoan 4 dieu 15`
- tt13-2023-btc SUBSTITUTION khoan 3 dieu 1 → `None`
- tt21-2018-bct SUBSTITUTION khoan 2 dieu 1 → `dieu 13`
- tt23-2016-nhnn REPEAL dieu 2 → `dieu 4`
- tt23-2016-nhnn REPEAL dieu 2 → `dieu 11`
- tt26-2015-btc SUBSTITUTION diem a khoan 12 dieu 1 → `khoan 3 dieu 18`
- tt26-2015-btc SUBSTITUTION diem c khoan 12 dieu 1 → `khoan 5 dieu 18`
- tt27-2014-nhnn SUBSTITUTION khoan 1 dieu 1 → `None`
- tt27-2014-nhnn SUBSTITUTION khoan 2 dieu 1 → `khoan 2 dieu 5`
- tt27-2014-nhnn SUBSTITUTION khoan 6 dieu 1 → `dieu 17`
- tt27-2014-nhnn SUBSTITUTION dieu 2 → `None`
- tt43-2018-nhnn SUBSTITUTION khoan 1 dieu 1 → `khoan 1 dieu 5`
- tt43-2018-nhnn SUBSTITUTION khoan 1 dieu 1 → `None`

## Gold bị bỏ sót (31)

- tt01-2022-bct [2] REPEAL diem a khoan 1 dieu 3 → `khoan 2 dieu 1`
- tt01-2022-bct [3] REPEAL diem a khoan 1 dieu 3 → `dieu 3`
- tt01-2022-bct [4] REPEAL diem a khoan 1 dieu 3 → `dieu 4`
- tt01-2022-bct [6] REPEAL diem a khoan 1 dieu 3 → `dieu 6`
- tt01-2022-bct [7] SUBSTITUTION khoan 2 dieu 1 → `None`
- tt01-2022-bct [9] REPEAL diem a khoan 1 dieu 3 → `dieu 13`
- tt01-2022-bct [29] SUBSTITUTION diem a khoan 1 dieu 3 → `None`
- tt119-2014-btc [21] SUBSTITUTION khoan 3 dieu 3 → `diem đ khoan 3 dieu 12`
- tt119-2014-btc [23] SUBSTITUTION khoan 3 dieu 3 → `diem d khoan 4 dieu 12`
- tt119-2014-btc [29] SUBSTITUTION khoan 6 dieu 3 → `dieu 15`
- tt130-2016-btc [36] SUBSTITUTION khoan 3 dieu 1 → `khoan 4 dieu 18`
- tt14-2019-nhnn [17] SUBSTITUTION khoan 1 dieu 1 → `dieu 17`
- tt14-2019-nhnn [30] INSERTION khoan 1 dieu 2 → `None`
- tt14-2019-nhnn [31] INSERTION khoan 1 dieu 2 → `None`
- tt21-2018-bct [32] SUBSTITUTION khoan 4 dieu 1 → `None`
- tt21-2018-bct [34] SUBSTITUTION khoan 4 dieu 1 → `None`
- tt23-2016-nhnn [7] SUBSTITUTION khoan 3 dieu 1 → `None`
- tt26-2015-btc [5] SUBSTITUTION khoan 3 dieu 1 → `diem a khoan 8 dieu 4`
- tt26-2015-btc [12] SUBSTITUTION khoan 4 dieu 1 → `khoan 10 dieu 7`
- tt26-2015-btc [14] REPEAL khoan 4 dieu 4 → `khoan 22 dieu 7`
- tt26-2015-btc [29] SUBSTITUTION khoan 10 dieu 1 → `dieu 15`
- tt26-2015-btc [30] SUBSTITUTION khoan 10 dieu 1 → `khoan 3 dieu 15`
- tt26-2015-btc [31] SUBSTITUTION khoan 11 dieu 1 → `diem b khoan 3 dieu 16`
- tt26-2015-btc [33] SUBSTITUTION khoan 12 dieu 1 → `dieu 18`
- tt43-2018-nhnn [23] SUBSTITUTION khoan 2 dieu 1 → `khoan 8 dieu 19`
- tt43-2018-nhnn [24] SUBSTITUTION khoan 2 dieu 1 → `khoan 8 dieu 19`
- tt43-2018-nhnn [25] SUBSTITUTION khoan 2 dieu 1 → `khoan 1 dieu 19`
- tt43-2018-nhnn [26] SUBSTITUTION khoan 2 dieu 1 → `khoan 2 dieu 19`
- tt43-2018-nhnn [27] SUBSTITUTION khoan 2 dieu 1 → `khoan 3 dieu 19`
- tt43-2018-nhnn [28] SUBSTITUTION khoan 2 dieu 1 → `khoan 3 dieu 19`
- tt43-2018-nhnn [29] SUBSTITUTION khoan 2 dieu 1 → `khoan 3 dieu 19`

## So với P1 baseline

noise = n_pred − pred khớp op với gold (RT-09: không được tăng so với P1).

| op | n_gold | op_lexical_agreement P1 → P3 | target_correct P1 → P3 | n_pred P1 → P3 | noise P1 → P3 |
| --- | --- | --- | --- | --- | --- |
| INSERTION | 18 | 16 → 16 | 1 → 15 | 20 → 16 | 4 → 0 |
| REPEAL | 12 | 3 → 6 | 3 → 6 | 6 → 8 | 3 → 2 |
| SUBSTITUTION | 83 | 48 → 60 | 40 → 59 | 72 → 72 | 24 → 12 |
| ALL | 113 | 67 → 82 | 44 → 80 | 98 → 96 | 31 → 14 |

- unmatched_predictions: P1 30 → P3 14
- đích UNIQUE sai: toàn bộ 2; nd50-2021: 0
