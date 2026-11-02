import pytest

from main import MAX_ACTIVE_KEYS_PER_USER

pytestmark = pytest.mark.integration


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


def create_key(client, token):
    response = client.post("/api/v1/keys/generate", headers=bearer(token))
    assert response.status_code == 200
    return response.json()


def test_generate_returns_the_key_id(client, new_access_token):
    created = create_key(client, new_access_token())

    assert isinstance(created["id"], int)
    assert created["api_key"].startswith("cg_")


def test_list_shows_only_my_keys_and_never_the_secret(client, new_access_token):
    token = new_access_token()
    first = create_key(client, token)
    second = create_key(client, token)
    create_key(client, new_access_token())  # another user's key

    response = client.get("/api/v1/keys", headers=bearer(token))

    assert response.status_code == 200
    keys = response.json()
    assert [key["id"] for key in keys] == [first["id"], second["id"]]
    assert set(keys[0]) == {"id", "is_active", "quota_limit", "created_at"}
    assert keys[0]["is_active"] is True
    assert keys[0]["quota_limit"] == 10
    assert first["api_key"] not in response.text


def test_revoked_key_stops_working_immediately(client, new_access_token):
    token = new_access_token()
    created = create_key(client, token)
    headers = {"X-API-Key": created["api_key"]}
    assert client.get("/api/v1/test-api-key", headers=headers).status_code == 200

    revoked = client.delete(f"/api/v1/keys/{created['id']}", headers=bearer(token))

    assert revoked.status_code == 204
    after = client.get("/api/v1/test-api-key", headers=headers)
    assert after.status_code == 401
    assert after.json()["detail"] == "API key is inactive"
    listed = client.get("/api/v1/keys", headers=bearer(token)).json()
    assert listed[0]["is_active"] is False


def test_revoking_twice_is_harmless(client, new_access_token):
    token = new_access_token()
    created = create_key(client, token)

    first = client.delete(f"/api/v1/keys/{created['id']}", headers=bearer(token))
    second = client.delete(f"/api/v1/keys/{created['id']}", headers=bearer(token))

    assert first.status_code == second.status_code == 204


def test_revoking_frees_a_slot_under_the_key_limit(client, new_access_token):
    token = new_access_token()
    keys = [create_key(client, token) for _ in range(MAX_ACTIVE_KEYS_PER_USER)]
    blocked = client.post("/api/v1/keys/generate", headers=bearer(token))
    assert blocked.status_code == 409

    client.delete(f"/api/v1/keys/{keys[0]['id']}", headers=bearer(token))

    assert client.post("/api/v1/keys/generate", headers=bearer(token)).status_code == 200


def test_cannot_revoke_someone_elses_key(client, new_access_token):
    owner = new_access_token()
    other = new_access_token()
    created = create_key(client, owner)

    response = client.delete(f"/api/v1/keys/{created['id']}", headers=bearer(other))

    assert response.status_code == 404
    still_works = client.get(
        "/api/v1/test-api-key", headers={"X-API-Key": created["api_key"]}
    )
    assert still_works.status_code == 200


def test_unknown_key_id_returns_404(client, new_access_token):
    response = client.delete("/api/v1/keys/999999999", headers=bearer(new_access_token()))

    assert response.status_code == 404
