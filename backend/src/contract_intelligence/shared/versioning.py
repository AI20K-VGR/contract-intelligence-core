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

# API contract version (DOC-05b). Chưa bump dù 2.0.0 bỏ endpoint (breaking với
# client còn gọi POST /dossiers/upload, webhook AI1/AI2 hay /reviews cũ): tài liệu
# DOC-05b chưa ra bản mới. Frontend hiện không gọi các endpoint đã bỏ và không đọc
# giá trị này. Chờ chốt với frontend (review PR #38) có nâng DOC-05b lên v2 không.
__api_contract__ = "v1.0.0"

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
