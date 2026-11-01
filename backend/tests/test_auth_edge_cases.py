import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest

from app.security import create_access_token

pytestmark = pytest.mark.integration


def test_duplicate_username_returns_409(client):
    body = {"username": f"pytest_{uuid.uuid4().hex[:8]}", "password": "TestPass123!"}

    assert client.post("/api/v1/auth/register", json=body).status_code == 201
    second = client.post("/api/v1/auth/register", json=body)

    assert second.status_code == 409
    assert second.json()["detail"] == "Username already registered"


def test_simultaneous_registrations_never_crash(client):
    body = {"username": f"pytest_{uuid.uuid4().hex[:8]}", "password": "TestPass123!"}

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
