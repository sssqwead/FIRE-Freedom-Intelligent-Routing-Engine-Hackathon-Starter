from __future__ import annotations
import os

class Settings:
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql+psycopg://fire:fire@db:5432/fire")
    USE_LLM: bool = os.getenv("USE_LLM", "false").lower() == "true"
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_BASE_URL: str = os.getenv("OPENAI_BASE_URL", "")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "openai/gpt-4.1-mini")
    PROCESS_BATCH_LIMIT: int = int(os.getenv("PROCESS_BATCH_LIMIT", "500"))
    GEOCODER_ENABLED: bool = os.getenv("GEOCODER_ENABLED", "true").lower() == "true"
    GEOCODER_TIMEOUT_SEC: float = float(os.getenv("GEOCODER_TIMEOUT_SEC", "4.0"))
    GEOCODER_USER_AGENT: str = os.getenv("GEOCODER_USER_AGENT", "fire-hackathon-geocoder/1.0")
    GEOCODER_LANG: str = os.getenv("GEOCODER_LANG", "ru")

settings = Settings()
