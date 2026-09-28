---
id: {{ID}}
title: "{{TITLE}}"
status: pending
mode: {{MODE}}
tdd: {{TDD}}
branch: {{BRANCH}}
created: {{CREATED}}
author: {{AUTHOR}}
decisions: []
phases:
{{PHASES_YAML}}
---

# Plan: {{TITLE}}

> TBD — thay từng phần dưới bằng thực tế của task. hs:cook ĐỌC file này làm
> hợp đồng; giữ ngắn, chính xác, có evidence (file:line / ID) cho mọi claim
> không hiển nhiên. Tag `[ASSUMED]` (hoặc `[PRIOR]` nếu claim dựa trên kiến thức có sẵn/training) lên claim chưa có anchor.

## Tổng quan
TBD — một đoạn: task làm gì, scope thật (cắt YAGNI), vì sao cần.

## Quyết định đã khoá
TBD — liệt kê quyết định user đã chốt (không re-litigate). Trống nếu chưa có.

## Ràng buộc (constraint-scan)
TBD — zone/policy/schema chi phối (ownership.yaml, stage-policy.yaml, schemas/).

## Features
TBD — liệt kê từng năng lực NGƯỜI DÙNG nhận được, mỗi dòng một mục, đặt tên ngắn
và ổn định (đây là trục `feature` của coverage-grid khi chạy `--grid`, và là thứ
`hs:discover` đối chiếu lại ở pass-2). Mô tả CÁI GÌ ship, không mô tả cách làm —
cách làm nằm ở `## Phases`.

## Phases
{{PHASES_TABLE}}

## Out of scope
TBD — cái cố ý KHÔNG làm đợt này.

## Acceptance (toàn plan)
- [ ] Mỗi phase red→green TDD; test suite của project xanh sau mỗi phase (dùng lệnh test thật của repo).
- [ ] Lint + type-check + build của project sạch (theo lệnh thật của repo).
- [ ] TBD — tiêu chí nghiệm thu đặc thù của plan này.

## Rollback
TBD — mỗi phase commit riêng; cách hoàn tác (git revert <range>, chạy lại gate build/verify của project nếu có).

## Risks
TBD — rủi ro + mitigation.
