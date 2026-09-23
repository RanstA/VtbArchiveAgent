from pathlib import Path

from pydantic_settings import (
    BaseSettings,
    SettingsConfigDict,
)


class Settings(BaseSettings):
    archive_data_root: Path

    database_path: Path = Path(
        "vtuber_archive.db"
    )

    # Event Scout 使用 OpenAI-compatible
    # Chat Completions API。
    #
    # 示例：
    #
    # EVENT_SCOUT_API_BASE_URL=...
    # EVENT_SCOUT_MODEL=...
    #
    # API Key 只放本地 .env，
    # 永远不要提交到仓库。
    event_scout_api_base_url: str | None = None
    event_scout_api_key: str | None = None
    event_scout_model: str | None = None

    event_scout_timeout_seconds: float = 60.0

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )


settings = Settings()