import gzip
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


def test_proxy_does_not_forward_stale_encoding_headers(mocked_client):
    body = b'{"message":"Hello, world!"}'
    compressed = gzip.compress(body)

    def downstream(request):
        return httpx.Response(
            200,
            content=compressed,
            headers={"content-encoding": "gzip", "content-type": "application/json"},
        )

    real_async_client = httpx.AsyncClient

    def fake_async_client(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(downstream)
        return real_async_client(*args, **kwargs)

    with patch("main.httpx.AsyncClient", fake_async_client), patch.dict(
        "main.DOWNSTREAM_SERVICES", {"hello": "http://downstream.test"}
    ):
        response = mocked_client.get(
            "/api/v1/proxy/hello/hello", headers={"X-API-Key": "unused"}
        )

    assert response.status_code == 200
    assert response.json() == {"message": "Hello, world!"}
    assert "content-encoding" not in response.headers
    assert response.headers["content-length"] == str(len(body))