import pytest

from main import MAX_ACTIVE_KEYS_PER_USER

pytestmark = pytest.mark.integration


def generate_key(client, token):
    return client.post(
        "/api/v1/keys/generate", headers={"Authorization": f"Bearer {token}"}
    )


def test_user_cannot_exceed_the_active_key_limit(client, new_access_token):
    token = new_access_token()

    for _ in range(MAX_ACTIVE_KEYS_PER_USER):
        assert generate_key(client, token).status_code == 200

    blocked = generate_key(client, token)

    assert blocked.status_code == 409
    assert "Key limit reached" in blocked.json()["detail"]


def test_the_limit_is_per_user(client, new_access_token):
    first_user = new_access_token()
    for _ in range(MAX_ACTIVE_KEYS_PER_USER):
        generate_key(client, first_user)

    second_user = new_access_token()

    assert generate_key(client, second_user).status_code == 200
