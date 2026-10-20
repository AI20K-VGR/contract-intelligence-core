"""Application configuration — pydantic-settings.

Mọi cấu hình đọc qua :class:`Settings`. Singleton được expose qua
``get_settings()`` (cache với ``functools.lru_cache``).
"""

from contract_intelligence.config.settings import Settings, get_settings

__all__ = ["Settings", "get_settings"]
