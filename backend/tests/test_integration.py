"""End-to-end tests against real PostgreSQL, Redis and the demo downstream.

Start the stack first: docker compose up -d
"""
import uuid
from unittest.mock import patch

import pytest

pytestmark = pytest.mark.integration

REAL_DOWNSTREAM = "http://127.0.0.1:8001"


def test_health(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_invalid_api_key_is_rejected(client):
    response = client.get(
        "/api/v1/proxy/unknown/hello", headers={"X-API-Key": "invalid-key"}
    )

    assert response.status_code == 401


def test_register_response(client):
    username = f"pytest_{uuid.uuid4().hex[:8]}"

    response = client.post(
        "/api/v1/auth/register",
        json={"username": username, "password": "TestPass123!"},
    )

    assert response.status_code == 201
    assert response.json() == {
        "message": "User successfully registered",
        "username": username,
    }


def test_login_returns_an_access_token(client, register_user):
    username, password = register_user()

    response = client.post(
        "/api/v1/auth/login", json={"username": username, "password": password}
    )

    assert response.status_code == 200
    assert response.json()["access_token"]


def test_login_errors_are_identical(client, register_user):
    username, _ = register_user()

    wrong_password = client.post(
        "/api/v1/auth/login", json={"username": username, "password": "WrongPass999!"}
    )
    unknown_user = client.post(
        "/api/v1/auth/login",
        json={"username": "no_such_user_xyz", "password": "WrongPass999!"},
    )

    assert wrong_password.status_code == unknown_user.status_code == 401
    assert wrong_password.json() == unknown_user.json()


def test_generated_key_is_active(client, new_access_token):
    response = client.post(
        "/api/v1/keys/generate",
        headers={"Authorization": f"Bearer {new_access_token()}"},
    )

    assert response.status_code == 200
    assert response.json()["api_key"]
    assert response.json()["status"] == "active"


def test_proxy_reaches_the_real_downstream(client, api_key):
    with patch.dict("main.DOWNSTREAM_SERVICES", {"hello": REAL_DOWNSTREAM}):
        response = client.get(
            "/api/v1/proxy/hello/hello", headers={"X-API-Key": api_key}
        )

    assert response.status_code == 200
    assert response.json() == {"message": "Hello, world!"}


def test_proxy_timeout(client, api_key):
    with patch.dict("main.DOWNSTREAM_SERVICES", {"hello": REAL_DOWNSTREAM}):
        response = client.get(
            "/api/v1/proxy/hello/slow", headers={"X-API-Key": api_key}
        )

    assert response.status_code == 504
    assert response.json()["detail"] == "Downstream service timeout"


def test_proxy_downstream_unavailable(client, api_key):
    with patch.dict("main.DOWNSTREAM_SERVICES", {"hello": "http://127.0.0.1:9999"}):
        response = client.get(
            "/api/v1/proxy/hello/hello", headers={"X-API-Key": api_key}
        )

    assert response.status_code == 502
    assert response.json()["detail"] == "Downstream service unavailable"


def test_rate_limit_blocks_after_the_quota(client, api_key):
    headers = {"X-API-Key": api_key}

    # New keys allow 10 requests per window.
    for _ in range(10):
        assert client.get("/api/v1/test-api-key", headers=headers).status_code == 200

    blocked = client.get("/api/v1/test-api-key", headers=headers)

    assert blocked.status_code == 429
    assert blocked.json()["detail"] == "Rate limit exceeded"
    assert 1 <= int(blocked.headers["Retry-After"]) <= 60
