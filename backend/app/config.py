from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# <project root>/.env for local runs; Docker passes real environment variables.
ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    """All configuration in one place, validated when the app starts."""

    model_config = SettingsConfigDict(env_file=ENV_FILE, extra="ignore")

    secret_key: str = Field(min_length=1)
    database_url: str
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_password: str | None = None
    downstream_hello_url: str | None = None
    downstream_timeout: float = 10.0
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    sql_echo: bool = False

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
