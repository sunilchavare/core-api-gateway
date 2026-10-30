import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from app.models import APIKey, User
from app.security import create_access_token
from main import app


@pytest.fixture(scope="module")
def client():
    # raise_server_exceptions=False: an unhandled crash shows up as a 500 response
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


def new_username():
    return f"pytest_{uuid.uuid4().hex[:8]}"


def test_duplicate_username_returns_409(client):
    body = {"username": new_username(), "password": "TestPass123!"}

    assert client.post("/api/v1/auth/register", json=body).status_code == 201
    second = client.post("/api/v1/auth/register", json=body)

    assert second.status_code == 409
    assert second.json()["detail"] == "Username already registered"


def test_simultaneous_registrations_never_crash(client):
    body = {"username": new_username(), "password": "TestPass123!"}

    with ThreadPoolExecutor(max_workers=8) as pool:
        codes = sorted(
            pool.map(
                lambda _: client.post("/api/v1/auth/register", json=body).status_code,
                range(8),
            )
        )

    assert codes == [201] + [409] * 7


def test_token_with_non_numeric_subject_is_rejected(client):
    token = create_access_token({"sub": "not-a-number"})

    response = client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 401


def test_key_quota_defaults_to_ten():
    assert APIKey.__table__.c.quota_limit.default.arg == 10


def test_created_at_is_timezone_aware():
    assert User.__table__.c.created_at.type.timezone is True