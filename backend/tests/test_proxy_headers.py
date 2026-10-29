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


def test_proxy_filters_request_headers(mocked_client):
    seen = {}

    def downstream(request):
        seen["headers"] = request.headers
        seen["body"] = request.content
        return httpx.Response(200, json={"ok": True})

    real_async_client = httpx.AsyncClient

    def fake_async_client(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(downstream)
        return real_async_client(*args, **kwargs)

    with patch("main.httpx.AsyncClient", fake_async_client), patch.dict(
        "main.DOWNSTREAM_SERVICES", {"hello": "http://downstream.test"}
    ):
        response = mocked_client.post(
            "/api/v1/proxy/hello/echo",
            json={"a": 1},
            headers={
                "X-API-Key": "secret-key",
                "X-Client-Name": "demo",
                "Keep-Alive": "timeout=5",
            },
        )

    assert response.status_code == 200
    headers = seen["headers"]
    # Gateway-only credentials and connection-level headers stay here.
    assert "x-api-key" not in headers
    assert "keep-alive" not in headers
    # Host must describe the downstream, not the gateway.
    assert headers["host"] == "downstream.test"
    # Content-Length must match the body that was actually sent.
    assert headers["content-length"] == str(len(seen["body"]))
    # Normal application headers still pass through.
    assert headers["x-client-name"] == "demo"
    
    