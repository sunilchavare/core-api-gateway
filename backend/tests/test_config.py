import pytest
from pydantic import ValidationError

from app.config import Settings


def test_missing_secret_key_fails_at_startup(monkeypatch):
    monkeypatch.delenv("SECRET_KEY", raising=False)

    with pytest.raises(ValidationError) as error:
        Settings(_env_file=None)

    assert "secret_key" in str(error.value)


def test_defaults(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "x")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@h/db")
    for name in ("DOWNSTREAM_TIMEOUT", "SQL_ECHO", "REDIS_PORT", "CORS_ORIGINS"):
        monkeypatch.delenv(name, raising=False)

    settings = Settings(_env_file=None)

    assert settings.downstream_timeout == 10
    assert settings.sql_echo is False
    assert settings.redis_port == 6379
    assert settings.cors_origin_list == [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]
