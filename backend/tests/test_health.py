from fastapi.testclient import TestClient
from main import app
from app.database import get_db
from unittest.mock import patch
import uuid
import pytest
client=TestClient(app)

@pytest.fixture(scope="session")
def client():
    with TestClient(app) as test_client:
        yield test_client

def test_health(client):
    response=client.get("/health")

    assert response.status_code==200
    assert response.json() == {"status":"ok"}

def test_proxy_unknown_service(client):
    response = client.get(
        "/api/v1/proxy/unknown/hello",
        headers={"X-API-Key": "invalid-key"}
    )

    assert response.status_code == 401

def test_register_response(client):
    username = f"pytest_{uuid.uuid4().hex[:8]}"

    response = client.post(
        "/api/v1/auth/register",
        json={
            "username": username,
            "password": "TestPass123!"
        }
    )

    assert response.status_code == 201
    assert response.json() == {
        "message": "User successfully registered",
        "username": username
    }

def test_login(client):
    username = f"pytest_{uuid.uuid4().hex[:8]}"
    password = "TestPass123!"

    register_response = client.post(
        "/api/v1/auth/register",
        json={
            "username": username,
            "password": password
        }
    )
    assert register_response.status_code == 201

    login_response = client.post(
        "/api/v1/auth/login",
        json={
            "username": username,
            "password": password
        }
    )
    assert login_response.status_code == 200
    assert login_response.json()["access_token"]

    access_token = login_response.json()["access_token"]

    key_response = client.post(
        "/api/v1/keys/generate",
        headers={"Authorization": f"Bearer {access_token}"}
    )

    assert key_response.status_code == 200
    assert key_response.json()["api_key"]
    assert key_response.json()["status"] == "active"

    api_key = key_response.json()["api_key"]

    # Use the host-accessible downstream URL only during this test.
    with patch.dict("main.DOWNSTREAM_SERVICES", {
        "hello": "http://127.0.0.1:8001"
    }):
        proxy_response = client.get(
            "/api/v1/proxy/hello/hello",
            headers={"X-API-Key": api_key}
        )

    assert proxy_response.status_code == 200
    assert proxy_response.json() == {"message": "Hello, world!"}


def test_proxy_timeout(client):
    username = f"pytest_{uuid.uuid4().hex[:8]}"
    password = "TestPass123!"

    client.post(
        "/api/v1/auth/register",
        json={"username": username, "password": password}
    )

    login_response = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password}
    )
    access_token = login_response.json()["access_token"]

    key_response = client.post(
        "/api/v1/keys/generate",
        headers={"Authorization": f"Bearer {access_token}"}
    )
    api_key = key_response.json()["api_key"]

    with patch.dict("main.DOWNSTREAM_SERVICES", {
        "hello": "http://127.0.0.1:8001"
    }):
        response = client.get(
            "/api/v1/proxy/hello/slow",
            headers={"X-API-Key": api_key}
        )

    assert response.status_code == 504
    assert response.json()["detail"] == "Downstream service timeout"

def test_proxy_downstream_unavailable(client):
    username = f"pytest_{uuid.uuid4().hex[:8]}"
    password = "TestPass123!"

    client.post(
        "/api/v1/auth/register",
        json={"username": username, "password": password}
    )

    login_response = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password}
    )
    access_token = login_response.json()["access_token"]

    key_response = client.post(
        "/api/v1/keys/generate",
        headers={"Authorization": f"Bearer {access_token}"}
    )
    api_key = key_response.json()["api_key"]

    with patch.dict("main.DOWNSTREAM_SERVICES", {"hello": "http://127.0.0.1:9999"}):
        response = client.get(
            "/api/v1/proxy/hello/hello",
            headers={"X-API-Key": api_key}
        )

    assert response.status_code == 502
    assert response.json()["detail"] == "Downstream service unavailable"