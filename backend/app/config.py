from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings
from sqlalchemy import URL


class Settings(BaseSettings):
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
