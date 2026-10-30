import asyncio

import fakeredis.aioredis
import pytest
from fastapi import HTTPException

import app.rate_limit as rate_limit
import app.security as security

WINDOW_SECONDS = 60


@pytest.fixture
def run_with_fake_redis(monkeypatch):
    """Run an async scenario against an in-memory Redis instead of the real one."""

    def run(scenario):
        async def wrapper():
            client = fakeredis.aioredis.FakeRedis(decode_responses=True)
            monkeypatch.setattr(rate_limit, "redis_client", client)
            return await scenario(client)

        return asyncio.run(wrapper())

    return run


def test_allows_up_to_the_quota_then_blocks(run_with_fake_redis):
    async def scenario(client):
        return [(await rate_limit.check_rate_limit("key-a", 3))[0] for _ in range(5)]

    assert run_with_fake_redis(scenario) == [True, True, True, False, False]


def test_retry_after_is_the_remaining_window(run_with_fake_redis):
    async def scenario(client):
        await rate_limit.check_rate_limit("key-r", 1)
        await client.expire("rate_limit:key-r", 20)
        return await rate_limit.check_rate_limit("key-r", 1)

    allowed, retry_after = run_with_fake_redis(scenario)
    assert allowed is False
    assert 1 <= retry_after <= 20


def test_counter_always_gets_an_expiry(run_with_fake_redis):
    async def scenario(client):
        await rate_limit.check_rate_limit("key-b", 10)
        return await client.ttl("rate_limit:key-b")

    assert 0 < run_with_fake_redis(scenario) <= WINDOW_SECONDS


def test_counter_without_expiry_heals_itself(run_with_fake_redis):
    # Simulates the old bug: the process died after INCR, before EXPIRE,
    # leaving a counter that would never reset.
    async def scenario(client):
        await client.set("rate_limit:key-c", 5)  # no expiry
        assert await client.ttl("rate_limit:key-c") == -1
        await rate_limit.check_rate_limit("key-c", 10)
        return await client.ttl("rate_limit:key-c")

    assert 0 < run_with_fake_redis(scenario) <= WINDOW_SECONDS


def test_later_requests_do_not_extend_the_window(run_with_fake_redis):
    async def scenario(client):
        await rate_limit.check_rate_limit("key-d", 10)
        await client.expire("rate_limit:key-d", 20)  # pretend 40s already passed
        await rate_limit.check_rate_limit("key-d", 10)
        return await client.ttl("rate_limit:key-d")

    assert 0 < run_with_fake_redis(scenario) <= 20


class FakeKey:
    is_active = True
    quota_limit = 10
    user_id = 1


class FakeResult:
    def scalar_one_or_none(self):
        return FakeKey()


class FakeDb:
    async def execute(self, statement):
        return FakeResult()


def test_429_response_has_retry_after_header(monkeypatch):
    async def blocked(api_key, quota_limit):
        return False, 42

    monkeypatch.setattr(security, "check_rate_limit", blocked)

    with pytest.raises(HTTPException) as error:
        asyncio.run(security.get_current_api_key(api_key="k", db=FakeDb()))

    assert error.value.status_code == 429
    assert error.value.headers["Retry-After"] == "42"


def test_allowed_request_returns_the_key(monkeypatch):
    async def allowed(api_key, quota_limit):
        return True, 30

    monkeypatch.setattr(security, "check_rate_limit", allowed)

    key = asyncio.run(security.get_current_api_key(api_key="k", db=FakeDb()))

    assert key.quota_limit == 10