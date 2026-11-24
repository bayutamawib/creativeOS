from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings
from sqlalchemy import URL


class Settings(BaseSettings):
    agency_timezone: str = "Asia/Jakarta"
    ai_provider: Literal["fixture", "compatible"] = "fixture"
    ai_model: str = "fixture-v1"
    ai_endpoint: str = ""
    ai_api_key: SecretStr | None = None
    ai_max_output_tokens: int = Field(2000, ge=128, le=8000)
    ai_timeout_seconds: int = Field(15, ge=1, le=30)
    file_provider: Literal["local", "google_drive"] = "local"
    video_max_bytes: int = Field(50 * 1024 * 1024, ge=1024 * 1024, le=500 * 1024 * 1024)
    drive_access_token: SecretStr | None = None
    storage_dir: str = "/home/creative/uploads"
    dev_mail_dir: str = "/home/creative/.local/mail"
    app_env: str = "production"
    web_origin: str = "http://localhost:3100"
    webhook_key: SecretStr | None = None
    workflow_key: SecretStr | None = None
    forms_key: SecretStr | None = None
    n8n_base_url: str = "http://n8n:5678"
    db_host: str = "postgres"
    db_port: int = 5432
    db_name: str = "creativeos"
    db_user: str = "creative_app"
    app_db_password: SecretStr

    @property
    def database_url(self) -> URL:
        return URL.create(
            "postgresql+psycopg",
            username=self.db_user,
            password=self.app_db_password.get_secret_value(),
            host=self.db_host,
            port=self.db_port,
            database=self.db_name,
        )


@lru_cache
def settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
