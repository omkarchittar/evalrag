from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", env_prefix="EVALRAG_")
    database_url: str = "postgresql+psycopg://evalrag:evalrag@localhost:5432/evalrag"
    environment: str = "development"
    allowed_origins: list[str] = ["http://localhost:3000"]
    openai_api_key: SecretStr | None = None
    openai_base_url: str = "https://api.openai.com/v1"
    generation_model: str = "gpt-4.1-mini"
    provider_timeout_seconds: float = Field(default=45, ge=1, le=120)
    session_hours: int = Field(default=12, ge=1, le=168)
    upload_limit_bytes: int = Field(default=10_000_000, ge=1, le=50_000_000)
    worker_poll_seconds: float = Field(default=1, ge=0.1, le=60)
    encryption_key: SecretStr | None = None
