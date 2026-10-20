# P3 — Corpus phát triển đã review (v3)

- Trạng thái review: `REVIEW_LOCKED_QUALITY_READINESS_BLOCKED`.
- Dataset: `quality-recovery-dev-20261011-v3`; gold đã duyệt: 600 dòng.
- Nhãn gold: `{"CONFLICT": 1, "DUPLICATE": 2, "GENERAL_SPECIFIC": 27, "REFERENCE": 7, "UNRELATED": 563}`.
- Review lock: `contract-graph-quality-review-lock/1`; SHA gold `11355553a39300a5557941ae38edc450e9ef72f8f8926666b9fa7a835865a0b3`.
- AI blind second-pass: 150 dòng; đồng thuận 149; bất đồng 1.
- Annotation độc lập của người thứ hai: được user miễn; không tuyên bố human-human agreement.
- Quality readiness: `BLOCKED`; blockers: `general_specific_positive_minimum_not_met, conflict_positive_minimum_not_met, conflict_cluster_minimum_not_met, conflict_cluster_dominance_exceeded, duplicate_positive_minimum_not_met, duplicate_cluster_minimum_not_met, duplicate_cluster_dominance_exceeded, reference_positive_minimum_not_met`.
- User miễn minimum-yield để tiếp tục, nhưng các metric/gate chất lượng ở P4/P5 vẫn giữ nguyên.
- Held-out không được đọc hoặc tune; không có classifier PASS hay quyền bật runtime.
- Manifest SHA-256: `cd4063217316971671b8992da9dbf50d00aa27613cd30d448862175e6b0059e3`.
