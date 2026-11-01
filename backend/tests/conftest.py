from unittest.mock import patch

import httpx
import pytest
from fastapi.testclient import TestClient

from app.security import get_current_api_key
from main import app


@pytest.fixture
def mocked_client():
    """TestClient with the API-key check skipped (no database or Redis needed)."""
    app.dependency_overrides[get_current_api_key] = lambda: None
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.pop(get_current_api_key, None)


@pytest.fixture
def fake_downstream(mocked_client):
    """Call it with handler(request) -> httpx.Response to fake the downstream service."""
    original_client = app.state.http_client

    with patch.dict("main.DOWNSTREAM_SERVICES", {"hello": "http://downstream.test"}):

        def use(handler):
            app.state.http_client = httpx.AsyncClient(
                transport=httpx.MockTransport(handler)
            )

        yield use

    app.state.http_client = original_client
