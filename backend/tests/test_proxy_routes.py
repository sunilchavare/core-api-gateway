from unittest.mock import patch

import httpx
import pytest
from fastapi.testclient import TestClient

from main import app
from app.security import get_current_api_key


@pytest.fixture
def mocked_client():
    app.dependency_overrides[get_current_api_key] = lambda: None
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.pop(get_current_api_key, None)


def test_hello_goes_through_the_generic_proxy_route(mocked_client):
    def downstream(request):
        assert request.url.path == "/hello"
        return httpx.Response(200, json={"message": "Hello, world!"})

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


def test_unknown_service_returns_404(mocked_client):
    response = mocked_client.get(
        "/api/v1/proxy/nope/anything", headers={"X-API-Key": "unused"}
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Service not found"