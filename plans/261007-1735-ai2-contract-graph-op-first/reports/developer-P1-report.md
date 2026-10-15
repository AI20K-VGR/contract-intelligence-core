# P1 developer report (tóm tắt, đã kiểm tại main)

- Harness suite: 52 passed (main chạy lại 2026-10-08).
- ai-service suite: 13 failed (đúng danh sách môi trường) / 1061 passed / 36 skipped (subagent chạy; P1 không sửa `ai-service/`).
- Dataset: 11 cặp, 4 cơ quan, 113 gold (SUBSTITUTION 83, INSERTION 18, REPEAL 12), 2.257.522 bytes, `verify_manifest == []`.
- p1-baseline: src_found 68/113, op_lexical_agreement 67/113, target_accuracy 44/68; nd50 26/26 src+op, 13/26 target.
- Deviation: scorer list-target + `.gitattributes` eol=lf (plan VL-5, người dùng chốt).
