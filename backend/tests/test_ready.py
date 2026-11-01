import fakeredis.aioredis
import pytest
import redis.asyncio
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.database import get_db
from main import app


class HealthyDb:
    async def execute(self, statement):
        return None


class BrokenDb:
    async def execute(self, statement):
        raise OperationalError("SELECT 1", {}, Exception("connection refused"))


@pytest.fixture
def check_ready(monkeypatch):
    """Call /health/ready with fake dependencies; each test picks what fails."""

    def run(db, redis_client):
        async def fake_get_db():
            yield db

        app.dependency_overrides[get_db] = fake_get_db
        monkeypatch.setattr("main.redis_client", redis_client)
        return TestClient(app).get("/health/ready")

    yield run
    app.dependency_overrides.pop(get_db, None)


def working_redis():
    return fakeredis.aioredis.FakeRedis(decode_responses=True)


def dead_redis():
    # Nothing listens on port 1, so every command raises ConnectionError.
    return redis.asyncio.Redis(host="127.0.0.1", port=1, socket_connect_timeout=1)


def test_liveness_does_not_depend_on_anything():
    response = TestClient(app).get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ready_when_database_and_redis_are_up(check_ready):
    response = check_ready(HealthyDb(), working_redis())

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok", "redis": "ok"}


def test_not_ready_when_database_is_down(check_ready):
    response = check_ready(BrokenDb(), working_redis())

    assert response.status_code == 503
    assert response.json() == {
        "status": "unavailable",
        "database": "unavailable",
        "redis": "ok",
    }


def test_not_ready_when_redis_is_down(check_ready):
    response = check_ready(HealthyDb(), dead_redis())

    assert response.status_code == 503
    assert response.json() == {
        "status": "unavailable",
        "database": "ok",
        "redis": "unavailable",
    }
