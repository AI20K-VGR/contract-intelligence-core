# P4 — Bổ sung gold và khóa HG-2

## Mục tiêu

Mở rộng reviewed gold đủ cho conservative precision gate và chốt recall floor trước final bake-off. Đây là human gate; không tự gán hoặc tự approve nhãn.

## Sizing baseline

HG-1 hiện có `CONFLICT=30`, `DUPLICATE=29`, `GENERAL_SPECIFIC=34`, `REFERENCE=8` approved positives. Sizing tối thiểu để có 60 gold positives mỗi label là lần lượt thêm `30`, `31`, `26`, `52` dòng nếu các dòng mới thực sự hợp lệ; đây là lower bound, không phải số nhãn được phép tự tạo.

## Human gate HG-2

Người dùng phải:

1. Chốt recall floor và liệu `CONFLICT`/`DUPLICATE` có zero-tolerance trong pilot.
2. Duyệt/relabel/reject các dòng bổ sung; mọi decision ghi vào phiếu và có SHA.
3. Xác nhận bộ dữ liệu mở rộng không chứa dữ liệu ngoài consent/scope.

## Files / artifacts

| Action | File | Mục đích |
|---|---|---|
| create | `plans/261010-1309-contract-graph-recall-remediation/reports/hg2-sizing.json` | count hiện có, số cần thêm, sampling plan |
| create | `plans/261010-1309-contract-graph-recall-remediation/reports/hg2-review.md` | receipt human gate |
| modify | `evals/contract_graph/pairs/manifest.json` | lock extension/review selection sau người dùng duyệt |
| modify | `evals/contract_graph/pairs/review.py` | validate decision counts nếu cần |
| modify | `plans/261010-1309-contract-graph-recall-remediation/plan.md` | ghi quyết định HG-2 |

## Acceptance

- Manifest verify OK; review decisions SHA, count và chronology nhất quán.
- Không thay đổi các dòng HG-1 đã lock sau khi bắt đầu final bake-off.
- Recall floor được ghi rõ; nếu chưa có human decision thì phase dừng và runtime vẫn off.
- Raw contract text và API key không vào git.
