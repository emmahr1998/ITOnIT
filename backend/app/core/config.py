from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration, loaded from environment variables / .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    APP_NAME: str = "ITOnIT API"
    APP_VERSION: str = "1.0.0"

    DATABASE_SERVER: str
    DATABASE_NAME: str
    DATABASE_DRIVER: str = "ODBC Driver 17 for SQL Server"
    DATABASE_USERNAME: Optional[str] = None
    DATABASE_PASSWORD: Optional[str] = None

    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    # Refresh tokens must outlive access tokens - that's the entire point of
    # having both (a short-lived access token, and a longer-lived one used
    # only to mint new access tokens without re-entering credentials).
    REFRESH_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7

    # Optional: used only by app.scripts.seed_initial_data. Admin creation is
    # skipped entirely when email/password are unset.
    INITIAL_ADMIN_EMAIL: Optional[str] = None
    INITIAL_ADMIN_PASSWORD: Optional[str] = None
    INITIAL_ADMIN_FIRST_NAME: Optional[str] = None
    INITIAL_ADMIN_LAST_NAME: Optional[str] = None

    # Attachments: files live on disk under this path, never in SQL Server.
    ATTACHMENT_STORAGE_PATH: str = "storage/attachments"
    MAX_ATTACHMENT_SIZE_BYTES: int = 10 * 1024 * 1024

    # Company logos: same disk-storage pattern as attachments, kept in a
    # separate directory (a logo isn't ticket-owned data) and capped much
    # smaller, since it's a small brand image, not a general file upload.
    LOGO_STORAGE_PATH: str = "storage/logos"
    MAX_LOGO_SIZE_BYTES: int = 2 * 1024 * 1024

    # CORS: browser origins allowed to call this API. Defaults cover the
    # Vite React dev server (5173) and the common CRA/alternate dev port
    # (3000). Override via the CORS_ORIGINS env var (a JSON array of
    # origins) to add/restrict origins per environment - see .env.example.
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:3000"]


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance so the .env file is parsed once."""
    return Settings()


settings = get_settings()
