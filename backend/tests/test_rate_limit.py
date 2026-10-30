import asyncio

import fakeredis.aioredis
import pytest

import app.rate_limit as rate_limit

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
        return [await rate_limit.check_rate_limit("key-a", 3) for _ in range(5)]

    assert run_with_fake_redis(scenario) == [True, True, True, False, False]


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