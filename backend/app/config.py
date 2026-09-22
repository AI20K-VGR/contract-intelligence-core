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
    # "tesseract" (local_baseline, default), "gpt_vision" (terra_assisted, ADR-03), or
    # "mistral_vision": Tesseract still runs in every case and always supplies geometry
    # (every word's own bbox, and line/table structure derived from it); the two vision
    # options additionally re-transcribe the page and substitute its text per line, and
    # per WORD within that line when the two sources also agree on word count (so
    # table-cell text from _ocr_tables benefits too, not just the line's own display
    # string) — when the line counts match, falling back to the Tesseract text (flagged
    # for review) otherwise, since a count mismatch means the two sources can no longer
    # be paired by position alone. mistral_vision follows the exact same
    # re-transcription/alignment shape as gpt_vision (see _mistral_vision_lines /
    # _mistral_vision_table in document_processing.py) — only which provider supplies
    # the replacement text differs; the two are mutually exclusive, never both at once.
    #
    # "gpt_vision_only" / "mistral_vision_only": Tesseract is NOT run at all for a
    # scanned/mixed page — the vision provider is the sole source of both text and
    # table structure (see _assemble_vision_only_page), not a substitution layered on
    # top of Tesseract's own geometry. Chosen deliberately over the two modes above
    # when Tesseract's own word-position clustering is unreliable enough (silently
    # dropping/merging table columns, or a line-count mismatch that falls back to
    # worse Tesseract text) that its bbox anchor is doing more harm than good. Every
    # bbox this mode produces is "inferred" — an even grid/vertical split, never a
    # real per-word/per-cell measurement — a conscious, explicit tradeoff (confirmed
    # before building this mode): correct text and table structure now, at the cost
    # of citation/bbox precision (tables.py already skips citing an "inferred" cell;
    # plain lines carry the same flag for the same honesty reason even though nothing
    # downstream currently branches on a line's own inferred flag). mistral_vision_only
    # is live-verified against real scanned tables; gpt_vision_only mirrors its shape
    # as closely as GPT's own no-markdown transcription convention allows but has NOT
    # been checked against a real page (see _GPT_VISION_FULL_PAGE_TABLE_PROMPT) — treat
    # it as best-effort until it has.
    ocr_engine: str = "tesseract"
    openai_api_key: str = ""
    ocr_vision_model: str = "gpt-5.6-terra"
    # The OpenAI SDK itself retries connection errors, timeouts, 429 rate limits, and 5xx
    # responses with backoff — none of those are this deployment's fault, and a page
    # shouldn't fall back to the lower-accuracy Tesseract text (flagged for review) over
    # a transient blip. Raised from the SDK's own default of 2. A permanent failure (bad
    # API key, unknown model name) still fails fast — the SDK does not retry those.
    ocr_vision_max_retries: int = 5
    # Mistral's dedicated Document AI OCR endpoint (client.ocr.process), not a chat
    # completion — see ai-service/src/contract_ocr/infrastructure/ocr/mistral_ocr.py for
    # the same provider integrated into the separate OCR lab, including the live-tested
    # gotcha this mirrors: table_format is deliberately left unset (API default, tables
    # stay inline as real markdown) rather than "markdown"/"html", which was confirmed
    # against a real scanned table to silently pull the table OUT of the main text into
    # a separate field this codebase never reads.
    mistral_api_key: str = ""
    ocr_mistral_model: str = "mistral-ocr-4"
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
    # How many pages one worker process claims and processes concurrently via
    # threads. Tesseract is CPU-bound and fast (~2-3s/page); gpt_vision is the
    # dominant cost (~15-35s/page, one network round trip) and I/O-bound, so
    # threading shortens a job's wall-clock time toward its slowest single page
    # instead of the sum of all pages. Still exactly one OS process, so this stays
    # safe under this deployment's single-writer SQLite constraint -- only the
    # in-process claim/finish transactions serialize, not the OCR work itself.
    # Set well above Tesseract's own CPU-bound sweet spot (~4, one per core) because
    # most pages that reach gpt_vision are waiting on the network, not a core --
    # threads spend nearly all their time blocked on the API round trip, not
    # competing for CPU, so a much higher count is still safe. Tune down if hitting
    # the OpenAI account's own requests-per-minute limit.
    page_concurrency: int = 24


settings = Settings()
