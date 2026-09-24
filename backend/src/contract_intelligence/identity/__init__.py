"""Identity bounded context — user accounts, authentication, session management.

Đây là bounded context độc lập. Nó KHÔNG thuộc về contract/extraction/conflict/review.
Auth dependencies (JWT, argon2) sống trong shared/auth/ — identity chỉ dùng protocol.

Quy tắc layer:
  interfaces → application → domain
  domain KHÔNG import fastapi/sqlalchemy/httpx/minio
  application KHÔNG import infrastructure/interfaces
"""

__all__ = []
