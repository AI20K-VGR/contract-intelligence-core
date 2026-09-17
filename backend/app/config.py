from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CI_", env_file=".env", extra="ignore")
    database_url: str = "postgresql+psycopg://ci:ci@localhost:5432/ci"
    artifact_root: Path = Path("data/artifacts")
    # JSON mapping secret tokens to server-owned identities/roles. No implicit admin.
    accounts: dict[str, dict[str, str]] = Field(default_factory=dict)
    max_upload_bytes: int = 30 * 1024 * 1024
    max_pages: int = 300
    max_pixels: int = 16_000_000
    dpi: int = 150
    ocr_languages: str = "vie+eng"
    ocr_timeout_seconds: int = 90
    lease_seconds: int = 180
    max_attempts: int = 3
    poll_seconds: float = 2


settings = Settings()
