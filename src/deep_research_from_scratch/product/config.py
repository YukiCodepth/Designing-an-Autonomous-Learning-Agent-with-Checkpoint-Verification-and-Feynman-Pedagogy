"""Application settings for the product API."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-backed settings for the FastAPI product service."""

    app_name: str = "Deep Research Copilot API"
    api_prefix: str = ""
    database_url: str = "postgresql+psycopg://copilot:copilot@127.0.0.1:5432/copilot"
    jwt_secret: str = "change-me-in-production"
    invite_secret: str = "change-me-for-invites"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24
    invite_expire_hours: int = 72
    cors_origins: list[str] = ["*"]
    app_base_url: str = "http://127.0.0.1:3000"
    artifacts_dir: str = str(Path.cwd() / "artifacts")
    uploads_dir: str = str(Path.cwd() / "uploads")
    worker_poll_seconds: int = 10
    embedding_model: str = "models/text-embedding-004"
    knowledge_chunk_size: int = 1200
    knowledge_chunk_overlap: int = 200

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
