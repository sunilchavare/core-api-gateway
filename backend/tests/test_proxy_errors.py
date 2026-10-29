from unittest.mock import patch

import httpx
import pytest
from fastapi.testclient import TestClient

from main import app
from app.security import get_current_api_key


@pytest.fixture
def mocked_client():
    # Skip real API-key lookup and Redis, so this test needs no database.
    app.dependency_overrides[get_current_api_key] = lambda: None
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.pop(get_current_api_key, None)


def call_proxy(client, handler):
    """Send one request through the gateway to a fake downstream."""
    real_async_client = httpx.AsyncClient

    def fake_async_client(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return real_async_client(*args, **kwargs)

    with patch("main.httpx.AsyncClient", fake_async_client), patch.dict(
        "main.DOWNSTREAM_SERVICES", {"hello": "http://downstream.test"}
    ):
        return client.get("/api/v1/proxy/hello/hello", headers={"X-API-Key": "unused"})


@pytest.mark.parametrize(
    "error, expected_status, expected_detail",
    [
        (httpx.ConnectTimeout("connect timed out"), 504, "Downstream service timeout"),
        (httpx.ReadTimeout("read timed out"), 504, "Downstream service timeout"),
        (httpx.PoolTimeout("pool timed out"), 504, "Downstream service timeout"),
        (httpx.ConnectError("refused"), 502, "Downstream service unavailable"),
        (httpx.ReadError("connection reset"), 502, "Downstream request failed"),
    ],
)
def test_proxy_maps_downstream_errors(mocked_client, error, expected_status, expected_detail):
    def downstream(request):
        raise error

    response = call_proxy(mocked_client, downstream)

    assert response.status_code == expected_status
    assert response.json()["detail"] == expected_detail


def test_proxy_passes_downstream_error_status_through(mocked_client):
    def downstream(request):
        return httpx.Response(404, json={"detail": "nope"})

    response = call_proxy(mocked_client, downstream)

    assert response.status_code == 404
    assert response.json() == {"detail": "nope"}