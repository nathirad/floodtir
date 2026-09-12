from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Allow running from repo root (scripts, etc.) or from apps/api/
_here = Path(__file__).parents[2]  # apps/api/
_env_file = _here / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=[str(_env_file), ".env"],
        env_file_encoding="utf-8",
    )

    database_url: str = "postgresql+asyncpg://floodtir:floodtir@localhost:5432/floodtir"
    redis_url: str = "redis://localhost:6379/0"
    debug: bool = False

    llm_base_url: str = "http://localhost:11434/v1"
    llm_api_key: str = "ollama"
    llm_model: str = "typhoon2.5-30b-instruct"

    corroboration_min_n: int = 1  # raise to ≥2 when real reporters are wired (G7)


settings = Settings()
