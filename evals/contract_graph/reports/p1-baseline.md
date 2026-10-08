# Contract graph eval — baseline

- Ground truth: `vbhn-note auto-gold (approved=false)` (chưa duyệt; không phải độ chính xác nghiệp vụ)
- Dataset: 11 cặp, manifest sha256 `f74399ae07193ba8975e2cb58e8d83af8abaaa112c00a3b9c31c24b615b05220`

## Tổng

| op | n_gold | n_pred | src_found | op_lexical_agreement | op_precision | target_accuracy |
| --- | --- | --- | --- | --- | --- | --- |
| SUBSTITUTION | 83 | 72 | 49/83 (0.590; CI95 0.483–0.690) | 48/83 (0.578; CI95 0.471–0.679) | 48/72 (0.667; CI95 0.552–0.765) | 40/49 (0.816; CI95 0.686–0.900) |
| INSERTION | 18 | 20 | 16/18 (0.889; CI95 0.672–0.969) | 16/18 (0.889; CI95 0.672–0.969) | 16/20 (0.800; CI95 0.584–0.919) | 1/16 (0.062; CI95 0.011–0.283) |
| REPEAL | 12 | 6 | 3/12 (0.250; CI95 0.089–0.532) | 3/12 (0.250; CI95 0.089–0.532) | 3/6 (0.500; CI95 0.188–0.812) | 3/3 (1.000; CI95 0.439–1.000) |
| ALL | 113 | 98 | 68/113 (0.602; CI95 0.510–0.687) | 67/113 (0.593; CI95 0.501–0.679) | 67/98 (0.684; CI95 0.586–0.767) | 44/68 (0.647; CI95 0.528–0.750) |

> `op_lexical_agreement` = đồng thuận từ vựng: gold lấy op từ động từ của chú thích VBHN và predictor map động từ của câu thao tác theo cùng quy ước, nên chỉ số này đo việc tìm đúng câu thao tác + động từ khớp, không đo phân loại đúng nghĩa (RT-09).

- gold OTHER (đếm, không chấm): 0; pred ghép vào OTHER: 0
- marker_hit: 84/97 (0.866; CI95 0.784–0.920)

## Theo cặp

| pair | n_gold | src_found | op_lexical_agreement | op_precision | target_accuracy |
| --- | --- | --- | --- | --- | --- |
| nd50-2021 | 26 | 26/26 (1.000; CI95 0.871–1.000) | 26/26 (1.000; CI95 0.871–1.000) | 26/30 (0.867; CI95 0.703–0.947) | 13/26 (0.500; CI95 0.321–0.679) |
| tt01-2022-bct | 12 | 6/12 (0.500; CI95 0.254–0.746) | 6/12 (0.500; CI95 0.254–0.746) | 6/11 (0.545; CI95 0.280–0.787) | 2/6 (0.333; CI95 0.097–0.700) |
| tt119-2014-btc | 11 | 8/11 (0.727; CI95 0.434–0.902) | 8/11 (0.727; CI95 0.434–0.902) | 8/10 (0.800; CI95 0.490–0.943) | 6/8 (0.750; CI95 0.409–0.928) |
| tt13-2023-btc | 4 | 3/4 (0.750; CI95 0.301–0.954) | 3/4 (0.750; CI95 0.301–0.954) | 3/3 (1.000; CI95 0.439–1.000) | 3/3 (1.000; CI95 0.439–1.000) |
| tt130-2016-btc | 6 | 5/6 (0.833; CI95 0.436–0.970) | 5/6 (0.833; CI95 0.436–0.970) | 5/6 (0.833; CI95 0.436–0.970) | 5/5 (1.000; CI95 0.566–1.000) |
| tt14-2019-nhnn | 3 | 1/3 (0.333; CI95 0.061–0.792) | 1/3 (0.333; CI95 0.061–0.792) | 1/13 (0.077; CI95 0.014–0.333) | 0/1 (0.000; CI95 0.000–0.793) |
| tt21-2018-bct | 14 | 2/14 (0.143; CI95 0.040–0.399) | 2/14 (0.143; CI95 0.040–0.399) | 2/2 (1.000; CI95 0.342–1.000) | 2/2 (1.000; CI95 0.342–1.000) |
| tt23-2016-nhnn | 6 | 1/6 (0.167; CI95 0.030–0.564) | 1/6 (0.167; CI95 0.030–0.564) | 1/1 (1.000; CI95 0.206–1.000) | 0/1 (0.000; CI95 0.000–0.793) |
| tt26-2015-btc | 17 | 13/17 (0.765; CI95 0.527–0.904) | 12/17 (0.706; CI95 0.469–0.867) | 12/16 (0.750; CI95 0.505–0.898) | 10/13 (0.769; CI95 0.497–0.918) |
| tt27-2014-nhnn | 6 | 3/6 (0.500; CI95 0.188–0.812) | 3/6 (0.500; CI95 0.188–0.812) | 3/6 (0.500; CI95 0.188–0.812) | 3/3 (1.000; CI95 0.439–1.000) |
| tt43-2018-nhnn | 8 | 0/8 (0.000; CI95 0.000–0.324) | 0/8 (0.000; CI95 0.000–0.324) | 0/0 (n/a) | 0/0 (n/a) |

## Sai đích (24)

- nd50-2021 [3] SUBSTITUTION diem a khoan 2 dieu 1: gold `diem c khoan 1 dieu 3` ≠ pred `diem c dieu 3`
- nd50-2021 [4] SUBSTITUTION diem b khoan 2 dieu 1: gold `diem đ khoan 1 dieu 3` ≠ pred `diem đ dieu 3`
- nd50-2021 [5] SUBSTITUTION diem c khoan 2 dieu 1: gold `diem e khoan 1 dieu 3` ≠ pred `diem e dieu 3`
- nd50-2021 [6] SUBSTITUTION diem d khoan 2 dieu 1: gold `diem g khoan 1 dieu 3` ≠ pred `diem g dieu 3`
- nd50-2021 [7] INSERTION diem đ khoan 2 dieu 1: gold `diem i1 khoan 1 dieu 3` ≠ pred `diem i1 dieu 3`
- nd50-2021 [8] INSERTION diem e khoan 2 dieu 1: gold `diem d1 khoan 2 dieu 3` ≠ pred `diem d1 dieu 3`
- nd50-2021 [9] INSERTION diem e khoan 2 dieu 1: gold `diem d2 khoan 2 dieu 3` ≠ pred `diem d2 dieu 3`
- nd50-2021 [11] INSERTION khoan 3 dieu 1: gold `khoan 5 dieu 4` ≠ pred `khoan 4 dieu 4`
- nd50-2021 [12] INSERTION khoan 4 dieu 1: gold `khoan 7 dieu 7` ≠ pred `khoan 6 dieu 7`
- nd50-2021 [13] INSERTION diem a khoan 5 dieu 1: gold `diem d1 khoan 3 dieu 15` ≠ pred `diem d1 dieu 15`
- nd50-2021 [14] INSERTION diem b khoan 5 dieu 1: gold `diem d1 khoan 5 dieu 15` ≠ pred `diem d1 dieu 15`
- nd50-2021 [15] INSERTION diem a khoan 6 dieu 1: gold `diem a1 khoan 4 dieu 18` ≠ pred `diem a1 dieu 18`
- nd50-2021 [16] INSERTION diem b khoan 6 dieu 1: gold `khoan 5a dieu 18` ≠ pred `khoan 5 dieu 18`
- tt01-2022-bct [7] SUBSTITUTION khoan 2 dieu 1: gold `None` ≠ pred `None`
- tt01-2022-bct [16] INSERTION khoan 4 dieu 1: gold `dieu 20a` ≠ pred `dieu 20`
- tt01-2022-bct [24] INSERTION khoan 5 dieu 1: gold `dieu 28a` ≠ pred `dieu 28`
- tt01-2022-bct [25] INSERTION khoan 6 dieu 1: gold `dieu 29a` ≠ pred `dieu 29`
- tt119-2014-btc [20] SUBSTITUTION khoan 3 dieu 3: gold `khoan 3 dieu 12` ≠ pred `dieu 12`
- tt119-2014-btc [27] INSERTION khoan 5 dieu 3: gold `diem a khoan 4 dieu 14` ≠ pred `khoan 4 dieu 14`
- tt14-2019-nhnn [17] SUBSTITUTION khoan 1 dieu 1: gold `dieu 17` ≠ pred `None`
- tt23-2016-nhnn [7] SUBSTITUTION khoan 3 dieu 1: gold `None` ≠ pred `dieu 5`
- tt26-2015-btc [4] INSERTION khoan 2 dieu 1: gold `khoan 3a dieu 4` ≠ pred `dieu 4`
- tt26-2015-btc [28] INSERTION diem b khoan 9 dieu 1: gold `khoan 14a dieu 14` ≠ pred `dieu 14`
- tt26-2015-btc [31] SUBSTITUTION khoan 11 dieu 1: gold `diem b khoan 3 dieu 16` ≠ pred `khoan 3 dieu 16`

## Pred không ghép được gold (30)

- nd50-2021 SUBSTITUTION khoan 2 dieu 1 → `khoan 2 dieu 3`
- nd50-2021 INSERTION khoan 5 dieu 1 → `khoan 5 dieu 15`
- nd50-2021 INSERTION khoan 6 dieu 1 → `khoan 5 dieu 18`
- nd50-2021 SUBSTITUTION khoan 14 dieu 1 → `khoan 3 dieu 38`
- tt01-2022-bct SUBSTITUTION khoan 1 dieu 1 → `khoan 2 dieu 2`
- tt01-2022-bct SUBSTITUTION khoan 2 dieu 1 → `khoan 1 dieu 5`
- tt01-2022-bct REPEAL khoan 1 dieu 1 → `None`
- tt01-2022-bct REPEAL diem a khoan 1 dieu 1 → `khoan 2 dieu 1`
- tt01-2022-bct REPEAL khoan 2 dieu 1 → `khoan 2 dieu 1`
- tt119-2014-btc SUBSTITUTION diem a khoan 6 dieu 3 → `diem c khoan 3 dieu 15`
- tt119-2014-btc SUBSTITUTION diem c khoan 6 dieu 3 → `diem c khoan 4 dieu 15`
- tt130-2016-btc SUBSTITUTION khoan 1 dieu 1 → `dieu 4`
- tt14-2019-nhnn SUBSTITUTION khoan 2 dieu 1 → `None`
- tt14-2019-nhnn SUBSTITUTION khoan 3 dieu 1 → `None`
- tt14-2019-nhnn SUBSTITUTION khoan 4 dieu 1 → `None`
- tt14-2019-nhnn SUBSTITUTION khoan 5 dieu 1 → `None`
- tt14-2019-nhnn SUBSTITUTION khoan 6 dieu 1 → `None`
- tt14-2019-nhnn SUBSTITUTION khoan 7 dieu 1 → `None`
- tt14-2019-nhnn SUBSTITUTION khoan 8 dieu 1 → `None`
- tt14-2019-nhnn SUBSTITUTION khoan 9 dieu 1 → `None`
- tt14-2019-nhnn SUBSTITUTION khoan 10 dieu 1 → `None`
- tt14-2019-nhnn SUBSTITUTION khoan 11 dieu 1 → `None`
- tt14-2019-nhnn SUBSTITUTION khoan 12 dieu 1 → `None`
- tt14-2019-nhnn INSERTION diem b khoan 12 dieu 1 → `dieu 4`
- tt26-2015-btc SUBSTITUTION khoan 9 dieu 1 → `dieu 14`
- tt26-2015-btc SUBSTITUTION diem a khoan 12 dieu 1 → `khoan 3 dieu 18`
- tt26-2015-btc SUBSTITUTION diem c khoan 12 dieu 1 → `khoan 5 dieu 18`
- tt27-2014-nhnn SUBSTITUTION khoan 1 dieu 1 → `khoan 3 dieu 4`
- tt27-2014-nhnn SUBSTITUTION khoan 2 dieu 1 → `khoan 2 dieu 5`
- tt27-2014-nhnn SUBSTITUTION khoan 6 dieu 1 → `dieu 17`

## Gold bị bỏ sót (45)

- tt01-2022-bct [2] REPEAL diem a khoan 1 dieu 3 → `khoan 2 dieu 1`
- tt01-2022-bct [3] REPEAL diem a khoan 1 dieu 3 → `dieu 3`
- tt01-2022-bct [4] REPEAL diem a khoan 1 dieu 3 → `dieu 4`
- tt01-2022-bct [6] REPEAL diem a khoan 1 dieu 3 → `dieu 6`
- tt01-2022-bct [9] REPEAL diem a khoan 1 dieu 3 → `dieu 13`
- tt01-2022-bct [29] SUBSTITUTION diem a khoan 1 dieu 3 → `None`
- tt119-2014-btc [21] SUBSTITUTION khoan 3 dieu 3 → `diem đ khoan 3 dieu 12`
- tt119-2014-btc [22] SUBSTITUTION khoan 3 dieu 3 → `khoan 4 dieu 12`
- tt119-2014-btc [23] SUBSTITUTION khoan 3 dieu 3 → `diem d khoan 4 dieu 12`
- tt13-2023-btc [34] SUBSTITUTION khoan 3 dieu 1 → `khoan 2 dieu 18`
- tt130-2016-btc [36] SUBSTITUTION khoan 3 dieu 1 → `khoan 4 dieu 18`
- tt14-2019-nhnn [30] INSERTION khoan 1 dieu 2 → `None`
- tt14-2019-nhnn [31] INSERTION khoan 1 dieu 2 → `None`
- tt21-2018-bct [11] SUBSTITUTION khoan 4 dieu 1 → `khoan 2 dieu 15`
- tt21-2018-bct [12] SUBSTITUTION khoan 4 dieu 1 → `khoan 1 dieu 16`
- tt21-2018-bct [13] SUBSTITUTION khoan 4 dieu 1 → `khoan 2 dieu 17`
- tt21-2018-bct [14] SUBSTITUTION khoan 4 dieu 1 → `khoan 2 dieu 18`
- tt21-2018-bct [19] SUBSTITUTION khoan 4 dieu 1 → `khoan 2 dieu 23`
- tt21-2018-bct [20] SUBSTITUTION khoan 4 dieu 1 → `khoan 1 dieu 24`
- tt21-2018-bct [21] SUBSTITUTION khoan 4 dieu 1 → `khoan 2 dieu 25`
- tt21-2018-bct [22] SUBSTITUTION khoan 4 dieu 1 → `khoan 2 dieu 26`
- tt21-2018-bct [26] SUBSTITUTION khoan 4 dieu 1 → `khoan 1 dieu 32`
- tt21-2018-bct [27] SUBSTITUTION khoan 4 dieu 1 → `khoan 3 dieu 32`
- tt21-2018-bct [32] SUBSTITUTION khoan 4 dieu 1 → `None`
- tt21-2018-bct [34] SUBSTITUTION khoan 4 dieu 1 → `None`
- tt23-2016-nhnn [5] SUBSTITUTION khoan 1 dieu 1 → `khoan 1 dieu 1`
- tt23-2016-nhnn [6] SUBSTITUTION khoan 2 dieu 1 → `khoan 2 dieu 3`
- tt23-2016-nhnn [8] REPEAL dieu 2 → `dieu 4`
- tt23-2016-nhnn [9] SUBSTITUTION khoan 4 dieu 1 → `dieu 5`
- tt23-2016-nhnn [14] REPEAL dieu 2 → `dieu 11`
- tt26-2015-btc [14] REPEAL khoan 4 dieu 4 → `khoan 22 dieu 7`
- tt26-2015-btc [17] REPEAL khoan 7 dieu 1 → `khoan 3 dieu 10`
- tt26-2015-btc [19] SUBSTITUTION khoan 8 dieu 1 → `khoan 11 dieu 10`
- tt26-2015-btc [30] SUBSTITUTION khoan 10 dieu 1 → `khoan 3 dieu 15`
- tt27-2014-nhnn [15] SUBSTITUTION dieu 2 → `diem d khoan 1 dieu 12`
- tt27-2014-nhnn [16] SUBSTITUTION dieu 2 → `khoan 2 dieu 16`
- tt27-2014-nhnn [22] SUBSTITUTION dieu 2 → `dieu 19`
- tt43-2018-nhnn [10] SUBSTITUTION khoan 1 dieu 1 → `diem v khoan 1 dieu 5`
- tt43-2018-nhnn [23] SUBSTITUTION khoan 2 dieu 1 → `khoan 8 dieu 19`
- tt43-2018-nhnn [24] SUBSTITUTION khoan 2 dieu 1 → `khoan 8 dieu 19`
- tt43-2018-nhnn [25] SUBSTITUTION khoan 2 dieu 1 → `khoan 1 dieu 19`
- tt43-2018-nhnn [26] SUBSTITUTION khoan 2 dieu 1 → `khoan 2 dieu 19`
- tt43-2018-nhnn [27] SUBSTITUTION khoan 2 dieu 1 → `khoan 3 dieu 19`
- tt43-2018-nhnn [28] SUBSTITUTION khoan 2 dieu 1 → `khoan 3 dieu 19`
- tt43-2018-nhnn [29] SUBSTITUTION khoan 2 dieu 1 → `khoan 3 dieu 19`
