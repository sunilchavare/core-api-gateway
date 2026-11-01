import uuid
from unittest.mock import patch

import httpx
import pytest
from fastapi.testclient import TestClient

from app.security import get_current_api_key
from main import app

PASSWORD = "TestPass123!"


# ---------------------------------------------------------------------------
# Integration fixtures: real PostgreSQL, Redis and (for proxy tests) downstream
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def client():
    """TestClient wired to the real database and Redis."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def register_user(client):
    """Factory: register a new random user and return (username, password)."""

    def make():
        username = f"pytest_{uuid.uuid4().hex[:8]}"
        response = client.post(
            "/api/v1/auth/register",
            json={"username": username, "password": PASSWORD},
        )
        assert response.status_code == 201
        return username, PASSWORD

    return make


@pytest.fixture
def new_access_token(client, register_user):
    """Factory: register a fresh user, log in, and return a JWT."""

    def make():
        username, password = register_user()
        response = client.post(
            "/api/v1/auth/login",
            json={"username": username, "password": password},
        )
        assert response.status_code == 200
        return response.json()["access_token"]

    return make


@pytest.fixture
def api_key(client, new_access_token):
    """A working API key for a brand-new user."""
    response = client.post(
        "/api/v1/keys/generate",
        headers={"Authorization": f"Bearer {new_access_token()}"},
    )
    assert response.status_code == 200
    return response.json()["api_key"]


# ---------------------------------------------------------------------------
# Unit-test fixtures: no database, Redis or downstream service needed
# ---------------------------------------------------------------------------


@pytest.fixture
def mocked_client():
    """TestClient with the API-key check skipped."""
    app.dependency_overrides[get_current_api_key] = lambda: None
    yield TestClient(app)
    app.dependency_overrides.pop(get_current_api_key, None)


@pytest.fixture
def fake_downstream(mocked_client):
    """Call it with handler(request) -> httpx.Response to fake the downstream service."""
    had_client = hasattr(app.state, "http_client")
    original_client = getattr(app.state, "http_client", None)

    with patch.dict("main.DOWNSTREAM_SERVICES", {"hello": "http://downstream.test"}):

        def use(handler):
            app.state.http_client = httpx.AsyncClient(
                transport=httpx.MockTransport(handler)
            )

        yield use

    if had_client:
        app.state.http_client = original_client
    elif hasattr(app.state, "http_client"):
        del app.state.http_client
