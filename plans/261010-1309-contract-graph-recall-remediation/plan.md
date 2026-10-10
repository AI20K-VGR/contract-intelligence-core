---
id: 261010-1309-contract-graph-recall-remediation
title: "AI2 contract graph — remediation recall thấp"
description: "Tách và sửa mất recall ở candidate generation và classifier, bổ sung gold HG-1 có kiểm soát, rồi xác minh lại P5 trước mọi enablement."
status: draft
priority: P1
effort: "~5 phase kỹ thuật + 1 human gate HG-2 cho recall floor và nhãn bổ sung"
mode: hard
tdd: true
branch: feature/ai2-contract-graph
tags: [ai2, contract-graph, recall, candidate-coverage, classifier, hg-1, bakeoff]
created: 2026-10-10
phases:
  - phases/phase-1-recall-diagnostic.md
  - phases/phase-2-candidate-coverage.md
  - phases/phase-3-classifier-calibration.md
  - phases/phase-4-gold-expansion.md
  - phases/phase-5-final-bakeoff.md
---

# Plan: AI2 contract graph — remediation recall thấp

## Mục tiêu

Đưa luồng 2 từ trạng thái quan sát `recall_any=2–10/101` về một mức có thể đánh giá an toàn bằng bằng chứng tách bạch: candidate coverage, classifier recall, conservative precision, false `DUPLICATE`, chi phí và độ trễ. Không bật runtime trong kế hoạch này; chỉ một verdict bake-off hợp lệ mới được phép đề xuất enablement.

## Baseline đã xác minh (OBSERVED, 2026-10-10)

- Snapshot live dùng requested `cx/gpt-5.5`, served `gpt-5.5`, family `openai`, sáu trial C1/B1/E1/C2/B2/E2 trên cùng HG-1 lock và code fingerprint.
- Recall any: C1 `5/101`, B1 `2/101`, E1 `7/101`, C2 `4/101`, B2 `3/101`, E2 `10/101`.
- Candidate coverage độc lập trên 101 gold positives: C `74/101`, B `77/101`, E `101/101`.
- E gửi đủ 655 candidate nhưng classifier trả `UNRELATED` cho `587/655` và `572/655`; không có `no_answer`, trace không có provider error. C/B cũng trả `UNRELATED` cho `139–146` candidate.
- `CONFLICT` đúng `0/30` và `DUPLICATE` đúng `0/29` ở mọi trial. E vẫn thấp dù candidate coverage `101/101`; vì vậy candidate pruning không phải nguyên nhân duy nhất.
- E vượt 550 giây ở cả hai trial (`714.874393s`, `737.984944s`).
- HG-1 approved hiện có các positive label: `CONFLICT=30`, `DUPLICATE=29`, `GENERAL_SPECIFIC=34`, `REFERENCE=8`; đủ để chẩn đoán nhưng chưa đủ để chứng minh gate precision bảo thủ `MIN_N=60`, `MIN_WILSON_LOWER=0.85`.
- Artifact verification/review hiện hành là `PASS`, decision runtime là `KEEP_OFF_INSUFFICIENT_N`; cờ vẫn tắt.

Evidence sources: `evals/contract_graph/reports/l2-p5-bakeoff.json`, `.harness/state/contract-graph-pairs/bakeoff-gpt55-final-20261010/`, `ai-service/app/pipeline/contract_graph/pair_candidates.py`, `ai-service/app/pipeline/contract_graph/pair_classifier.py`, `evals/contract_graph/pairs/bakeoff.py`.

## Giả thuyết cần kiểm chứng

| ID | Giả thuyết | Cách phân biệt | Kết quả cần có |
|---|---|---|---|
| H1 | C/B bỏ sót do top-k và heuristic candidate | Đối chiếu từng gold positive với candidate set, nguồn, score, lý do loại | Bảng coverage theo label/stratum/source |
| H2 | Classifier gpt-5.5 quá bảo thủ hoặc rubric không đủ rõ | Chạy diagnostic dev, lưu label raw, rejection reason, span/direction; không tuning held-out | Tách `UNRELATED` khỏi lỗi schema/grounding |
| H3 | Nhãn HG-1 hoặc định nghĩa label gây khó cho model | Audit riêng conflict/duplicate/reference với dev examples và người duyệt | Danh sách ambiguity được phân loại, không tự relabel held-out |
| H4 | Chi phí E làm dừng sớm | Đối chiếu `pairs_sent`, `pairs_unclassified`, deadline và tokens | E không được coi là cải thiện nếu vượt budget |

## Quyết định thiết kế và giới hạn

- Giữ `MIN_N=60`, Wilson lower `0.85`, consent, model-family gate, exact span grounding và false-duplicate veto; không hạ ngưỡng để làm pass.
- Held-out HG-1 không được dùng để tune prompt, top-k, model hay chọn mẫu. Mọi tune dùng dev hoặc bộ diagnostic mới được ghi provenance.
- Raw hợp đồng và raw API response không đưa vào artifact tracked; artifact chỉ ghi pair id, label, stratum, coverage, rejection code, digest và aggregate.
- Model phải ghi requested/served model cho mọi trial; classifier phải khác model cụ thể của labeler.
- `CONFLICT`/`DUPLICATE` bằng 0 là hard stop cho mọi đề xuất enablement. Conservative precision vẫn phải đạt gate hiện hành; recall được nâng thành safety metric bắt buộc trong plan này.
- Human gate HG-2 phải chốt recall floor trước final bake-off. Đề xuất mặc định: Wilson lower recall `>=0.85` cho các label scored; nếu chưa chốt, chỉ được báo cáo và giữ off.

## Phạm vi / ngoài phạm vi

**Trong phạm vi:** diagnostic scorer, candidate coverage, prompt/classifier calibration, sizing và bổ sung nhãn HG-1, bake-off P5, tests và reports.

**Ngoài phạm vi:** thay đổi BE contract, UI, migration/storage, tự bật `AI2_CONTRACT_GRAPH_PAIRS_ENABLED`, dùng nhãn GPT chưa được người duyệt, hoặc chạy tiếp live trial chỉ để tìm một winner khi chưa sửa nguyên nhân.

## Tiêu chí hoàn thành

1. Diagnostic chứng minh được tỷ lệ mất ở từng tầng: candidate miss, classifier `UNRELATED`, schema/grounding rejection, budget/unclassified.
2. Candidate coverage trên dev đạt engineering target `>=95%` cho từng scored label; mọi ngoại lệ có lý do và report.
3. Diagnostic classifier không còn `CONFLICT`/`DUPLICATE` bằng 0 trên dev; output vẫn phải grounded và direction hợp lệ.
4. HG-1 mở rộng có phiếu người duyệt, manifest lock mới, decisions SHA mới và không có thay đổi âm thầm trong held-out.
5. Final bake-off có C/B/E × 2 trial, cùng model/fingerprint/lock; không có false `DUPLICATE`, không có provider/trace lỗi, E trong budget `550s/500,000 tokens` nếu được giữ lại.
6. Final decision phải qua recall safety gate HG-2 và gate precision hiện hành. Nếu không đạt, verdict giữ `KEEP_OFF_*`, không dùng `PASS_WITH_RISK` để enable.
7. Full eval, focused tests, Ruff, manifest verify và artifact review đều PASS.

## Phases

| Phase | Mục đích | Human gate | Kết quả đóng phase |
|---|---|---|---|
| P1 | Chẩn đoán false negative và instrumentation | Không tune held-out | `l2-p6-recall-diagnostic.*` + verification |
| P2 | Sửa/đo candidate coverage trên dev | Không sửa held-out | candidate report + tests |
| P3 | Hiệu chỉnh classifier và rejection telemetry | Không nới grounding | classifier report + tests |
| P4 | Bổ sung gold và khóa HG-2 | Người dùng duyệt recall floor + nhãn | manifest lock + sizing receipt |
| P5 | Bake-off cuối và decision | Human review trước enablement | six trials, decision, review/verification |

## Red-team trước khi cook

- **Leakage:** nếu dùng held-out để chọn prompt/model, kết quả mất giá trị. Mitigation: mọi thay đổi được freeze trên dev; held-out chỉ chạy sau lock.
- **Recall gaming:** nới `UNRELATED` thành positive hoặc bỏ span validation sẽ tăng số đo giả. Mitigation: giữ schema, exact span, conservative precision và false-duplicate veto.
- **Model overfit:** few-shot lấy trực tiếp từ held-out sẽ làm contamination. Mitigation: dùng dev examples có digest và ghi nguồn.
- **Budget drift:** E có thể thắng recall nhưng vượt thời gian. Mitigation: preflight trước trial, budget là điều kiện bắt buộc.
- **Label ambiguity:** conflict/duplicate/reference có thể bị người duyệt hiểu khác nhau. Mitigation: audit rubric và yêu cầu người duyệt relabel/reject minh bạch, không sửa ngầm.
- **Provider variance:** requested model không đảm bảo served model. Mitigation: kiểm tra served model từng trace và một fingerprint cho cả run.

## Validation log

- VL-1 | 2026-10-10 | P5 live snapshot xác nhận recall thấp, E over-budget, C/B candidate ceiling và E classifier conservatism.
- VL-2 | 2026-10-10 | Full eval `225 passed`, focused bake-off `61 passed`, Ruff sạch, manifest verify OK.
- VL-3 | 2026-10-10 | Decision hiện hành `KEEP_OFF_INSUFFICIENT_N`; verification/review artifact `PASS`; runtime flag vẫn tắt.
- VL-4 | 2026-10-10 | Scope challenge: HOLD — cần remediation có đo lường trước khi tiếp tục live bake-off; không mở rộng sang BE/UI/storage.

## Next step

Kế hoạch này cần human approval trước khi cook. Sau approval, chạy P1 diagnostic; không chạy lại full P5 trước khi P1–P3 có report và code/prompt fingerprint được freeze.
