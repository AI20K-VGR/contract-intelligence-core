# P5 follow-up — model guard và điều kiện PASS

**Ngày:** 2026-10-09  
**Worktree:** `C:\Users\dungs\OneDrive\Documents\VSF-ai2-contract-graph`  
**Nhánh:** `feature/ai2-contract-graph`

## Thay đổi đã sửa

- Thêm bộ nhận diện model dùng chung tại `ai-service/app/pipeline/contract_graph/model_family.py`.
- Runtime classifier dùng bộ nhận diện này thay cho tuple prefix cố định; các model reasoning mới như `o5-mini` không bị fallback sai.
- `evals/contract_graph/pairs/models.py` tái sử dụng cùng nguồn quy tắc.
- Thêm regression test `test_reasoning_openai_model_family_uses_shared_gate`.

## Kiểm chứng

- Red trước sửa: test model `o5-mini` không sinh prediction.
- Green sau sửa: test predictor `19 passed`.
- Full eval contract graph: `224 passed`.
- Ruff trên phạm vi thay đổi: `All checks passed`.
- Dataset: `verify ok`.

## Blocker để đạt PASS

Policy P5 yêu cầu từng nhãn đạt `n >= 60` và Wilson lower `>= 0.85`. HG-1 đang khóa `181` dòng với số gold approved:

| Nhãn | Số dòng |
|---|---:|
| `CONFLICT` | 30 |
| `DUPLICATE` | 29 |
| `GENERAL_SPECIFIC` | 34 |
| `REFERENCE` | 8 |

Vì `passed` không thể vượt số gold đúng nhãn, bộ dữ liệu hiện tại không thể đạt cổng này; `REFERENCE` là giới hạn rõ nhất. Quyết định P5 hiện vẫn `HUMAN_DECISION`, runtime flag phải giữ tắt.

Thay đổi guard làm đổi code fingerprint, vì vậy sáu trial P5 trước đó không còn là bằng chứng cho snapshot mới và phải chạy lại sau khi chốt hướng dữ liệu/policy.

## Hướng xử lý cần quyết định

1. Mở rộng HG-1 bằng các mẫu đã được người dùng duyệt, đủ số dương cho từng nhãn; hoặc
2. Phê duyệt amendment thay đổi gate P5, sau đó cập nhật test, tài liệu và chạy lại bake-off.

Không thay đổi verdict thủ công và không ghi secret vào artifact.
