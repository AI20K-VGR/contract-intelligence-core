"""Backend SemVer version — đồng bộ với DOC-05b v1.0.0 API contract.

Mọi HTTP response trả về header ``X-Backend-Version: <value>`` để Frontend
và integrations kiểm tra compatibility (SemVer theo ADR-12).

Quy tắc tăng phiên bản:
    MAJOR — breaking API change (xóa field, đổi kiểu field)
    MINOR — thêm endpoint mới hoặc thêm optional field
    PATCH — bugfix, refactor nội bộ, không ảnh hưởng client

Changelog (ADR-12):
    v1.0.0 — Sprint 3 baseline. Auth + Contract BC + Document upload + Manifest.
    v1.1.0 — Sprint 4. **AI service integration** (DOC-05c v1.0.0):
                - POST /dossiers/upload — multipart tạo dossier + auto-trigger run
                  (đã gỡ: dùng POST /dossiers → Kafka dossier.uploaded)
                - POST /dossiers/{id}/runs — async pipeline trigger qua AI service
                - POST /documents/{id}/re-ocr — async Re-OCR submission
                - GET  /runs/{id}/events — SSE stream real-time updates
                - GET  /ai/healthz, /readyz, /ai/jobs/{id} — AI service proxy
                - BackgroundDispatcher + PipelineOrchestrator
                  drive OCR → Extract → Compare chain.
                - canonical persistence (Semantic Gate — ADR-05)
    v2.0.0 — Sprint 3 backend (PR#28 và các commit sau). **Breaking:**
                - bỏ POST /dossiers/upload (dùng POST /dossiers)
                - bỏ webhook callback AI1/AI2 và API /reviews cũ
             Thêm (MINOR, gộp vào bản này):
                - POST /dossiers/{id}/ai2/retry, /ocr/retry-failed, /split
                - chia sẻ read/edit có hạn, lịch sử hỏi đáp theo người dùng

Nguồn duy nhất của version: ``pyproject.toml`` và ``contract_intelligence.__version__``
phải bằng ``__version__`` ở đây (có test kiểm tra).

Khi DOC-05b thay đổi breaking → bump MAJOR (v2.0.0).
Khi DOC-05c thay đổi breaking → bump MAJOR (v2.0.0) + bump __ai_contract__.
"""

from __future__ import annotations

# SemVer — bump theo ADR-12 khi release
__version__ = "2.0.0"

# API contract version = phiên bản DOC-05b. v1.1.0 (PR #41): thêm /queries,
# /ocr/retry-failed, /split. MINOR vì các endpoint 2.0.0 bỏ đi chưa từng có trong
# DOC-05b. Độc lập với __version__ (SemVer của backend, vẫn 2.0.0).
# v1.2.0 (DEC-BE-AI2-01 B4): thêm 422 DOSSIER_TOO_MANY_DOCUMENTS và contract_not_unique.
# v1.3.0: finding.review.latest (lượt thẩm định gần nhất) trên /findings, /conflicts.
# v1.4.0: POST /dossiers/{id}/ai2/reindex — AI2 dựng lại dữ liệu từ OCR đã lưu.
# v1.5.0: GET /documents/{id}/lines; 409 trên POST /dossiers/{id}/ocr khi đang OCR.
# v1.5.1: lịch sử hỏi đáp có endpoint "search" và mã lỗi AI2_UNAVAILABLE.
# v1.6.0: đề xuất /notifications trong DOC-05b; backend chưa có, nên bỏ qua số này.
# v1.7.0: GET /users/directory, GET /review-queue; my_access, locked, approved_at trên hồ sơ.
# v2.0.0: bỏ scope=all của GET /dossiers/{id}/queries; ai hỏi chỉ xem lịch sử của mình.
# v2.0.1: ghi giới hạn tải hồ sơ (50 MiB mỗi file, 100 MB mỗi request trên bản online).
# v2.0.2: /documents/{id}/content nhận Range (206/416) và If-None-Match (304), có ETag.
# v2.1.0: GET /dossiers/{id}/ai2/contract-graph, .../evidence, .../processing-trace;
#         PATCH /dossiers/{id}/ai2-content-sharing-consent.
# v3.0.0: token không có role ứng dụng → 403; /ai/jobs chỉ ADMINISTRATOR; batch
#         cancel/resume chỉ người tạo hoặc ADMINISTRATOR (#96). Thu hẹp quyền nên MAJOR.
# v3.1.0: bật consent AI2 tự reindex hồ sơ đã qua AI2; consent trả thêm ai2_reindex_queued.
# v3.2.0: progress {done,total,unit} trên /runs/{id}/steps và SSE step.changed;
#         mã lỗi AI1_NO_READABLE_PAGE khi AI1 không đọc được trang nào.
# v3.3.0: GET /dossiers thêm document_counts, contract_ocr; header Server-Timing.
# v4.0.0: PUT /dossiers/{id}/access kiểm tra người nhận mới trong Keycloak (422
#         share_recipient_not_found); GET /users/lookup; /users/directory bắt OPERATOR
#         gửi q; không gửi thư tới tên miền dành riêng. Thu hẹp hành vi nên MAJOR.
# v4.1.0: phiên Keycloak đã kết thúc (back-channel logout) → token của phiên đó
#         nhận 401 "Session has ended" ngay, không chờ hết hạn.
# v5.0.0: không gửi được thư thì không có quyền. PUT /dossiers/{id}/access từ chối
#         người nhận mới có tên miền không nhận thư (422 share_recipient_undeliverable)
#         và gỡ người gửi thư lỗi, trả họ trong email_not_sent. Thu hẹp hành vi nên MAJOR.
__api_contract__ = "v5.0.0"

# AI service contract version (DOC-05c) — wrap khi AI service sẵn sàng
__ai_contract__ = "v1.0.0"

# Build metadata (PEP 440) — informational only
__build__ = "sprint3-backend"


def full_version() -> str:
    """Trả về version string đầy đủ — dùng cho header / OpenAPI metadata."""
    return f"{__version__}+{__build__}"


__all__ = [
    "__api_contract__",
    "__ai_contract__",
    "__build__",
    "__version__",
    "full_version",
]
