# P1 — bằng chứng và telemetry từng cặp

- **Trạng thái replay lịch sử:** `INCOMPLETE_HISTORICAL_REPLAY`.
- Thêm telemetry opt-in từ classifier qua pair builder tới evaluation predictor; diagnostic nhận diện event chính xác và giữ aggregate attribution là aggregate khi không có event.
- Mặc định collector tắt (`event_sink=None`). Event không chứa clause text, span, prompt, provider response, credentials hay exception message.
- Kiểm thử: focused `143 passed`; consent/flag-off regression `16 passed`.
- P1 không gửi request tới model/provider.

## Replay và giới hạn bằng chứng

Diagnostic provenance trỏ tới commit `533b8e051442d788e58536e0ccc521371c89c412`; P5 review lock là `c504df83323aa1a47c9ace3336f47aa70af6799d`. Frozen dataset manifest xác minh không có lỗi; SHA-256 manifest là `5ec4686918743e4419e74e4e4da20af1f733732a1f14b378bd8efcb5c9182cd7`.

Ba hash P5 khớp source tại commit diagnostic: `pair_candidates.py`, `pair_builder.py`, `client.py`. Bốn hash không khớp: `pair_classifier.py`, `predictor.py`, `bakeoff.py`, `score.py`. Vì vậy không khẳng định commit diagnostic tái hiện đúng toàn bộ P5 context. Bốn snapshot P5 không có pair events; nguyên nhân lịch sử ở cấp từng cặp vẫn là `unknown` nếu chỉ còn counter tổng hợp.

Candidate coverage đã có từ diagnostic trước: B `77/101`, C `74/101`, E `101/101`. Đây là bằng chứng coverage, không phải attribution cho các prediction miss của P5.

Telemetry mới chỉ có hiệu lực khi evaluation caller cung cấp `event_sink`. Các event phân biệt `candidate_miss`, `accepted`, `model_unrelated`, `validator_reject(reason)`, `citation_reject`, `no_answer`, `not_sent`; sự cố unknown/duplicate/malformed ID được ghi thành batch event, không gán tùy tiện cho pair. Request ID scoped theo lượt gọi, batch ID theo từng batch. Diagnostic báo số terminal event, event thiếu/thừa so với candidate inventory, và chênh accepted event với prediction để phát hiện sai lệch accounting. Không đưa telemetry vào product stats, coverage hay wire.

## Kiểm thử

- Red trước implementation: `5 failed, 137 passed`; thất bại đúng ở callback classifier/builder, predictor collection và việc diagnostic gán aggregate counter thành nguyên nhân cụ thể.
- Focused green: `143 passed in 1.59s`.
- Consent/flag-off regression: `16 passed in 143.92s`.

Chi tiết SHA-256 của nguồn hiện tại, so sánh hash P5 và kết quả lệnh nằm trong [JSON evidence](quality-recovery-p1-evidence.json). Artifact xác minh phase: [verification-P1.json](../../../plans/261010-2022-contract-graph-quality-recovery/artifacts/verification-P1.json).
