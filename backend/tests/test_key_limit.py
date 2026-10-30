import uuid

import pytest
from fastapi.testclient import TestClient

from main import MAX_ACTIVE_KEYS_PER_USER, app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


def make_user_token(client):
    username = f"pytest_{uuid.uuid4().hex[:8]}"
    password = "TestPass123!"
    client.post("/api/v1/auth/register", json={"username": username, "password": password})
    login = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    return login.json()["access_token"]


def generate_key(client, token):
    return client.post(
        "/api/v1/keys/generate", headers={"Authorization": f"Bearer {token}"}
    )


def test_user_cannot_exceed_the_active_key_limit(client):
    token = make_user_token(client)

    for _ in range(MAX_ACTIVE_KEYS_PER_USER):
        assert generate_key(client, token).status_code == 200

    blocked = generate_key(client, token)

    assert blocked.status_code == 409
    assert "Key limit reached" in blocked.json()["detail"]


def test_the_limit_is_per_user(client):
    first_user = make_user_token(client)
    for _ in range(MAX_ACTIVE_KEYS_PER_USER):
        generate_key(client, first_user)

    second_user = make_user_token(client)

    assert generate_key(client, second_user).status_code == 200