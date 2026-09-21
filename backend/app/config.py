from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CI_", env_file=".env", extra="ignore")
    database_url: str = "postgresql+psycopg://ci:ci@localhost:5432/ci"
    artifact_root: Path = Path("data/artifacts")
    max_upload_bytes: int = 30 * 1024 * 1024
    max_pages: int = 300
    # 300 DPI is the accuracy floor Tesseract's own docs recommend; below that, thin
    # Vietnamese diacritics blur into noise or drop out entirely. max_pixels is sized
    # to still admit a 300 DPI render of an oversized (A3) scanned page.
    max_pixels: int = 40_000_000
    dpi: int = 300
    ocr_languages: str = "vie+eng"
    ocr_timeout_seconds: int = 90
    # "tesseract" (local_baseline, default) or "gpt_vision" (terra_assisted, ADR-03):
    # Tesseract still runs either way to anchor line bbox/order; gpt_vision additionally
    # re-transcribes the page and substitutes its text per line when the line counts
    # match, falling back to the Tesseract text (flagged for review) otherwise, since a
    # count mismatch means the two sources can no longer be paired by position alone.
    ocr_engine: str = "tesseract"
    openai_api_key: str = ""
    ocr_vision_model: str = "gpt-5.6-terra"
    # The OpenAI SDK itself retries connection errors, timeouts, 429 rate limits, and 5xx
    # responses with backoff — none of those are this deployment's fault, and a page
    # shouldn't fall back to the lower-accuracy Tesseract text (flagged for review) over
    # a transient blip. Raised from the SDK's own default of 2. A permanent failure (bad
    # API key, unknown model name) still fails fast — the SDK does not retry those.
    ocr_vision_max_retries: int = 5
    # Table Continuity Agent (app/table_continuity.py): only reached for a genuinely
    # ambiguous cross-page table pair, and only when a job's own config explicitly
    # opts in (Job.config["table_continuity_agent"], set per dossier by the caller of
    # POST /dossiers/{id}/jobs — never a deployment-wide default). Sends a small
    # metadata/text packet (never a page image, never a full table) to DeepSeek's
    # hosted, OpenAI-wire-compatible API.
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-flash"
    lease_seconds: int = 180
    max_attempts: int = 3
    poll_seconds: float = 2


settings = Settings()
