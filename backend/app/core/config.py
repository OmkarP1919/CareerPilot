from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql://user:password@localhost:5432/careerpilot"
    FIREBASE_PROJECT_ID: str = ""
    ADZUNA_APP_ID: str = ""
    ADZUNA_APP_KEY: str = ""
    ADZUNA_COUNTRY: str = "us"

    # AI resume tailoring (Phase 3A). Optional - the application must fail
    # gracefully when these are not configured.
    AI_PROVIDER: str = ""            # e.g. "openai"
    AI_API_KEY: str = ""             # never hardcoded, read from env
    AI_MODEL: str = ""               # e.g. "gpt-4o-mini"
    AI_BASE_URL: str = ""            # optional custom OpenAI-compatible endpoint (e.g. OpenRouter)
    AI_TIMEOUT_SECONDS: float = 60.0

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    return Settings()
